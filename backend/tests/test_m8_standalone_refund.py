"""
Manual-acceptance follow-up — standalone staff Refund action, independent
of cancellation. Reuses the existing M8 refund distribution/lifecycle code
(_distribute_and_process_refund, _total_captured_and_refunded,
_acquire_booking_lock) rather than a parallel financial implementation, so
these tests focus on what's new: the endpoint never touches Booking.status,
enforces the refundable ceiling, requires authorization/reason, and applies
proportional platform-fee reversal exactly like cancellation refunds do.
"""
from decimal import Decimal

import pytest

from database import SessionLocal
from tests.test_bookings import (  # noqa: F401 (autouse fixtures)
    _bookable_setup,
    _create_and_approve_branch,
    _invite_and_accept_staff,
    client,
    _auth,
    seed_reference_data,
    stub_booking_emails,
)
from tests.test_m8_cancellation_reschedule import (
    _customer_token_for,
    _fully_paid_booking,
    _set_platform_fee,
    stub_razorpay,  # noqa: F401 (autouse fixture)
)
import crud_payment
from models import Booking, BookingFinancial, Payment, Refund


def test_standalone_partial_refund_does_not_change_booking_status():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)

    response = client.post(
        f"/api/v1/bookings/{booking['id']}/refund",
        json={"amount": "100.00", "reason": "Service quality issue"},
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["booking"]["status"] == "Confirmed"
    assert body["booking"]["cancellation_reason"] is None
    assert Decimal(body["refund"]["final_amount"]) == Decimal("100.00")

    db = SessionLocal()
    try:
        b = db.query(Booking).filter(Booking.id == booking["id"]).first()
        assert b.status == "Confirmed"
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking["id"]).first()
        assert Decimal(financial.amount_refunded) == Decimal("100.00")
        refund = db.query(Refund).filter(Refund.booking_id == booking["id"]).first()
        assert refund.reason == "Service quality issue"
        assert refund.role_snapshot == "BUSINESS_OWNER"
        assert refund.status == "Completed"
    finally:
        db.close()


def test_standalone_full_refund_does_not_cancel_booking():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)
    total_paid = Decimal(booking["amount_paid"])

    response = client.post(
        f"/api/v1/bookings/{booking['id']}/refund",
        json={"amount": str(total_paid), "reason": "Full goodwill refund"},
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["booking"]["status"] == "Confirmed"

    db = SessionLocal()
    try:
        b = db.query(Booking).filter(Booking.id == booking["id"]).first()
        assert b.status == "Confirmed"  # never auto-cancelled, even on a full refund
        assert b.cancellation_reason is None
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking["id"]).first()
        assert Decimal(financial.amount_refunded) == total_paid
    finally:
        db.close()


