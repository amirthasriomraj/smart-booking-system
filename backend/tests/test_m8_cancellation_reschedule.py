"""
Milestone 8 Phase 8-10 — Cancellation/refund, reschedule financial
workflows, and Platform Fee reversal tests.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from database import SessionLocal
from tests.test_bookings import (  # noqa: F401 (autouse fixtures)
    _bookable_setup,
    _create_walk_in,
    _invite_and_accept_staff,
    _next_weekday_date,
    client,
    _auth,
    seed_reference_data,
    stub_booking_emails,
    WEEKDAY,
)
import crud_payment
from models import Booking, BookingFinancial, Payment, Refund, PlatformFeeSetting, User


FAR_ENOUGH_DATE = _next_weekday_date(WEEKDAY) + timedelta(weeks=2)


@pytest.fixture(autouse=True)
def stub_razorpay(monkeypatch):
    monkeypatch.setattr(
        crud_payment.razorpay_service, "create_order",
        lambda amount, currency, receipt: {"id": f"order_fake_{receipt}"},
    )
    monkeypatch.setattr(crud_payment.razorpay_service, "verify_payment_signature", lambda *a, **k: True)
    monkeypatch.setattr(crud_payment.razorpay_service, "fetch_payment", lambda payment_id: {"status": "captured", "amount": 10**12})
    monkeypatch.setattr(crud_payment.razorpay_service, "to_paise", lambda amount: 10**12)
    monkeypatch.setattr(crud_payment.razorpay_service, "create_refund", lambda *a, **k: {"id": "rfnd_fake", "status": "processed"})


def _customer_token_for(setup):
    import uuid
    unique = uuid.uuid4().hex[:8]
    payload = {
        "first_name": "Cust", "last_name": "Omer", "email": f"cust_{unique}@example.com",
        "mobile_number": "9999999999", "password": "Testpass123",
    }
    response = client.post("/api/v1/customers/register", json=payload)
    assert response.status_code == 200, response.text
    login = client.post("/api/v1/auth/login", data={"username": payload["email"], "password": "Testpass123"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _fully_paid_booking(setup, customer_token, booking_date=FAR_ENOUGH_DATE):
    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(booking_date),
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


def _deposit_booking(setup, customer_token, booking_date=FAR_ENOUGH_DATE):
    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(booking_date),
            "start_time": "09:00:00", "payment_option": "Deposit",
        },
        headers=_auth(customer_token),
    ).json()
    verify = client.post(
        f"/api/v1/customer/checkout/{checkout['hold_id']}/verify",
        json={"razorpay_payment_id": "pay_dep_1", "razorpay_signature": "sig_dep_1"},
        headers=_auth(customer_token),
    ).json()
    return verify["booking"]


def _set_platform_fee(pct: Decimal):
    """Sets the platform-default fee row directly (no admin endpoint
    exists in this milestone's scope)."""
    db = SessionLocal()
    try:
        row = db.query(PlatformFeeSetting).filter(PlatformFeeSetting.business_id.is_(None)).first()
        owner = db.query(User).first()
        if row is None:
            db.add(PlatformFeeSetting(business_id=None, fee_percentage=pct, updated_by=owner.id))
        else:
            row.fee_percentage = pct
        db.commit()
    finally:
        db.close()


# -----------------------------
# Cancellation refund brackets (rule 2/15)
# -----------------------------

def test_cancellation_full_refund_at_48h_or_more():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)

    cancel = client.post(f"/api/v1/customer/bookings/{booking['id']}/cancel", json={}, headers=_auth(customer_token))
    assert cancel.status_code == 200, cancel.text
    body = cancel.json()
    assert body["status"] == "Cancelled"
    assert body["refund"]["overridden"] is False
    assert Decimal(body["refund"]["final_amount"]) == Decimal(body["refund"]["calculated_amount"])
    assert body["refund"]["calculated_percentage"] == "100"


def test_cancellation_fifty_percent_between_24_and_48h():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)

    db = SessionLocal()
    try:
        b = db.query(Booking).filter(Booking.id == booking["id"]).first()
        # Exactly 30h from now regardless of current wall-clock time (avoids
        # the flakiness of adding whole days to a fixed time-of-day).
        appointment = datetime.utcnow() + timedelta(hours=30)
        b.booking_date = appointment.date()
        b.start_time = appointment.time()
        db.commit()
        hours_left = (appointment - datetime.utcnow()).total_seconds() / 3600
        assert 24 < hours_left < 48, hours_left
    finally:
        db.close()

    cancel = client.post(f"/api/v1/customer/bookings/{booking['id']}/cancel", json={}, headers=_auth(customer_token))
    assert cancel.status_code == 200, cancel.text
    body = cancel.json()
    assert body["refund"]["calculated_percentage"] == "50"
    financial_paid = Decimal(_fetch_financial(booking["id"]).amount_paid)
    assert Decimal(body["refund"]["final_amount"]) == (financial_paid * Decimal("50") / Decimal("100"))


