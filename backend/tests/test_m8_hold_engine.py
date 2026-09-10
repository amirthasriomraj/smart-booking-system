"""
Milestone 8 Phase 2 — Availability & Hold Engine tests.

Reuses test_bookings.py's fixture helpers. SQLite (this suite's dialect)
cannot exercise the real advisory-lock concurrency guarantee — that is
verified separately against live PostgreSQL (see the Phase 2 completion
report). These tests prove the shared occupancy/overlap logic itself:
Hold<->Booking<->Hold mutual exclusion, buffer semantics preserved, and
expiry releasing the slot.
"""
from datetime import datetime, time, timedelta

import pytest
from fastapi import HTTPException

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
from models import Business, Branch, BranchService, BookingHold
import crud_hold


def _setup_with_customer():
    setup = _bookable_setup()
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])
    return setup, customer


def _acquire(db, setup, customer, start_time="09:00:00", hold_minutes=6):
    business = db.query(Business).filter(Business.id == setup["business_id"]).first()
    branch = db.query(Branch).filter(Branch.id == setup["branch"]["id"]).first()
    branch_service = db.query(BranchService).filter(BranchService.id == setup["branch_service"]["id"]).first()
    return crud_hold.acquire_hold(
        db,
        business=business,
        branch=branch,
        branch_service=branch_service,
        booking_date=BOOKING_DATE,
        start_time=time.fromisoformat(start_time),
        resource_id=None,
        customer_id=customer["id"],
        hold_type="CustomerCheckout",
        hold_minutes=hold_minutes,
        price_snapshot={"final_amount": "100.00"},
        created_by=business.owner_user_id,
    )


def test_active_hold_blocks_booking_for_same_slot():
    setup, customer = _setup_with_customer()
    db = SessionLocal()
    try:
        hold = _acquire(db, setup, customer)
        assert hold.status == "Active"
        assert hold.resource_id == setup["resource"]["id"]
    finally:
        db.close()

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
    assert response.status_code == 409, response.text


def test_booking_blocks_hold_for_same_slot():
    setup, customer = _setup_with_customer()
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

    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            _acquire(db, setup, customer)
        assert exc_info.value.status_code == 409
    finally:
        db.close()


def test_active_hold_blocks_another_hold_for_same_slot():
    setup, customer = _setup_with_customer()
    db = SessionLocal()
    try:
        _acquire(db, setup, customer)
        with pytest.raises(HTTPException) as exc_info:
            _acquire(db, setup, customer)
        assert exc_info.value.status_code == 409
    finally:
        db.close()


def test_buffer_minutes_enforced_against_active_hold():
    """Mirrors test_bookings.py::test_booking_buffer_minutes_blocks_adjacent_slot,
    but the pre-existing occupant is a Hold, not a Booking."""
    setup = _bookable_setup(booking_buffer_minutes=15)
    customer = _create_walk_in(setup["business_id"], setup["owner_token"])

    db = SessionLocal()
    try:
        # Hold: 09:00-09:30 (service duration 30). 15-minute buffer pads to 08:45-09:45.
        _acquire(db, setup, customer, start_time="09:00:00")
    finally:
        db.close()

    # 09:30 starts exactly when the hold's own interval ends, but is still
    # inside the padded 08:45-09:45 buffer window -> must be rejected.
    response = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"],
            "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE),
            "start_time": "09:30:00",
        },
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 409, response.text

    # 09:45 is exactly at the end of the padded buffer window -> must succeed.
    response = client.post(
        f"/api/v1/branches/{setup['branch']['id']}/bookings",
        json={
            "customer_id": customer["id"],
            "branch_service_id": setup["branch_service"]["id"],
            "booking_date": str(BOOKING_DATE),
            "start_time": "09:45:00",
        },
        headers=_auth(setup["owner_token"]),
    )
    assert response.status_code == 200, response.text


def test_expired_hold_no_longer_blocks_availability():
    setup, customer = _setup_with_customer()
    db = SessionLocal()
    try:
        hold = _acquire(db, setup, customer)
        # Simulate elapsed time without waiting or invoking the sweep task
        # (ID-046: an unswept-but-lapsed hold must stop occupying
        # immediately — see _existing_active_holds_for_resource_date).
        hold.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

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


def test_sweep_marks_expired_holds_and_is_idempotent():
    setup, customer = _setup_with_customer()
    db = SessionLocal()
    try:
        hold = _acquire(db, setup, customer)
        hold_id = hold.id
        hold.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()

        # >=1 rather than ==1: other tests in this session may also have left
        # expired-but-unswept holds behind (SQLite test.db is shared across
        # the whole test file/session, not reset per test) — this test only
        # asserts its own hold gets swept and that a second pass is a no-op.
        assert crud_hold.sweep_expired_holds(db) >= 1
        assert crud_hold.sweep_expired_holds(db) == 0  # idempotent: nothing left to sweep

        db.refresh(hold)
        assert hold.status == "Expired"
    finally:
        db.close()


def test_release_hold_is_idempotent():
    setup, customer = _setup_with_customer()
    db = SessionLocal()
    try:
        hold = _acquire(db, setup, customer)
        crud_hold.release_hold(db, hold, "Cancelled")
        assert hold.status == "Cancelled"
        # Calling again must not raise or flip an already-terminal status.
        crud_hold.release_hold(db, hold, "Expired")
        assert hold.status == "Cancelled"
    finally:
        db.close()