def test_standalone_refund_rejects_amount_exceeding_refundable_ceiling():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)
    total_paid = Decimal(booking["amount_paid"])

    response = client.post(
        f"/api/v1/bookings/{booking['id']}/refund",
        json={"amount": str(total_paid + Decimal("1")), "reason": "Too much"},
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 400, response.text


def test_standalone_refund_sequential_requests_never_exceed_ceiling():
    """Duplicate/concurrent-refund safety: the refundable ceiling is
    recomputed fresh on every call (under the same per-booking advisory
    lock cancellation refunds use), so a second request that would push
    the total past what was actually captured is rejected — proving two
    requests for the same booking can never jointly over-refund."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)
    total_paid = Decimal(booking["amount_paid"])
    majority = (total_paid * Decimal("0.7")).quantize(Decimal("0.01"))
    remainder = (total_paid - majority).quantize(Decimal("0.01"))

    first = client.post(
        f"/api/v1/bookings/{booking['id']}/refund",
        json={"amount": str(majority), "reason": "First partial refund"},
        headers=_auth(setup["owner_token"]),
    )
    assert first.status_code == 200, first.text

    # Would exceed what was actually captured -> rejected, not silently capped.
    second = client.post(
        f"/api/v1/bookings/{booking['id']}/refund",
        json={"amount": str(majority), "reason": "Second refund attempt"},
        headers=_auth(setup["owner_token"]),
    )
    assert second.status_code == 400, second.text

    # Exactly the remaining balance succeeds.
    third = client.post(
        f"/api/v1/bookings/{booking['id']}/refund",
        json={"amount": str(remainder), "reason": "Remaining balance refund"},
        headers=_auth(setup["owner_token"]),
    )
    assert third.status_code == 200, third.text

    db = SessionLocal()
    try:
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking["id"]).first()
        assert Decimal(financial.amount_refunded) == total_paid
        refund_count = db.query(Refund).filter(Refund.booking_id == booking["id"]).count()
        assert refund_count == 2  # the rejected attempt created no row
    finally:
        db.close()


def test_standalone_refund_requires_reason():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)

    missing_field = client.post(
        f"/api/v1/bookings/{booking['id']}/refund",
        json={"amount": "50.00"},
        headers=_auth(setup["owner_token"]),
    )
    assert missing_field.status_code == 422, missing_field.text

    blank_reason = client.post(
        f"/api/v1/bookings/{booking['id']}/refund",
        json={"amount": "50.00", "reason": "   "},
        headers=_auth(setup["owner_token"]),
    )
    assert blank_reason.status_code == 400, blank_reason.text


def test_standalone_refund_authorization_owner_and_own_branch_manager_allowed_other_branch_manager_rejected():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)

    other_branch = _create_and_approve_branch(setup["business_id"], setup["owner_token"])
    _, other_bm_token = _invite_and_accept_staff(
        setup["business_id"], setup["owner_token"], "BRANCH_MANAGER", branch_id=other_branch["id"]
    )
    forbidden = client.post(
        f"/api/v1/bookings/{booking['id']}/refund",
        json={"amount": "50.00", "reason": "Should be rejected"},
        headers=_auth(other_bm_token),
    )
    assert forbidden.status_code == 403, forbidden.text

    _, own_bm_token = _invite_and_accept_staff(
        setup["business_id"], setup["owner_token"], "BRANCH_MANAGER", branch_id=setup["branch"]["id"]
    )
    allowed = client.post(
        f"/api/v1/bookings/{booking['id']}/refund",
        json={"amount": "50.00", "reason": "Own-branch manager refund"},
        headers=_auth(own_bm_token),
    )
    assert allowed.status_code == 200, allowed.text

    db = SessionLocal()
    try:
        refund = db.query(Refund).filter(Refund.booking_id == booking["id"]).first()
        assert refund.role_snapshot == "BRANCH_MANAGER"
    finally:
        db.close()


def test_standalone_refund_applies_proportional_platform_fee_reversal():
    _set_platform_fee(Decimal("5"))
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_id == booking["id"]).first()
        assert Decimal(payment.platform_fee_amount) == (Decimal(payment.amount) * Decimal("5") / Decimal("100"))
        full_fee = Decimal(payment.platform_fee_amount)
        payment_amount = Decimal(payment.amount)
    finally:
        db.close()

    refund_amount = Decimal("100.00")
    response = client.post(
        f"/api/v1/bookings/{booking['id']}/refund",
        json={"amount": str(refund_amount), "reason": "Partial refund with fee reversal"},
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text

    expected_reversal = (full_fee * refund_amount / payment_amount).quantize(Decimal("0.01"))
    db = SessionLocal()
    try:
        refund = db.query(Refund).filter(Refund.booking_id == booking["id"]).first()
        assert Decimal(refund.platform_fee_reversal_amount) == expected_reversal
    finally:
        db.close()


def test_standalone_refund_appears_in_payment_history():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)

    client.post(
        f"/api/v1/bookings/{booking['id']}/refund",
        json={"amount": "75.00", "reason": "History visibility check"},
        headers=_auth(setup["owner_token"]),
    )

    history = client.get(f"/api/v1/bookings/{booking['id']}/payments", headers=_auth(setup["owner_token"]))
    assert history.status_code == 200, history.text
    refunds = history.json()["refunds"]
    assert len(refunds) == 1
    assert Decimal(refunds[0]["final_amount"]) == Decimal("75.00")
    assert refunds[0]["reason"] == "History visibility check"
    assert refunds[0]["status"] == "Completed"


def test_standalone_refund_pending_provider_confirmation_does_not_change_status_or_double_count(monkeypatch):
    """Reuses the same asynchronous Razorpay refund-lifecycle handling as
    cancellation refunds: a 'pending' provider response leaves the Refund
    Initiated and defers the BookingFinancial.amount_refunded increment —
    and, either way, never touches Booking.status."""
    monkeypatch.setattr(crud_payment.razorpay_service, "create_refund", lambda *a, **k: {"id": "rfnd_pending_standalone", "status": "pending"})
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)

    response = client.post(
        f"/api/v1/bookings/{booking['id']}/refund",
        json={"amount": "50.00", "reason": "Pending provider confirmation check"},
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["booking"]["status"] == "Confirmed"

    db = SessionLocal()
    try:
        refund = db.query(Refund).filter(Refund.razorpay_refund_id == "rfnd_pending_standalone").first()
        assert refund.status == "Initiated"
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking["id"]).first()
        assert Decimal(financial.amount_refunded) == Decimal("0")  # deferred until webhook confirms
        b = db.query(Booking).filter(Booking.id == booking["id"]).first()
        assert b.status == "Confirmed"
    finally:
        db.close()


def test_refundable_amount_field_tracks_partial_and_full_refunds():
    """Manual-acceptance follow-up: BookingResponse.refundable_amount must
    reflect exactly what a standalone refund could still move — starting
    at the full captured amount, decreasing after a partial refund, and
    reaching zero (so the frontend hides the Refund action) after a full
    refund of everything captured."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token)
    total_paid = Decimal(booking["amount_paid"])
    assert Decimal(booking["refundable_amount"]) == total_paid

    partial = (total_paid * Decimal("0.4")).quantize(Decimal("0.01"))
    client.post(
        f"/api/v1/bookings/{booking['id']}/refund",
        json={"amount": str(partial), "reason": "Partial refund"},
        headers=_auth(setup["owner_token"]),
    )
    get_after_partial = client.get(f"/api/v1/bookings/{booking['id']}", headers=_auth(setup["owner_token"]))
    assert Decimal(get_after_partial.json()["refundable_amount"]) == total_paid - partial

    remainder = total_paid - partial
    client.post(
        f"/api/v1/bookings/{booking['id']}/refund",
        json={"amount": str(remainder), "reason": "Remaining refund"},
        headers=_auth(setup["owner_token"]),
    )
    get_after_full = client.get(f"/api/v1/bookings/{booking['id']}", headers=_auth(setup["owner_token"]))
    assert Decimal(get_after_full.json()["refundable_amount"]) == Decimal("0")


def test_refundable_amount_is_zero_for_reserve_without_payment_and_legacy_bookings():
    setup = _bookable_setup()
    from tests.test_bookings import _create_walk_in, BOOKING_DATE
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    rwp = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/checkout/reserve-without-payment",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "09:00:00",
        },
        headers=_auth(setup["owner_token"]),
    ).json()["booking"]
    assert Decimal(rwp["refundable_amount"]) == Decimal("0")

    legacy = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE), "start_time": "10:00:00",
        },
        headers=_auth(setup["owner_token"]),
    ).json()
    assert Decimal(legacy["refundable_amount"]) == Decimal("0")
