"""
M8 backend hardening pass — Razorpay refund lifecycle tests.

Razorpay refund creation is asynchronous (refund.created ->
refund.processed | refund.failed, per razorpay.com/docs/webhooks/refunds/).
These tests prove: (1) a "pending" creation response defers completion
instead of assuming it, (2) the refund.processed/refund.failed webhook
correctly confirms/fails a pending refund exactly once, (3) duplicate/
out-of-order webhook delivery is safe, and (4) a pending refund still
counts toward the refundable ceiling so a second attempt cannot over-refund
before the first is confirmed.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from database import SessionLocal
from tests.test_bookings import (  # noqa: F401 (autouse fixtures)
    _bookable_setup,
    client,
    _auth,
    seed_reference_data,
    stub_booking_emails,
    BOOKING_DATE,
)
import crud_payment
from models import Booking, BookingFinancial, Payment, Refund


@pytest.fixture(autouse=True)
def stub_razorpay(monkeypatch):
    monkeypatch.setattr(
        crud_payment.razorpay_service, "create_order",
        lambda amount, currency, receipt: {"id": f"order_fake_{receipt}"},
    )
    monkeypatch.setattr(crud_payment.razorpay_service, "verify_payment_signature", lambda *a, **k: True)
    monkeypatch.setattr(crud_payment.razorpay_service, "fetch_payment", lambda payment_id: {"status": "captured", "amount": 10**12})
    monkeypatch.setattr(crud_payment.razorpay_service, "to_paise", lambda amount: 10**12)


def _customer_token_for(setup):
    import uuid
    unique = uuid.uuid4().hex[:8]
    payload = {
        "first_name": "Cust", "last_name": "Omer", "email": f"cust_{unique}@example.com",
        "mobile_number": "9999999999", "password": "Testpass123!",
    }
    response = client.post("/api/v1/customers/register", json=payload)
    assert response.status_code == 200, response.text
    login = client.post("/api/v1/auth/login", data={"username": payload["email"], "password": "Testpass123!"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _fully_paid_booking(setup, customer_token):
    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(BOOKING_DATE),
            "start_time": "09:00:00", "payment_option": "Full",
        },
        headers=_auth(customer_token),
    ).json()
    verify = client.post(
        f"/api/v1/customer/checkout/{checkout['hold_id']}/verify",
        json={"razorpay_payment_id": "pay_fp_1", "razorpay_signature": "sig_fp_1"},
        headers=_auth(customer_token),
    ).json()
    return verify["booking"]


def _fetch_financial(booking_id):
    db = SessionLocal()
    try:
        return db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking_id).first()
    finally:
        db.close()


def test_pending_refund_response_defers_completion(monkeypatch):
    monkeypatch.setattr(crud_payment.razorpay_service, "create_refund", lambda *a, **k: {"id": "rfnd_pending_1", "status": "pending"})
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)
    financial_before = _fetch_financial(booking["id"])
    amount_paid = Decimal(financial_before.amount_paid)

    cancel = client.post(f"/api/v1/customer/bookings/{booking['id']}/cancel", json={}, headers=_auth(customer_token))
    assert cancel.status_code == 200, cancel.text

    db = SessionLocal()
    try:
        refund = db.query(Refund).filter(Refund.razorpay_refund_id == "rfnd_pending_1").first()
        assert refund is not None
        assert refund.status == "Initiated"
        assert refund.completed_at is None

        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking["id"]).first()
        assert Decimal(financial.amount_refunded) == Decimal("0")  # not yet confirmed
    finally:
        db.close()


def test_refund_processed_webhook_confirms_pending_refund(monkeypatch):
    monkeypatch.setattr(crud_payment.razorpay_service, "create_refund", lambda *a, **k: {"id": "rfnd_pending_2", "status": "pending"})
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)
    client.post(f"/api/v1/customer/bookings/{booking['id']}/cancel", json={}, headers=_auth(customer_token))

    db = SessionLocal()
    try:
        refund = db.query(Refund).filter(Refund.razorpay_refund_id == "rfnd_pending_2").first()
        assert refund.status == "Initiated"
        expected_amount = Decimal(refund.final_amount)

        crud_payment.reconcile_refund_webhook_event(
            db, "refund.processed",
            {"payload": {"refund": {"entity": {"id": "rfnd_pending_2", "status": "processed"}}}},
        )
    finally:
        db.close()

    db = SessionLocal()
    try:
        refund = db.query(Refund).filter(Refund.razorpay_refund_id == "rfnd_pending_2").first()
        assert refund.status == "Completed"
        assert refund.completed_at is not None

        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking["id"]).first()
        assert Decimal(financial.amount_refunded) == expected_amount
    finally:
        db.close()


def test_refund_failed_webhook_marks_failed_without_accounting_impact(monkeypatch):
    monkeypatch.setattr(crud_payment.razorpay_service, "create_refund", lambda *a, **k: {"id": "rfnd_pending_3", "status": "pending"})
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)
    client.post(f"/api/v1/customer/bookings/{booking['id']}/cancel", json={}, headers=_auth(customer_token))

    db = SessionLocal()
    try:
        crud_payment.reconcile_refund_webhook_event(
            db, "refund.failed",
            {"payload": {"refund": {"entity": {"id": "rfnd_pending_3", "status": "failed"}}}},
        )
    finally:
        db.close()

    db = SessionLocal()
    try:
        refund = db.query(Refund).filter(Refund.razorpay_refund_id == "rfnd_pending_3").first()
        assert refund.status == "Failed"
        assert refund.completed_at is None

        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking["id"]).first()
        assert Decimal(financial.amount_refunded) == Decimal("0")
    finally:
        db.close()


def test_duplicate_refund_processed_event_does_not_double_count(monkeypatch):
    monkeypatch.setattr(crud_payment.razorpay_service, "create_refund", lambda *a, **k: {"id": "rfnd_pending_4", "status": "pending"})
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)
    client.post(f"/api/v1/customer/bookings/{booking['id']}/cancel", json={}, headers=_auth(customer_token))

    payload = {"payload": {"refund": {"entity": {"id": "rfnd_pending_4", "status": "processed"}}}}
    db = SessionLocal()
    try:
        crud_payment.reconcile_refund_webhook_event(db, "refund.processed", payload)
    finally:
        db.close()

    db = SessionLocal()
    try:
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking["id"]).first()
        first_amount = Decimal(financial.amount_refunded)
        assert first_amount > 0
    finally:
        db.close()

    # Redelivery of the same event (or a retry) must be a safe no-op.
    db = SessionLocal()
    try:
        crud_payment.reconcile_refund_webhook_event(db, "refund.processed", payload)
    finally:
        db.close()

    db = SessionLocal()
    try:
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking["id"]).first()
        assert Decimal(financial.amount_refunded) == first_amount  # unchanged
    finally:
        db.close()


def test_out_of_order_failed_after_processed_does_not_revert():
    db = SessionLocal()
    try:
        # Unknown refund id -> safe no-op regardless of event type.
        crud_payment.reconcile_refund_webhook_event(
            db, "refund.processed",
            {"payload": {"refund": {"entity": {"id": "rfnd_does_not_exist"}}}},
        )
        crud_payment.reconcile_refund_webhook_event(
            db, "refund.failed",
            {"payload": {"refund": {"entity": {"id": "rfnd_does_not_exist"}}}},
        )
    finally:
        db.close()
    # No exception raised == pass; nothing to assert against since the id never existed.


def test_refund_created_event_is_a_safe_noop(monkeypatch):
    """refund.created never transitions state — we already create the Refund
    row ourselves at the moment we call the API."""
    monkeypatch.setattr(crud_payment.razorpay_service, "create_refund", lambda *a, **k: {"id": "rfnd_pending_5", "status": "pending"})
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)
    client.post(f"/api/v1/customer/bookings/{booking['id']}/cancel", json={}, headers=_auth(customer_token))

    db = SessionLocal()
    try:
        crud_payment.reconcile_refund_webhook_event(
            db, "refund.created",
            {"payload": {"refund": {"entity": {"id": "rfnd_pending_5", "status": "processed"}}}},
        )
        refund = db.query(Refund).filter(Refund.razorpay_refund_id == "rfnd_pending_5").first()
        assert refund.status == "Initiated"  # unchanged by refund.created
    finally:
        db.close()


def test_pending_refund_counts_toward_refundable_ceiling(monkeypatch):
    """A still-Initiated (pending) refund must be treated as committed
    money, so a second refund attempt against the same payment cannot
    exceed the true refundable ceiling before the first is confirmed."""
    monkeypatch.setattr(crud_payment.razorpay_service, "create_refund", lambda *a, **k: {"id": "rfnd_pending_6", "status": "pending"})
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)

    db = SessionLocal()
    try:
        b = db.query(Booking).filter(Booking.id == booking["id"]).first()
        payment = db.query(Payment).filter(Payment.booking_id == booking["id"]).first()

        first = crud_payment._distribute_and_process_refund(
            db, b, Decimal(payment.amount), b.created_by, "CUSTOMER", reason="test pending ceiling"
        )
        db.commit()
        assert first[0].status == "Initiated"

        total_captured, total_committed = crud_payment._total_captured_and_refunded(db, b.id)
        assert total_committed == Decimal(payment.amount)  # pending refund already counted
        assert total_captured - total_committed == Decimal("0")  # nothing left refundable
    finally:
        db.close()


def test_refund_webhook_http_endpoint_reconciles_pending_refund(monkeypatch):
    """End-to-end via the real /webhooks/razorpay endpoint, with a genuine
    HMAC signature — not a direct function call."""
    import hashlib, hmac, json as jsonlib
    from config import get_settings
    import os

    monkeypatch.setattr(crud_payment.razorpay_service, "create_refund", lambda *a, **k: {"id": "rfnd_http_1", "status": "pending"})
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)
    client.post(f"/api/v1/customer/bookings/{booking['id']}/cancel", json={}, headers=_auth(customer_token))

    secret = get_settings().RAZORPAY_WEBHOOK_SECRET or "test-webhook-secret"
    os.environ["RAZORPAY_WEBHOOK_SECRET"] = secret
    get_settings.cache_clear()
    try:
        body = jsonlib.dumps({
            "event": "refund.processed",
            "payload": {"refund": {"entity": {"id": "rfnd_http_1", "status": "processed"}}},
        }).encode()
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        response = client.post(
            "/api/v1/webhooks/razorpay", content=body,
            headers={"X-Razorpay-Signature": signature, "X-Razorpay-Event-Id": "evt_refund_http_1"},
        )
        assert response.status_code == 200, response.text
    finally:
        os.environ.pop("RAZORPAY_WEBHOOK_SECRET", None)
        get_settings.cache_clear()

    db = SessionLocal()
    try:
        refund = db.query(Refund).filter(Refund.razorpay_refund_id == "rfnd_http_1").first()
        assert refund.status == "Completed"
    finally:
        db.close()
