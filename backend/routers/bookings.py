from datetime import date as DateType
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database import SessionLocal
from schemas_booking import (
    AvailabilityResponse,
    StaffBookingCreateRequest,
    CustomerBookingCreateRequest,
    BookingRescheduleRequest,
    BookingCancelRequest,
    BookingReassignResourceRequest,
    BookingResponse,
    BookingHistoryEntryResponse,
)
import crud_booking
from dependencies import get_current_user
from services.email_service import (
    send_booking_confirmation_email,
    send_booking_rescheduled_email,
    send_booking_cancelled_email,
    send_booking_completed_email,
)

router = APIRouter(tags=["Bookings"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _notify(background_tasks: BackgroundTasks, send_fn, db: Session, booking) -> None:
    context = crud_booking.get_booking_notification_context(db, booking)
    background_tasks.add_task(
        send_fn,
        context["email"], context["business_name"], context["branch_name"], context["service_name"],
        context["booking_date"], context["start_time"],
    )


# -----------------------------
# Availability Engine (PRD §14.6, §16.3; TAS Part 4 §3) — staff-facing
# -----------------------------

@router.get("/branches/{branch_id}/availability", response_model=AvailabilityResponse)
def get_branch_availability(
    branch_id: int,
    branch_service_id: int,
    date: DateType,
    resource_id: Optional[int] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_booking.compute_availability(db, branch_id, branch_service_id, date, resource_id)


# -----------------------------
# Staff booking management (PRD §18.4, §90.8)
# -----------------------------

@router.post("/branches/{branch_id}/bookings", response_model=BookingResponse)
def create_staff_booking(
    branch_id: int,
    payload: StaffBookingCreateRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = crud_booking.create_staff_booking(db, branch_id, payload, current_user)
    _notify(background_tasks, send_booking_confirmation_email, db, booking)
    return crud_booking.serialize_booking(db, booking)


@router.get("/branches/{branch_id}/bookings", response_model=List[BookingResponse])
def list_branch_bookings(
    branch_id: int,
    booking_date: Optional[DateType] = None,
    status: Optional[str] = None,
    resource_id: Optional[int] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bookings = crud_booking.list_bookings_for_branch(db, branch_id, current_user, booking_date, status, resource_id)
    return [crud_booking.serialize_booking(db, b) for b in bookings]


@router.get("/businesses/{business_id}/bookings", response_model=List[BookingResponse])
def list_business_bookings(
    business_id: int,
    booking_date: Optional[DateType] = None,
    status: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bookings = crud_booking.list_bookings_for_business(db, business_id, current_user, booking_date, status)
    return [crud_booking.serialize_booking(db, b) for b in bookings]


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = crud_booking.get_booking_for_staff(db, booking_id, current_user)
    return crud_booking.serialize_booking(db, booking)


@router.get("/bookings/{booking_id}/history", response_model=List[BookingHistoryEntryResponse])
def get_booking_history(
    booking_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_booking.get_booking_history(db, booking_id, current_user)


@router.post("/bookings/{booking_id}/reschedule", response_model=BookingResponse)
def reschedule_staff_booking(
    booking_id: int,
    payload: BookingRescheduleRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = crud_booking.reschedule_booking(db, booking_id, payload, current_user, actor_is_customer=False)
    _notify(background_tasks, send_booking_rescheduled_email, db, booking)
    return crud_booking.serialize_booking(db, booking)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingResponse)
def cancel_staff_booking(
    booking_id: int,
    payload: BookingCancelRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = crud_booking.cancel_booking(db, booking_id, payload, current_user, actor_is_customer=False)
    _notify(background_tasks, send_booking_cancelled_email, db, booking)
    return crud_booking.serialize_booking(db, booking)


@router.post("/bookings/{booking_id}/reassign-resource", response_model=BookingResponse)
def reassign_booking_resource(
    booking_id: int,
    payload: BookingReassignResourceRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = crud_booking.reassign_booking_resource(db, booking_id, payload, current_user)
    return crud_booking.serialize_booking(db, booking)


@router.post("/bookings/{booking_id}/complete", response_model=BookingResponse)
def complete_booking(
    booking_id: int,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = crud_booking.complete_booking(db, booking_id, current_user)
    _notify(background_tasks, send_booking_completed_email, db, booking)
    return crud_booking.serialize_booking(db, booking)


# -----------------------------
# Customer self-service (PRD §35, §90.3; ID-035, ID-040)
# -----------------------------

@router.get("/customer/branches/{branch_id}/availability", response_model=AvailabilityResponse)
def get_customer_branch_availability(
    branch_id: int,
    branch_service_id: int,
    date: DateType,
    resource_id: Optional[int] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_booking.compute_availability(db, branch_id, branch_service_id, date, resource_id)


@router.post("/customer/bookings", response_model=BookingResponse)
def create_customer_booking(
    payload: CustomerBookingCreateRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = crud_booking.create_customer_booking(db, payload, current_user)
    _notify(background_tasks, send_booking_confirmation_email, db, booking)
    return crud_booking.serialize_booking(db, booking)


@router.get("/customer/bookings", response_model=List[BookingResponse])
def list_customer_bookings(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bookings = crud_booking.list_bookings_for_customer(db, current_user)
    return [crud_booking.serialize_booking(db, b) for b in bookings]


@router.get("/customer/bookings/{booking_id}", response_model=BookingResponse)
def get_customer_booking(
    booking_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = crud_booking.get_booking_for_customer(db, booking_id, current_user)
    return crud_booking.serialize_booking(db, booking)


@router.post("/customer/bookings/{booking_id}/reschedule", response_model=BookingResponse)
def reschedule_customer_booking(
    booking_id: int,
    payload: BookingRescheduleRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = crud_booking.reschedule_booking(db, booking_id, payload, current_user, actor_is_customer=True)
    _notify(background_tasks, send_booking_rescheduled_email, db, booking)
    return crud_booking.serialize_booking(db, booking)


@router.post("/customer/bookings/{booking_id}/cancel", response_model=BookingResponse)
def cancel_customer_booking(
    booking_id: int,
    payload: BookingCancelRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = crud_booking.cancel_booking(db, booking_id, payload, current_user, actor_is_customer=True)
    _notify(background_tasks, send_booking_cancelled_email, db, booking)
    return crud_booking.serialize_booking(db, booking)
