"""
Milestone 8 Phase 5 — Customer checkout tests.

Razorpay network calls are stubbed (no live credentials configured) —
`verify_payment_signature`'s actual HMAC logic is exercised directly and
unmocked in tests/test_m8_webhook.py; here the focus is the checkout/hold/
finalization orchestration, which is provider-call-shape-independent.
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
from models import BookingHold, Payment, BookingFinancial, Refund


FAR_FUTURE_DATE = date.today() + timedelta(days=10)


@pytest.fixture(autouse=True)
def stub_razorpay(monkeypatch):
    monkeypatch.setattr(
        crud_payment.razorpay_service, "create_order",
        lambda amount, currency, receipt: {"id": f"order_fake_{receipt}"},
    )
    monkeypatch.setattr(crud_payment.razorpay_service, "verify_payment_signature", lambda *a, **k: True)
    # Phase 8 hardening: capture now also requires a server-side fetch
    # confirming provider status + amount, independent of the signature.
    monkeypatch.setattr(crud_payment.razorpay_service, "fetch_payment", lambda payment_id: {"status": "captured", "amount": 10**12})
    monkeypatch.setattr(crud_payment.razorpay_service, "to_paise", lambda amount: 10**12)
    monkeypatch.setattr(crud_payment.razorpay_service, "create_refund", lambda *a, **k: {"id": "rfnd_fake", "status": "processed"})


def _customer_token_for(setup):
    """Registers and logs in a real Customer user (checkout requires the
    CUSTOMER role path, distinct from the owner/staff walk-in fixtures)."""
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


def test_full_payment_checkout_creates_hold_then_confirms_booking():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)

    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(BOOKING_DATE),
            "start_time": "09:00:00", "payment_option": "Full",
        },
        headers=_auth(customer_token),
    )
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert body["status"] == "AwaitingPayment"
    assert body["hold_id"] is not None
    assert body["razorpay_order_id"].startswith("order_fake_")

    verify = client.post(
        f"/api/v1/customer/checkout/{body['hold_id']}/verify",
        json={"razorpay_payment_id": "pay_fake_1", "razorpay_signature": "sig_fake_1"},
        headers=_auth(customer_token),
    )
    assert verify.status_code == 200, verify.text
    booking = verify.json()["booking"]
    assert booking["status"] == "Confirmed"

    db = SessionLocal()
    try:
        hold = db.query(BookingHold).filter(BookingHold.id == body["hold_id"]).first()
        assert hold.status == "Completed"
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking["id"]).first()
        assert financial.financial_status == "FullyPaid"
        assert Decimal(financial.amount_paid) == Decimal(financial.total_amount)
    finally:
        db.close()


def test_deposit_checkout_requires_seven_days_eligibility():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)

    # BOOKING_DATE is "next Monday" (test_bookings.py), not guaranteed >=7
    # days out, so a Deposit request against it must be rejected.
    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(date.today() + timedelta(days=1)),
            "start_time": "09:00:00", "payment_option": "Deposit",
        },
        headers=_auth(customer_token),
    )
    assert checkout.status_code == 409, checkout.text


def test_zero_amount_coupon_confirms_immediately_with_no_hold_and_no_payment():
    setup = _bookable_setup()
    coupon = client.post(
        f"/api/v1/businesses/{setup['business_id']}/coupons",
        json={
            "code": "FREE100", "discount_type": "Percentage", "discount_value": "100",
            "valid_from": str(date.today()), "valid_until": str(date.today() + timedelta(days=30)),
        },
        headers=_auth(setup["owner_token"]),
    ).json()

    customer_token = _customer_token_for(setup)
    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(BOOKING_DATE),
            "start_time": "09:00:00", "payment_option": "Full", "coupon_code": coupon["code"],
        },
        headers=_auth(customer_token),
    )
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert body["status"] == "Confirmed"
    assert body["booking"]["status"] == "Confirmed"

    db = SessionLocal()
    try:
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == body["booking"]["id"]).first()
        assert financial.financial_status == "FullyPaid"
        assert Decimal(financial.total_amount) == Decimal("0")
        payment_count = db.query(Payment).filter(Payment.booking_id == body["booking"]["id"]).count()
        assert payment_count == 0  # no Razorpay checkout / Payment row for a ₹0 booking
    finally:
        db.close()


def test_payment_after_lost_hold_triggers_automatic_refund_not_double_booking():
    """Simulates decision 16: the hold expired (or was reclaimed) between
    checkout creation and payment verification. The verify call must not
    create an overlapping Booking, and must trigger an automatic refund."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)

    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(BOOKING_DATE),
            "start_time": "09:00:00", "payment_option": "Full",
        },
        headers=_auth(customer_token),
    ).json()
    hold_id = checkout["hold_id"]

    db = SessionLocal()
    try:
        hold = db.query(BookingHold).filter(BookingHold.id == hold_id).first()
        hold.status = "Expired"  # simulate the sweep (or a stale-hold expiry) having already run
        db.commit()
    finally:
        db.close()

    verify = client.post(
        f"/api/v1/customer/checkout/{hold_id}/verify",
        json={"razorpay_payment_id": "pay_fake_lost", "razorpay_signature": "sig_fake_lost"},
        headers=_auth(customer_token),
    )
    assert verify.status_code == 409, verify.text

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_hold_id == hold_id).first()
        assert payment.status == "Captured"  # money WAS captured (signature verified)
        assert payment.booking_id is None  # but never attached to a Booking
        refund = db.query(Refund).filter(Refund.payment_id == payment.id).first()
        assert refund is not None
        assert refund.booking_id is None
        assert refund.status == "Completed"
    finally:
        db.close()


def test_verify_rejects_invalid_signature(monkeypatch):
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    monkeypatch.setattr(crud_payment.razorpay_service, "verify_payment_signature", lambda *a, **k: False)

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
        json={"razorpay_payment_id": "pay_fake_bad", "razorpay_signature": "wrong"},
        headers=_auth(customer_token),
    )
    assert verify.status_code == 400, verify.text

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_hold_id == checkout["hold_id"]).first()
        assert payment.status == "Failed"
    finally:
        db.close()


def test_verify_rejects_valid_signature_if_provider_reports_not_captured(monkeypatch):
    """Phase 8 hardening: a valid signature must NOT be treated as capture
    proof by itself — if Razorpay's own fetch reports the payment as, say,
    merely 'authorized' (not yet captured), the booking must not be
    confirmed."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    monkeypatch.setattr(crud_payment.razorpay_service, "fetch_payment", lambda payment_id: {"status": "authorized", "amount": 10**12})

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
        json={"razorpay_payment_id": "pay_fake_authorized_only", "razorpay_signature": "sig_ok"},
        headers=_auth(customer_token),
    )
    assert verify.status_code == 400, verify.text

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_hold_id == checkout["hold_id"]).first()
        assert payment.status == "Failed"
        assert payment.booking_id is None  # never confirmed into a Booking
    finally:
        db.close()


def test_verify_rejects_valid_signature_if_captured_amount_mismatches(monkeypatch):
    """Phase 8 hardening: captured amount must match what we expect —
    guards against a signature being replayed against a payment captured
    for a different (e.g. tampered) amount."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    monkeypatch.setattr(crud_payment.razorpay_service, "fetch_payment", lambda payment_id: {"status": "captured", "amount": 1})

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
        json={"razorpay_payment_id": "pay_fake_amount_mismatch", "razorpay_signature": "sig_ok"},
        headers=_auth(customer_token),
    )
    assert verify.status_code == 400, verify.text

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_hold_id == checkout["hold_id"]).first()
        assert payment.status == "Failed"
    finally:
        db.close()
