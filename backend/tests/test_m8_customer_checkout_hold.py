"""
Manual-acceptance fixes — customer checkout review flow.

Three bugs were diagnosed and fixed across this flow:
1. The customer checkout summary never showed the coupon's effect before
   payment (no backend preview/refresh mechanism existed).
2. An unhandled Razorpay SDK failure (e.g. invalid credentials) leaked a
   raw stack trace instead of the application's normal structured error.
3. Selecting a slot (or refreshing the summary for a coupon/payment-option
   change) contacted Razorpay eagerly, so a broken gateway surfaced
   "Payment gateway is currently unavailable" before the customer ever
   clicked Book/Proceed to Pay, and the checkout summary panel — including
   the Pay/Book button — never rendered because the request failed.

These tests cover: creating a checkout hold with the authoritative
breakdown and no Razorpay contact at all (no Booking, no Payment, no
order), refreshing it when the coupon or payment option changes (same
slot, new amount, still no Razorpay contact), the ₹0-after-100%-coupon
path (no hold at all), the NEW Phase-2 "create checkout payment" step
that is the only point where a Razorpay order is created (called only on
the final Book/Proceed to Pay action), hold finalization still working
through the UNCHANGED existing verify endpoint, deposit_percentage being
returned alongside deposit_amount, and Razorpay failures returning a
clean structured error at every wrapped call site instead of a stack
trace.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
import razorpay.errors

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
from models import BookingHold, Payment, Booking, BookingFinancial


@pytest.fixture(autouse=True)
def stub_razorpay(monkeypatch):
    calls = {"create_order": 0}

    def _create_order(amount, currency, receipt):
        calls["create_order"] += 1
        return {"id": f"order_fake_{receipt}"}

    monkeypatch.setattr(crud_payment.razorpay_service, "create_order", _create_order)
    monkeypatch.setattr(crud_payment.razorpay_service, "verify_payment_signature", lambda *a, **k: True)
    monkeypatch.setattr(crud_payment.razorpay_service, "fetch_payment", lambda payment_id: {"status": "captured", "amount": 10**12})
    monkeypatch.setattr(crud_payment.razorpay_service, "to_paise", lambda amount: 10**12)
    return calls


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


def _create_coupon(setup, code="SAVE20", value="20"):
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


def _hold_request(setup, **extra):
    payload = {
        "branch_service_id": setup["branch_service"]["id"], "booking_date": str(BOOKING_DATE),
        "start_time": "09:00:00", "payment_option": "Full",
    }
    payload.update(extra)
    return payload


def _create_hold(setup, customer_token, **extra):
    response = client.post(
        "/api/v1/customer/checkout/hold", json=_hold_request(setup, **extra), headers=_auth(customer_token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _pay_for_hold(hold_id, customer_token):
    return client.post(f"/api/v1/customer/checkout/{hold_id}/pay", headers=_auth(customer_token))


# -----------------------------
# Bug 1 fix — checkout hold creation and coupon-triggered refresh
# -----------------------------

def test_create_checkout_hold_returns_authoritative_breakdown_without_booking_or_payment(stub_razorpay):
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)

    body = _create_hold(setup, customer_token)
    assert body["kind"] == "Hold"
    assert body["hold_id"] is not None
    assert body["final_amount"] == "300.00"
    assert body["amount_due_now"] == "300.00"
    assert body["coupon_code"] is None
    assert body["deposit_percentage"] is None
    # Bug 3 fix: selecting a slot never contacts Razorpay — no order exists
    # until the customer explicitly clicks Proceed to Pay.
    assert body["razorpay_order_id"] is None
    assert body["razorpay_key_id"] is None
    assert stub_razorpay["create_order"] == 0

    db = SessionLocal()
    try:
        hold = db.query(BookingHold).filter(BookingHold.id == body["hold_id"]).first()
        assert hold is not None
        assert hold.status == "Active"
        assert hold.hold_type == "CustomerCheckout"
        assert db.query(Booking).filter(Booking.resource_id == setup["resource"]["id"]).count() == 0  # selecting/reviewing never books
        assert db.query(Payment).filter(Payment.booking_hold_id == hold.id).count() == 0  # no Payment merely from selecting a slot
    finally:
        db.close()


def test_refresh_hold_with_coupon_changes_the_authoritative_amount(stub_razorpay):
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    original = _create_hold(setup, customer_token)
    coupon = _create_coupon(setup)

    refreshed = client.post(
        f"/api/v1/customer/checkout/{original['hold_id']}/refresh",
        json={"payment_option": "Full", "coupon_code": coupon["code"]},
        headers=_auth(customer_token),
    )
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()
    assert body["kind"] == "Hold"
    assert body["hold_id"] != original["hold_id"]
    assert body["coupon_code"] == coupon["code"]
    assert Decimal(body["final_amount"]) == (Decimal(original["final_amount"]) * Decimal("0.8")).quantize(Decimal("0.01"))
    # Same slot, never re-derived from the request.
    assert body["booking_date"] == original["booking_date"]
    assert body["start_time"] == original["start_time"]
    # Bug 3 fix: refreshing the summary never contacts Razorpay either.
    assert body["razorpay_order_id"] is None
    assert stub_razorpay["create_order"] == 0

    db = SessionLocal()
    try:
        old_hold = db.query(BookingHold).filter(BookingHold.id == original["hold_id"]).first()
        assert old_hold.status == "Cancelled"
        new_hold = db.query(BookingHold).filter(BookingHold.id == body["hold_id"]).first()
        assert new_hold.status == "Active"
        assert db.query(Payment).filter(Payment.booking_hold_id == new_hold.id).count() == 0
    finally:
        db.close()


def test_refresh_hold_with_invalid_coupon_does_not_destroy_existing_hold():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    original = _create_hold(setup, customer_token)

    refreshed = client.post(
        f"/api/v1/customer/checkout/{original['hold_id']}/refresh",
        json={"payment_option": "Full", "coupon_code": "DOES-NOT-EXIST"},
        headers=_auth(customer_token),
    )
    assert refreshed.status_code == 404, refreshed.text

    db = SessionLocal()
    try:
        old_hold = db.query(BookingHold).filter(BookingHold.id == original["hold_id"]).first()
        assert old_hold.status == "Active"
    finally:
        db.close()


def test_refresh_hold_rejected_for_a_different_customer():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    other_customer_token = _customer_token_for(setup)
    original = _create_hold(setup, customer_token)

    response = client.post(
        f"/api/v1/customer/checkout/{original['hold_id']}/refresh",
        json={"payment_option": "Full"},
        headers=_auth(other_customer_token),
    )
    assert response.status_code == 403, response.text


def test_full_to_deposit_refresh_updates_amount_due_and_balance_and_returns_percentage():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    far_enough = BOOKING_DATE + timedelta(weeks=2)
    original = _create_hold(setup, customer_token, booking_date=str(far_enough))
    assert original["deposit_amount"] is None
    assert original["deposit_percentage"] is None

    refreshed = client.post(
        f"/api/v1/customer/checkout/{original['hold_id']}/refresh",
        json={"payment_option": "Deposit"},
        headers=_auth(customer_token),
    )
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()
    assert body["payment_option"] == "Deposit"
    assert body["deposit_percentage"] == "25"
    expected_deposit = (Decimal(body["final_amount"]) * Decimal("25") / Decimal("100")).quantize(Decimal("0.01"))
    assert Decimal(body["deposit_amount"]) == expected_deposit
    assert Decimal(body["amount_due_now"]) == expected_deposit
    assert Decimal(body["balance_due"]) == Decimal(body["final_amount"]) - expected_deposit
    assert body["balance_due_at"] is not None

    # And back to Full drops the deposit fields again.
    back_to_full = client.post(
        f"/api/v1/customer/checkout/{body['hold_id']}/refresh",
        json={"payment_option": "Full"},
        headers=_auth(customer_token),
    ).json()
    assert back_to_full["deposit_amount"] is None
    assert back_to_full["deposit_percentage"] is None
    assert Decimal(back_to_full["amount_due_now"]) == Decimal(back_to_full["final_amount"])


# -----------------------------
# Bug 4 fix — re-validating the SAME coupon on a hold's own refresh must
# not count that still-Active hold as a reservation against itself.
# -----------------------------

def test_second_refresh_with_the_same_coupon_succeeds():
    """Reproduces the reported manual-acceptance bug: applying a coupon,
    then refreshing again while keeping that same coupon, used to fail
    with 'You have already used this coupon the maximum number of times'
    because the hold-to-be-replaced counted as a reservation against
    itself. A per_customer_usage_limit of 1 (the API default) is the
    tightest case."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    coupon = _create_coupon(setup, code="REUSE1", value="10")
    original = _create_hold(setup, customer_token)

    first = client.post(
        f"/api/v1/customer/checkout/{original['hold_id']}/refresh",
        json={"payment_option": "Full", "coupon_code": coupon["code"]},
        headers=_auth(customer_token),
    )
    assert first.status_code == 200, first.text
    h2 = first.json()
    assert h2["coupon_code"] == coupon["code"]

    second = client.post(
        f"/api/v1/customer/checkout/{h2['hold_id']}/refresh",
        json={"payment_option": "Full", "coupon_code": coupon["code"]},
        headers=_auth(customer_token),
    )
    assert second.status_code == 200, second.text
    h3 = second.json()
    assert h3["coupon_code"] == coupon["code"]
    assert h3["hold_id"] != h2["hold_id"]