def test_cancellation_zero_refund_under_24h():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)

    db = SessionLocal()
    try:
        b = db.query(Booking).filter(Booking.id == booking["id"]).first()
        b.booking_date = date.today()
        b.start_time = (datetime.utcnow() + timedelta(hours=5)).time()
        db.commit()
    finally:
        db.close()

    cancel = client.post(f"/api/v1/customer/bookings/{booking['id']}/cancel", json={}, headers=_auth(customer_token))
    assert cancel.status_code == 200, cancel.text
    body = cancel.json()
    assert body["refund"]["calculated_percentage"] == "0"
    assert Decimal(body["refund"]["final_amount"]) == Decimal("0")


def _fetch_financial(booking_id):
    db = SessionLocal()
    try:
        return db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking_id).first()
    finally:
        db.close()


def test_refund_based_on_money_actually_paid_not_total_value():
    """Deposit-only example from the frozen rules: paid 25%, cancel >=48h
    -> refund the deposit actually paid, not the full booking value."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _deposit_booking(setup, customer_token)

    financial_before = _fetch_financial(booking["id"])
    amount_paid = Decimal(financial_before.amount_paid)
    total_amount = Decimal(financial_before.total_amount)
    assert amount_paid < total_amount  # only the deposit was paid

    cancel = client.post(f"/api/v1/customer/bookings/{booking['id']}/cancel", json={}, headers=_auth(customer_token))
    assert cancel.status_code == 200, cancel.text
    body = cancel.json()
    assert Decimal(body["refund"]["final_amount"]) == amount_paid  # not total_amount


# -----------------------------
# Staff refund override (rule 16)
# -----------------------------

def test_staff_refund_override_requires_reason():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)

    cancel = client.post(
        f"/api/v1/bookings/{booking['id']}/cancel",
        json={"refund_override_amount": "500"},
        headers=_auth(setup["owner_token"]),
    )
    assert cancel.status_code == 400, cancel.text


def test_staff_refund_override_cannot_exceed_refundable_amount():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)
    financial = _fetch_financial(booking["id"])
    too_much = Decimal(financial.amount_paid) + Decimal("1000")

    cancel = client.post(
        f"/api/v1/bookings/{booking['id']}/cancel",
        json={"reason": "Goodwill gesture", "refund_override_amount": str(too_much)},
        headers=_auth(setup["owner_token"]),
    )
    assert cancel.status_code == 400, cancel.text


def test_staff_refund_override_applies_final_amount():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)
    financial = _fetch_financial(booking["id"])
    override_amount = (Decimal(financial.amount_paid) / 2).quantize(Decimal("0.01"))

    cancel = client.post(
        f"/api/v1/bookings/{booking['id']}/cancel",
        json={"reason": "Service quality issue", "refund_override_amount": str(override_amount)},
        headers=_auth(setup["owner_token"]),
    )
    assert cancel.status_code == 200, cancel.text
    body = cancel.json()
    assert body["refund"]["overridden"] is True
    assert Decimal(body["refund"]["final_amount"]) == override_amount


def test_plain_staff_cancellation_does_not_require_reason():
    """PRD §20 baseline unchanged: reason is optional unless overriding the refund."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)

    cancel = client.post(f"/api/v1/bookings/{booking['id']}/cancel", json={}, headers=_auth(setup["owner_token"]))
    assert cancel.status_code == 200, cancel.text


# -----------------------------
# Platform fee reversal (rule 20; ID-051)
# -----------------------------

