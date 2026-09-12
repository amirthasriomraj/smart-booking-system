from datetime import date as DateType
from decimal import Decimal
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database import SessionLocal
from schemas_booking import (
    AvailabilityResponse,
    StaffBookingCreateRequest,
    CustomerBookingCreateRequest,
    BookingRescheduleRequest,
    StaffRescheduleRequest,
    BookingCancelRequest,
    BookingReassignResourceRequest,
    BookingResponse,
    PaginatedBookings,
    BookingHistoryEntryResponse,
)
from schemas_payment import (
    BookingActionResponse,
    BookingPaymentHistoryResponse,
    StaffRefundRequest,
    StandaloneRefundResponse,
)
import crud_booking
import crud_payment
from dependencies import get_current_user
from services import notification_service
from services.email_service import (
    send_booking_confirmation_email,
    send_booking_rescheduled_email,
    send_booking_cancelled_email,
    send_booking_completed_email,
    send_refund_notification_email,
    send_reschedule_price_difference_email,
)

router = APIRouter(tags=["Bookings"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _notify(background_tasks: BackgroundTasks, send_fn, db: Session, booking, notification_type: str) -> None:
    context = crud_booking.get_booking_notification_context(db, booking)
    background_tasks.add_task(
        notification_service.log_and_send,
        context["user_id"], notification_type,
        lambda: send_fn(
            context["email"], context["business_name"], context["branch_name"], context["service_name"],
            context["booking_date"], context["start_time"],
        ),
        booking.business_id, "Booking", booking.id,
    )


def _notify_refund_outcome(background_tasks: BackgroundTasks, db: Session, booking, refund_result: dict) -> None:
    if not refund_result or Decimal(refund_result.get("final_amount", "0")) <= 0:
        return
    context = crud_booking.get_booking_notification_context(db, booking)
    # A booking can be refunded via a mix of Gateway/Manual portions; the
    # notification names whichever method the largest portion used.
    from models import Refund
    refund_rows = db.query(Refund).filter(Refund.id.in_(refund_result.get("refund_ids", []))).all()
    method = max(refund_rows, key=lambda r: r.final_amount).refund_method if refund_rows else "Manual"
    background_tasks.add_task(
        notification_service.log_and_send,
        booking.created_by, "RefundNotification",
        lambda: send_refund_notification_email(
            context["email"], context["business_name"], context["service_name"], refund_result["final_amount"], method,
        ),
        booking.business_id, "Booking", booking.id,
    )


def _flatten_action_result(result: dict) -> dict:
    """Merges the booking's own fields to the top level (matching the
    pre-Milestone-8 flat BookingResponse shape these endpoints already
    returned, for backward compatibility) alongside the financial outcome."""
    return {**result["booking"], "refund": result.get("refund"), "price_adjustment": result.get("price_adjustment")}


def _notify_price_adjustment(background_tasks: BackgroundTasks, db: Session, booking, price_result: dict) -> None:
    if not price_result:
        return
    context = crud_booking.get_booking_notification_context(db, booking)
    amount = price_result.get("amount_due") or price_result.get("amount_refunded")
    background_tasks.add_task(
        notification_service.log_and_send,
        booking.created_by, "ReschedulePriceDifference",
        lambda: send_reschedule_price_difference_email(
            context["email"], context["business_name"], context["service_name"], price_result["action"], amount,
        ),
        booking.business_id, "Booking", booking.id,
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
    _notify(background_tasks, send_booking_confirmation_email, db, booking, "BookingConfirmation")
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


@router.get("/businesses/{business_id}/bookings", response_model=PaginatedBookings)
def list_business_bookings(
    business_id: int,
    booking_date: Optional[DateType] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    resource_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    branch_service_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    date_from: Optional[DateType] = None,
    date_to: Optional[DateType] = None,
    sort: str = "-booking_date",
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = crud_booking.list_bookings_for_business(
        db, business_id, current_user, booking_date, status,
        page, page_size, search, resource_id, customer_id, branch_service_id,
        branch_id, date_from, date_to, sort,
    )
    result["items"] = [crud_booking.serialize_booking(db, b) for b in result["items"]]
    return result


@router.get("/branches/{branch_id}/booking-history", response_model=PaginatedBookings)
def list_branch_booking_history(
    branch_id: int,
    status: Optional[str] = None,
    date_from: Optional[DateType] = None,
    date_to: Optional[DateType] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Branch Manager's Booking History (M9 follow-up) — separate from the
    operational /branches/{id}/bookings list used by Booking Management."""
    result = crud_booking.list_booking_history_for_branch(db, branch_id, current_user, status, date_from, date_to, page, page_size)
    result["items"] = [crud_booking.serialize_booking(db, b) for b in result["items"]]
    return result


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


@router.get("/bookings/{booking_id}/payments", response_model=BookingPaymentHistoryResponse)
def get_booking_payment_history(
    booking_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    crud_booking.get_booking_for_staff(db, booking_id, current_user)
    return crud_payment.get_payment_history(db, booking_id)


@router.get("/bookings/{booking_id}/reschedule-preview")
def preview_reschedule_price_difference(
    booking_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Read-only: what a reschedule's price difference and default payment
    method would be right now (rule 14) — no reschedule, Payment, or
    Refund is created. Lets the staff UI show the amount and preselect the
    default payment method before the reschedule is actually submitted."""
    booking = crud_booking.get_booking_for_staff(db, booking_id, current_user)
    return crud_payment.preview_reschedule_price_difference(db, booking)


@router.post("/bookings/{booking_id}/reschedule", response_model=BookingActionResponse)
def reschedule_staff_booking(
    booking_id: int,
    payload: StaffRescheduleRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = crud_payment.reschedule_staff_booking(db, booking_id, payload, current_user)
    booking = crud_booking.get_booking_or_404(db, booking_id)
    _notify(background_tasks, send_booking_rescheduled_email, db, booking, "BookingRescheduled")
    _notify_price_adjustment(background_tasks, db, booking, result.get("price_adjustment"))
    return _flatten_action_result(result)


@router.post("/bookings/{booking_id}/reschedule-difference/confirm-payment", response_model=BookingActionResponse)
def confirm_reschedule_difference_payment(
    booking_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Staff manually confirms a reschedule-difference collection that
    wasn't captured synchronously — Direct UPI/Bank Transfer, or an Email
    Payment Link the customer has since paid — mirroring
    `confirm_external_payment`'s role for the original checkout hold flow."""
    result = crud_payment.staff_confirm_reschedule_difference_payment(db, booking_id, current_user)
    return _flatten_action_result(result)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingActionResponse)
def cancel_staff_booking(
    booking_id: int,
    payload: BookingCancelRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = crud_payment.staff_cancel_booking_with_refund(db, booking_id, payload, current_user)
    booking = crud_booking.get_booking_or_404(db, booking_id)
    _notify(background_tasks, send_booking_cancelled_email, db, booking, "BookingCancelled")
    _notify_refund_outcome(background_tasks, db, booking, result.get("refund"))
    return _flatten_action_result(result)


@router.post("/bookings/{booking_id}/refund", response_model=StandaloneRefundResponse)
def refund_booking(
    booking_id: int,
    payload: StaffRefundRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Standalone refund (partial or full), independent of cancellation —
    the booking's status/cancellation_reason are never touched here."""
    result = crud_payment.staff_refund_booking(db, booking_id, payload, current_user)
    booking = crud_booking.get_booking_or_404(db, booking_id)
    _notify_refund_outcome(background_tasks, db, booking, result.get("refund"))
    return result


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
    _notify(background_tasks, send_booking_completed_email, db, booking, "BookingCompleted")
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
    _notify(background_tasks, send_booking_confirmation_email, db, booking, "BookingConfirmation")
    return crud_booking.serialize_booking(db, booking)


@router.get("/customer/bookings", response_model=PaginatedBookings)
def list_customer_bookings(
    date_from: Optional[DateType] = None,
    date_to: Optional[DateType] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = crud_booking.list_bookings_for_customer(db, current_user, date_from, date_to, page, page_size)
    result["items"] = [crud_booking.serialize_booking(db, b) for b in result["items"]]
    return result


# -----------------------------
# Resource User self-service (M9 Phase 6, PRD §35 Resource Dashboard)
# -----------------------------

@router.get("/resource/bookings", response_model=List[BookingResponse])
def list_resource_user_bookings(
    scope: str = "upcoming",
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bookings = crud_booking.list_bookings_for_resource_user(db, current_user, scope)
    return [crud_booking.serialize_booking(db, b) for b in bookings]


@router.get("/customer/bookings/{booking_id}", response_model=BookingResponse)
def get_customer_booking(
    booking_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = crud_booking.get_booking_for_customer(db, booking_id, current_user)
    return crud_booking.serialize_booking(db, booking)


@router.get("/customer/bookings/{booking_id}/payments", response_model=BookingPaymentHistoryResponse)
def get_customer_booking_payment_history(
    booking_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    crud_booking.get_booking_for_customer(db, booking_id, current_user)
    return crud_payment.get_payment_history(db, booking_id)


@router.post("/customer/bookings/{booking_id}/reschedule", response_model=BookingActionResponse)
def reschedule_customer_booking(
    booking_id: int,
    payload: BookingRescheduleRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = crud_payment.reschedule_customer_booking(db, booking_id, payload, current_user)
    booking = crud_booking.get_booking_or_404(db, booking_id)
    _notify(background_tasks, send_booking_rescheduled_email, db, booking, "BookingRescheduled")
    _notify_price_adjustment(background_tasks, db, booking, result.get("price_adjustment"))
    return _flatten_action_result(result)


@router.post("/customer/bookings/{booking_id}/cancel", response_model=BookingActionResponse)
def cancel_customer_booking(
    booking_id: int,
    payload: BookingCancelRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = crud_payment.cancel_customer_booking_with_refund(db, booking_id, payload, current_user)
    booking = crud_booking.get_booking_or_404(db, booking_id)
    _notify(background_tasks, send_booking_cancelled_email, db, booking, "BookingCancelled")
    _notify_refund_outcome(background_tasks, db, booking, result.get("refund"))
    return _flatten_action_result(result)