def test_coupon_then_deposit_refresh_keeping_same_coupon_succeeds():
    """Scenario B from the manual-acceptance report: apply a coupon, then
    switch Full -> Deposit while keeping that same coupon."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    far_enough = BOOKING_DATE + timedelta(weeks=2)
    coupon = _create_coupon(setup, code="REUSE2", value="10")
    original = _create_hold(setup, customer_token, booking_date=str(far_enough))

    with_coupon = client.post(
        f"/api/v1/customer/checkout/{original['hold_id']}/refresh",
        json={"payment_option": "Full", "coupon_code": coupon["code"]},
        headers=_auth(customer_token),
    )
    assert with_coupon.status_code == 200, with_coupon.text
    h2 = with_coupon.json()

    to_deposit = client.post(
        f"/api/v1/customer/checkout/{h2['hold_id']}/refresh",
        json={"payment_option": "Deposit", "coupon_code": coupon["code"]},
        headers=_auth(customer_token),
    )
    assert to_deposit.status_code == 200, to_deposit.text
    body = to_deposit.json()
    assert body["coupon_code"] == coupon["code"]
    assert body["payment_option"] == "Deposit"
    assert body["deposit_percentage"] == "25"


def test_deposit_then_coupon_refresh_succeeds():
    """Scenario A from the manual-acceptance report: switch Full ->
    Deposit first (no coupon yet), then apply a coupon on the next
    refresh."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    far_enough = BOOKING_DATE + timedelta(weeks=2)
    coupon = _create_coupon(setup, code="REUSE3", value="10")
    original = _create_hold(setup, customer_token, booking_date=str(far_enough))

    to_deposit = client.post(
        f"/api/v1/customer/checkout/{original['hold_id']}/refresh",
        json={"payment_option": "Deposit"},
        headers=_auth(customer_token),
    )
    assert to_deposit.status_code == 200, to_deposit.text
    h2 = to_deposit.json()

    with_coupon = client.post(
        f"/api/v1/customer/checkout/{h2['hold_id']}/refresh",
        json={"payment_option": "Deposit", "coupon_code": coupon["code"]},
        headers=_auth(customer_token),
    )
    assert with_coupon.status_code == 200, with_coupon.text
    body = with_coupon.json()
    assert body["coupon_code"] == coupon["code"]
    assert body["payment_option"] == "Deposit"