def test_platform_fee_reversal_matches_worked_example():
    """rule 20 worked example: paid=4000, rate=5%, fee=200; 50% refund (2000) -> reverse 100."""
    _set_platform_fee(Decimal("5"))
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)

    payment = None
    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_id == booking["id"]).first()
        assert Decimal(payment.platform_fee_amount) == Decimal(payment.amount) * Decimal("5") / Decimal("100")
    finally:
        db.close()

    db = SessionLocal()
    try:
        b = db.query(Booking).filter(Booking.id == booking["id"]).first()
        appointment = datetime.utcnow() + timedelta(hours=30)
        b.booking_date = appointment.date()
        b.start_time = appointment.time()
        db.commit()
    finally:
        db.close()

    cancel = client.post(f"/api/v1/customer/bookings/{booking['id']}/cancel", json={}, headers=_auth(customer_token))
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["refund"]["calculated_percentage"] == "50"

    db = SessionLocal()
    try:
        refund = db.query(Refund).filter(Refund.payment_id == payment.id).first()
        expected_reversal = (Decimal(payment.platform_fee_amount) * Decimal(refund.final_amount) / Decimal(payment.amount)).quantize(Decimal("0.01"))
        assert Decimal(refund.platform_fee_reversal_amount) == expected_reversal
    finally:
        db.close()


def test_manager_override_platform_fee_reversal_matches_worked_example():
    """rule 20 worked example: paid=4000, fee=200, manager overrides refund
    to 3000 -> business retains 1000, effective fee retained 50, so 150 of
    the original 200 is reversed."""
    _set_platform_fee(Decimal("5"))
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_id == booking["id"]).first()
        payment_amount = Decimal(payment.amount)
        payment_id = payment.id
    finally:
        db.close()

    override_amount = (payment_amount * Decimal("3000") / Decimal("4000")).quantize(Decimal("0.01")) if payment_amount != Decimal("4000") else Decimal("3000")

    cancel = client.post(
        f"/api/v1/bookings/{booking['id']}/cancel",
        json={"reason": "Service quality issue", "refund_override_amount": str(override_amount)},
        headers=_auth(setup["owner_token"]),
    )
    assert cancel.status_code == 200, cancel.text

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        refund = db.query(Refund).filter(Refund.payment_id == payment_id).first()
        expected_reversal = (Decimal(payment.platform_fee_amount) * override_amount / payment_amount).quantize(Decimal("0.01"))
        assert Decimal(refund.platform_fee_reversal_amount) == expected_reversal
    finally:
        db.close()


# -----------------------------
# Cancellation idempotency (Phase 8 concurrency guard)
# -----------------------------

def test_reprocessing_cancellation_refund_does_not_double_refund():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)

    db = SessionLocal()
    try:
        b = db.query(Booking).filter(Booking.id == booking["id"]).first()
        hours_before = (datetime.combine(b.booking_date, b.start_time) - datetime.utcnow()).total_seconds() / 3600.0

        first = crud_payment._apply_cancellation_refund(db, b, hours_before, b.created_by, "CUSTOMER", None, None)
        assert first is not None
        assert first.get("already_processed") is not True

        second = crud_payment._apply_cancellation_refund(db, b, hours_before, b.created_by, "CUSTOMER", None, None)
        assert second["already_processed"] is True
        assert second["refund_ids"] == first["refund_ids"]
    finally:
        db.close()

    db = SessionLocal()
    try:
        refunds = db.query(Refund).filter(Refund.booking_id == booking["id"]).all()
        assert len(refunds) == 1  # never duplicated
    finally:
        db.close()


# -----------------------------
# Reschedule restrictions (rule 3; ID-047)
# -----------------------------

def test_customer_reschedule_rejected_under_24h():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token, booking_date=FAR_ENOUGH_DATE)

    db = SessionLocal()
    try:
        b = db.query(Booking).filter(Booking.id == booking["id"]).first()
        b.booking_date = date.today()
        b.start_time = (datetime.utcnow() + timedelta(hours=5)).time()
        db.commit()
    finally:
        db.close()

    reschedule = client.post(
        f"/api/v1/customer/bookings/{booking['id']}/reschedule",
        json={"booking_date": str(FAR_ENOUGH_DATE + timedelta(weeks=1)), "start_time": "09:00:00"},
        headers=_auth(customer_token),
    )
    assert reschedule.status_code == 409, reschedule.text


def test_customer_reschedule_allowed_once_then_rejected():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token, booking_date=FAR_ENOUGH_DATE)

    first = client.post(
        f"/api/v1/customer/bookings/{booking['id']}/reschedule",
        json={"booking_date": str(FAR_ENOUGH_DATE + timedelta(weeks=1)), "start_time": "10:00:00"},
        headers=_auth(customer_token),
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/api/v1/customer/bookings/{booking['id']}/reschedule",
        json={"booking_date": str(FAR_ENOUGH_DATE + timedelta(weeks=2)), "start_time": "10:00:00"},
        headers=_auth(customer_token),
    )
    assert second.status_code == 409, second.text


