import json
from datetime import datetime, date, time
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import (
    User,
    UserProfile,
    Business,
    BusinessMember,
    Role,
    Branch,
    BranchAssignment,
    Resource,
    ResourceWorkingHours,
    ServiceTemplate,
    BranchService,
    BranchServiceResourceCategory,
    PlatformCustomer,
    BusinessCustomer,
    Booking,
    BookingHistory,
)
from audit import write_audit
from crud_branch import get_branch_by_id
from crud_service import get_branch_service_or_404
from crud_resource import get_resource_or_404
import crud_customer

# ID-038: technical default (not a frozen PRD business rule) — the step
# interval the Availability Engine uses to generate candidate start times.
SLOT_GRANULARITY_MINUTES = 15

BOOKABLE_STATUSES = ("Confirmed", "Completed")  # occupy the resource; Cancelled releases it (PRD §20)


# -------------------------
# LOOKUP HELPERS
# -------------------------

def _get_business_or_404(db: Session, business_id: int) -> Business:
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


def get_booking_or_404(db: Session, booking_id: int) -> Booking:
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


def _get_business_customer_or_404(db: Session, business_customer_id: int) -> BusinessCustomer:
    bc = db.query(BusinessCustomer).filter(BusinessCustomer.id == business_customer_id).first()
    if not bc:
        raise HTTPException(status_code=404, detail="Customer not found")
    return bc


# -------------------------
# AUTHORIZATION HELPERS (same pattern as crud_resource.py / crud_service.py)
# -------------------------

def _has_active_role(db: Session, business_id: int, user_id: int, role_code: str) -> bool:
    return (
        db.query(BusinessMember)
        .join(Role, BusinessMember.role_id == Role.id)
        .filter(
            BusinessMember.business_id == business_id,
            BusinessMember.user_id == user_id,
            BusinessMember.status == "Active",
            Role.code == role_code,
        )
        .first()
        is not None
    )


def _get_manager_current_branch_id(db: Session, business_id: int, user_id: int) -> Optional[int]:
    member = (
        db.query(BusinessMember)
        .join(Role, BusinessMember.role_id == Role.id)
        .filter(
            BusinessMember.business_id == business_id,
            BusinessMember.user_id == user_id,
            BusinessMember.status == "Active",
            Role.code == "BRANCH_MANAGER",
        )
        .first()
    )
    if not member:
        return None
    assignment = (
        db.query(BranchAssignment)
        .filter(BranchAssignment.business_member_id == member.id, BranchAssignment.is_current == True)  # noqa: E712
        .first()
    )
    return assignment.branch_id if assignment else None


def _require_branch_booking_staff_access(db: Session, branch: Branch, current_user: User) -> Business:
    """
    Booking creation/list/reschedule/cancel/reassign/complete: Business Owner
    (business-wide) or Branch Manager restricted to their currently assigned
    branch (PRD §18.4, §21; HR User and Resource User are not named anywhere
    in the PRD's booking sections and are not authorized booking actors).
    """
    business = _get_business_or_404(db, branch.business_id)
    if _has_active_role(db, business.id, current_user.id, "BUSINESS_OWNER"):
        return business
    if _get_manager_current_branch_id(db, business.id, current_user.id) == branch.id:
        return business
    raise HTTPException(status_code=403, detail="Not authorized to manage bookings for this branch")


def _require_business_wide_booking_read_access(db: Session, business_id: int, current_user: User) -> Business:
    """Business-wide booking listing: Business Owner only (mirrors crud_service's business-wide read pattern)."""
    business = _get_business_or_404(db, business_id)
    if not _has_active_role(db, business_id, current_user.id, "BUSINESS_OWNER"):
        raise HTTPException(status_code=403, detail="Not authorized to view bookings for this business")
    return business