def test_three_consecutive_refreshes_with_the_same_coupon_succeed():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    coupon = _create_coupon(setup, code="REUSE4", value="10")
    hold = _create_hold(setup, customer_token)

    for payment_option in ("Full", "Full", "Full"):
        response = client.post(
            f"/api/v1/customer/checkout/{hold['hold_id']}/refresh",
            json={"payment_option": payment_option, "coupon_code": coupon["code"]},
            headers=_auth(customer_token),
        )
        assert response.status_code == 200, response.text
        hold = response.json()
        assert hold["coupon_code"] == coupon["code"]


def test_another_customers_active_hold_with_coupon_still_counts_toward_total_limit():
    """The exclusion is scoped to the one hold being refreshed — it must
    never exclude a genuinely different hold, including another
    customer's, from the coupon's capacity check."""
    setup = _bookable_setup()
    customer_a = _customer_token_for(setup)
    customer_b = _customer_token_for(setup)
    response = client.post(
        f"/api/v1/businesses/{setup['business_id']}/coupons",
        json={
            "code": "SCARCE1", "discount_type": "Percentage", "discount_value": "10",
            "valid_from": str(date.today()), "valid_until": str(date.today() + timedelta(days=365)),
            "total_usage_limit": 1,
        },
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    coupon = response.json()

    hold_a = _create_hold(setup, customer_a, start_time="09:00:00")
    reserved = client.post(
        f"/api/v1/customer/checkout/{hold_a['hold_id']}/refresh",
        json={"payment_option": "Full", "coupon_code": coupon["code"]},
        headers=_auth(customer_a),
    )
    assert reserved.status_code == 200, reserved.text

    hold_b = _create_hold(setup, customer_b, start_time="10:00:00")
    blocked = client.post(
        f"/api/v1/customer/checkout/{hold_b['hold_id']}/refresh",
        json={"payment_option": "Full", "coupon_code": coupon["code"]},
        headers=_auth(customer_b),
    )
    assert blocked.status_code == 409, blocked.text
    assert "usage limit" in blocked.json()["error"]["message"].lower()


def test_same_customers_separate_hold_with_coupon_still_counts_toward_per_customer_limit():
    """A genuinely separate hold of the SAME customer (not the one being
    refreshed) must still count — the exclusion only ever names the one
    hold currently being replaced."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    coupon = _create_coupon(setup, code="ONEUSE1", value="10")  # default per_customer_usage_limit == 1

    first_slot_hold = _create_hold(setup, customer_token, start_time="09:00:00")
    first_reserved = client.post(
        f"/api/v1/customer/checkout/{first_slot_hold['hold_id']}/refresh",
        json={"payment_option": "Full", "coupon_code": coupon["code"]},
        headers=_auth(customer_token),
    )
    assert first_reserved.status_code == 200, first_reserved.text

    # A second, independent hold for a different slot — not derived from
    # refreshing the first — trying to use the same coupon.
    second_slot_hold = _create_hold(setup, customer_token, start_time="10:00:00")
    blocked = client.post(
        f"/api/v1/customer/checkout/{second_slot_hold['hold_id']}/refresh",
        json={"payment_option": "Full", "coupon_code": coupon["code"]},
        headers=_auth(customer_token),
    )
    assert blocked.status_code == 409, blocked.text
    assert "maximum number of times" in blocked.json()["error"]["message"].lower()


# -----------------------------
# Bug 3 fix — Razorpay is only contacted at the final Proceed to Pay step
# -----------------------------

def test_selecting_slot_does_not_call_razorpay_even_when_gateway_is_broken(monkeypatch):
    """The hold-creation endpoint must succeed regardless of Razorpay's
    health, since it never calls it."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)

    def _boom(*args, **kwargs):
        raise razorpay.errors.BadRequestError("Authentication failed")
    monkeypatch.setattr(crud_payment.razorpay_service, "create_order", _boom)

    response = client.post(
        "/api/v1/customer/checkout/hold", json=_hold_request(setup), headers=_auth(customer_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["kind"] == "Hold"


def test_refreshing_hold_does_not_call_razorpay_even_when_gateway_is_broken(monkeypatch):
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    original = _create_hold(setup, customer_token)
    coupon = _create_coupon(setup, code="SAVE10D", value="10")

    def _boom(*args, **kwargs):
        raise razorpay.errors.GatewayError("network issue")
    monkeypatch.setattr(crud_payment.razorpay_service, "create_order", _boom)

    response = client.post(
        f"/api/v1/customer/checkout/{original['hold_id']}/refresh",
        json={"payment_option": "Full", "coupon_code": coupon["code"]},
        headers=_auth(customer_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["kind"] == "Hold"


def test_checkout_payment_is_the_point_razorpay_order_creation_occurs(stub_razorpay):
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    hold = _create_hold(setup, customer_token)
    assert stub_razorpay["create_order"] == 0

    response = _pay_for_hold(hold["hold_id"], customer_token)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "AwaitingPayment"
    assert body["hold_id"] == hold["hold_id"]
    assert body["razorpay_order_id"] is not None
    assert body["razorpay_key_id"] is not None
    assert stub_razorpay["create_order"] == 1

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_hold_id == hold["hold_id"]).first()
        assert payment is not None
        assert payment.status == "Created"
        assert payment.method == "RazorpayOnline"
        assert str(payment.amount) == hold["amount_due_now"]
    finally:
        db.close()


def test_checkout_payment_rejects_a_second_attempt_on_the_same_hold():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    hold = _create_hold(setup, customer_token)
    first = _pay_for_hold(hold["hold_id"], customer_token)
    assert first.status_code == 200, first.text

    second = _pay_for_hold(hold["hold_id"], customer_token)
    assert second.status_code == 409, second.text


def test_checkout_payment_rejected_for_a_different_customer():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    other_customer_token = _customer_token_for(setup)
    hold = _create_hold(setup, customer_token)

    response = _pay_for_hold(hold["hold_id"], other_customer_token)
    assert response.status_code == 403, response.text


def test_checkout_hold_finalizes_via_existing_unchanged_verify_endpoint():
    """Hold finalization must still work exactly as before — the customer
    now goes hold -> pay -> verify; the pre-existing verify endpoint needs
    no changes at all."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    hold = _create_hold(setup, customer_token)
    pay = _pay_for_hold(hold["hold_id"], customer_token)
    assert pay.status_code == 200, pay.text

    verify = client.post(
        f"/api/v1/customer/checkout/{hold['hold_id']}/verify",
        json={"razorpay_payment_id": "pay_fake_1", "razorpay_signature": "sig_fake_1"},
        headers=_auth(customer_token),
    )
    assert verify.status_code == 200, verify.text
    booking = verify.json()["booking"]
    assert booking["status"] == "Confirmed"

    db = SessionLocal()
    try:
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking["id"]).first()
        assert financial.financial_status == "FullyPaid"
        assert Decimal(financial.amount_paid) == Decimal(financial.total_amount)
    finally:
        db.close()


def test_verify_without_a_payment_attempt_is_rejected():
    """A hold that was reviewed but never sent through /pay has no Payment
    row yet — verify must reject it rather than finalizing for free."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    hold = _create_hold(setup, customer_token)

    verify = client.post(
        f"/api/v1/customer/checkout/{hold['hold_id']}/verify",
        json={"razorpay_payment_id": "pay_fake_1", "razorpay_signature": "sig_fake_1"},
        headers=_auth(customer_token),
    )
    assert verify.status_code == 404, verify.text


def test_create_checkout_hold_zero_amount_returns_no_payment_required_without_hold(stub_razorpay):
    setup = _bookable_setup()
    coupon = _create_coupon(setup, code="FREE100", value="100")
    customer_token = _customer_token_for(setup)

    body = _create_hold(setup, customer_token, coupon_code=coupon["code"])
    assert body["kind"] == "NoPaymentRequired"
    assert body["hold_id"] is None
    assert body["razorpay_order_id"] is None
    assert Decimal(body["final_amount"]) == Decimal("0")
    assert Decimal(body["amount_due_now"]) == Decimal("0")
    assert stub_razorpay["create_order"] == 0

    db = SessionLocal()
    try:
        assert db.query(BookingHold).filter(BookingHold.resource_id == setup["resource"]["id"]).count() == 0
        assert db.query(Payment).filter(Payment.branch_id == setup["branch"]["id"]).count() == 0
        assert db.query(Booking).filter(Booking.resource_id == setup["resource"]["id"]).count() == 0
    finally:
        db.close()


def test_confirm_no_payment_required_via_existing_one_shot_endpoint():
    setup = _bookable_setup()
    coupon = _create_coupon(setup, code="FREE100B", value="100")
    customer_token = _customer_token_for(setup)

    _create_hold(setup, customer_token, coupon_code=coupon["code"])

    confirm = client.post(
        "/api/v1/customer/checkout",
        json=_hold_request(setup, coupon_code=coupon["code"]),
        headers=_auth(customer_token),
    )
    assert confirm.status_code == 200, confirm.text
    body = confirm.json()
    assert body["status"] == "Confirmed"

    db = SessionLocal()
    try:
        booking = db.query(Booking).filter(Booking.id == body["booking"]["id"]).first()
        assert booking is not None
        assert db.query(Payment).filter(Payment.booking_id == booking.id).count() == 0
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking.id).first()
        assert financial.financial_status == "FullyPaid"
        assert Decimal(financial.amount_paid) == Decimal("0")
    finally:
        db.close()


def test_refresh_hold_transitions_to_no_payment_required_when_coupon_makes_it_free(stub_razorpay):
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    original = _create_hold(setup, customer_token)
    coupon = _create_coupon(setup, code="FREE100C", value="100")

    refreshed = client.post(
        f"/api/v1/customer/checkout/{original['hold_id']}/refresh",
        json={"payment_option": "Full", "coupon_code": coupon["code"]},
        headers=_auth(customer_token),
    )
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()
    assert body["kind"] == "NoPaymentRequired"
    assert body["hold_id"] is None
    assert stub_razorpay["create_order"] == 0

    db = SessionLocal()
    try:
        old_hold = db.query(BookingHold).filter(BookingHold.id == original["hold_id"]).first()
        assert old_hold.status == "Cancelled"  # released, not left dangling
        assert db.query(BookingHold).filter(
            BookingHold.resource_id == setup["resource"]["id"], BookingHold.status == "Active",
        ).count() == 0
    finally:
        db.close()


def test_deposit_ineligible_for_near_date_rejected_at_hold_creation():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    response = client.post(
        "/api/v1/customer/checkout/hold",
        json=_hold_request(setup, payment_option="Deposit", booking_date=str(date.today() + timedelta(days=1))),
        headers=_auth(customer_token),
    )
    assert response.status_code == 409, response.text


def test_existing_customer_checkout_endpoint_still_works_unmodified():
    """The existing one-shot flow (bug-2-affected path) must keep working
    exactly as before for a plain Full payment — this is not a redesign."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    checkout = client.post("/api/v1/customer/checkout", json=_hold_request(setup), headers=_auth(customer_token))
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
    assert verify.json()["booking"]["status"] == "Confirmed"


# -----------------------------
# Bug 2 fix — Razorpay SDK failures return a structured API error
# -----------------------------

def test_razorpay_failure_on_existing_one_shot_checkout_returns_structured_error(monkeypatch):
    """Same fix applied to the pre-existing /customer/checkout call site —
    this is exactly the reported 'Proceed to Pay' -> 'Checkout failed' bug."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)

    def _boom(*args, **kwargs):
        raise razorpay.errors.BadRequestError("Authentication failed")
    monkeypatch.setattr(crud_payment.razorpay_service, "create_order", _boom)

    response = client.post("/api/v1/customer/checkout", json=_hold_request(setup), headers=_auth(customer_token))
    assert response.status_code == 502, response.text
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == 502


def test_razorpay_failure_on_checkout_payment_returns_structured_error(monkeypatch):
    """The NEW Phase-2 finalize step is where the wrap now needs to apply
    for the hold/review flow, since hold creation/refresh no longer call
    Razorpay at all."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    hold = _create_hold(setup, customer_token)

    def _boom(*args, **kwargs):
        raise razorpay.errors.BadRequestError("Authentication failed")
    monkeypatch.setattr(crud_payment.razorpay_service, "create_order", _boom)

    response = _pay_for_hold(hold["hold_id"], customer_token)
    assert response.status_code == 502, response.text
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == 502
    assert "unavailable" in body["error"]["message"].lower()
    assert "Authentication failed" not in response.text
    assert "Traceback" not in response.text

    db = SessionLocal()
    try:
        # Same as the pre-existing one-shot checkout's failure behavior: the
        # hold survives a failed payment attempt and is reclaimed by TTL.
        holds = db.query(BookingHold).filter(BookingHold.resource_id == setup["resource"]["id"]).all()
        assert len(holds) == 1
        assert holds[0].status == "Active"
        assert db.query(Payment).filter(Payment.booking_hold_id == hold["hold_id"]).count() == 0
    finally:
        db.close()


def test_razorpay_failure_on_balance_payment_initiation_returns_structured_error(monkeypatch):
    """Confirms the wrap was applied consistently to another existing
    create_order call site (Phase 7 balance payment), not just checkout."""
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    far_future = BOOKING_DATE + timedelta(weeks=2)
    checkout = client.post(
        "/api/v1/customer/checkout",
        json=_hold_request(setup, payment_option="Deposit", booking_date=str(far_future)),
        headers=_auth(customer_token),
    ).json()
    verify = client.post(
        f"/api/v1/customer/checkout/{checkout['hold_id']}/verify",
        json={"razorpay_payment_id": "pay_dep_1", "razorpay_signature": "sig_dep_1"},
        headers=_auth(customer_token),
    )
    assert verify.status_code == 200, verify.text
    booking_id = verify.json()["booking"]["id"]

    def _boom(*args, **kwargs):
        raise razorpay.errors.ServerError("provider outage")
    monkeypatch.setattr(crud_payment.razorpay_service, "create_order", _boom)

    response = client.post(f"/api/v1/customer/bookings/{booking_id}/pay-balance", headers=_auth(customer_token))
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == 502
