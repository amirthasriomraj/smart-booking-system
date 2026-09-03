"""
Milestone 8 Phase 1B — model/constraint sanity tests.

Scope is deliberately narrow: Phase 1B is schema only (no business-flow
code exists yet), so these tests only prove the new SQLAlchemy models and
their SQLite-representable constraints behave as designed. They reuse the
existing `_bookable_setup`/`_create_walk_in` fixture helpers from
test_bookings.py to get a real, valid `Booking` row rather than
hand-assembling one.

The PostgreSQL-only GiST exclusion constraints (bookings/booking_holds true
interval overlap) and the PlatformFeeSetting default-row partial index's
production behavior were verified separately against a real PostgreSQL
database during Phase 1B (see the completion report) — per instruction,
this SQLite-based suite is not relied on to prove those two things, even
though the default-row index happens to also be enforced on SQLite (tested
below as a bonus, not as the primary proof).
"""
from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from tests.test_bookings import (  # noqa: F401 (seed_reference_data/stub_booking_emails are autouse fixtures)
    _bookable_setup,
    _create_walk_in,
    client,
    _auth,
    seed_reference_data,
    stub_booking_emails,
    BOOKING_DATE,
)
from models import (
    User,
    Business,
    BookingFinancial,
    BookingHold,
    Coupon,
    CouponRedemption,
    PlatformFeeSetting,
    RazorpayWebhookEvent,
)


def _make_confirmed_booking():
    """Real Booking row via the existing M7 API, for FK-correct M8 fixtures."""
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    response = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"],
            "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE),
            "start_time": "09:00:00",
        },
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    return response.json(), setup, customer


def _owner_user_id(db, business_id):
    return db.query(Business).filter(Business.id == business_id).first().owner_user_id


def test_booking_financial_is_one_to_one_with_booking():
    booking, _, _ = _make_confirmed_booking()
    db = SessionLocal()
    try:
        db.add(
            BookingFinancial(
                booking_id=booking["id"],
                business_id=booking["business_id"],
                branch_id=booking["branch_id"],
                total_amount=100,
                base_price=100,
                financial_status="FullyPaid",
            )
        )
        db.commit()

        db.add(
            BookingFinancial(
                booking_id=booking["id"],
                business_id=booking["business_id"],
                branch_id=booking["branch_id"],
                total_amount=100,
                base_price=100,
                financial_status="FullyPaid",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_booking_hold_requires_customer_id():
    booking, setup, customer = _make_confirmed_booking()
    db = SessionLocal()
    try:
        owner_id = _owner_user_id(db, setup["business_id"])
        db.add(
            BookingHold(
                business_id=setup["business_id"],
                branch_id=setup["branch"]["id"],
                branch_service_id=setup["branch_service"]["id"],
                resource_id=setup["resource"]["id"],
                customer_id=None,
                booking_date=date.today() + timedelta(days=14),
                start_time=time(10, 0),
                end_time=time(10, 30),
                hold_type="CustomerCheckout",
                expires_at=datetime.utcnow() + timedelta(minutes=6),
                price_snapshot={},
                created_by=owner_id,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_coupon_code_unique_per_business():
    _, setup, _ = _make_confirmed_booking()
    db = SessionLocal()
    try:
        owner_id = _owner_user_id(db, setup["business_id"])
        kwargs = dict(
            business_id=setup["business_id"],
            code="SAVE10",
            discount_type="Percentage",
            discount_value=10,
            valid_from=date.today(),
            valid_until=date.today() + timedelta(days=30),
            created_by=owner_id,
        )
        db.add(Coupon(**kwargs))
        db.commit()

        db.add(Coupon(**kwargs))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_coupon_redemption_unique_per_coupon_and_booking():
    booking, setup, customer = _make_confirmed_booking()
    db = SessionLocal()
    try:
        owner_id = _owner_user_id(db, setup["business_id"])
        coupon = Coupon(
            business_id=setup["business_id"],
            code="ONCE",
            discount_type="Fixed",
            discount_value=50,
            valid_from=date.today(),
            valid_until=date.today() + timedelta(days=30),
            created_by=owner_id,
        )
        db.add(coupon)
        db.commit()

        redemption_kwargs = dict(
            business_id=setup["business_id"],
            coupon_id=coupon.id,
            booking_id=booking["id"],
            customer_id=customer["id"],
            discount_applied_amount=50,
        )
        db.add(CouponRedemption(**redemption_kwargs))
        db.commit()

        db.add(CouponRedemption(**redemption_kwargs))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_platform_fee_setting_default_row_is_singleton():
    """Bonus coverage: this same partial-index design is authoritatively
    verified against PostgreSQL separately (see Phase 1B report); SQLite
    happens to enforce it identically, so it is also exercised here."""
    db = SessionLocal()
    try:
        existing = db.query(PlatformFeeSetting).filter(PlatformFeeSetting.business_id.is_(None)).first()
        if existing:
            pytest.skip("a platform-default row already exists from another test/session")

        owner = db.query(User).first()
        db.add(PlatformFeeSetting(business_id=None, fee_percentage=5, updated_by=owner.id))
        db.commit()

        db.add(PlatformFeeSetting(business_id=None, fee_percentage=7, updated_by=owner.id))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_razorpay_webhook_event_id_is_unique():
    db = SessionLocal()
    try:
        db.add(RazorpayWebhookEvent(provider_event_id="evt_dup_1", event_type="payment.captured", payload={}))
        db.commit()

        db.add(RazorpayWebhookEvent(provider_event_id="evt_dup_1", event_type="payment.captured", payload={}))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()