def _require_owning_customer(db: Session, booking: Booking, current_user: User) -> None:
    platform_customer = crud_customer._require_customer_self(db, current_user)
    business_customer = db.query(BusinessCustomer).filter(BusinessCustomer.id == booking.customer_id).first()
    if not business_customer or business_customer.platform_customer_id != platform_customer.id:
        raise HTTPException(status_code=403, detail="Not authorized to manage this booking")


# -------------------------
# BOOKING VALIDATION GATES (PRD §16.3, §18.4, §24, BR-042-BR-044)
# -------------------------

def _check_bookable_state(business: Business, branch: Branch, branch_service: BranchService) -> None:
    if business.status != "Active":
        raise HTTPException(status_code=409, detail="Business is not Active")
    if branch.approval_status != "Approved" or not branch.is_active:
        # ID-001: Bookings are allowed only when the Branch satisfies both
        # the approval and operational-state rules.
        raise HTTPException(status_code=409, detail="Branch is not Approved and Active")
    if branch_service.status != "Approved":  # ID-020: Approved is itself the bookable state
        raise HTTPException(status_code=409, detail="Service is not Approved")


def _eligible_resource_ids(db: Session, branch_service: BranchService) -> List[int]:
    """Active resources, in this branch, whose category is allowed for the service."""
    category_ids = [
        row.resource_category_id
        for row in db.query(BranchServiceResourceCategory)
        .filter(BranchServiceResourceCategory.branch_service_id == branch_service.id)
        .all()
    ]
    if not category_ids:
        return []
    return [
        r.id
        for r in db.query(Resource)
        .filter(
            Resource.branch_id == branch_service.branch_id,
            Resource.status == "Active",
            Resource.resource_category_id.in_(category_ids),
        )
        .order_by(Resource.id)
        .all()
    ]


# -------------------------
# TIME ARITHMETIC
# -------------------------