def test_staff_reschedule_requires_reason_only_when_overriding():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token, booking_date=FAR_ENOUGH_DATE)

    # First customer reschedule consumes the allowance.
    client.post(
        f"/api/v1/customer/bookings/{booking['id']}/reschedule",
        json={"booking_date": str(FAR_ENOUGH_DATE + timedelta(weeks=1)), "start_time": "10:00:00"},
        headers=_auth(customer_token),
    )

    # Staff reschedule now overrides the exhausted allowance -> reason required.
    without_reason = client.post(
        f"/api/v1/bookings/{booking['id']}/reschedule",
        json={"booking_date": str(FAR_ENOUGH_DATE + timedelta(weeks=2)), "start_time": "11:00:00"},
        headers=_auth(setup["owner_token"]),
    )
    assert without_reason.status_code == 400, without_reason.text

    with_reason = client.post(
        f"/api/v1/bookings/{booking['id']}/reschedule",
        json={"booking_date": str(FAR_ENOUGH_DATE + timedelta(weeks=2)), "start_time": "11:00:00", "reason": "Customer called in"},
        headers=_auth(setup["owner_token"]),
    )
    assert with_reason.status_code == 200, with_reason.text


# -----------------------------
# Reschedule price difference (rule 14)
# -----------------------------

def test_reschedule_price_increase_creates_collectible_payment():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token, booking_date=FAR_ENOUGH_DATE)

    from crud_service import get_branch_service_or_404
    db = SessionLocal()
    try:
        bs = get_branch_service_or_404(db, booking["branch_service_id"])
        bs.price = Decimal(bs.price) + Decimal("500")
        db.commit()
    finally:
        db.close()

    reschedule = client.post(
        f"/api/v1/customer/bookings/{booking['id']}/reschedule",
        json={"booking_date": str(FAR_ENOUGH_DATE + timedelta(weeks=1)), "start_time": "10:00:00"},
        headers=_auth(customer_token),
    )
    assert reschedule.status_code == 200, reschedule.text
    body = reschedule.json()
    assert body["price_adjustment"]["action"] == "CollectDifference"
    assert Decimal(body["price_adjustment"]["difference"]) == Decimal("500")

    verify = client.post(
        f"/api/v1/customer/bookings/{booking['id']}/pay-reschedule-difference/verify",
        json={"razorpay_payment_id": "pay_diff_1", "razorpay_signature": "sig_diff_1"},
        headers=_auth(customer_token),
    )
    assert verify.status_code == 200, verify.text

    financial = _fetch_financial(booking["id"])
    assert Decimal(financial.total_amount) == Decimal(financial.amount_paid)


def test_reschedule_price_decrease_issues_automatic_refund():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token, booking_date=FAR_ENOUGH_DATE)

    from crud_service import get_branch_service_or_404
    db = SessionLocal()
    try:
        bs = get_branch_service_or_404(db, booking["branch_service_id"])
        bs.price = Decimal(bs.price) - Decimal("300")
        db.commit()
    finally:
        db.close()

    reschedule = client.post(
        f"/api/v1/customer/bookings/{booking['id']}/reschedule",
        json={"booking_date": str(FAR_ENOUGH_DATE + timedelta(weeks=1)), "start_time": "10:00:00"},
        headers=_auth(customer_token),
    )
    assert reschedule.status_code == 200, reschedule.text
    body = reschedule.json()
    assert body["price_adjustment"]["action"] == "RefundIssued"
    assert Decimal(body["price_adjustment"]["amount_refunded"]) == Decimal("300")

    db = SessionLocal()
    try:
        refunds = db.query(Refund).filter(Refund.booking_id == booking["id"]).all()
        assert len(refunds) == 1
        assert refunds[0].final_amount == Decimal("300")
    finally:
        db.close()


def test_reschedule_no_price_change_has_no_price_adjustment():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token, booking_date=FAR_ENOUGH_DATE)

    reschedule = client.post(
        f"/api/v1/customer/bookings/{booking['id']}/reschedule",
        json={"booking_date": str(FAR_ENOUGH_DATE + timedelta(weeks=1)), "start_time": "10:00:00"},
        headers=_auth(customer_token),
    )
    assert reschedule.status_code == 200, reschedule.text
    assert reschedule.json()["price_adjustment"] is None
