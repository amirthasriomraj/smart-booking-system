"""Milestone 8 Phase 6 — Staff payment flow tests."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from database import SessionLocal
from tests.test_bookings import (  # noqa: F401 (autouse fixtures)
    _bookable_setup,
    _create_walk_in,
    client,
    _auth,
    seed_reference_data,
    stub_booking_emails,
    BOOKING_DATE,
)
import crud_payment
from models import Payment, BookingFinancial, BookingHold


@pytest.fixture(autouse=True)
def stub_razorpay(monkeypatch):
    monkeypatch.setattr(
        crud_payment.razorpay_service, "create_order",
        lambda amount, currency, receipt: {"id": f"order_fake_{receipt}"},
    )
    monkeypatch.setattr(
        crud_payment.razorpay_service, "create_payment_link",
        lambda *a, **k: {"id": "plink_fake_1", "short_url": "https://rzp.io/fake"},
    )
    monkeypatch.setattr(crud_payment.razorpay_service, "verify_payment_signature", lambda *a, **k: True)


def test_staff_cash_checkout_finalizes_immediately():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    response = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/checkout/cash",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00",
            "payment_option": "Full", "cash_received": "1000",
        },
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    booking = response.json()["booking"]
    assert booking["status"] == "Confirmed"

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_id == booking["id"]).first()
        assert payment.method == "Cash"
        assert payment.status == "Captured"
        assert Decimal(payment.cash_received) == Decimal("1000")
        assert Decimal(payment.change_returned) == Decimal("1000") - Decimal(payment.amount)
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking["id"]).first()
        assert financial.financial_status == "FullyPaid"
    finally:
        db.close()


def test_staff_cash_checkout_rejects_insufficient_cash():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    response = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/checkout/cash",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00",
            "payment_option": "Full", "cash_received": "1",
        },
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 400, response.text


def test_staff_price_override_requires_reason():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    response = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/checkout/cash",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00",
            "payment_option": "Full", "cash_received": "1000", "final_price_override": "500",
        },
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 400, response.text


def test_staff_final_price_override_recorded_in_history():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    response = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/checkout/cash",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00",
            "payment_option": "Full", "cash_received": "500",
            "final_price_override": "500", "price_override_reason": "Loyalty discount",
        },
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    booking = response.json()["booking"]

    from models import BookingPriceAdjustment
    db = SessionLocal()
    try:
        adjustment = db.query(BookingPriceAdjustment).filter(BookingPriceAdjustment.booking_id == booking["id"]).first()
        assert adjustment is not None
        assert adjustment.adjustment_type == "FinalOverride"
        assert adjustment.reason == "Loyalty discount"
        assert Decimal(adjustment.new_value) == Decimal("500")
    finally:
        db.close()


def test_staff_reserve_without_payment_creates_no_hold_and_no_payment():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    response = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/checkout/reserve-without-payment",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00",
        },
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    booking = response.json()["booking"]
    assert booking["status"] == "Confirmed"

    db = SessionLocal()
    try:
        assert db.query(Payment).filter(Payment.booking_id == booking["id"]).count() == 0
        assert db.query(BookingHold).filter(BookingHold.resource_id == setup["resource"]["id"]).count() == 0
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking["id"]).first()
        assert financial.financial_status == "ReserveWithoutPayment"
        assert financial.balance_due_at is None
        assert Decimal(financial.amount_paid) == Decimal("0")
    finally:
        db.close()


def test_staff_external_checkout_then_manual_confirm():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    checkout = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/checkout/external",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00", "payment_option": "Full",
        },
        headers=_auth(setup["owner_token"]),
    )
    assert checkout.status_code == 200, checkout.text
    hold_id = checkout.json()["hold_id"]

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_hold_id == hold_id).first()
        assert payment.method == "ExternalManual"
        assert payment.status == "Created"
    finally:
        db.close()

    confirm = client.post(f"/api/v1/holds/{hold_id}/confirm-external-payment", headers=_auth(setup["owner_token"]))
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["booking"]["status"] == "Confirmed"

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_hold_id == hold_id).first()
        assert payment.status == "Captured"
        assert payment.verified_by is not None
    finally:
        db.close()


def test_staff_email_link_checkout_and_webhook_finalizes_booking():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    checkout = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/checkout/email-link",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00", "payment_option": "Full",
        },
        headers=_auth(setup["owner_token"]),
    )
    assert checkout.status_code == 200, checkout.text
    hold_id = checkout.json()["hold_id"]

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_hold_id == hold_id).first()
        payment_link_id = payment.razorpay_order_id
        assert payment_link_id == "plink_fake_1"
    finally:
        db.close()

    import hashlib, hmac, json as jsonlib
    from config import get_settings
    body = jsonlib.dumps({
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {"entity": {"id": payment_link_id}},
            "payment": {"entity": {"id": "pay_link_paid_1"}},
        },
    }).encode()
    secret = get_settings().RAZORPAY_WEBHOOK_SECRET or "test-webhook-secret"
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    import os
    os.environ["RAZORPAY_WEBHOOK_SECRET"] = secret
    get_settings.cache_clear()

    webhook = client.post(
        "/api/v1/webhooks/razorpay", content=body,
        headers={"X-Razorpay-Signature": signature, "X-Razorpay-Event-Id": "evt_link_paid_1"},
    )
    assert webhook.status_code == 200, webhook.text

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_hold_id == hold_id).first()
        assert payment.status == "Captured"
        assert payment.booking_id is not None
        hold = db.query(BookingHold).filter(BookingHold.id == hold_id).first()
        assert hold.status == "Completed"
    finally:
        db.close()
        os.environ.pop("RAZORPAY_WEBHOOK_SECRET", None)
        get_settings.cache_clear()