def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _minutes_to_time(m: int) -> time:
    return time(hour=(m // 60) % 24, minute=m % 60)


def _overlaps_with_buffer(candidate_start: int, candidate_end: int, existing_start: int, existing_end: int, buffer_minutes: int) -> bool:
    padded_start = existing_start - buffer_minutes
    padded_end = existing_end + buffer_minutes
    return candidate_start < padded_end and padded_start < candidate_end


def _resource_working_window(db: Session, resource_id: int, weekday: int):
    row = (
        db.query(ResourceWorkingHours)
        .filter(ResourceWorkingHours.resource_id == resource_id, ResourceWorkingHours.weekday == weekday)
        .first()
    )
    if not row or row.is_closed or row.opening_time is None or row.closing_time is None:
        return None
    return row.opening_time, row.closing_time, row.break_start_time, row.break_end_time


def _existing_bookings_for_resource_date(
    db: Session, resource_id: int, booking_date: date, exclude_booking_id: Optional[int] = None
) -> List[Booking]:
    query = db.query(Booking).filter(
        Booking.resource_id == resource_id,
        Booking.booking_date == booking_date,
        Booking.status.in_(BOOKABLE_STATUSES),
    )
    if exclude_booking_id is not None:
        query = query.filter(Booking.id != exclude_booking_id)
    return query.all()


def _resource_bookings_count_for_date(
    db: Session, resource_id: int, booking_date: date, exclude_booking_id: Optional[int] = None
) -> int:
    query = db.query(Booking).filter(
        Booking.resource_id == resource_id,
        Booking.booking_date == booking_date,
        Booking.status.in_(BOOKABLE_STATUSES),
    )
    if exclude_booking_id is not None:
        query = query.filter(Booking.id != exclude_booking_id)
    return query.count()


def _resource_is_free(
    db: Session,
    resource: Resource,
    booking_date: date,
    start_time: time,
    duration_minutes: int,
    exclude_booking_id: Optional[int] = None,
) -> bool:
    """
    Working hours + break window + buffer-padded overlap + daily cap
    (ID-013's stored Resource attributes, enforced here per ID-013/ID-037).
    """
    window = _resource_working_window(db, resource.id, booking_date.weekday())
    if window is None:
        return False
    opening, closing, break_start, break_end = window

    start_m = _minutes(start_time)
    end_m = start_m + duration_minutes
    if start_m < _minutes(opening) or end_m > _minutes(closing):
        return False

    if break_start is not None and break_end is not None:
        if start_m < _minutes(break_end) and _minutes(break_start) < end_m:
            return False

    if resource.max_bookings_per_day is not None:
        if _resource_bookings_count_for_date(db, resource.id, booking_date, exclude_booking_id) >= resource.max_bookings_per_day:
            return False

    buffer_minutes = resource.booking_buffer_minutes or 0
    for existing in _existing_bookings_for_resource_date(db, resource.id, booking_date, exclude_booking_id):
        if _overlaps_with_buffer(start_m, end_m, _minutes(existing.start_time), _minutes(existing.end_time), buffer_minutes):
            return False

    return True


def _resource_free_slots(db: Session, resource: Resource, booking_date: date, duration_minutes: int) -> List[Tuple[time, time]]:
    window = _resource_working_window(db, resource.id, booking_date.weekday())
    if window is None:
        return []
    opening, closing, _break_start, _break_end = window

    open_m, close_m = _minutes(opening), _minutes(closing)
    slots: List[Tuple[time, time]] = []
    cursor = open_m
    while cursor + duration_minutes <= close_m:
        start_t = _minutes_to_time(cursor)
        if _resource_is_free(db, resource, booking_date, start_t, duration_minutes):
            slots.append((start_t, _minutes_to_time(cursor + duration_minutes)))
        cursor += SLOT_GRANULARITY_MINUTES
    return slots


# -------------------------
# AVAILABILITY ENGINE (PRD §14.6, §16.3; TAS Part 4 §3)
# Read-only: never creates a booking. Reusable by both the staff and
# customer booking flows via the two router wrappers.
# -------------------------

def compute_availability(
    db: Session, branch_id: int, branch_service_id: int, target_date: date, resource_id: Optional[int] = None
) -> dict:
    branch_service = get_branch_service_or_404(db, branch_service_id)
    if branch_service.branch_id != branch_id:
        raise HTTPException(status_code=400, detail="Service does not belong to this branch")

    branch = get_branch_by_id(db, branch_id)
    business = _get_business_or_404(db, branch.business_id)
    _check_bookable_state(business, branch, branch_service)

    eligible_ids = _eligible_resource_ids(db, branch_service)
    if resource_id is not None:
        if resource_id not in eligible_ids:
            raise HTTPException(status_code=400, detail="Resource is not eligible for this service")
        eligible_ids = [resource_id]

    resources = db.query(Resource).filter(Resource.id.in_(eligible_ids)).all() if eligible_ids else []

    slot_map = {}
    for resource in resources:
        for start_t, end_t in _resource_free_slots(db, resource, target_date, branch_service.duration):
            slot_map.setdefault((start_t, end_t), set()).add(resource.id)

    slots = [
        {"start_time": start_t, "end_time": end_t, "available_resource_ids": sorted(ids)}
        for (start_t, end_t), ids in sorted(slot_map.items())
    ]

    return {"branch_id": branch_id, "branch_service_id": branch_service_id, "date": target_date, "slots": slots}


# -------------------------
# RESOURCE ASSIGNMENT ENGINE (PRD §21; TAS Part 4 §4; ID-039)
# -------------------------

def _resolve_resource_for_booking(
    db: Session,
    branch_service: BranchService,
    booking_date: date,
    start_time: time,
    duration_minutes: int,
    resource_id: Optional[int],
    exclude_booking_id: Optional[int] = None,
) -> Resource:
    eligible_ids = _eligible_resource_ids(db, branch_service)
    if not eligible_ids:
        raise HTTPException(status_code=409, detail="No eligible resources are configured for this service")

    if resource_id is not None:
        # Manual assignment (ID-039): caller explicitly chose a resource.
        if resource_id not in eligible_ids:
            raise HTTPException(status_code=400, detail="Resource is not eligible for this service")
        resource = get_resource_or_404(db, resource_id)
        if not _resource_is_free(db, resource, booking_date, start_time, duration_minutes, exclude_booking_id):
            raise HTTPException(status_code=409, detail="Resource is not available at the requested time")
        return resource

    # Automatic "First Available" (ID-039, TAS Part 4 §4 — V1's only algorithm).
    for candidate_id in eligible_ids:
        candidate = get_resource_or_404(db, candidate_id)
        if _resource_is_free(db, candidate, booking_date, start_time, duration_minutes, exclude_booking_id):
            return candidate
    raise HTTPException(status_code=409, detail="No resource is available at the requested time")


# -------------------------
# BOOKING HISTORY (PRD §22; TAS Part 3 §9)
# -------------------------

def _booking_state_snapshot(booking: Booking) -> dict:
    return {
        "booking_date": booking.booking_date.isoformat(),
        "start_time": booking.start_time.isoformat(),
        "end_time": booking.end_time.isoformat(),
        "resource_id": booking.resource_id,
        "status": booking.status,
    }


def _write_booking_history(
    db: Session, booking: Booking, action: str, previous_state: Optional[dict], new_state: Optional[dict], performed_by: int
) -> None:
    db.add(
        BookingHistory(
            booking_id=booking.id,
            action=action,
            previous_state=previous_state,
            new_state=new_state,
            performed_by=performed_by,
        )
    )


def _state_to_audit_string(state: Optional[dict]) -> Optional[str]:
    return json.dumps(state) if state is not None else None


def get_booking_history(db: Session, booking_id: int, current_user: User) -> List[BookingHistory]:
    booking = get_booking_or_404(db, booking_id)
    branch = get_branch_by_id(db, booking.branch_id)
    _require_branch_booking_staff_access(db, branch, current_user)
    return (
        db.query(BookingHistory)
        .filter(BookingHistory.booking_id == booking_id)
        .order_by(BookingHistory.performed_at)
        .all()
    )


# -------------------------
# BOOKING CREATION (PRD §18.4; BR-042-BR-044)
# -------------------------

def create_staff_booking(db: Session, branch_id: int, payload, current_user: User) -> Booking:
    branch = get_branch_by_id(db, branch_id)
    business = _require_branch_booking_staff_access(db, branch, current_user)

    branch_service = get_branch_service_or_404(db, payload.branch_service_id)
    if branch_service.branch_id != branch.id:
        raise HTTPException(status_code=400, detail="Service does not belong to this branch")
    _check_bookable_state(business, branch, branch_service)

    business_customer = _get_business_customer_or_404(db, payload.customer_id)
    if business_customer.business_id != business.id:
        raise HTTPException(status_code=400, detail="Customer does not belong to this business")
    if business_customer.status != "Active":
        raise HTTPException(status_code=409, detail="Customer is not Active")

    duration_minutes = branch_service.duration
    resource = _resolve_resource_for_booking(
        db, branch_service, payload.booking_date, payload.start_time, duration_minutes, payload.resource_id
    )

    booking = Booking(
        business_id=business.id,
        branch_id=branch.id,
        customer_id=business_customer.id,
        branch_service_id=branch_service.id,
        resource_id=resource.id,
        booking_date=payload.booking_date,
        start_time=payload.start_time,
        end_time=_minutes_to_time(_minutes(payload.start_time) + duration_minutes),
        status="Confirmed",
        created_by=current_user.id,
    )
    db.add(booking)
    db.flush()

    _write_booking_history(db, booking, "Created", None, _booking_state_snapshot(booking), current_user.id)

    write_audit(
        db,
        business_id=business.id,
        entity_type="Booking",
        entity_id=booking.id,
        action="BOOKING_CREATED",
        performed_by=current_user.id,
        new_value=_state_to_audit_string(_booking_state_snapshot(booking)),
        commit=False,
    )

    db.commit()
    db.refresh(booking)
    return booking


def _get_or_create_business_customer_for_self_booking(db: Session, business: Business, current_user: User) -> BusinessCustomer:
    """ID-040: auto-provision a BusinessCustomer at self-booking time if none exists yet."""
    platform_customer = crud_customer._require_customer_self(db, current_user)

    existing = (
        db.query(BusinessCustomer)
        .filter(
            BusinessCustomer.business_id == business.id,
            BusinessCustomer.platform_customer_id == platform_customer.id,
        )
        .first()
    )
    if existing:
        return existing

    business_customer = BusinessCustomer(
        business_id=business.id,
        platform_customer_id=platform_customer.id,
        customer_number="PENDING",
        status="Active",
    )
    db.add(business_customer)
    db.flush()  # ID-033: assign id before generating customer_number
    business_customer.customer_number = crud_customer._generate_customer_number(business_customer.id)

    write_audit(
        db,
        business_id=business.id,
        entity_type="BusinessCustomer",
        entity_id=business_customer.id,
        action="CUSTOMER_CREATED",
        performed_by=current_user.id,
        new_value=f"customer_number={business_customer.customer_number}",
        commit=False,
    )

    return business_customer


def create_customer_booking(db: Session, payload, current_user: User) -> Booking:
    branch_service = get_branch_service_or_404(db, payload.branch_service_id)
    branch = get_branch_by_id(db, branch_service.branch_id)
    business = _get_business_or_404(db, branch.business_id)
    _check_bookable_state(business, branch, branch_service)

    business_customer = _get_or_create_business_customer_for_self_booking(db, business, current_user)
    if business_customer.status != "Active":
        raise HTTPException(status_code=409, detail="Your account is not Active with this business")

    duration_minutes = branch_service.duration
    resource = _resolve_resource_for_booking(
        db, branch_service, payload.booking_date, payload.start_time, duration_minutes, payload.resource_id
    )

    booking = Booking(
        business_id=business.id,
        branch_id=branch.id,
        customer_id=business_customer.id,
        branch_service_id=branch_service.id,
        resource_id=resource.id,
        booking_date=payload.booking_date,
        start_time=payload.start_time,
        end_time=_minutes_to_time(_minutes(payload.start_time) + duration_minutes),
        status="Confirmed",
        created_by=current_user.id,
    )
    db.add(booking)
    db.flush()

    _write_booking_history(db, booking, "Created", None, _booking_state_snapshot(booking), current_user.id)

    write_audit(
        db,
        business_id=business.id,
        entity_type="Booking",
        entity_id=booking.id,
        action="BOOKING_CREATED",
        performed_by=current_user.id,
        new_value=_state_to_audit_string(_booking_state_snapshot(booking)),
        commit=False,
    )

    db.commit()
    db.refresh(booking)
    return booking


# -------------------------
# RESCHEDULE (PRD §19; BR-046)
# -------------------------

def _require_active_status(booking: Booking) -> None:
    if booking.status != "Confirmed":
        raise HTTPException(status_code=409, detail=f"Booking cannot be modified from status {booking.status}")


def reschedule_booking(db: Session, booking_id: int, payload, current_user: User, *, actor_is_customer: bool) -> Booking:
    booking = get_booking_or_404(db, booking_id)
    branch = get_branch_by_id(db, booking.branch_id)
    business = _get_business_or_404(db, booking.business_id)

    if actor_is_customer:
        _require_owning_customer(db, booking, current_user)
    else:
        _require_branch_booking_staff_access(db, branch, current_user)

    _require_active_status(booking)

    branch_service = get_branch_service_or_404(db, booking.branch_service_id)
    _check_bookable_state(business, branch, branch_service)  # §19.2: re-validate availability

    duration_minutes = branch_service.duration

    if payload.resource_id is not None:
        # Caller (staff) explicitly requested a specific resource — manual
        # assignment, validated exactly (PRD §19.1: "date, time and/or...
        # Resource"; staff's explicit Reassign Resource action, §21, is a
        # separate endpoint — this is the optional resource_id on the
        # reschedule request itself, not exposed in the customer UI).
        resource = _resolve_resource_for_booking(
            db, branch_service, payload.booking_date, payload.start_time, duration_minutes,
            payload.resource_id, exclude_booking_id=booking.id,
        )
    else:
        # No resource explicitly requested: prefer keeping the currently
        # assigned resource if it's still eligible and free at the new time;
        # otherwise fall back to automatic "First Available" among all
        # eligible resources (ID-039), the same as booking creation. Without
        # this fallback, a reschedule to a time when only the *original*
        # resource is busy would be wrongly rejected even though another
        # eligible resource is free and the Availability Engine already
        # advertises the slot as bookable.
        current_resource = get_resource_or_404(db, booking.resource_id)
        current_still_eligible = booking.resource_id in _eligible_resource_ids(db, branch_service)
        if current_still_eligible and _resource_is_free(
            db, current_resource, payload.booking_date, payload.start_time, duration_minutes, exclude_booking_id=booking.id
        ):
            resource = current_resource
        else:
            resource = _resolve_resource_for_booking(
                db, branch_service, payload.booking_date, payload.start_time, duration_minutes,
                None, exclude_booking_id=booking.id,
            )

    previous_state = _booking_state_snapshot(booking)

    booking.booking_date = payload.booking_date
    booking.start_time = payload.start_time
    booking.end_time = _minutes_to_time(_minutes(payload.start_time) + duration_minutes)
    booking.resource_id = resource.id

    new_state = _booking_state_snapshot(booking)

    _write_booking_history(db, booking, "Rescheduled", previous_state, new_state, current_user.id)

    write_audit(
        db,
        business_id=business.id,
        entity_type="Booking",
        entity_id=booking.id,
        action="BOOKING_RESCHEDULED",
        performed_by=current_user.id,
        previous_value=_state_to_audit_string(previous_state),
        new_value=_state_to_audit_string(new_state),
        commit=False,
    )

    db.commit()
    db.refresh(booking)
    return booking


# -------------------------
# CANCELLATION (PRD §20; BR-045; ID-035)
# -------------------------

def cancel_booking(db: Session, booking_id: int, payload, current_user: User, *, actor_is_customer: bool) -> Booking:
    booking = get_booking_or_404(db, booking_id)
    branch = get_branch_by_id(db, booking.branch_id)
    business = _get_business_or_404(db, booking.business_id)

    if actor_is_customer:
        _require_owning_customer(db, booking, current_user)
    else:
        _require_branch_booking_staff_access(db, branch, current_user)

    _require_active_status(booking)

    previous_state = _booking_state_snapshot(booking)
    booking.status = "Cancelled"
    booking.cancellation_reason = payload.reason
    new_state = _booking_state_snapshot(booking)

    _write_booking_history(db, booking, "Cancelled", previous_state, new_state, current_user.id)

    write_audit(
        db,
        business_id=business.id,
        entity_type="Booking",
        entity_id=booking.id,
        action="BOOKING_CANCELLED",
        performed_by=current_user.id,
        previous_value=_state_to_audit_string(previous_state),
        new_value=_state_to_audit_string(new_state),
        reason=payload.reason,
        commit=False,
    )

    db.commit()
    db.refresh(booking)
    return booking


# -------------------------
# MANUAL RESOURCE OVERRIDE (PRD §21; BR-048, BR-049)
# -------------------------

def reassign_booking_resource(db: Session, booking_id: int, payload, current_user: User) -> Booking:
    booking = get_booking_or_404(db, booking_id)
    branch = get_branch_by_id(db, booking.branch_id)
    business = _require_branch_booking_staff_access(db, branch, current_user)  # §21: Business Owner / Branch Manager only

    _require_active_status(booking)

    branch_service = get_branch_service_or_404(db, booking.branch_service_id)
    duration_minutes = branch_service.duration

    new_resource = get_resource_or_404(db, payload.resource_id)
    if new_resource.branch_id != booking.branch_id:
        raise HTTPException(status_code=400, detail="Resource must belong to the same branch")
    if new_resource.id not in _eligible_resource_ids(db, branch_service):
        raise HTTPException(status_code=400, detail="Resource Category is not allowed for this service")
    if not _resource_is_free(db, new_resource, booking.booking_date, booking.start_time, duration_minutes, exclude_booking_id=booking.id):
        raise HTTPException(status_code=409, detail="Resource is not available at the booking's scheduled time")

    previous_state = _booking_state_snapshot(booking)
    booking.resource_id = new_resource.id
    new_state = _booking_state_snapshot(booking)

    _write_booking_history(db, booking, "ResourceReassigned", previous_state, new_state, current_user.id)

    write_audit(
        db,
        business_id=business.id,
        entity_type="Booking",
        entity_id=booking.id,
        action="BOOKING_RESOURCE_REASSIGNED",
        performed_by=current_user.id,
        previous_value=_state_to_audit_string(previous_state),
        new_value=_state_to_audit_string(new_state),
        commit=False,
    )

    db.commit()
    db.refresh(booking)
    return booking


# -------------------------
# COMPLETION (PRD §18.7; ID-041, ID-042)
# -------------------------

def complete_booking(db: Session, booking_id: int, current_user: User) -> Booking:
    booking = get_booking_or_404(db, booking_id)
    branch = get_branch_by_id(db, booking.branch_id)
    business = _require_branch_booking_staff_access(db, branch, current_user)  # ID-041

    _require_active_status(booking)

    previous_state = _booking_state_snapshot(booking)
    booking.status = "Completed"
    booking.completed_at = datetime.utcnow()
    new_state = _booking_state_snapshot(booking)

    _write_booking_history(db, booking, "Completed", previous_state, new_state, current_user.id)  # ID-042

    write_audit(
        db,
        business_id=business.id,
        entity_type="Booking",
        entity_id=booking.id,
        action="BOOKING_COMPLETED",
        performed_by=current_user.id,
        previous_value=_state_to_audit_string(previous_state),
        new_value=_state_to_audit_string(new_state),
        commit=False,
    )  # ID-042

    db.commit()
    db.refresh(booking)
    return booking


# -------------------------
# LISTING / DETAIL (staff)
# -------------------------

def list_bookings_for_branch(
    db: Session, branch_id: int, current_user: User,
    booking_date: Optional[date] = None, status: Optional[str] = None, resource_id: Optional[int] = None,
) -> List[Booking]:
    branch = get_branch_by_id(db, branch_id)
    _require_branch_booking_staff_access(db, branch, current_user)

    query = db.query(Booking).filter(Booking.branch_id == branch_id)
    if booking_date is not None:
        query = query.filter(Booking.booking_date == booking_date)
    if status is not None:
        query = query.filter(Booking.status == status)
    if resource_id is not None:
        query = query.filter(Booking.resource_id == resource_id)
    return query.order_by(Booking.booking_date.desc(), Booking.start_time.desc()).all()


def list_bookings_for_business(
    db: Session, business_id: int, current_user: User,
    booking_date: Optional[date] = None, status: Optional[str] = None,
) -> List[Booking]:
    _require_business_wide_booking_read_access(db, business_id, current_user)

    query = db.query(Booking).filter(Booking.business_id == business_id)
    if booking_date is not None:
        query = query.filter(Booking.booking_date == booking_date)
    if status is not None:
        query = query.filter(Booking.status == status)
    return query.order_by(Booking.booking_date.desc(), Booking.start_time.desc()).all()


def get_booking_for_staff(db: Session, booking_id: int, current_user: User) -> Booking:
    booking = get_booking_or_404(db, booking_id)
    branch = get_branch_by_id(db, booking.branch_id)
    _require_branch_booking_staff_access(db, branch, current_user)
    return booking


# -------------------------
# LISTING / DETAIL (customer, PRD §35)
# -------------------------

def list_bookings_for_customer(db: Session, current_user: User) -> List[Booking]:
    platform_customer = crud_customer._require_customer_self(db, current_user)
    business_customer_ids = [
        bc.id
        for bc in db.query(BusinessCustomer).filter(BusinessCustomer.platform_customer_id == platform_customer.id).all()
    ]
    if not business_customer_ids:
        return []
    return (
        db.query(Booking)
        .filter(Booking.customer_id.in_(business_customer_ids))
        .order_by(Booking.booking_date.desc(), Booking.start_time.desc())
        .all()
    )


def get_booking_for_customer(db: Session, booking_id: int, current_user: User) -> Booking:
    booking = get_booking_or_404(db, booking_id)
    _require_owning_customer(db, booking, current_user)
    return booking


# -------------------------
# SERIALIZATION
# -------------------------

def serialize_booking(db: Session, booking: Booking) -> dict:
    branch = db.query(Branch).filter(Branch.id == booking.branch_id).first()
    business_customer = db.query(BusinessCustomer).filter(BusinessCustomer.id == booking.customer_id).first()

    customer_name = None
    if business_customer:
        platform_customer = (
            db.query(PlatformCustomer).filter(PlatformCustomer.id == business_customer.platform_customer_id).first()
        )
        if platform_customer:
            profile = db.query(UserProfile).filter(UserProfile.user_id == platform_customer.user_id).first()
            if profile and (profile.first_name or profile.last_name):
                customer_name = f"{profile.first_name or ''} {profile.last_name or ''}".strip()

    branch_service = db.query(BranchService).filter(BranchService.id == booking.branch_service_id).first()
    template = (
        db.query(ServiceTemplate).filter(ServiceTemplate.id == branch_service.service_template_id).first()
        if branch_service else None
    )
    resource = db.query(Resource).filter(Resource.id == booking.resource_id).first()

    return {
        "id": booking.id,
        "business_id": booking.business_id,
        "branch_id": booking.branch_id,
        "branch_name": branch.branch_name if branch else None,
        "customer_id": booking.customer_id,
        "customer_number": business_customer.customer_number if business_customer else None,
        "customer_name": customer_name,
        "branch_service_id": booking.branch_service_id,
        "service_name": template.name if template else None,
        "resource_id": booking.resource_id,
        "resource_name": resource.resource_name if resource else None,
        "booking_date": booking.booking_date,
        "start_time": booking.start_time,
        "end_time": booking.end_time,
        "status": booking.status,
        "cancellation_reason": booking.cancellation_reason,
        "completed_at": booking.completed_at,
        "created_by": booking.created_by,
        "created_at": booking.created_at,
        "updated_at": booking.updated_at,
    }


# -------------------------
# NOTIFICATIONS (PRD §23, §37.2)
# -------------------------

def get_booking_notification_context(db: Session, booking: Booking) -> dict:
    """Enriches a Booking with what services.email_service's booking notifiers need."""
    business_customer = db.query(BusinessCustomer).filter(BusinessCustomer.id == booking.customer_id).first()
    platform_customer = (
        db.query(PlatformCustomer).filter(PlatformCustomer.id == business_customer.platform_customer_id).first()
    )
    user = db.query(User).filter(User.id == platform_customer.user_id).first()
    branch = db.query(Branch).filter(Branch.id == booking.branch_id).first()
    business = db.query(Business).filter(Business.id == booking.business_id).first()
    branch_service = db.query(BranchService).filter(BranchService.id == booking.branch_service_id).first()
    template = (
        db.query(ServiceTemplate).filter(ServiceTemplate.id == branch_service.service_template_id).first()
        if branch_service else None
    )

    return {
        "email": user.email,
        "business_name": business.business_name if business else None,
        "branch_name": branch.branch_name if branch else None,
        "service_name": template.name if template else None,
        "booking_date": booking.booking_date,
        "start_time": booking.start_time,
    }
