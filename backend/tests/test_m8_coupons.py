"""Milestone 8 Phase 3 — Coupon engine tests (API-level CRUD/approval + direct
unit tests for the concurrency-safe validate_and_reserve_coupon check)."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from database import SessionLocal
from tests.test_bookings import (  # noqa: F401 (autouse fixtures)
    _bookable_setup,
    _create_branch,
    _create_walk_in,
    _invite_and_accept_staff,
    client,
    _auth,
    seed_reference_data,
    stub_booking_emails,
    BOOKING_DATE,
)
import crud_coupon
from models import BookingHold, Business


def _coupon_payload(**overrides):
    payload = {
        "code": "SAVE10",
        "discount_type": "Percentage",
        "discount_value": "10",
        "valid_from": str(date.today()),
        "valid_until": str(date.today() + timedelta(days=30)),
    }
    payload.update(overrides)
    return payload


def test_owner_can_create_business_wide_coupon():
    setup = _bookable_setup()
    response = client.post(
        f"/api/v1/businesses/{setup['business_id']}/coupons",
        json=_coupon_payload(),
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    coupon = response.json()
    assert coupon["branch_id"] is None
    assert coupon["approval_status"] is None
    assert coupon["status"] == "Active"


def test_owner_created_branch_coupon_is_auto_approved():
    setup = _bookable_setup()
    response = client.post(
        f"/api/v1/businesses/{setup['business_id']}/coupons",
        json=_coupon_payload(branch_id=setup["branch"]["id"]),
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["approval_status"] == "Approved"


def test_branch_manager_created_coupon_is_pending_until_owner_approves():
    setup = _bookable_setup()
    _, manager_token = _invite_and_accept_staff(
        setup["business_id"], setup["owner_token"], "BRANCH_MANAGER", branch_id=setup["branch"]["id"]
    )
    response = client.post(
        f"/api/v1/businesses/{setup['business_id']}/coupons",
        json=_coupon_payload(branch_id=setup["branch"]["id"]),
        headers=_auth(manager_token),
    )
    assert response.status_code == 200, response.text
    coupon = response.json()
    assert coupon["approval_status"] == "Pending"

    approve = client.post(
        f"/api/v1/coupons/{coupon['id']}/approve", json={}, headers=_auth(setup["owner_token"])
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["approval_status"] == "Approved"


def test_branch_manager_cannot_create_business_wide_coupon():
    setup = _bookable_setup()
    _, manager_token = _invite_and_accept_staff(
        setup["business_id"], setup["owner_token"], "BRANCH_MANAGER", branch_id=setup["branch"]["id"]
    )
    response = client.post(
        f"/api/v1/businesses/{setup['business_id']}/coupons",
        json=_coupon_payload(),  # branch_id omitted -> business-wide
        headers=_auth(manager_token),
    )
    assert response.status_code == 403, response.text


def test_branch_manager_cannot_manage_another_branch_coupon():
    setup = _bookable_setup()
    other_branch = _create_branch(setup["business_id"], setup["owner_token"])
    _, manager_token = _invite_and_accept_staff(
        setup["business_id"], setup["owner_token"], "BRANCH_MANAGER", branch_id=setup["branch"]["id"]
    )
    response = client.post(
        f"/api/v1/businesses/{setup['business_id']}/coupons",
        json=_coupon_payload(branch_id=other_branch["id"]),
        headers=_auth(manager_token),
    )
    assert response.status_code == 403, response.text


def test_duplicate_code_per_business_rejected():
    setup = _bookable_setup()
    first = client.post(
        f"/api/v1/businesses/{setup['business_id']}/coupons", json=_coupon_payload(),
        headers=_auth(setup["owner_token"]),
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"/api/v1/businesses/{setup['business_id']}/coupons", json=_coupon_payload(),
        headers=_auth(setup["owner_token"]),
    )
    assert second.status_code == 409, second.text


def test_status_toggle_inactive_active():
    setup = _bookable_setup()
    coupon = client.post(
        f"/api/v1/businesses/{setup['business_id']}/coupons", json=_coupon_payload(),
        headers=_auth(setup["owner_token"]),
    ).json()
    response = client.patch(
        f"/api/v1/coupons/{coupon['id']}/status", json={"status": "Inactive"}, headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "Inactive"


# -----------------------------
# validate_and_reserve_coupon (direct, DB-level condition + concurrency tests)
# -----------------------------

def _create_active_business_wide_coupon(setup, **overrides):
    payload = _coupon_payload(**overrides)
    response = client.post(
        f"/api/v1/businesses/{setup['business_id']}/coupons", json=payload, headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_validate_rejects_inactive_coupon():
    setup = _bookable_setup()
    coupon = _create_active_business_wide_coupon(setup)
    client.patch(f"/api/v1/coupons/{coupon['id']}/status", json={"status": "Inactive"}, headers=_auth(setup["owner_token"]))

    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            crud_coupon.validate_and_reserve_coupon(
                db, coupon["code"], setup["business_id"], setup["branch"]["id"],
                setup["branch_service"]["id"], customer_id=1, booking_amount=Decimal("1000"), booking_date=BOOKING_DATE,
            )
        assert exc_info.value.status_code == 409
    finally:
        db.close()


def test_validate_rejects_wrong_branch():
    setup = _bookable_setup()
    coupon = _create_active_business_wide_coupon(setup, branch_id=setup["branch"]["id"])

    other_branch = _create_branch(setup["business_id"], setup["owner_token"])

    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            crud_coupon.validate_and_reserve_coupon(
                db, coupon["code"], setup["business_id"], other_branch["id"],
                setup["branch_service"]["id"], customer_id=1, booking_amount=Decimal("1000"), booking_date=BOOKING_DATE,
            )
        assert exc_info.value.status_code == 409
    finally:
        db.close()


def test_validate_rejects_below_min_booking_amount():
    setup = _bookable_setup()
    coupon = _create_active_business_wide_coupon(setup, min_booking_amount="500")

    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            crud_coupon.validate_and_reserve_coupon(
                db, coupon["code"], setup["business_id"], setup["branch"]["id"],
                setup["branch_service"]["id"], customer_id=1, booking_amount=Decimal("100"), booking_date=BOOKING_DATE,
            )
        assert exc_info.value.status_code == 409
    finally:
        db.close()


def test_validate_rejects_wrong_weekday():
    setup = _bookable_setup()
    other_weekday = (BOOKING_DATE.weekday() + 1) % 7
    coupon = _create_active_business_wide_coupon(setup, applicable_weekdays=[other_weekday])

    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            crud_coupon.validate_and_reserve_coupon(
                db, coupon["code"], setup["business_id"], setup["branch"]["id"],
                setup["branch_service"]["id"], customer_id=1, booking_amount=Decimal("1000"), booking_date=BOOKING_DATE,
            )
        assert exc_info.value.status_code == 409
    finally:
        db.close()


def test_validate_rejects_wrong_service():
    setup = _bookable_setup()
    # Coupon scoped to the existing branch_service only; validating against
    # any other service id must be rejected.
    coupon = _create_active_business_wide_coupon(setup, branch_service_ids=[setup["branch_service"]["id"]])

    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            crud_coupon.validate_and_reserve_coupon(
                db, coupon["code"], setup["business_id"], setup["branch"]["id"],
                branch_service_id=999999, customer_id=1, booking_amount=Decimal("1000"), booking_date=BOOKING_DATE,
            )
        assert exc_info.value.status_code == 409
    finally:
        db.close()


def test_validate_enforces_total_usage_limit_counting_active_holds():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    coupon = _create_active_business_wide_coupon(setup, total_usage_limit=1)

    db = SessionLocal()
    try:
        coupon_row = crud_coupon.get_coupon_or_404(db, coupon["id"])
        business = db.query(Business).filter(Business.id == setup["business_id"]).first()

        # Simulate an in-progress checkout hold reserving the coupon's only unit of capacity.
        db.add(BookingHold(
            business_id=setup["business_id"], branch_id=setup["branch"]["id"],
            branch_service_id=setup["branch_service"]["id"], resource_id=setup["resource"]["id"],
            customer_id=customer["id"], booking_date=BOOKING_DATE, start_time=time(9, 0), end_time=time(9, 30),
            hold_type="CustomerCheckout", status="Active",
            expires_at=datetime.utcnow() + timedelta(minutes=6),
            price_snapshot={"coupon_id": coupon_row.id}, created_by=business.owner_user_id,
        ))
        db.commit()

        second_customer = _create_walk_in(setup["business_id"], setup["owner_token"])
        with pytest.raises(HTTPException) as exc_info:
            crud_coupon.validate_and_reserve_coupon(
                db, coupon["code"], setup["business_id"], setup["branch"]["id"],
                setup["branch_service"]["id"], customer_id=second_customer["id"],
                booking_amount=Decimal("1000"), booking_date=BOOKING_DATE,
            )
        assert exc_info.value.status_code == 409
    finally:
        db.close()


def test_validate_enforces_per_customer_usage_limit():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    coupon = _create_active_business_wide_coupon(setup, per_customer_usage_limit=1)

    db = SessionLocal()
    try:
        coupon_row = crud_coupon.get_coupon_or_404(db, coupon["id"])
        # A real booking is needed as the FK target for CouponRedemption.
        booking_resp = client.post(
            f"/api/v1/branches/{setup['branch']['id']}/bookings",
            json={
                "customer_id": customer["id"], "branch_service_id": setup["branch_service"]["id"],
                "booking_date": str(BOOKING_DATE), "start_time": "09:00:00",
            },
            headers=_auth(setup["owner_token"]),
        )
        assert booking_resp.status_code == 200, booking_resp.text
        booking = booking_resp.json()

        crud_coupon.redeem_coupon(
            db, coupon_row, booking["id"], customer["id"], Decimal("100"), performed_by=booking["created_by"]
        )
        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            crud_coupon.validate_and_reserve_coupon(
                db, coupon["code"], setup["business_id"], setup["branch"]["id"],
                setup["branch_service"]["id"], customer_id=customer["id"],
                booking_amount=Decimal("1000"), booking_date=BOOKING_DATE,
            )
        assert exc_info.value.status_code == 409
    finally:
        db.close()


def test_validate_succeeds_for_eligible_coupon():
    setup = _bookable_setup()
    coupon = _create_active_business_wide_coupon(setup)

    db = SessionLocal()
    try:
        result = crud_coupon.validate_and_reserve_coupon(
            db, coupon["code"], setup["business_id"], setup["branch"]["id"],
            setup["branch_service"]["id"], customer_id=1, booking_amount=Decimal("1000"), booking_date=BOOKING_DATE,
        )
        assert result.code == coupon["code"]
    finally:
        db.close()
