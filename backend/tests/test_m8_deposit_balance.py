"""Milestone 8 Phase 7 — Deposit, balance payment, reminder and deadline tests."""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from database import SessionLocal
from tests.test_bookings import (  # noqa: F401 (autouse fixtures)
    _bookable_setup,
    _create_walk_in,
    _next_weekday_date,
    client,
    _auth,
    seed_reference_data,
    stub_booking_emails,
    WEEKDAY,
)
import crud_payment
from models import BookingFinancial, Booking, Payment


FAR_ENOUGH_DATE = _next_weekday_date(WEEKDAY) + timedelta(weeks=2)  # comfortably >= 7 days out, same weekday as fixtures


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


def test_deposit_checkout_produces_awaiting_balance_with_correct_amounts():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)

    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(FAR_ENOUGH_DATE),
            "start_time": "09:00:00", "payment_option": "Deposit",
        },
        headers=_auth(customer_token),
    )
    assert checkout.status_code == 200, checkout.text
    hold_id = checkout.json()["hold_id"]

    verify = client.post(
        f"/api/v1/customer/checkout/{hold_id}/verify",
        json={"razorpay_payment_id": "pay_dep_1", "razorpay_signature": "sig_dep_1"},
        headers=_auth(customer_token),
    )
    assert verify.status_code == 200, verify.text
    booking = verify.json()["booking"]

    db = SessionLocal()
    try:
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking["id"]).first()
        assert financial.financial_status == "AwaitingBalance"
        assert financial.deposit_required is True
        assert Decimal(financial.deposit_amount) == (Decimal(financial.total_amount) * Decimal("25") / Decimal("100")).quantize(Decimal("0.01"))
        assert Decimal(financial.amount_paid) == Decimal(financial.deposit_amount)
        assert Decimal(financial.balance_due) == Decimal(financial.total_amount) - Decimal(financial.deposit_amount)

        appointment_dt = datetime.combine(booking["booking_date"] if isinstance(booking["booking_date"], date) else date.fromisoformat(booking["booking_date"]), datetime.strptime(booking["start_time"], "%H:%M:%S").time())
        expected_deadline = appointment_dt - timedelta(hours=48)
        assert financial.balance_due_at == expected_deadline
    finally:
        db.close()


def test_balance_payment_flow_completes_booking():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)

    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(FAR_ENOUGH_DATE),
            "start_time": "09:00:00", "payment_option": "Deposit",
        },
        headers=_auth(customer_token),
    ).json()
    verify = client.post(
        f"/api/v1/customer/checkout/{checkout['hold_id']}/verify",
        json={"razorpay_payment_id": "pay_dep_2", "razorpay_signature": "sig_dep_2"},
        headers=_auth(customer_token),
    ).json()
    booking_id = verify["booking"]["id"]

    initiate = client.post(f"/api/v1/customer/bookings/{booking_id}/pay-balance", headers=_auth(customer_token))
    assert initiate.status_code == 200, initiate.text
    assert initiate.json()["razorpay_order_id"].startswith("order_fake_")

    pay = client.post(
        f"/api/v1/customer/bookings/{booking_id}/pay-balance/verify",
        json={"razorpay_payment_id": "pay_bal_1", "razorpay_signature": "sig_bal_1"},
        headers=_auth(customer_token),
    )
    assert pay.status_code == 200, pay.text
    assert pay.json()["status"] == "FullyPaid"

    db = SessionLocal()
    try:
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking_id).first()
        assert financial.financial_status == "FullyPaid"
        assert Decimal(financial.amount_paid) == Decimal(financial.total_amount)
    finally:
        db.close()


def test_reminder_and_deadline_scheduling_functions():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)

    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(FAR_ENOUGH_DATE),
            "start_time": "09:00:00", "payment_option": "Deposit",
        },
        headers=_auth(customer_token),
    ).json()
    verify = client.post(
        f"/api/v1/customer/checkout/{checkout['hold_id']}/verify",
        json={"razorpay_payment_id": "pay_dep_3", "razorpay_signature": "sig_dep_3"},
        headers=_auth(customer_token),
    ).json()
    booking_id = verify["booking"]["id"]

    db = SessionLocal()
    try:
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking_id).first()

        # Not yet within the 72h reminder window (appointment is ~2+ weeks out).
        assert financial.id not in [f.id for f in crud_payment.find_bookings_due_for_balance_reminder(db)]

        # Simulate "now" being inside the reminder window.
        simulated_now = financial.balance_due_at - timedelta(hours=12)
        due = crud_payment.find_bookings_due_for_balance_reminder(db, now=simulated_now)
        assert financial.id in [f.id for f in due]

        crud_payment.mark_balance_reminder_sent(db, financial)
        db.refresh(financial)
        due_again = crud_payment.find_bookings_due_for_balance_reminder(db, now=simulated_now)
        assert financial.id not in [f.id for f in due_again]  # idempotent: reminded once only

        # Not yet past the deadline.
        assert financial.id not in [f.id for f in crud_payment.find_bookings_past_balance_deadline(db)]

        # Simulate "now" being past the deadline and enforce it.
        past_deadline = financial.balance_due_at + timedelta(minutes=1)
        past_due = crud_payment.find_bookings_past_balance_deadline(db, now=past_deadline)
        assert financial.id in [f.id for f in past_due]

        result = crud_payment.enforce_balance_deadline(db, financial.id)
        assert result is True

        db.refresh(financial)
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        assert financial.financial_status == "BalanceDefaulted"
        assert booking.status == "Cancelled"
        assert booking.cancellation_reason is not None

        # Idempotent: calling again on an already-defaulted row is a safe no-op.
        assert crud_payment.enforce_balance_deadline(db, financial.id) is False
    finally:
        db.close()


