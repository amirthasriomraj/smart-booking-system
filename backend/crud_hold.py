"""
Milestone 8 Phase 2 — Availability & Hold Engine (ID-046, ID-056).

`BookingHold` is a separate, database-authoritative domain concept from
`Booking` (ID-046) — never a provisional `Confirmed` booking. Acquisition
reuses `crud_booking`'s existing resource-assignment/overlap/buffer engine
(`_resolve_resource_for_booking`, `_resource_is_free`) so a hold occupies
exactly the same availability space a Booking does, under the same
`_acquire_resource_lock` concurrency guarantee — there is one authoritative
overlap engine in this codebase, not two.

Reserve Without Payment never calls anything in this module (ID-046
correction): it goes straight to a normal `Booking` with no hold and no
expiry.
"""
from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import Business, Branch, BranchService, BookingHold
from audit import write_audit
import crud_booking


def get_hold_or_404(db: Session, hold_id: int) -> BookingHold:
    hold = db.query(BookingHold).filter(BookingHold.id == hold_id).first()
    if not hold:
        raise HTTPException(status_code=404, detail="Hold not found")
    return hold


def acquire_hold(
    db: Session,
    business: Business,
    branch: Branch,
    branch_service: BranchService,
    booking_date: date,
    start_time: time,
    resource_id: Optional[int],
    customer_id: int,
    hold_type: str,
    hold_minutes: int,
    price_snapshot: dict,
    created_by: int,
) -> BookingHold:
    """
    Concurrency-safe hold acquisition (ID-046/ID-056). `customer_id` is
    always required (a `BusinessCustomer.id`) — every M8 checkout flow
    resolves/creates the customer before acquiring a hold, exactly like
    `create_staff_booking`/`create_customer_booking` already require a
    resolved customer before creating a Booking; there is no flow where a
    hold's customer is genuinely unknown.

    Re-validates the same bookable-state gates `create_staff_booking`/
    `create_customer_booking` use (business Active, branch Approved+Active,
    service Approved) before resolving a resource, so a hold can never be
    acquired for a slot that could not also become a real Booking.
    """
    crud_booking._check_bookable_state(business, branch, branch_service)

    duration_minutes = branch_service.duration
    resource = crud_booking._resolve_resource_for_booking(
        db, branch_service, booking_date, start_time, duration_minutes, resource_id
    )

    hold = BookingHold(
        business_id=business.id,
        branch_id=branch.id,
        branch_service_id=branch_service.id,
        resource_id=resource.id,
        customer_id=customer_id,
        booking_date=booking_date,
        start_time=start_time,
        end_time=crud_booking._minutes_to_time(crud_booking._minutes(start_time) + duration_minutes),
        hold_type=hold_type,
        status="Active",
        expires_at=datetime.utcnow() + timedelta(minutes=hold_minutes),
        price_snapshot=price_snapshot,
        created_by=created_by,
    )
    db.add(hold)
    db.flush()

    write_audit(
        db,
        business_id=business.id,
        entity_type="BookingHold",
        entity_id=hold.id,
        action="HOLD_CREATED",
        performed_by=created_by,
        new_value=f"resource_id={resource.id} expires_at={hold.expires_at.isoformat()}",
        commit=False,
    )

    db.commit()
    db.refresh(hold)
    return hold


def release_hold(db: Session, hold: BookingHold, status: str, performed_by: Optional[int] = None) -> BookingHold:
    """Explicit release (staff/customer aborts checkout). `status` is
    'Cancelled' for an explicit abort or 'Expired' for the sweep (see
    `sweep_expired_holds`). A no-op if the hold is already non-Active —
    idempotent, safe to call more than once (ID-056)."""
    if hold.status != "Active":
        return hold

    hold.status = status
    write_audit(
        db,
        business_id=hold.business_id,
        entity_type="BookingHold",
        entity_id=hold.id,
        action="HOLD_RELEASED",
        performed_by=performed_by,
        new_value=f"status={status}",
        commit=False,
    )
    db.commit()
    db.refresh(hold)
    return hold


def sweep_expired_holds(db: Session) -> int:
    """
    Idempotent expiry sweep (ID-049/ID-056): flips every Active hold past
    its `expires_at` to Expired. Safe to run repeatedly/concurrently — a
    hold already moved to Expired by a prior run (or already Completed by a
    finalized checkout) is simply not matched again. This is the function
    the Milestone 8 Phase 7 Celery Beat task calls; no schedule is wired up
    yet in this phase.

    Note: a hold past `expires_at` already stops occupying availability
    the moment it lapses (`_existing_active_holds_for_resource_date` checks
    `expires_at > now()` directly), regardless of how often this sweep
    runs — this function's job is only to keep `status` accurate for
    reporting/audit, not to enforce availability.
    """
    expired = (
        db.query(BookingHold)
        .filter(BookingHold.status == "Active", BookingHold.expires_at <= datetime.utcnow())
        .all()
    )
    for hold in expired:
        hold.status = "Expired"
    db.commit()
    return len(expired)
