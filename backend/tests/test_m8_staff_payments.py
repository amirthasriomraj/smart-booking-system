"""
Milestone 8 Phase 6 — Staff payment flow tests.

Manual-acceptance fix: staff checkout is now two-phase — selecting a slot
(POST .../checkout/hold) acquires a 10-minute StaffCheckout hold with the
full authoritative price/coupon/deposit breakdown but creates no Booking;
a separate finalize call per payment method (POST /holds/{id}/checkout/...)
then creates the Payment/Booking using that same hold's locked-in terms.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from database import SessionLocal
from tests.test_bookings import (  # noqa: F401 (autouse fixtures)
    _bookable_setup,
    _create_walk_in,
    _create_and_approve_branch,
    _invite_and_accept_staff,
    _next_weekday_date,
    client,
    _auth,
    seed_reference_data,
    stub_booking_emails,
    BOOKING_DATE,
    WEEKDAY,
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


def _create_hold(setup, customer_id, **extra):
    payload = {
        "customer_id": customer_id, "branch_service_id": setup["branch_service"]["id"],
        "booking_date": str(BOOKING_DATE), "start_time": "09:00:00", "payment_option": "Full",
    }
    payload.update(extra)
    response = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/checkout/hold",
        json=payload,
        headers=_auth(setup["owner_token"]),
    )
    return response


def test_selecting_a_slot_creates_a_hold_not_a_booking():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    response = _create_hold(setup, customer["id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["hold_id"] is not None
    assert body["final_amount"] == "300.00"
    assert body["amount_due_now"] == "300.00"

    db = SessionLocal()
    try:
        hold = db.query(BookingHold).filter(BookingHold.id == body["hold_id"]).first()
        assert hold is not None
        assert hold.status == "Active"
        assert hold.hold_type == "StaffCheckout"
        # No Booking and no Payment exist yet — selecting/reviewing never books.
        assert db.query(Payment).filter(Payment.booking_hold_id == hold.id).count() == 0
        from models import Booking
        assert db.query(Booking).filter(Booking.resource_id == setup["resource"]["id"]).count() == 0
    finally:
        db.close()


def test_staff_cash_checkout_finalizes_immediately():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    hold_id = _create_hold(setup, customer["id"]).json()["hold_id"]

    response = client.post(
        f"/api/v1/holds/{hold_id}/checkout/cash",
        json={"cash_received": "1000"},
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    booking = body["booking"]
    assert booking["status"] == "Confirmed"
    assert body["cash_received"] == "1000.00" or Decimal(body["cash_received"]) == Decimal("1000")
    assert Decimal(body["change_returned"]) == Decimal("1000") - Decimal(body["amount_charged"])

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
    hold_id = _create_hold(setup, customer["id"]).json()["hold_id"]

    response = client.post(
        f"/api/v1/holds/{hold_id}/checkout/cash",
        json={"cash_received": "1"},
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 400, response.text


def test_finalize_twice_against_same_hold_is_rejected():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    hold_id = _create_hold(setup, customer["id"]).json()["hold_id"]

    first = client.post(
        f"/api/v1/holds/{hold_id}/checkout/cash", json={"cash_received": "1000"}, headers=_auth(setup["owner_token"]),
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/api/v1/holds/{hold_id}/checkout/cash", json={"cash_received": "1000"}, headers=_auth(setup["owner_token"]),
    )
    assert second.status_code == 409, second.text


def test_staff_price_override_requires_reason():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    response = _create_hold(setup, customer["id"], final_price_override="500")
    assert response.status_code == 400, response.text


def test_staff_final_price_override_recorded_in_history():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    hold_response = _create_hold(
        setup, customer["id"], final_price_override="500", price_override_reason="Loyalty discount",
    )
    assert hold_response.status_code == 200, hold_response.text
    assert hold_response.json()["final_amount"] == "500.00"
    hold_id = hold_response.json()["hold_id"]

    response = client.post(
        f"/api/v1/holds/{hold_id}/checkout/cash", json={"cash_received": "500"}, headers=_auth(setup["owner_token"]),
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
    hold_id = _create_hold(setup, customer["id"]).json()["hold_id"]

    checkout = client.post(f"/api/v1/holds/{hold_id}/checkout/external", headers=_auth(setup["owner_token"]))
    assert checkout.status_code == 200, checkout.text
    assert checkout.json()["hold_id"] == hold_id

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
    hold_id = _create_hold(setup, customer["id"]).json()["hold_id"]

    checkout = client.post(f"/api/v1/holds/{hold_id}/checkout/email-link", headers=_auth(setup["owner_token"]))
    assert checkout.status_code == 200, checkout.text

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


def test_staff_deposit_hold_rejected_when_appointment_too_soon():
    """Deposit eligibility (>= 7x24h) is still enforced authoritatively at
    hold-creation time — the manual-acceptance fix only changed when the
    Booking/Payment get created, not this rule."""
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    response = _create_hold(setup, customer["id"], payment_option="Deposit")
    assert response.status_code == 409, response.text


def test_staff_deposit_hold_and_cash_finalize_charges_only_the_deposit():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    far_enough_date = _next_weekday_date(WEEKDAY) + timedelta(weeks=2)

    hold_response = _create_hold(
        setup, customer["id"], payment_option="Deposit", booking_date=str(far_enough_date),
    )
    assert hold_response.status_code == 200, hold_response.text
    body = hold_response.json()
    assert body["payment_option"] == "Deposit"
    assert Decimal(body["deposit_amount"]) == (Decimal(body["final_amount"]) * Decimal("25") / Decimal("100")).quantize(Decimal("0.01"))
    assert Decimal(body["amount_due_now"]) == Decimal(body["deposit_amount"])
    assert body["balance_due_at"] is not None

    finalize = client.post(
        f"/api/v1/holds/{body['hold_id']}/checkout/cash",
        json={"cash_received": body["deposit_amount"]},
        headers=_auth(setup["owner_token"]),
    )
    assert finalize.status_code == 200, finalize.text
    booking = finalize.json()["booking"]
    assert booking["financial_status"] == "AwaitingBalance"
    assert Decimal(booking["amount_paid"]) == Decimal(body["deposit_amount"])
    assert Decimal(booking["balance_due"]) == Decimal(body["balance_due"])


# -----------------------------
# Manual-acceptance fix — refreshing the Booking & Payment Summary for
# the same slot after a pricing-affecting input changes, without
# mutating the frozen BookingHold.price_snapshot (ID-054).
# -----------------------------

def _create_percentage_coupon(setup, code="SAVE20", value="20"):
    response = client.post(
        f"/api/v1/businesses/{setup['business_id']}/coupons",
        json={
            "code": code, "discount_type": "Percentage", "discount_value": value,
            "valid_from": str(date.today()), "valid_until": str(date.today() + timedelta(days=365)),
        },
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_refresh_hold_recomputes_price_for_same_slot_with_new_coupon():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    original = _create_hold(setup, customer["id"]).json()
    coupon = _create_percentage_coupon(setup)

    refreshed = client.post(
        f"/api/v1/holds/{original['hold_id']}/refresh",
        json={"payment_option": "Full", "coupon_code": coupon["code"]},
        headers=_auth(setup["owner_token"]),
    )
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()

    assert body["hold_id"] != original["hold_id"]  # a brand-new hold, not a mutated one
    assert body["coupon_code"] == coupon["code"]
    assert Decimal(body["final_amount"]) == (Decimal(original["final_amount"]) * Decimal("0.8")).quantize(Decimal("0.01"))
    # Same slot — never re-derived from the request.
    assert body["booking_date"] == original["booking_date"]
    assert body["start_time"] == original["start_time"]
    assert body["resource_id"] == original["resource_id"]

    db = SessionLocal()
    try:
        old_hold = db.query(BookingHold).filter(BookingHold.id == original["hold_id"]).first()
        assert old_hold.status == "Cancelled"
        new_hold = db.query(BookingHold).filter(BookingHold.id == body["hold_id"]).first()
        assert new_hold.status == "Active"
        assert new_hold.hold_type == "StaffCheckout"
    finally:
        db.close()

    # The refreshed hold finalizes normally, exactly like a freshly created one.
    finalize = client.post(
        f"/api/v1/holds/{body['hold_id']}/checkout/cash",
        json={"cash_received": body["final_amount"]},
        headers=_auth(setup["owner_token"]),
    )
    assert finalize.status_code == 200, finalize.text


def test_refresh_hold_with_invalid_coupon_does_not_destroy_existing_hold():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    original = _create_hold(setup, customer["id"]).json()

    refreshed = client.post(
        f"/api/v1/holds/{original['hold_id']}/refresh",
        json={"payment_option": "Full", "coupon_code": "DOES-NOT-EXIST"},
        headers=_auth(setup["owner_token"]),
    )
    assert refreshed.status_code == 404, refreshed.text

    db = SessionLocal()
    try:
        old_hold = db.query(BookingHold).filter(BookingHold.id == original["hold_id"]).first()
        assert old_hold.status == "Active"  # untouched — the bad input never got a chance to release it
    finally:
        db.close()


def test_refresh_hold_price_override_without_reason_does_not_destroy_existing_hold():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    original = _create_hold(setup, customer["id"]).json()

    refreshed = client.post(
        f"/api/v1/holds/{original['hold_id']}/refresh",
        json={"payment_option": "Full", "final_price_override": "1"},
        headers=_auth(setup["owner_token"]),
    )
    assert refreshed.status_code == 400, refreshed.text

    db = SessionLocal()
    try:
        old_hold = db.query(BookingHold).filter(BookingHold.id == original["hold_id"]).first()
        assert old_hold.status == "Active"
    finally:
        db.close()


def test_refresh_hold_with_price_override_and_reason_succeeds():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    original = _create_hold(setup, customer["id"]).json()

    refreshed = client.post(
        f"/api/v1/holds/{original['hold_id']}/refresh",
        json={"payment_option": "Full", "final_price_override": "123.45", "price_override_reason": "Loyalty discount"},
        headers=_auth(setup["owner_token"]),
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["final_amount"] == "123.45"


def test_refresh_hold_rejects_a_hold_already_used_for_a_payment_attempt():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    original = _create_hold(setup, customer["id"]).json()

    client.post(
        f"/api/v1/holds/{original['hold_id']}/checkout/external", headers=_auth(setup["owner_token"]),
    )

    refreshed = client.post(
        f"/api/v1/holds/{original['hold_id']}/refresh",
        json={"payment_option": "Full"},
        headers=_auth(setup["owner_token"]),
    )
    assert refreshed.status_code == 409, refreshed.text


def test_refresh_hold_releases_old_hold_even_if_reacquire_fails(monkeypatch):
    """If the slot can no longer be acquired under the new terms (raced
    away in the interim), the caller gets a clear error and must have the
    user reselect a slot — the stale hold has already been released."""
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    original = _create_hold(setup, customer["id"]).json()

    import crud_hold as crud_hold_module
    from fastapi import HTTPException

    def _boom(*args, **kwargs):
        raise HTTPException(status_code=409, detail="Slot no longer available")

    monkeypatch.setattr(crud_hold_module, "acquire_hold", _boom)

    refreshed = client.post(
        f"/api/v1/holds/{original['hold_id']}/refresh",
        json={"payment_option": "Full"},
        headers=_auth(setup["owner_token"]),
    )
    assert refreshed.status_code == 409, refreshed.text

    db = SessionLocal()
    try:
        old_hold = db.query(BookingHold).filter(BookingHold.id == original["hold_id"]).first()
        assert old_hold.status == "Cancelled"
    finally:
        db.close()


# -----------------------------
# Manual-acceptance fix — explicit hold discard, used by the frontend to
# invalidate a stale Booking & Payment Summary when the customer/branch/
# service/date changes underneath an already-acquired hold.
# -----------------------------

def test_discard_hold_releases_an_active_hold():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    original = _create_hold(setup, customer["id"]).json()

    response = client.post(f"/api/v1/holds/{original['hold_id']}/discard", headers=_auth(setup["owner_token"]))
    assert response.status_code == 200, response.text

    db = SessionLocal()
    try:
        hold = db.query(BookingHold).filter(BookingHold.id == original["hold_id"]).first()
        assert hold.status == "Cancelled"
    finally:
        db.close()


def test_discard_hold_is_safe_to_call_twice():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    original = _create_hold(setup, customer["id"]).json()

    first = client.post(f"/api/v1/holds/{original['hold_id']}/discard", headers=_auth(setup["owner_token"]))
    assert first.status_code == 200, first.text
    second = client.post(f"/api/v1/holds/{original['hold_id']}/discard", headers=_auth(setup["owner_token"]))
    assert second.status_code == 200, second.text


def test_discard_hold_does_not_touch_a_hold_already_used_for_a_payment_attempt():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    original = _create_hold(setup, customer["id"]).json()

    client.post(f"/api/v1/holds/{original['hold_id']}/checkout/external", headers=_auth(setup["owner_token"]))

    response = client.post(f"/api/v1/holds/{original['hold_id']}/discard", headers=_auth(setup["owner_token"]))
    assert response.status_code == 200, response.text  # tolerant, but...

    db = SessionLocal()
    try:
        hold = db.query(BookingHold).filter(BookingHold.id == original["hold_id"]).first()
        assert hold.status == "Active"  # ...the in-flight payment attempt's hold is left alone
    finally:
        db.close()


def test_discard_hold_rejected_for_a_different_branchs_manager():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    original = _create_hold(setup, customer["id"]).json()

    other_branch = _create_and_approve_branch(setup["business_id"], setup["owner_token"])
    _, other_bm_token = _invite_and_accept_staff(
        setup["business_id"], setup["owner_token"], "BRANCH_MANAGER", branch_id=other_branch["id"]
    )

    response = client.post(f"/api/v1/holds/{original['hold_id']}/discard", headers=_auth(other_bm_token))
    assert response.status_code == 403, response.text