def test_verify_balance_payment_after_deadline_already_enforced_refunds_automatically(monkeypatch):
    """The other direction of the same race proven live against PostgreSQL
    in the Phase 5-7 report. `financial_status` must still be
    'AwaitingBalance' when `_get_awaiting_balance_financial_or_404` checks
    it (otherwise the request is rejected before any capture is even
    attempted, which is a different, simpler, already-correct path) — the
    deadline sweep instead "wins" concurrently while this request's
    signature verification network call is in flight, which is what the
    lock-based re-check inside verify_balance_payment exists to catch.
    Simulated here by making the stubbed verify_payment_signature call
    flip the row, exactly like a real concurrent sweep would."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)

    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(FAR_ENOUGH_DATE),
            "start_time": "09:00:00", "payment_option": "Deposit",
        },
        headers=_auth(customer_token),
    ).json()
    verify = client.post(
        f"/api/v1/customer/checkout/{checkout['hold_id']}/verify",
        json={"razorpay_payment_id": "pay_dep_5", "razorpay_signature": "sig_dep_5"},
        headers=_auth(customer_token),
    ).json()
    booking_id = verify["booking"]["id"]

    client.post(f"/api/v1/customer/bookings/{booking_id}/pay-balance", headers=_auth(customer_token))

    def signature_ok_but_deadline_wins_concurrently(*a, **k):
        session = SessionLocal()
        try:
            financial = session.query(BookingFinancial).filter(BookingFinancial.booking_id == booking_id).first()
            booking = session.query(Booking).filter(Booking.id == booking_id).first()
            financial.financial_status = "BalanceDefaulted"
            booking.status = "Cancelled"
            session.commit()
        finally:
            session.close()
        return True

    monkeypatch.setattr(crud_payment.razorpay_service, "verify_payment_signature", signature_ok_but_deadline_wins_concurrently)

    from models import Refund
    pay = client.post(
        f"/api/v1/customer/bookings/{booking_id}/pay-balance/verify",
        json={"razorpay_payment_id": "pay_bal_late", "razorpay_signature": "sig_bal_late"},
        headers=_auth(customer_token),
    )
    assert pay.status_code == 409, pay.text

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_id == booking_id, Payment.payment_type == "BalancePayment").first()
        assert payment.status == "Captured"  # money was verified/captured
        refund = db.query(Refund).filter(Refund.payment_id == payment.id).first()
        assert refund is not None
        assert refund.status == "Completed"
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking_id).first()
        assert financial.financial_status == "BalanceDefaulted"  # not silently overwritten back to FullyPaid
    finally:
        db.close()


def test_enforce_balance_deadline_is_noop_if_already_paid():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)

    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(FAR_ENOUGH_DATE),
            "start_time": "09:00:00", "payment_option": "Deposit",
        },
        headers=_auth(customer_token),
    ).json()
    verify = client.post(
        f"/api/v1/customer/checkout/{checkout['hold_id']}/verify",
        json={"razorpay_payment_id": "pay_dep_4", "razorpay_signature": "sig_dep_4"},
        headers=_auth(customer_token),
    ).json()
    booking_id = verify["booking"]["id"]

    client.post(f"/api/v1/customer/bookings/{booking_id}/pay-balance", headers=_auth(customer_token))
    client.post(
        f"/api/v1/customer/bookings/{booking_id}/pay-balance/verify",
        json={"razorpay_payment_id": "pay_bal_2", "razorpay_signature": "sig_bal_2"},
        headers=_auth(customer_token),
    )

    db = SessionLocal()
    try:
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking_id).first()
        assert financial.financial_status == "FullyPaid"
        assert crud_payment.enforce_balance_deadline(db, financial.id) is False
        db.refresh(financial)
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        assert booking.status == "Confirmed"  # never touched
    finally:
        db.close()
