"""
M8 reschedule financial-difference fix (manual-acceptance bug report):
"Manager made a Cash booking with a coupon applied, collected the deposit
only, booking confirmed. Reschedule failed with 'Payment gateway is
currently unavailable.'"

Two related defects, fixed together:

1. `apply_reschedule_price_difference` compared the service's raw catalog
   price against the booking's already-DISCOUNTED `total_amount`, so any
   coupon (or price override) discount was mistaken for a "price increase"
   equal to the discount on every single reschedule of that booking — even
   when the service's actual price never changed. The Razorpay-unavailable
   message was only how this surfaced (invalid Test Mode credentials);
   the underlying bug would have wrongly billed the customer even with
   working credentials.

2. A genuine price increase was unconditionally collected via Razorpay
   regardless of the booking's actual original payment method — with no
   way to collect a Cash-paid booking's genuine difference in cash, and no
   way for a Reserve-Without-Payment booking (no prior payment at all) to
   collect anything.

These tests cover the corrected like-for-like price comparison, the
default-to-original-payment-method behavior, staff's explicit override
capability (with mandatory reason + audit), the customer-always-Razorpay
restriction, and that zero-difference/refund/platform-fee/original-payment
integrity are all preserved.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from database import SessionLocal
from tests.test_bookings import (  # noqa: F401 (autouse fixtures)
    _bookable_setup, _create_walk_in, client, _auth, seed_reference_data,
    stub_booking_emails, _next_weekday_date, WEEKDAY,
)
import crud_payment
from models import Payment, Refund, BookingFinancial, AuditLog
from crud_service import get_branch_service_or_404


FAR_ENOUGH_DATE = _next_weekday_date(WEEKDAY) + timedelta(weeks=2)


@pytest.fixture(autouse=True)
def stub_razorpay(monkeypatch):
    monkeypatch.setattr(
        crud_payment.razorpay_service, "create_order",
        lambda amount, currency, receipt: {"id": f"order_fake_{receipt}"},
    )
    monkeypatch.setattr(
        crud_payment.razorpay_service, "create_payment_link",
        lambda amount, currency, **k: {"id": f"plink_fake_{amount}", "short_url": "https://rzp.io/fake"},
    )
    monkeypatch.setattr(crud_payment.razorpay_service, "verify_payment_signature", lambda *a, **k: True)
    monkeypatch.setattr(crud_payment.razorpay_service, "fetch_payment", lambda payment_id: {"status": "captured", "amount": 10**12})
    monkeypatch.setattr(crud_payment.razorpay_service, "to_paise", lambda amount: 10**12)
    monkeypatch.setattr(crud_payment.razorpay_service, "create_refund", lambda *a, **k: {"id": "rfnd_fake", "status": "processed"})


def _customer_token_for(setup):
    import uuid
    unique = uuid.uuid4().hex[:8]
    payload = {
        "first_name": "Cust", "last_name": "Omer", "email": f"resched_{unique}@example.com",
        "mobile_number": "9999999999", "password": "Testpass123!",
    }
    response = client.post("/api/v1/customers/register", json=payload)
    assert response.status_code == 200, response.text
    login = client.post("/api/v1/auth/login", data={"username": payload["email"], "password": "Testpass123!"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _create_coupon(setup, code="RESCHEDFIX", value="10"):
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


def _customer_full_payment_with_coupon(setup, customer_token, coupon_code, booking_date=FAR_ENOUGH_DATE, start_time="09:00:00"):
    checkout = client.post(
        "/api/v1/customer/checkout",
        json={
            "branch_service_id": setup["branch_service"]["id"], "booking_date": str(booking_date),
            "start_time": start_time, "payment_option": "Full", "coupon_code": coupon_code,
        },
        headers=_auth(customer_token),
    ).json()
    verify = client.post(
        f"/api/v1/customer/checkout/{checkout['hold_id']}/verify",
        json={"razorpay_payment_id": "pay_c1", "razorpay_signature": "sig_c1"},
        headers=_auth(customer_token),
    ).json()
    return verify["booking"]


def _staff_hold(setup, customer_id, **extra):
    payload = {
        "customer_id": customer_id, "branch_service_id": setup["branch_service"]["id"],
        "booking_date": str(FAR_ENOUGH_DATE), "start_time": "09:00:00", "payment_option": "Full",
    }
    payload.update(extra)
    response = client.post(f"/api/v1/branches/{setup['branch']['id']}/checkout/hold", json=payload, headers=_auth(setup["owner_token"]))
    assert response.status_code == 200, response.text
    return response.json()


def _staff_cash_booking(setup, customer_id, **hold_extra):
    hold = _staff_hold(setup, customer_id, **hold_extra)
    finalize = client.post(
        f"/api/v1/holds/{hold['hold_id']}/checkout/cash",
        json={"cash_received": hold["amount_due_now"]},
        headers=_auth(setup["owner_token"]),
    )
    assert finalize.status_code == 200, finalize.text
    return finalize.json()["booking"]


def _staff_external_booking(setup, customer_id, **hold_extra):
    hold = _staff_hold(setup, customer_id, **hold_extra)
    finalize = client.post(f"/api/v1/holds/{hold['hold_id']}/checkout/external", headers=_auth(setup["owner_token"]))
    assert finalize.status_code == 200, finalize.text
    confirm = client.post(f"/api/v1/holds/{hold['hold_id']}/confirm-external-payment", headers=_auth(setup["owner_token"]))
    assert confirm.status_code == 200, confirm.text
    return confirm.json()["booking"]


def _staff_rwp_booking(setup, customer_id, **extra):
    payload = {
        "customer_id": customer_id, "branch_service_id": setup["branch_service"]["id"],
        "booking_date": str(FAR_ENOUGH_DATE), "start_time": "09:00:00",
    }
    payload.update(extra)
    response = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/checkout/reserve-without-payment",
        json=payload, headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    return response.json()["booking"]


def _staff_reschedule(setup, booking_id, booking_date=None, start_time="10:00:00", reason="ops reschedule", **extra):
    payload = {"booking_date": str(booking_date or FAR_ENOUGH_DATE + timedelta(weeks=1)), "start_time": start_time, "reason": reason}
    payload.update(extra)
    return client.post(f"/api/v1/bookings/{booking_id}/reschedule", json=payload, headers=_auth(setup["owner_token"]))


def _fetch_financial(booking_id):
    db = SessionLocal()
    try:
        return db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking_id).first()
    finally:
        db.close()


def _bump_price(branch_service_id, delta: Decimal):
    db = SessionLocal()
    try:
        bs = get_branch_service_or_404(db, branch_service_id)
        bs.price = Decimal(bs.price) + delta
        db.commit()
    finally:
        db.close()


# -----------------------------
# PART 1 — like-for-like price-difference calculation
# -----------------------------

def test_1_coupon_booking_reschedule_to_unchanged_price_produces_zero_difference(monkeypatch):
    """The exact reported bug: ₹300 service + 10% coupon = ₹270 booking;
    reschedule to another slot at the SAME ₹300 catalog price must show
    ₹0 difference and must NEVER contact Razorpay."""
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    coupon = _create_coupon(setup, "ZERO1")
    booking = _staff_cash_booking(setup, customer["id"], payment_option="Deposit", coupon_code=coupon["code"])
    financial_before = _fetch_financial(booking["id"])
    assert Decimal(financial_before.total_amount) == Decimal("270.00")

    calls = {"create_order": 0}
    monkeypatch.setattr(crud_payment.razorpay_service, "create_order", lambda *a, **k: calls.__setitem__("create_order", calls["create_order"] + 1) or {"id": "should-not-be-called"})

    response = _staff_reschedule(setup, booking["id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["price_adjustment"] is None
    assert calls["create_order"] == 0

    financial_after = _fetch_financial(booking["id"])
    assert Decimal(financial_after.total_amount) == Decimal("270.00")
    assert Decimal(financial_after.amount_paid) == Decimal(financial_before.amount_paid)

    db = SessionLocal()
    try:
        assert db.query(Payment).filter(Payment.booking_id == booking["id"], Payment.payment_type == "RescheduleCollection").count() == 0
        assert db.query(Refund).filter(Refund.booking_id == booking["id"]).count() == 0
    finally:
        db.close()


def test_2_coupon_booking_genuine_price_increase_collects_only_genuine_difference(monkeypatch):
    """₹300 + 10% coupon = ₹270. Catalog price genuinely rises to ₹400 ->
    recomputing the SAME 10% coupon against ₹400 gives ₹360; the genuine
    difference collected must be ₹90 (360-270), NOT ₹130 (400-270)."""
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    coupon = _create_coupon(setup, "GENUP1")
    booking = _staff_cash_booking(setup, customer["id"], coupon_code=coupon["code"])
    _bump_price(booking["branch_service_id"], Decimal("100"))  # 300 -> 400

    response = _staff_reschedule(setup, booking["id"], payment_method="Cash", cash_received="90")
    assert response.status_code == 200, response.text
    adj = response.json()["price_adjustment"]
    assert adj["action"] == "CollectDifference"
    assert Decimal(adj["difference"]) == Decimal("90.00")
    assert Decimal(adj["amount_due"]) == Decimal("90.00")

    financial = _fetch_financial(booking["id"])
    assert Decimal(financial.total_amount) == Decimal("360.00")


def test_3_coupon_booking_genuine_price_decrease_refunds_only_genuine_decrease(monkeypatch):
    """₹300 + 10% coupon = ₹270 (Full, Cash). Catalog price genuinely
    drops to ₹200 -> recomputing the coupon gives ₹180; genuine decrease
    collected must be ₹90 (270-180), NOT ₹70 (270-200)."""
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    coupon = _create_coupon(setup, "GENDOWN1")
    booking = _staff_cash_booking(setup, customer["id"], coupon_code=coupon["code"])
    _bump_price(booking["branch_service_id"], Decimal("-100"))  # 300 -> 200

    response = _staff_reschedule(setup, booking["id"])
    assert response.status_code == 200, response.text
    adj = response.json()["price_adjustment"]
    assert adj["action"] == "RefundIssued"
    assert Decimal(adj["amount_refunded"]) == Decimal("90.00")

    financial = _fetch_financial(booking["id"])
    assert Decimal(financial.total_amount) == Decimal("180.00")

    db = SessionLocal()
    try:
        refund = db.query(Refund).filter(Refund.booking_id == booking["id"]).first()
        assert refund.refund_method == "Manual"
        assert Decimal(refund.final_amount) == Decimal("90.00")
    finally:
        db.close()


def test_4_booking_without_coupon_existing_behavior_unaffected():
    """No coupon: catalog price IS the booking's total_amount, so the
    like-for-like fix must produce the exact same result as before."""
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    booking = _staff_cash_booking(setup, customer["id"])
    _bump_price(booking["branch_service_id"], Decimal("500"))

    response = _staff_reschedule(setup, booking["id"], payment_method="Cash", cash_received="500")
    assert response.status_code == 200, response.text
    adj = response.json()["price_adjustment"]
    assert adj["action"] == "CollectDifference"
    assert Decimal(adj["difference"]) == Decimal("500.00")


def test_5_price_override_booking_no_false_difference():
    """A booking with a final_price_override must be compared like-for-like
    too — the override itself must not be mistaken for a false difference
    when the catalog price alone changes."""
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    # Catalog 300, final_price_override -> 250 (a manual discount, no coupon).
    booking = _staff_cash_booking(setup, customer["id"], final_price_override="250", price_override_reason="loyalty discount")
    financial_before = _fetch_financial(booking["id"])
    assert Decimal(financial_before.total_amount) == Decimal("250.00")

    # No genuine catalog price change at all.
    response = _staff_reschedule(setup, booking["id"])
    assert response.status_code == 200, response.text
    assert response.json()["price_adjustment"] is None


def test_6_coupon_plus_price_override_like_for_like():
    """Coupon AND a base_price_override together: reschedule to the SAME
    catalog price must still show zero difference."""
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    coupon = _create_coupon(setup, "COMBO1")
    # base_price_override 280 (instead of catalog 300), then 10% coupon -> 252.
    booking = _staff_cash_booking(
        setup, customer["id"], coupon_code=coupon["code"],
        base_price_override="280", price_override_reason="negotiated base",
    )
    financial = _fetch_financial(booking["id"])
    assert Decimal(financial.total_amount) == Decimal("252.00")

    response = _staff_reschedule(setup, booking["id"])
    assert response.status_code == 200, response.text
    assert response.json()["price_adjustment"] is None


def test_14_zero_difference_creates_no_payment_refund_or_attempt(monkeypatch):
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    coupon = _create_coupon(setup, "ZERO2")
    booking = _staff_cash_booking(setup, customer["id"], coupon_code=coupon["code"])

    calls = {"create_order": 0, "create_payment_link": 0}
    monkeypatch.setattr(crud_payment.razorpay_service, "create_order", lambda *a, **k: calls.__setitem__("create_order", 1) or {"id": "x"})
    monkeypatch.setattr(crud_payment.razorpay_service, "create_payment_link", lambda *a, **k: calls.__setitem__("create_payment_link", 1) or {"id": "x", "short_url": "x"})

    response = _staff_reschedule(setup, booking["id"])
    assert response.status_code == 200, response.text
    assert response.json()["price_adjustment"] is None
    assert calls == {"create_order": 0, "create_payment_link": 0}

    db = SessionLocal()
    try:
        assert db.query(Payment).filter(Payment.booking_id == booking["id"], Payment.payment_type == "RescheduleCollection").count() == 0
        assert db.query(Refund).filter(Refund.booking_id == booking["id"]).count() == 0
    finally:
        db.close()


# -----------------------------
# PART 2/3 — payment method default & override
# -----------------------------

def test_7_razorpay_paid_booking_genuine_increase_uses_razorpay():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    from tests.test_m8_cancellation_reschedule import _fully_paid_booking
    booking = _fully_paid_booking(setup, customer_token, booking_date=FAR_ENOUGH_DATE)
    _bump_price(booking["branch_service_id"], Decimal("500"))

    response = client.post(
        f"/api/v1/customer/bookings/{booking['id']}/reschedule",
        json={"booking_date": str(FAR_ENOUGH_DATE + timedelta(weeks=1)), "start_time": "10:00:00"},
        headers=_auth(customer_token),
    )
    assert response.status_code == 200, response.text
    adj = response.json()["price_adjustment"]
    assert adj["action"] == "CollectDifference"
    assert adj["payment_method"] == "RazorpayOnline"
    assert adj["razorpay_order_id"]

    verify = client.post(
        f"/api/v1/customer/bookings/{booking['id']}/pay-reschedule-difference/verify",
        json={"razorpay_payment_id": "pay_diff_1", "razorpay_signature": "sig_diff_1"},
        headers=_auth(customer_token),
    )
    assert verify.status_code == 200, verify.text


def test_8_razorpay_paid_booking_genuine_decrease_uses_razorpay_refund():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    from tests.test_m8_cancellation_reschedule import _fully_paid_booking
    booking = _fully_paid_booking(setup, customer_token, booking_date=FAR_ENOUGH_DATE)
    _bump_price(booking["branch_service_id"], Decimal("-100"))

    response = client.post(
        f"/api/v1/customer/bookings/{booking['id']}/reschedule",
        json={"booking_date": str(FAR_ENOUGH_DATE + timedelta(weeks=1)), "start_time": "10:00:00"},
        headers=_auth(customer_token),
    )
    assert response.status_code == 200, response.text
    adj = response.json()["price_adjustment"]
    assert adj["action"] == "RefundIssued"

    db = SessionLocal()
    try:
        refund = db.query(Refund).filter(Refund.booking_id == booking["id"]).first()
        assert refund.refund_method == "Gateway"
    finally:
        db.close()


def test_9_cash_booking_genuine_increase_defaults_to_cash():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    booking = _staff_cash_booking(setup, customer["id"])
    _bump_price(booking["branch_service_id"], Decimal("200"))

    response = _staff_reschedule(setup, booking["id"], cash_received="200")
    assert response.status_code == 200, response.text
    adj = response.json()["price_adjustment"]
    assert adj["default_payment_method"] == "Cash"
    assert adj["payment_method"] == "Cash"
    assert adj["action"] == "CollectDifference"
    assert Decimal(adj["change_returned"]) == Decimal("0.00")

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_id == booking["id"], Payment.payment_type == "RescheduleCollection").first()
        assert payment.method == "Cash"
        assert payment.status == "Captured"
        assert payment.platform_fee_amount is None
    finally:
        db.close()

    financial = _fetch_financial(booking["id"])
    assert Decimal(financial.amount_paid) == Decimal("500.00")  # 300 original + 200 diff


def test_10_cash_booking_genuine_decrease_defaults_to_cash_refund():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    booking = _staff_cash_booking(setup, customer["id"])
    _bump_price(booking["branch_service_id"], Decimal("-150"))

    response = _staff_reschedule(setup, booking["id"])
    assert response.status_code == 200, response.text
    adj = response.json()["price_adjustment"]
    assert adj["action"] == "RefundIssued"
    assert Decimal(adj["amount_refunded"]) == Decimal("150.00")

    db = SessionLocal()
    try:
        refund = db.query(Refund).filter(Refund.booking_id == booking["id"]).first()
        assert refund.refund_method == "Manual"
    finally:
        db.close()


def test_11_cash_booking_staff_overrides_to_email_payment_link():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"], email="walkin_override@example.com")
    booking = _staff_cash_booking(setup, customer["id"])
    _bump_price(booking["branch_service_id"], Decimal("120"))

    # No reason -> rejected.
    rejected = _staff_reschedule(setup, booking["id"], payment_method="EmailPaymentLink")
    assert rejected.status_code == 400, rejected.text

    response = _staff_reschedule(
        setup, booking["id"], payment_method="EmailPaymentLink", override_reason="customer not physically present",
    )
    assert response.status_code == 200, response.text
    adj = response.json()["price_adjustment"]
    assert adj["default_payment_method"] == "Cash"
    assert adj["payment_method"] == "EmailPaymentLink"
    assert adj["payment_link"]

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_id == booking["id"], Payment.payment_type == "RescheduleCollection").first()
        assert payment.method == "RazorpayOnline"  # storage convention, same as staff_finalize_email_link_hold
        assert payment.status == "Created"

        audit = (
            db.query(AuditLog)
            .filter(AuditLog.entity_type == "Booking", AuditLog.entity_id == booking["id"],
                    AuditLog.action == "RESCHEDULE_DIFFERENCE_PAYMENT_METHOD_OVERRIDDEN")
            .first()
        )
        assert audit is not None
        assert audit.previous_value == "Cash"
        assert audit.new_value == "EmailPaymentLink"
        assert audit.reason == "customer not physically present"
    finally:
        db.close()

    # Staff later confirms the link was paid.
    confirm = client.post(
        f"/api/v1/bookings/{booking['id']}/reschedule-difference/confirm-payment",
        headers=_auth(setup["owner_token"]),
    )
    assert confirm.status_code == 200, confirm.text
    financial = _fetch_financial(booking["id"])
    assert Decimal(financial.amount_paid) == Decimal("420.00")  # 300 + 120


def test_12_direct_external_booking_defaults_to_external_manual():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    booking = _staff_external_booking(setup, customer["id"])
    _bump_price(booking["branch_service_id"], Decimal("80"))

    response = _staff_reschedule(setup, booking["id"])
    assert response.status_code == 200, response.text
    adj = response.json()["price_adjustment"]
    assert adj["default_payment_method"] == "ExternalManual"
    assert adj["payment_method"] == "ExternalManual"
    assert adj["requires_manual_confirmation"] is True

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_id == booking["id"], Payment.payment_type == "RescheduleCollection").first()
        assert payment.method == "ExternalManual"
        assert payment.status == "Created"
    finally:
        db.close()

    confirm = client.post(
        f"/api/v1/bookings/{booking['id']}/reschedule-difference/confirm-payment",
        headers=_auth(setup["owner_token"]),
    )
    assert confirm.status_code == 200, confirm.text
    financial = _fetch_financial(booking["id"])
    assert Decimal(financial.amount_paid) == Decimal("380.00")  # 300 + 80


def test_13_reserve_without_payment_requires_staff_to_choose_method():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    booking = _staff_rwp_booking(setup, customer["id"])
    _bump_price(booking["branch_service_id"], Decimal("100"))

    no_method = _staff_reschedule(setup, booking["id"])
    assert no_method.status_code == 400, no_method.text

    response = _staff_reschedule(setup, booking["id"], payment_method="Cash", cash_received="100")
    assert response.status_code == 200, response.text
    adj = response.json()["price_adjustment"]
    assert adj["default_payment_method"] is None
    assert adj["payment_method"] == "Cash"


# -----------------------------
# PART 4/5 — ledger integrity, original payments untouched, platform fee
# -----------------------------

def test_15_original_payment_record_not_modified_by_increase():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    booking = _staff_cash_booking(setup, customer["id"])
    db = SessionLocal()
    try:
        original_payment = db.query(Payment).filter(Payment.booking_id == booking["id"]).first()
        original_id, original_amount, original_status = original_payment.id, Decimal(original_payment.amount), original_payment.status
    finally:
        db.close()

    _bump_price(booking["branch_service_id"], Decimal("60"))
    response = _staff_reschedule(setup, booking["id"], cash_received="60")
    assert response.status_code == 200, response.text

    db = SessionLocal()
    try:
        original_payment = db.query(Payment).filter(Payment.id == original_id).first()
        assert Decimal(original_payment.amount) == original_amount
        assert original_payment.status == original_status
        # A distinct NEW Payment row for the increment, not a mutation of the original.
        all_payments = db.query(Payment).filter(Payment.booking_id == booking["id"]).all()
        assert len(all_payments) == 2
    finally:
        db.close()


def test_16_amount_paid_and_due_correct_after_increase_decrease_and_no_change():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    booking = _staff_cash_booking(setup, customer["id"])  # total 300, paid 300

    # No change.
    r1 = _staff_reschedule(setup, booking["id"], start_time="10:00:00")
    assert r1.status_code == 200, r1.text
    f1 = _fetch_financial(booking["id"])
    assert Decimal(f1.total_amount) == Decimal("300.00")
    assert Decimal(f1.amount_paid) == Decimal("300.00")

    # Increase by 50.
    _bump_price(booking["branch_service_id"], Decimal("50"))
    r2 = _staff_reschedule(setup, booking["id"], start_time="11:00:00", cash_received="50")
    assert r2.status_code == 200, r2.text
    f2 = _fetch_financial(booking["id"])
    assert Decimal(f2.total_amount) == Decimal("350.00")
    assert Decimal(f2.amount_paid) == Decimal("350.00")

    # Decrease by 80.
    _bump_price(booking["branch_service_id"], Decimal("-80"))
    r3 = _staff_reschedule(setup, booking["id"], start_time="12:00:00")
    assert r3.status_code == 200, r3.text
    f3 = _fetch_financial(booking["id"])
    assert Decimal(f3.total_amount) == Decimal("270.00")
    assert Decimal(f3.amount_refunded) == Decimal("80.00")


def test_17_platform_fee_applied_on_online_increment_and_reversed_on_refund():
    from tests.test_m8_cancellation_reschedule import _set_platform_fee, _fully_paid_booking
    _set_platform_fee(Decimal("5"))
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    booking = _fully_paid_booking(setup, customer_token, booking_date=FAR_ENOUGH_DATE)
    _bump_price(booking["branch_service_id"], Decimal("100"))

    reschedule = client.post(
        f"/api/v1/customer/bookings/{booking['id']}/reschedule",
        json={"booking_date": str(FAR_ENOUGH_DATE + timedelta(weeks=1)), "start_time": "10:00:00"},
        headers=_auth(customer_token),
    )
    assert reschedule.status_code == 200, reschedule.text
    verify = client.post(
        f"/api/v1/customer/bookings/{booking['id']}/pay-reschedule-difference/verify",
        json={"razorpay_payment_id": "pay_diff_fee", "razorpay_signature": "sig_diff_fee"},
        headers=_auth(customer_token),
    )
    assert verify.status_code == 200, verify.text

    db = SessionLocal()
    try:
        diff_payment = db.query(Payment).filter(Payment.booking_id == booking["id"], Payment.payment_type == "RescheduleCollection").first()
        assert Decimal(diff_payment.platform_fee_amount) == Decimal("5.00")  # 5% of 100
    finally:
        db.close()


def test_17b_cash_increment_never_earns_platform_fee():
    from tests.test_m8_cancellation_reschedule import _set_platform_fee
    _set_platform_fee(Decimal("5"))
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    booking = _staff_cash_booking(setup, customer["id"])
    _bump_price(booking["branch_service_id"], Decimal("100"))

    response = _staff_reschedule(setup, booking["id"], cash_received="100")
    assert response.status_code == 200, response.text

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.booking_id == booking["id"], Payment.payment_type == "RescheduleCollection").first()
        assert payment.platform_fee_amount is None
    finally:
        db.close()


def test_18_override_without_reason_is_rejected():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"], email="noreason@example.com")
    booking = _staff_cash_booking(setup, customer["id"])
    _bump_price(booking["branch_service_id"], Decimal("40"))

    response = _staff_reschedule(setup, booking["id"], payment_method="EmailPaymentLink")
    assert response.status_code == 400, response.text

    db = SessionLocal()
    try:
        assert db.query(Payment).filter(Payment.booking_id == booking["id"], Payment.payment_type == "RescheduleCollection").count() == 0
    finally:
        db.close()


def test_19_customer_self_reschedule_cannot_override_payment_method():
    setup = _bookable_setup()
    customer_token = _customer_token_for(setup)
    from tests.test_m8_cancellation_reschedule import _fully_paid_booking
    booking = _fully_paid_booking(setup, customer_token, booking_date=FAR_ENOUGH_DATE)
    _bump_price(booking["branch_service_id"], Decimal("50"))

    response = client.post(
        f"/api/v1/customer/bookings/{booking['id']}/reschedule",
        json={
            "booking_date": str(FAR_ENOUGH_DATE + timedelta(weeks=1)), "start_time": "10:00:00",
            "payment_method": "Cash", "cash_received": "50",
        },
        headers=_auth(customer_token),
    )
    # BookingRescheduleRequest forbids unknown fields -> customers cannot even submit these.
    assert response.status_code == 422, response.text


# -----------------------------
# Frontend completion — read-only reschedule price-difference preview
# -----------------------------

def test_preview_zero_difference():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    coupon = _create_coupon(setup, "PREVIEWZERO")
    booking = _staff_cash_booking(setup, customer["id"], coupon_code=coupon["code"])

    response = client.get(f"/api/v1/bookings/{booking['id']}/reschedule-preview", headers=_auth(setup["owner_token"]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["action"] is None
    assert Decimal(body["difference"]) == Decimal("0.00")

    # Read-only: no Payment/Refund/schedule change from calling preview alone.
    db = SessionLocal()
    try:
        assert db.query(Payment).filter(Payment.booking_id == booking["id"], Payment.payment_type == "RescheduleCollection").count() == 0
    finally:
        db.close()


def test_preview_genuine_increase_shows_default_method_and_amount():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    booking = _staff_cash_booking(setup, customer["id"])
    _bump_price(booking["branch_service_id"], Decimal("70"))

    response = client.get(f"/api/v1/bookings/{booking['id']}/reschedule-preview", headers=_auth(setup["owner_token"]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["action"] == "CollectDifference"
    assert Decimal(body["amount_due"]) == Decimal("70.00")
    assert body["default_payment_method"] == "Cash"

    db = SessionLocal()
    try:
        assert db.query(Payment).filter(Payment.booking_id == booking["id"], Payment.payment_type == "RescheduleCollection").count() == 0
    finally:
        db.close()


def test_preview_genuine_decrease_shows_estimate_no_selector_fields():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    booking = _staff_cash_booking(setup, customer["id"])
    _bump_price(booking["branch_service_id"], Decimal("-40"))

    response = client.get(f"/api/v1/bookings/{booking['id']}/reschedule-preview", headers=_auth(setup["owner_token"]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["action"] == "RefundIssued"
    assert Decimal(body["amount_estimate"]) == Decimal("40.00")
    assert "default_payment_method" not in body


def test_preview_reserve_without_payment_has_no_default_method():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    booking = _staff_rwp_booking(setup, customer["id"])
    _bump_price(booking["branch_service_id"], Decimal("90"))

    response = client.get(f"/api/v1/bookings/{booking['id']}/reschedule-preview", headers=_auth(setup["owner_token"]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["action"] == "CollectDifference"
    assert body["default_payment_method"] is None


def test_preview_does_not_depend_on_target_date_or_time():
    """The preview endpoint takes no date/time parameter at all — the
    difference is driven only by the service's current price vs the
    booking's locked-in terms, confirmed by calling it repeatedly with no
    change in between and getting an identical result."""
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    booking = _staff_cash_booking(setup, customer["id"])
    _bump_price(booking["branch_service_id"], Decimal("25"))

    first = client.get(f"/api/v1/bookings/{booking['id']}/reschedule-preview", headers=_auth(setup["owner_token"]))
    second = client.get(f"/api/v1/bookings/{booking['id']}/reschedule-preview", headers=_auth(setup["owner_token"]))
    assert first.json() == second.json()
