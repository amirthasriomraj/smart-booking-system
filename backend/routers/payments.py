from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from database import SessionLocal
from schemas_payment import (
    CustomerCheckoutRequest,
    CustomerCheckoutSummaryResponse,
    CustomerCheckoutRefreshRequest,
    StaffCheckoutRequestBase,
    StaffCheckoutSummaryResponse,
    StaffCheckoutRefreshRequest,
    StaffCashFinalizeRequest,
    StaffReserveWithoutPaymentRequest,
    PaymentVerifyRequest,
    CheckoutResponse,
    BalancePaymentInitiateResponse,
)
import crud_payment
import crud_booking
import crud_hold
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


@router.post("/customer/checkout/hold", response_model=CustomerCheckoutSummaryResponse)
def customer_create_checkout_hold(
    payload: CustomerCheckoutRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Phase 1 of the customer checkout review flow (manual-acceptance
    fix): selecting a slot shows the authoritative price/coupon/deposit
    breakdown — and, for a non-zero amount, a real Razorpay order — before
    any payment happens; no Booking is created here. A ₹0 result (100%-off
    coupon) never acquires a hold; confirm that case via the existing
    /customer/checkout endpoint. A non-zero result finalizes through the
    existing /customer/checkout/{hold_id}/verify, unchanged."""
    return crud_payment.create_customer_checkout_hold(db, payload, current_user)


@router.post("/customer/checkout/{hold_id}/refresh", response_model=CustomerCheckoutSummaryResponse)
def customer_refresh_checkout_hold(
    hold_id: int,
    payload: CustomerCheckoutRefreshRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recomputes the summary for the SAME slot after the coupon or
    payment option changes — releases the existing hold and acquires a
    new one under the new terms; never mutates the frozen price_snapshot.
    Never contacts Razorpay."""
    return crud_payment.refresh_customer_checkout_hold(db, hold_id, payload, current_user)


@router.post("/customer/checkout/{hold_id}/pay", response_model=CheckoutResponse)
def customer_create_checkout_payment(
    hold_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Phase 2 of the customer checkout review flow: called only when the
    customer clicks the final Book/Proceed to Pay action for an
    already-reviewed hold. This is the first point that creates a real
    Razorpay order — the frontend opens the Razorpay widget only after
    this call succeeds, then finalizes via the existing
    /customer/checkout/{hold_id}/verify, unchanged."""
    return crud_payment.create_customer_checkout_payment(db, hold_id, current_user)


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

@router.post("/customer/bookings/{booking_id}/pay-reschedule-difference/verify", response_model=CheckoutResponse)
def verify_reschedule_price_difference_payment(
    booking_id: int,
    payload: PaymentVerifyRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_payment.verify_reschedule_price_difference_payment(db, booking_id, payload, current_user)


@router.post("/branches/{branch_id}/checkout/hold", response_model=StaffCheckoutSummaryResponse)
def staff_create_checkout_hold(
    branch_id: int,
    payload: StaffCheckoutRequestBase,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Phase 1 of the staff checkout review flow: selecting a slot acquires
    a 10-minute hold with the full authoritative price/coupon/deposit
    breakdown, but creates no Booking. The frontend shows this summary,
    lets staff pick a payment method, then finalizes via one of the
    `/holds/{hold_id}/checkout/...` endpoints below using this hold_id."""
    return crud_payment.staff_create_checkout_hold(db, branch_id, payload, current_user)


@router.post("/holds/{hold_id}/refresh", response_model=StaffCheckoutSummaryResponse)
def staff_refresh_checkout_hold(
    hold_id: int,
    payload: StaffCheckoutRefreshRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recomputes the Booking & Payment Summary for the SAME slot after
    staff changes a pricing-affecting input (coupon, price override,
    payment option) — without mutating the frozen hold's price_snapshot.
    Safely releases the existing hold and acquires a new one for the
    identical slot under the new terms; if the slot can no longer be
    acquired, this returns a clear error and the caller must have the
    user reselect a slot."""
    return crud_payment.staff_refresh_checkout_hold(db, hold_id, payload, current_user)


@router.post("/holds/{hold_id}/discard", response_model=CheckoutResponse)
def staff_discard_checkout_hold(
    hold_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Explicitly releases an abandoned StaffCheckout hold — called when
    the frontend invalidates an active Booking & Payment Summary because
    the customer/branch/service/date changed underneath it. Safe/no-op if
    the hold is already gone or already has a payment attempt against it."""
    return crud_payment.staff_discard_checkout_hold(db, hold_id, current_user)


@router.post("/holds/{hold_id}/checkout/cash", response_model=CheckoutResponse)
def staff_finalize_cash_hold(
    hold_id: int,
    payload: StaffCashFinalizeRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = crud_payment.staff_finalize_cash_hold(db, hold_id, payload, current_user)
    from models import Booking, BookingFinancial
    booking = db.query(Booking).filter(Booking.id == result["booking"]["id"]).first()
    financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking.id).first()
    _notify_booking_confirmation(background_tasks, db, booking, financial)
    return result


@router.post("/holds/{hold_id}/checkout/email-link", response_model=CheckoutResponse)
def staff_finalize_email_link_hold(
    hold_id: int,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hold = crud_hold.get_hold_or_404(db, hold_id)
    customer_id, branch_service_id, branch_id = hold.customer_id, hold.branch_service_id, hold.branch_id

    result = crud_payment.staff_finalize_email_link_hold(db, hold_id, current_user)

    business_customer = crud_booking._get_business_customer_or_404(db, customer_id)
    email = crud_payment._business_customer_email(db, business_customer)
    if email and result.get("payment_link"):
        from crud_service import get_branch_service_or_404
        from crud_branch import get_branch_by_id
        from models import ServiceTemplate
        branch_service = get_branch_service_or_404(db, branch_service_id)
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


@router.post("/holds/{hold_id}/checkout/external", response_model=CheckoutResponse)
def staff_finalize_external_hold(
    hold_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_payment.staff_finalize_external_hold(db, hold_id, current_user)


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
