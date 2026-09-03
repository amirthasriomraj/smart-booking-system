from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from database import SessionLocal
from schemas_payment import (
    CustomerCheckoutRequest,
    StaffCashCheckoutRequest,
    StaffEmailLinkCheckoutRequest,
    StaffExternalCheckoutRequest,
    StaffReserveWithoutPaymentRequest,
    PaymentVerifyRequest,
    CheckoutResponse,
    BalancePaymentInitiateResponse,
)
import crud_payment
import crud_booking
from dependencies import get_current_user
from services import notification_service, email_service

router = APIRouter(tags=["Payments"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _notify_booking_confirmation(background_tasks: BackgroundTasks, db: Session, booking, financial) -> None:
    context = crud_booking.get_booking_notification_context(db, booking)
    if financial is not None and financial.financial_status == "AwaitingBalance":
        background_tasks.add_task(
            notification_service.log_and_send,
            booking.created_by, "DepositConfirmation",
            lambda: email_service.send_deposit_confirmation_email(
                context["email"], context["business_name"], context["branch_name"], context["service_name"],
                context["booking_date"], context["start_time"], financial.total_amount, financial.deposit_amount,
                financial.balance_due, financial.balance_due_at,
            ),
            booking.business_id, "Booking", booking.id,
        )
    else:
        background_tasks.add_task(
            notification_service.log_and_send,
            booking.created_by, "BookingConfirmation",
            lambda: email_service.send_booking_confirmation_email(
                context["email"], context["business_name"], context["branch_name"], context["service_name"],
                context["booking_date"], context["start_time"],
            ),
            booking.business_id, "Booking", booking.id,
        )


def _notify_balance_paid(background_tasks: BackgroundTasks, db: Session, booking) -> None:
    context = crud_booking.get_booking_notification_context(db, booking)
    background_tasks.add_task(
        notification_service.log_and_send,
        booking.created_by, "BalancePaidConfirmation",
        lambda: email_service.send_balance_paid_confirmation_email(
            context["email"], context["business_name"], context["branch_name"], context["service_name"],
            context["booking_date"], context["start_time"],
        ),
        booking.business_id, "Booking", booking.id,
    )


# -----------------------------
# Phase 5 — Customer checkout (rule 11)
# -----------------------------

@router.post("/customer/checkout", response_model=CheckoutResponse)
def customer_checkout(
    payload: CustomerCheckoutRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = crud_payment.create_customer_checkout(db, payload, current_user)
    if result.get("status") == "Confirmed":
        from models import Booking, BookingFinancial
        booking = db.query(Booking).filter(Booking.id == result["booking"]["id"]).first()
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking.id).first()
        _notify_booking_confirmation(background_tasks, db, booking, financial)
    return result


@router.post("/customer/checkout/{hold_id}/verify", response_model=CheckoutResponse)
def customer_checkout_verify(
    hold_id: int,
    payload: PaymentVerifyRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = crud_payment.verify_customer_checkout_payment(db, hold_id, payload, current_user)
    from models import Booking, BookingFinancial
    booking = db.query(Booking).filter(Booking.id == result["booking"]["id"]).first()
    financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking.id).first()
    _notify_booking_confirmation(background_tasks, db, booking, financial)
    return result


# -----------------------------
# Phase 7 — Balance payment (rule 6)
# -----------------------------

@router.post("/customer/bookings/{booking_id}/pay-balance", response_model=BalancePaymentInitiateResponse)
def initiate_balance_payment(
    booking_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_payment.initiate_balance_payment(db, booking_id, current_user)


@router.post("/customer/bookings/{booking_id}/pay-balance/verify", response_model=CheckoutResponse)
def verify_balance_payment(
    booking_id: int,
    payload: PaymentVerifyRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = crud_payment.verify_balance_payment(db, booking_id, payload, current_user)
    from models import Booking
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    _notify_balance_paid(background_tasks, db, booking)
    return result


# -----------------------------
# Phase 6 — Staff payment flows (rule 12)
# -----------------------------

@router.post("/branches/{branch_id}/checkout/cash", response_model=CheckoutResponse)
def staff_cash_checkout(
    branch_id: int,
    payload: StaffCashCheckoutRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = crud_payment.staff_cash_checkout(db, branch_id, payload, current_user)
    from models import BookingFinancial
    financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking.id).first()
    _notify_booking_confirmation(background_tasks, db, booking, financial)
    return {"status": "Confirmed", "booking": crud_booking.serialize_booking(db, booking)}


@router.post("/branches/{branch_id}/checkout/email-link", response_model=CheckoutResponse)
def staff_email_link_checkout(
    branch_id: int,
    payload: StaffEmailLinkCheckoutRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = crud_payment.staff_email_link_checkout(db, branch_id, payload, current_user)

    business_customer = crud_booking._get_business_customer_or_404(db, payload.customer_id)
    email = crud_payment._business_customer_email(db, business_customer)
    if email and result.get("payment_link"):
        from crud_service import get_branch_service_or_404
        from crud_branch import get_branch_by_id
        from models import ServiceTemplate
        branch_service = get_branch_service_or_404(db, payload.branch_service_id)
        template = db.query(ServiceTemplate).filter(ServiceTemplate.id == branch_service.service_template_id).first()
        branch = get_branch_by_id(db, branch_id)
        business = crud_booking._get_business_or_404(db, branch.business_id)
        background_tasks.add_task(
            notification_service.log_and_send,
            business_customer.platform_customer_id, "PaymentLinkEmail",
            lambda: email_service.send_payment_link_email(
                email, business.business_name, template.name if template else "your booking",
                result.get("amount_due", ""), result["payment_link"],
            ),
            business.id,
        )
    return result


@router.post("/branches/{branch_id}/checkout/external", response_model=CheckoutResponse)
def staff_external_checkout(
    branch_id: int,
    payload: StaffExternalCheckoutRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_payment.staff_external_checkout(db, branch_id, payload, current_user)


@router.post("/holds/{hold_id}/confirm-external-payment", response_model=CheckoutResponse)
def confirm_external_payment(
    hold_id: int,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = crud_payment.staff_confirm_external_payment(db, hold_id, current_user)
    from models import BookingFinancial
    financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking.id).first()
    _notify_booking_confirmation(background_tasks, db, booking, financial)
    return {"status": "Confirmed", "booking": crud_booking.serialize_booking(db, booking)}


@router.post("/branches/{branch_id}/checkout/reserve-without-payment", response_model=CheckoutResponse)
def staff_reserve_without_payment(
    branch_id: int,
    payload: StaffReserveWithoutPaymentRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = crud_payment.staff_reserve_without_payment(db, branch_id, payload, current_user)
    return {"status": "Confirmed", "booking": crud_booking.serialize_booking(db, booking)}
