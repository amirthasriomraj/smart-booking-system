"""
Milestone 8 Phases 5-7 — Checkout, Payment Finalization, Deposits & Balance
Collection (ID-046, ID-048, ID-051, ID-054, ID-055, ID-056; rules 5-14).

One shared finalization path (`_finalize_hold_to_booking`) is used by every
flow that goes through a `BookingHold` (customer online checkout, staff
cash/walk-in, staff emailed payment link, staff external-manual) so the
concurrency/locking/re-validation guarantees are identical everywhere.
Reserve Without Payment is the one flow that deliberately never touches a
`BookingHold` or `Payment` at all (ID-046 correction).
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import (
    Business, Branch, BranchService, BookingHold, Payment, Refund,
    BookingFinancial, Booking, BookingPriceAdjustment, PlatformFeeSetting,
    User, PlatformCustomer, BusinessCustomer, AuditLog,
)
from audit import write_audit
import crud_booking
import crud_hold
import crud_coupon
import pricing
from crud_branch import get_branch_by_id
from crud_service import get_branch_service_or_404
from services import razorpay_service
from config import get_settings

CUSTOMER_HOLD_MINUTES = 6
STAFF_HOLD_MINUTES = 10
STANDARD_DEPOSIT_PERCENTAGE = Decimal("25")
DEPOSIT_MIN_DAYS = 7
BALANCE_REMINDER_HOURS_BEFORE = 72
BALANCE_DEADLINE_HOURS_BEFORE = 48

TWO_PLACES = Decimal("0.01")


# -------------------------
# SHARED HELPERS
# -------------------------

def appointment_datetime(booking_date, start_time) -> datetime:
    return datetime.combine(booking_date, start_time)


def _business_customer_email(db: Session, business_customer: BusinessCustomer) -> Optional[str]:
    platform_customer = db.query(PlatformCustomer).filter(PlatformCustomer.id == business_customer.platform_customer_id).first()
    if not platform_customer:
        return None
    user = db.query(User).filter(User.id == platform_customer.user_id).first()
    return user.email if user else None


def _actor_role_label(db: Session, business_id: int, user_id: int) -> str:
    if crud_booking._has_active_role(db, business_id, user_id, "BUSINESS_OWNER"):
        return "BUSINESS_OWNER"
    if crud_booking._get_manager_current_branch_id(db, business_id, user_id) is not None:
        return "BRANCH_MANAGER"
    return "SYSTEM"


def _refund_status_from_response(response: dict) -> "tuple[str, Optional[datetime]]":
    """
    Post-Phase-10 hardening: Razorpay refund creation is asynchronous
    (verified against current docs — razorpay.com/docs/webhooks/refunds/).
    A refund's lifecycle is `refund.created` -> `refund.processed` |
    `refund.failed`; the create-refund API call's own response already
    reports a `status` field reflecting which stage it's at: `"processed"`
    for a normal-speed refund confirmed complete synchronously (the common
    case), `"pending"` for one still awaiting the provider's asynchronous
    confirmation (e.g. instant-speed refunds under load), or `"failed"`.
    Anything not explicitly `"processed"`/`"failed"` is treated
    conservatively as still pending — final confirmation then arrives via
    `reconcile_refund_webhook_event`. This is the one place that decides
    "Completed" vs "Initiated" vs "Failed"; every `create_refund` call site
    in this module uses it rather than assuming success.
    """
    provider_status = (response or {}).get("status")
    if provider_status == "processed":
        return "Completed", datetime.utcnow()
    if provider_status == "failed":
        return "Failed", None
    return "Initiated", None


def _acquire_booking_lock(db: Session, booking_id: int) -> None:
    """
    Phase 8 concurrency guard: transaction-scoped advisory lock serializing
    financial mutations (cancellation refund, refund override) for one
    booking, so two concurrent cancellation attempts on the same booking
    can never both process a refund. Uses the single-bigint-key form of
    `pg_advisory_xact_lock`, a separate lock namespace from the
    two-int-key form `crud_booking._acquire_resource_lock` uses for
    resource/date occupancy — the two never collide. No-op on SQLite, same
    rationale as `crud_booking._acquire_resource_lock`.
    """
    if db.bind.dialect.name != "postgresql":
        return
    db.execute(text("SELECT pg_advisory_xact_lock(:booking_id)"), {"booking_id": booking_id})


_CANCELLATION_REFUND_AUDIT_ACTIONS = ("BOOKING_CANCELLATION_REFUND_CALCULATED", "BOOKING_REFUND_OVERRIDDEN")


def _existing_cancellation_refund_result(db: Session, booking_id: int) -> Optional[AuditLog]:
    """Idempotency guard: a cancellation-refund audit entry already exists
    for this booking once it has been processed once. Combined with
    `_acquire_booking_lock`, this ensures a second concurrent (or retried)
    cancellation request observes the already-recorded outcome instead of
    issuing a second refund."""
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_type == "Booking",
            AuditLog.entity_id == booking_id,
            AuditLog.action.in_(_CANCELLATION_REFUND_AUDIT_ACTIONS),
        )
        .order_by(AuditLog.id.desc())
        .first()
    )


def effective_platform_fee_rate(db: Session, business_id: int) -> Decimal:
    """ID-051: business override if one exists, else the platform default row."""
    override = db.query(PlatformFeeSetting).filter(PlatformFeeSetting.business_id == business_id).first()
    if override:
        return Decimal(override.fee_percentage)
    default = db.query(PlatformFeeSetting).filter(PlatformFeeSetting.business_id.is_(None)).first()
    return Decimal(default.fee_percentage) if default else Decimal("0")


def _snapshot_platform_fee_rate(db: Session, booking_financial: BookingFinancial) -> Decimal:
    """ID-051: set once, from the effective rate at the booking's FIRST
    financial transaction, and never re-read afterward."""
    if booking_financial.platform_fee_rate_snapshot is None:
        booking_financial.platform_fee_rate_snapshot = effective_platform_fee_rate(db, booking_financial.business_id)
    return Decimal(booking_financial.platform_fee_rate_snapshot)


def _apply_platform_fee(db: Session, payment: Payment, booking_financial: BookingFinancial) -> None:
    """rule 19/22: the platform fee is earned ONLY on online payments."""
    if payment.method != "RazorpayOnline":
        return
    rate = _snapshot_platform_fee_rate(db, booking_financial)
    payment.platform_fee_rate_snapshot = rate
    payment.platform_fee_amount = (Decimal(payment.amount) * rate / Decimal("100")).quantize(TWO_PLACES)


def _require_deposit_eligible(booking_date, start_time) -> None:
    if not pricing.is_deposit_eligible(appointment_datetime(booking_date, start_time), datetime.utcnow(), DEPOSIT_MIN_DAYS):
        raise HTTPException(status_code=409, detail="Deposit payment requires the appointment to be at least 7 days away")


def compute_checkout_breakdown(
    db: Session, business: Business, branch: Branch, branch_service: BranchService, business_customer_id: int,
    booking_date, coupon_code: Optional[str], base_price_override: Optional[Decimal] = None,
    final_price_override: Optional[Decimal] = None,
):
    """Shared by customer and staff checkout: coupon validation (against
    the effective base price) + the frozen calculation order (rule 9/10)."""
    base_price = Decimal(branch_service.price)
    coupon = None
    if coupon_code:
        coupon = crud_coupon.validate_and_reserve_coupon(
            db, coupon_code, business.id, branch.id, branch_service.id, business_customer_id,
            base_price_override if base_price_override is not None else base_price, booking_date,
        )
    breakdown = pricing.compute_price(base_price, base_price_override, coupon, final_price_override)
    return breakdown, coupon


def _price_snapshot(
    breakdown, payment_option: str, deposit_amount: Optional[Decimal], balance_due: Optional[Decimal],
    platform_fee_rate: Decimal, resource_id: Optional[int],
    base_price_override: Optional[Decimal] = None, final_price_override: Optional[Decimal] = None,
    price_override_reason: Optional[str] = None, price_override_actor_id: Optional[int] = None,
) -> dict:
    """ID-054: the full checkout-terms snapshot captured at hold creation
    and left untouched for the hold's lifetime."""
    return {
        "calculated_price": str(breakdown.calculated_price),
        "effective_base_price": str(breakdown.effective_base_price),
        "base_price_override": str(base_price_override) if base_price_override is not None else None,
        "coupon_id": breakdown.coupon_id,
        "discount_amount": str(breakdown.discount_amount),
        "pre_final_override_amount": str(breakdown.effective_base_price - breakdown.discount_amount),
        "final_price_override": str(final_price_override) if final_price_override is not None else None,
        "final_amount": str(breakdown.final_amount),
        "price_override_reason": price_override_reason,
        "price_override_actor_id": price_override_actor_id,
        "payment_option": payment_option,
        "deposit_amount": str(deposit_amount) if deposit_amount is not None else None,
        "balance_due": str(balance_due) if balance_due is not None else None,
        "platform_fee_rate": str(platform_fee_rate),
        "resource_id": resource_id,
        "currency": "INR",
    }


def _write_price_adjustment_history(db: Session, booking: Booking, snapshot: dict) -> None:
    actor_id = snapshot.get("price_override_actor_id")
    if actor_id is None:
        return
    role_snapshot = _actor_role_label(db, booking.business_id, actor_id)
    if snapshot.get("base_price_override"):
        db.add(BookingPriceAdjustment(
            booking_id=booking.id, adjustment_type="BaseOverride",
            previous_value=Decimal(snapshot["calculated_price"]), new_value=Decimal(snapshot["base_price_override"]),
            actor_id=actor_id, role_snapshot=role_snapshot, reason=snapshot.get("price_override_reason"),
        ))
    if snapshot.get("final_price_override"):
        db.add(BookingPriceAdjustment(
            booking_id=booking.id, adjustment_type="FinalOverride",
            previous_value=Decimal(snapshot["pre_final_override_amount"]), new_value=Decimal(snapshot["final_price_override"]),
            actor_id=actor_id, role_snapshot=role_snapshot, reason=snapshot.get("price_override_reason"),
        ))


# -------------------------
# SHARED HOLD -> BOOKING FINALIZATION (ID-056)
# -------------------------

def _finalize_hold_to_booking(db: Session, hold: BookingHold, payment: Optional[Payment]) -> Booking:
    """
    Called once a payment has been verified/collected (online signature
    verified, cash physically collected, or staff manually confirmed
    external payment). Re-acquires the resource lock, expires any stale
    Active holds for this resource/date (so the GiST exclusion constraint
    never wrongly blocks this insert), and re-validates the exact resource
    the hold reserved is still free — excluding the hold's own occupancy —
    before creating the Booking. `payment` is None only for the
    zero-payable-after-100%-coupon path, which never creates a Payment row.

    If the hold is no longer Active (expired and/or reclaimed since it was
    created), no Booking is created; if a payment was captured, it is
    handled by `_handle_lost_hold_payment` (ID-056) instead, and this
    raises so the caller returns a clear error to the client.
    """
    business = crud_booking._get_business_or_404(db, hold.business_id)
    branch = get_branch_by_id(db, hold.branch_id)
    branch_service = get_branch_service_or_404(db, hold.branch_service_id)

    crud_booking._acquire_resource_lock(db, hold.resource_id, hold.booking_date)
    crud_booking._expire_stale_holds_for_resource_date(db, hold.resource_id, hold.booking_date)
    db.refresh(hold)

    if hold.status != "Active":
        if payment is not None:
            _handle_lost_hold_payment(db, hold, payment)
        raise HTTPException(
            status_code=409,
            detail="This slot is no longer available. Any payment collected is being refunded automatically.",
        )

    resource = crud_booking._resolve_resource_for_booking(
        db, branch_service, hold.booking_date, hold.start_time, branch_service.duration,
        hold.resource_id, exclude_hold_id=hold.id,
    )

    booking = Booking(
        business_id=business.id, branch_id=branch.id, customer_id=hold.customer_id,
        branch_service_id=branch_service.id, resource_id=resource.id,
        booking_date=hold.booking_date, start_time=hold.start_time, end_time=hold.end_time,
        status="Confirmed", created_by=hold.created_by,
    )
    db.add(booking)
    db.flush()

    crud_booking._write_booking_history(
        db, booking, "Created", None, crud_booking._booking_state_snapshot(booking), hold.created_by
    )
    write_audit(
        db, business_id=business.id, entity_type="Booking", entity_id=booking.id, action="BOOKING_CREATED",
        performed_by=hold.created_by,
        new_value=crud_booking._state_to_audit_string(crud_booking._booking_state_snapshot(booking)), commit=False,
    )

    snapshot = hold.price_snapshot or {}
    final_amount = Decimal(snapshot.get("final_amount", "0"))
    deposit_amount = snapshot.get("deposit_amount")
    balance_due = snapshot.get("balance_due")
    coupon_id = snapshot.get("coupon_id")

    deposit_required = deposit_amount is not None
    financial_status = "AwaitingBalance" if deposit_required else "FullyPaid"
    balance_due_at = None
    if deposit_required:
        balance_due_at = appointment_datetime(hold.booking_date, hold.start_time) - timedelta(hours=BALANCE_DEADLINE_HOURS_BEFORE)

    booking_financial = BookingFinancial(
        booking_id=booking.id, business_id=business.id, branch_id=branch.id,
        total_amount=final_amount, amount_paid=Decimal(payment.amount) if payment else Decimal("0"),
        deposit_required=deposit_required, deposit_amount=Decimal(deposit_amount) if deposit_amount else None,
        balance_due=Decimal(balance_due) if balance_due else None, balance_due_at=balance_due_at,
        financial_status=financial_status, coupon_id=coupon_id,
        base_price=Decimal(snapshot.get("calculated_price", str(final_amount))),
        base_price_override=Decimal(snapshot["base_price_override"]) if snapshot.get("base_price_override") else None,
        final_price_override=Decimal(snapshot["final_price_override"]) if snapshot.get("final_price_override") else None,
    )
    db.add(booking_financial)
    db.flush()

    if payment is not None:
        payment.booking_id = booking.id
        _apply_platform_fee(db, payment, booking_financial)
    else:
        # rule 10: platform default row still consulted for the snapshot
        # even though this booking carries no fee-earning payment.
        _snapshot_platform_fee_rate(db, booking_financial)

    _write_price_adjustment_history(db, booking, snapshot)

    if coupon_id is not None:
        coupon = crud_coupon.get_coupon_or_404(db, coupon_id)
        discount_amount = Decimal(snapshot.get("discount_amount", "0"))
        crud_coupon.redeem_coupon(db, coupon, booking.id, hold.customer_id, discount_amount, performed_by=hold.created_by)

    hold.status = "Completed"

    db.commit()
    db.refresh(booking)
    return booking


def _handle_lost_hold_payment(db: Session, hold: BookingHold, payment: Payment) -> None:
    """
    ID-056: money was captured (or, for a manual/cash flow that should
    never reach this branch, recorded) against a hold that is no longer
    valid. Never creates an overlapping Booking. For an online payment,
    issues an automatic gateway refund; the resulting Refund row has no
    booking_id (nothing to reference — see the Refund model docstring).
    """
    if payment.method == "RazorpayOnline" and payment.razorpay_payment_id:
        try:
            response = razorpay_service.create_refund(payment.razorpay_payment_id, Decimal(payment.amount))
            razorpay_refund_id = response.get("id")
            refund_status, completed_at = _refund_status_from_response(response)
        except Exception:
            razorpay_refund_id = None
            refund_status, completed_at = "Failed", None
        refund_method = "Gateway"
    else:
        # Cash/manual flows finalize synchronously in the same request that
        # collects the money, so a lost hold should never reach this branch
        # for them — recorded defensively rather than silently dropped.
        razorpay_refund_id = None
        refund_status, completed_at = "Failed", None
        refund_method = "Manual"

    refund = Refund(
        business_id=hold.business_id, branch_id=hold.branch_id, booking_id=None, payment_id=payment.id,
        calculated_amount=Decimal(payment.amount), final_amount=Decimal(payment.amount),
        reason="Automatic refund: checkout hold expired/was lost before payment could be finalized",
        actor_id=hold.created_by, role_snapshot="SYSTEM", refund_method=refund_method,
        razorpay_refund_id=razorpay_refund_id, status=refund_status, completed_at=completed_at,
    )
    db.add(refund)

    write_audit(
        db, business_id=hold.business_id, entity_type="BookingHold", entity_id=hold.id,
        action="HOLD_PAYMENT_LOST_AUTO_REFUND", performed_by=hold.created_by,
        new_value=f"payment_id={payment.id} refund_status={refund_status}", commit=False,
    )
    hold.status = "Expired"
    db.commit()


# -------------------------
# PHASE 5 — CUSTOMER CHECKOUT
# -------------------------

def create_customer_checkout(db: Session, payload, current_user: User) -> dict:
    branch_service = get_branch_service_or_404(db, payload.branch_service_id)
    branch = get_branch_by_id(db, branch_service.branch_id)
    business = crud_booking._get_business_or_404(db, branch.business_id)
    crud_booking._check_bookable_state(business, branch, branch_service)

    business_customer = crud_booking._get_or_create_business_customer_for_self_booking(db, business, current_user)
    if business_customer.status != "Active":
        raise HTTPException(status_code=409, detail="Your account is not Active with this business")

    if payload.payment_option not in ("Full", "Deposit"):
        raise HTTPException(status_code=400, detail="payment_option must be Full or Deposit")

    breakdown, coupon = compute_checkout_breakdown(
        db, business, branch, branch_service, business_customer.id, payload.booking_date, payload.coupon_code
    )

    deposit_amount = balance_due = None
    if payload.payment_option == "Deposit":
        _require_deposit_eligible(payload.booking_date, payload.start_time)
        deposit_amount, balance_due = pricing.compute_deposit(breakdown.final_amount, STANDARD_DEPOSIT_PERCENTAGE)
        amount_due_now = deposit_amount
    else:
        amount_due_now = breakdown.final_amount

    if amount_due_now == 0:
        # rule 10/13: a legitimate 100%-off booking skips Razorpay entirely.
        booking = crud_booking.create_customer_booking(db, payload, current_user)
        booking_financial = BookingFinancial(
            booking_id=booking.id, business_id=business.id, branch_id=branch.id,
            total_amount=breakdown.final_amount, amount_paid=Decimal("0"), deposit_required=False,
            financial_status="FullyPaid", coupon_id=breakdown.coupon_id, base_price=breakdown.calculated_price,
        )
        db.add(booking_financial)
        db.flush()
        _snapshot_platform_fee_rate(db, booking_financial)
        if coupon is not None:
            crud_coupon.redeem_coupon(
                db, coupon, booking.id, business_customer.id, breakdown.discount_amount, performed_by=current_user.id
            )
        db.commit()
        db.refresh(booking)
        return {"status": "Confirmed", "booking": crud_booking.serialize_booking(db, booking)}

    price_snapshot = _price_snapshot(
        breakdown, payload.payment_option, deposit_amount, balance_due,
        effective_platform_fee_rate(db, business.id), payload.resource_id,
    )
    hold = crud_hold.acquire_hold(
        db, business=business, branch=branch, branch_service=branch_service,
        booking_date=payload.booking_date, start_time=payload.start_time, resource_id=payload.resource_id,
        customer_id=business_customer.id, hold_type="CustomerCheckout", hold_minutes=CUSTOMER_HOLD_MINUTES,
        price_snapshot=price_snapshot, created_by=current_user.id,
    )

    order = razorpay_service.create_order(amount_due_now, "INR", receipt=f"hold-{hold.id}")
    payment = Payment(
        business_id=business.id, branch_id=branch.id, booking_hold_id=hold.id,
        payment_type="Deposit" if payload.payment_option == "Deposit" else "FullPayment",
        method="RazorpayOnline", status="Created", amount=amount_due_now, currency="INR",
        razorpay_order_id=order["id"], created_by=current_user.id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    settings = get_settings()
    return {
        "status": "AwaitingPayment", "hold_id": hold.id, "expires_at": hold.expires_at,
        "razorpay_order_id": order["id"], "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "amount_due": amount_due_now, "currency": "INR",
    }


def verify_customer_checkout_payment(db: Session, hold_id: int, payload, current_user: User) -> dict:
    hold = crud_hold.get_hold_or_404(db, hold_id)
    if hold.hold_type != "CustomerCheckout":
        raise HTTPException(status_code=404, detail="Hold not found")

    payment = db.query(Payment).filter(Payment.booking_hold_id == hold.id).order_by(Payment.id.desc()).first()
    if not payment:
        raise HTTPException(status_code=404, detail="No payment attempt found for this hold")

    _verify_and_capture_payment(db, payment, payload.razorpay_payment_id, payload.razorpay_signature)
    booking = _finalize_hold_to_booking(db, hold, payment)
    return {"status": "Confirmed", "booking": crud_booking.serialize_booking(db, booking)}


def _verify_and_capture_payment(db: Session, payment: Payment, razorpay_payment_id: str, razorpay_signature: str) -> None:
    """
    rule 11/26, reviewed and hardened in Phase 8: server-side signature
    verification is necessary but NOT sufficient. A valid signature only
    proves the `(order_id, payment_id)` pairing is authentic — it is not
    proof that the payment was actually captured (it can be produced for a
    merely-authorized, or even a since-refunded, payment). Every capture
    now requires an explicit server-to-server fetch against Razorpay's
    Payments API confirming `status == "captured"` and a matching amount,
    before this Payment row is ever marked Captured. The browser callback
    is never trusted at any point in this sequence.

    Idempotent: if this Payment was already Captured (e.g. the webhook
    beat the client's verify call), re-verifying is a safe no-op.
    """
    if payment.status == "Captured":
        return
    if payment.status != "Created":
        raise HTTPException(status_code=409, detail=f"Payment cannot be verified from status {payment.status}")

    if not razorpay_service.verify_payment_signature(payment.razorpay_order_id, razorpay_payment_id, razorpay_signature):
        payment.status = "Failed"
        db.commit()
        raise HTTPException(status_code=400, detail="Payment verification failed")

    # Signature alone is not capture proof (Phase 8 hardening) — confirm
    # against Razorpay directly.
    try:
        provider_payment = razorpay_service.fetch_payment(razorpay_payment_id)
    except Exception:
        payment.status = "Failed"
        db.commit()
        raise HTTPException(status_code=400, detail="Unable to confirm payment capture with the payment provider")

    if provider_payment.get("status") != "captured":
        payment.status = "Failed"
        db.commit()
        raise HTTPException(status_code=400, detail=f"Payment has not been captured (provider status: {provider_payment.get('status')})")

    if int(provider_payment.get("amount", -1)) != razorpay_service.to_paise(payment.amount):
        payment.status = "Failed"
        db.commit()
        raise HTTPException(status_code=400, detail="Captured amount does not match the expected amount")

    payment.razorpay_payment_id = razorpay_payment_id
    payment.verified_at = datetime.utcnow()
    payment.status = "Captured"


# -------------------------
# PHASE 6 — STAFF PAYMENT FLOWS (rule 12; ID-046)
# -------------------------

def _staff_checkout_common(db: Session, branch_id: int, payload, current_user: User):
    branch = get_branch_by_id(db, branch_id)
    business = crud_booking._require_branch_booking_staff_access(db, branch, current_user)
    branch_service = get_branch_service_or_404(db, payload.branch_service_id)
    if branch_service.branch_id != branch.id:
        raise HTTPException(status_code=400, detail="Service does not belong to this branch")
    crud_booking._check_bookable_state(business, branch, branch_service)

    business_customer = crud_booking._get_business_customer_or_404(db, payload.customer_id)
    if business_customer.business_id != business.id:
        raise HTTPException(status_code=400, detail="Customer does not belong to this business")
    if business_customer.status != "Active":
        raise HTTPException(status_code=409, detail="Customer is not Active")

    if getattr(payload, "base_price_override", None) is not None or getattr(payload, "final_price_override", None) is not None:
        if not getattr(payload, "price_override_reason", None):
            raise HTTPException(status_code=400, detail="A reason is required when overriding price (rule 9)")

    breakdown, coupon = compute_checkout_breakdown(
        db, business, branch, branch_service, business_customer.id, payload.booking_date, payload.coupon_code,
        getattr(payload, "base_price_override", None), getattr(payload, "final_price_override", None),
    )

    if payload.payment_option not in ("Full", "Deposit"):
        raise HTTPException(status_code=400, detail="payment_option must be Full or Deposit")

    deposit_amount = balance_due = None
    if payload.payment_option == "Deposit":
        _require_deposit_eligible(payload.booking_date, payload.start_time)
        deposit_pct = getattr(payload, "deposit_percentage_override", None)
        if deposit_pct is None:
            deposit_pct = STANDARD_DEPOSIT_PERCENTAGE
        elif not (Decimal("0") <= Decimal(deposit_pct) <= Decimal("100")):
            raise HTTPException(status_code=400, detail="deposit_percentage_override must be between 0 and 100")
        deposit_amount, balance_due = pricing.compute_deposit(breakdown.final_amount, Decimal(deposit_pct))
        amount_due_now = deposit_amount
    else:
        amount_due_now = breakdown.final_amount

    price_snapshot = _price_snapshot(
        breakdown, payload.payment_option, deposit_amount, balance_due,
        effective_platform_fee_rate(db, business.id), payload.resource_id,
        getattr(payload, "base_price_override", None), getattr(payload, "final_price_override", None),
        getattr(payload, "price_override_reason", None), current_user.id,
    )

    return business, branch, branch_service, business_customer, amount_due_now, price_snapshot


def staff_cash_checkout(db: Session, branch_id: int, payload, current_user: User) -> Booking:
    """Business rule 12.A — interactive/walk-in cash or offline payment."""
    business, branch, branch_service, business_customer, amount_due_now, price_snapshot = _staff_checkout_common(
        db, branch_id, payload, current_user
    )

    if Decimal(payload.cash_received) < amount_due_now:
        raise HTTPException(status_code=400, detail="Cash received is less than the amount due")
    change_returned = (Decimal(payload.cash_received) - amount_due_now).quantize(TWO_PLACES)

    hold = crud_hold.acquire_hold(
        db, business=business, branch=branch, branch_service=branch_service,
        booking_date=payload.booking_date, start_time=payload.start_time, resource_id=payload.resource_id,
        customer_id=business_customer.id, hold_type="StaffWalkIn", hold_minutes=STAFF_HOLD_MINUTES,
        price_snapshot=price_snapshot, created_by=current_user.id,
    )

    payment = Payment(
        business_id=business.id, branch_id=branch.id, booking_hold_id=hold.id,
        payment_type="Deposit" if payload.payment_option == "Deposit" else "FullPayment",
        method="Cash", status="Captured", amount=amount_due_now, currency="INR",
        cash_received=Decimal(payload.cash_received), change_returned=change_returned,
        verified_by=current_user.id, created_by=current_user.id, verified_at=datetime.utcnow(),
    )
    db.add(payment)
    db.flush()

    return _finalize_hold_to_booking(db, hold, payment)


def staff_email_link_checkout(db: Session, branch_id: int, payload, current_user: User) -> dict:
    """Business rule 12.B — staff sends an online payment link by email
    (typical use: booking taken over phone). Finalization happens later,
    when the customer pays and the Razorpay webhook confirms it (or staff
    later calls the same confirm-external path if the link is paid but the
    webhook is delayed)."""
    business, branch, branch_service, business_customer, amount_due_now, price_snapshot = _staff_checkout_common(
        db, branch_id, payload, current_user
    )

    hold = crud_hold.acquire_hold(
        db, business=business, branch=branch, branch_service=branch_service,
        booking_date=payload.booking_date, start_time=payload.start_time, resource_id=payload.resource_id,
        customer_id=business_customer.id, hold_type="StaffEmailLink", hold_minutes=STAFF_HOLD_MINUTES,
        price_snapshot=price_snapshot, created_by=current_user.id,
    )

    customer_email = _business_customer_email(db, business_customer)
    if not customer_email:
        raise HTTPException(status_code=400, detail="Customer has no email on file — use the direct external payment flow instead")

    link = razorpay_service.create_payment_link(
        amount_due_now, "INR", description=f"Booking payment ({branch_service.duration} min)",
        customer_name=customer_email, customer_email=customer_email,
    )

    # razorpay_order_id is reused to hold the Payment Link id (`plink_...`)
    # for this flow — there is no separate Order for a Payment Link, and
    # the webhook correlates `payment_link.paid` events back to this
    # Payment via that same id (see routers/payments_webhook.py).
    payment = Payment(
        business_id=business.id, branch_id=branch.id, booking_hold_id=hold.id,
        payment_type="Deposit" if payload.payment_option == "Deposit" else "FullPayment",
        method="RazorpayOnline", status="Created", amount=amount_due_now, currency="INR",
        razorpay_order_id=link["id"], created_by=current_user.id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    return {
        "status": "AwaitingPayment", "hold_id": hold.id, "expires_at": hold.expires_at,
        "payment_link": link.get("short_url"), "amount_due": amount_due_now, "currency": "INR",
    }


def staff_external_checkout(db: Session, branch_id: int, payload, current_user: User) -> dict:
    """Business rule 12.C — phone booking, no email; customer pays directly
    via the business's external UPI/bank details. Staff later confirms via
    `staff_confirm_external_payment`."""
    business, branch, branch_service, business_customer, amount_due_now, price_snapshot = _staff_checkout_common(
        db, branch_id, payload, current_user
    )

    hold = crud_hold.acquire_hold(
        db, business=business, branch=branch, branch_service=branch_service,
        booking_date=payload.booking_date, start_time=payload.start_time, resource_id=payload.resource_id,
        customer_id=business_customer.id, hold_type="StaffExternalManual", hold_minutes=STAFF_HOLD_MINUTES,
        price_snapshot=price_snapshot, created_by=current_user.id,
    )

    payment = Payment(
        business_id=business.id, branch_id=branch.id, booking_hold_id=hold.id,
        payment_type="Deposit" if payload.payment_option == "Deposit" else "FullPayment",
        method="ExternalManual", status="Created", amount=amount_due_now, currency="INR",
        created_by=current_user.id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    return {"status": "AwaitingPayment", "hold_id": hold.id, "expires_at": hold.expires_at}


def staff_confirm_external_payment(db: Session, hold_id: int, current_user: User) -> Booking:
    """Staff manually verifies an external/direct payment (rule 12.C) or a
    payment-link payment the webhook hasn't reconciled yet (rule 12.B)."""
    hold = crud_hold.get_hold_or_404(db, hold_id)
    branch = get_branch_by_id(db, hold.branch_id)
    crud_booking._require_branch_booking_staff_access(db, branch, current_user)

    payment = db.query(Payment).filter(Payment.booking_hold_id == hold.id).order_by(Payment.id.desc()).first()
    if not payment:
        raise HTTPException(status_code=404, detail="No payment attempt found for this hold")
    if payment.status not in ("Created", "Captured"):
        raise HTTPException(status_code=409, detail=f"Payment cannot be confirmed from status {payment.status}")

    if payment.status != "Captured":
        payment.status = "Captured"
        payment.verified_by = current_user.id
        payment.verified_at = datetime.utcnow()

    return _finalize_hold_to_booking(db, hold, payment)


def staff_reserve_without_payment(db: Session, branch_id: int, payload, current_user: User) -> Booking:
    """
    Business rule 8/13.D (ID-046 correction): Confirmed immediately, ₹0
    collected, no hold, no payment hold expiry, and — critically — no
    `BookingHold` row and no synthetic `Payment` row (RWP moves no money).
    The financial arrangement is represented entirely by
    `BookingFinancial.financial_status = "ReserveWithoutPayment"`
    (`balance_due_at = NULL`, so neither the 72h reminder nor the 48h
    deadline sweep ever touches it) plus the normal Booking
    history/audit trail (rule 8: "must show that the booking was reserved
    without payment").
    """
    booking = crud_booking.create_staff_booking(db, branch_id, payload, current_user)
    branch_service = get_branch_service_or_404(db, booking.branch_service_id)

    booking_financial = BookingFinancial(
        booking_id=booking.id, business_id=booking.business_id, branch_id=booking.branch_id,
        total_amount=Decimal(branch_service.price), amount_paid=Decimal("0"), deposit_required=False,
        financial_status="ReserveWithoutPayment", base_price=Decimal(branch_service.price),
    )
    db.add(booking_financial)
    db.flush()

    write_audit(
        db, business_id=booking.business_id, entity_type="Booking", entity_id=booking.id,
        action="BOOKING_RESERVED_WITHOUT_PAYMENT", performed_by=current_user.id,
        new_value="amount_paid=0", commit=False,
    )
    db.commit()
    db.refresh(booking)
    return booking


# -------------------------
# PHASE 7 — BALANCE PAYMENT (rule 6)
# -------------------------

def _get_awaiting_balance_financial_or_404(db: Session, booking_id: int) -> BookingFinancial:
    financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking_id).first()
    if not financial:
        raise HTTPException(status_code=404, detail="No financial record found for this booking")
    if financial.financial_status != "AwaitingBalance":
        raise HTTPException(status_code=409, detail=f"Booking is not awaiting a balance payment (status: {financial.financial_status})")
    return financial


def initiate_balance_payment(db: Session, booking_id: int, current_user: User) -> dict:
    booking = crud_booking.get_booking_or_404(db, booking_id)
    crud_booking._require_owning_customer(db, booking, current_user)
    crud_booking._require_active_status(booking)
    financial = _get_awaiting_balance_financial_or_404(db, booking_id)

    order = razorpay_service.create_order(Decimal(financial.balance_due), "INR", receipt=f"balance-{booking_id}")
    payment = Payment(
        business_id=booking.business_id, branch_id=booking.branch_id, booking_id=booking.id,
        payment_type="BalancePayment", method="RazorpayOnline", status="Created",
        amount=financial.balance_due, currency="INR", razorpay_order_id=order["id"], created_by=current_user.id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    settings = get_settings()
    return {
        "razorpay_order_id": order["id"], "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "amount_due": financial.balance_due, "currency": "INR",
    }


def verify_balance_payment(db: Session, booking_id: int, payload, current_user: User) -> dict:
    booking = crud_booking.get_booking_or_404(db, booking_id)
    crud_booking._require_owning_customer(db, booking, current_user)
    financial = _get_awaiting_balance_financial_or_404(db, booking_id)

    payment = (
        db.query(Payment)
        .filter(Payment.booking_id == booking.id, Payment.payment_type == "BalancePayment")
        .order_by(Payment.id.desc())
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="No balance payment attempt found for this booking")

    _verify_and_capture_payment(db, payment, payload.razorpay_payment_id, payload.razorpay_signature)

    # ID-056-style race guard: the 48h deadline sweep (enforce_balance_deadline)
    # may be racing this exact commit. Re-acquire the same resource advisory
    # lock and re-check under it, so whichever of the two transactions
    # commits first is authoritative — never both.
    crud_booking._acquire_resource_lock(db, booking.resource_id, booking.booking_date)
    db.refresh(financial)
    if financial.financial_status != "AwaitingBalance":
        # The deadline sweep won: the deposit is already forfeited and the
        # booking cancelled. Money was captured above — never silently
        # discarded — so it is refunded automatically, mirroring the
        # lost-hold exceptional path.
        if payment.method == "RazorpayOnline" and payment.razorpay_payment_id:
            try:
                refund_response = razorpay_service.create_refund(payment.razorpay_payment_id, Decimal(payment.amount))
                razorpay_refund_id = refund_response.get("id")
                refund_status, completed_at = _refund_status_from_response(refund_response)
            except Exception:
                razorpay_refund_id = None
                refund_status, completed_at = "Failed", None
        else:
            razorpay_refund_id = None
            refund_status, completed_at = "Failed", None
        db.add(Refund(
            business_id=booking.business_id, branch_id=booking.branch_id, booking_id=booking.id, payment_id=payment.id,
            calculated_amount=Decimal(payment.amount), final_amount=Decimal(payment.amount),
            reason="Automatic refund: balance payment captured after the 48-hour deadline had already been enforced",
            actor_id=current_user.id, role_snapshot="SYSTEM", refund_method="Gateway",
            razorpay_refund_id=razorpay_refund_id, status=refund_status, completed_at=completed_at,
        ))
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="The balance payment deadline had already passed and your booking was cancelled. Your payment is being refunded automatically.",
        )

    financial.amount_paid = Decimal(financial.amount_paid) + Decimal(payment.amount)
    financial.financial_status = "FullyPaid"
    _apply_platform_fee(db, payment, financial)

    write_audit(
        db, business_id=booking.business_id, entity_type="Booking", entity_id=booking.id,
        action="BOOKING_BALANCE_PAID", performed_by=current_user.id,
        new_value=f"amount_paid={financial.amount_paid}", commit=False,
    )
    db.commit()
    db.refresh(booking)
    return {"status": "FullyPaid", "booking": crud_booking.serialize_booking(db, booking)}


# -------------------------
# PHASE 7 — SCHEDULED BALANCE REMINDER / DEADLINE ENFORCEMENT (ID-048, ID-049)
# -------------------------

def find_bookings_due_for_balance_reminder(db: Session, now: Optional[datetime] = None) -> list:
    """rule 6: fires once, at 72h before the appointment (= 24h before the
    balance_due_at deadline, since balance_due_at = appointment - 48h)."""
    now = now or datetime.utcnow()
    reminder_threshold = now + timedelta(hours=BALANCE_REMINDER_HOURS_BEFORE - BALANCE_DEADLINE_HOURS_BEFORE)
    return (
        db.query(BookingFinancial)
        .filter(
            BookingFinancial.financial_status == "AwaitingBalance",
            BookingFinancial.balance_reminder_sent_at.is_(None),
            BookingFinancial.balance_due_at.isnot(None),
            BookingFinancial.balance_due_at <= reminder_threshold,
            BookingFinancial.balance_due_at > now,
        )
        .all()
    )


def mark_balance_reminder_sent(db: Session, financial: BookingFinancial) -> None:
    """Idempotency guard for the reminder job: once set, this row is never
    matched by `find_bookings_due_for_balance_reminder` again."""
    financial.balance_reminder_sent_at = datetime.utcnow()
    db.commit()


def find_bookings_past_balance_deadline(db: Session, now: Optional[datetime] = None) -> list:
    now = now or datetime.utcnow()
    return (
        db.query(BookingFinancial)
        .filter(
            BookingFinancial.financial_status == "AwaitingBalance",
            BookingFinancial.balance_due_at.isnot(None),
            BookingFinancial.balance_due_at <= now,
        )
        .all()
    )


def enforce_balance_deadline(db: Session, financial_id: int) -> bool:
    """
    Processes exactly one `BookingFinancial` row (ID-048's automatic
    Confirmed -> Cancelled transition). Re-acquires the booking's resource
    advisory lock and re-fetches the row before acting, so a customer's
    balance payment completing concurrently with this sweep can never both
    "win" (decision 16's payment-vs-deadline race) — whichever transaction
    commits first is authoritative, and the other observes the
    already-changed `financial_status` and safely no-ops. Idempotent: safe
    to call more than once for the same id.
    """
    financial = db.query(BookingFinancial).filter(BookingFinancial.id == financial_id).first()
    if not financial or financial.financial_status != "AwaitingBalance":
        return False

    booking = db.query(Booking).filter(Booking.id == financial.booking_id).first()
    if not booking or booking.status != "Confirmed":
        return False

    crud_booking._acquire_resource_lock(db, booking.resource_id, booking.booking_date)
    db.refresh(financial)
    if financial.financial_status != "AwaitingBalance":
        return False  # a concurrent balance payment won the race

    previous_state = crud_booking._booking_state_snapshot(booking)
    booking.status = "Cancelled"
    booking.cancellation_reason = "Balance payment deadline missed (automatic system cancellation)"
    new_state = crud_booking._booking_state_snapshot(booking)

    crud_booking._write_booking_history(db, booking, "Cancelled", previous_state, new_state, performed_by=None)
    write_audit(
        db, business_id=booking.business_id, entity_type="Booking", entity_id=booking.id,
        action="BOOKING_BALANCE_DEFAULTED", performed_by=None,
        previous_value=crud_booking._state_to_audit_string(previous_state),
        new_value=crud_booking._state_to_audit_string(new_state),
        reason=booking.cancellation_reason, commit=False,
    )

    financial.financial_status = "BalanceDefaulted"
    # rule 6/21: deposit is forfeited -> customer refund = 0, and the
    # platform fee already earned on the deposit is explicitly NOT reversed
    # (rule 21). A ₹0 refund is not a refund event, so no Refund row here.

    db.commit()
    return True


# -------------------------
# WEBHOOK RECONCILIATION (rule 12.B; ID-055/ID-056)
# -------------------------

def reconcile_webhook_event(db: Session, event_type: str, payload: dict) -> None:
    """
    Defense-in-depth / the only completion path for the staff emailed-
    payment-link flow (rule 12.B): the customer pays externally, and there
    is no client of ours present to call a `/verify` endpoint, so the
    webhook is the sole confirmation signal. For order-based flows
    (customer checkout, balance payment) this reconciles a Payment that a
    delayed/never-arriving client `/verify` call left stuck in `Created`.

    Payload field paths (`payload.payment.entity.id`,
    `payload.payment.entity.order_id`, `payload.payment_link.entity.id`)
    follow Razorpay's documented webhook payload structure; the exact
    shape should be spot-checked against a live payload before production
    use, since Razorpay's docs pages for the individual payload schemas
    were not directly fetchable during Phase 5-7 implementation (see the
    completion report).

    Never trusts the webhook signature check has already happened —
    callers (routers/payments_webhook.py) verify it before this runs.
    Idempotent: a Payment already Captured/Failed is left untouched.
    """
    entity = (payload or {}).get("payload", {})
    razorpay_payment_id = entity.get("payment", {}).get("entity", {}).get("id")
    order_id = entity.get("payment", {}).get("entity", {}).get("order_id")
    payment_link_id = entity.get("payment_link", {}).get("entity", {}).get("id")

    payment = None
    if order_id:
        payment = db.query(Payment).filter(Payment.razorpay_order_id == order_id).first()
    if payment is None and payment_link_id:
        payment = db.query(Payment).filter(Payment.razorpay_order_id == payment_link_id).first()
    if payment is None or payment.status != "Created":
        return  # nothing to reconcile, or already handled by a /verify call

    if event_type in ("payment.failed",):
        payment.status = "Failed"
        db.commit()
        return

    if event_type not in ("payment.captured", "payment_link.paid"):
        return

    payment.razorpay_payment_id = razorpay_payment_id
    payment.verified_at = datetime.utcnow()
    payment.status = "Captured"
    db.commit()

    if payment.booking_hold_id is not None:
        hold = db.query(BookingHold).filter(BookingHold.id == payment.booking_hold_id).first()
        if hold is not None:
            try:
                _finalize_hold_to_booking(db, hold, payment)
            except HTTPException:
                pass  # already handled (refund issued) inside _finalize_hold_to_booking's lost-hold path
    elif payment.booking_id is not None and payment.payment_type == "BalancePayment":
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == payment.booking_id).first()
        if financial is not None and financial.financial_status == "AwaitingBalance":
            financial.amount_paid = Decimal(financial.amount_paid) + Decimal(payment.amount)
            financial.financial_status = "FullyPaid"
            _apply_platform_fee(db, payment, financial)
            db.commit()


_REFUND_LIFECYCLE_EVENTS = ("refund.processed", "refund.failed")


def reconcile_refund_webhook_event(db: Session, event_type: str, payload: dict) -> None:
    """
    Post-Phase-10 hardening: Razorpay refund processing is asynchronous
    (verified against current docs — the lifecycle is `refund.created` ->
    `refund.processed` | `refund.failed`, with a separate
    `refund.speed_changed` event that never changes completion state).
    Every `create_refund` call site in this module now records a refund as
    `Initiated` unless the creation response itself already reported
    `"processed"`/`"failed"` (see `_refund_status_from_response`); this
    function applies the deferred confirmation when it arrives.

    Idempotent and safe under duplicate/out-of-order delivery: only a
    Refund currently `Initiated` is ever transitioned — a refund already
    `Completed` or `Failed` (whether from a synchronous response or a
    prior webhook) is left untouched no matter which event arrives, how
    many times, or in what order, so `BookingFinancial.amount_refunded`
    can never be incremented twice for the same refund. `refund.created`
    is intentionally a no-op here: we already create the Refund row
    ourselves at the moment we call the API, so this event only ever
    confirms something we already have, never something to newly create
    (creating a webhook-driven Refund row here could produce one with no
    corresponding booking/payment context).

    Payload path (`payload.refund.entity.id`) follows Razorpay's
    documented refund webhook payload structure
    (razorpay.com/docs/webhooks/refunds/); as with the payment webhook
    reconciliation above, the exact shape should be spot-checked against a
    live payload before production use, since the docs page for the full
    payload schema was not directly fetchable during implementation.
    """
    if event_type not in _REFUND_LIFECYCLE_EVENTS:
        return

    entity = (payload or {}).get("payload", {})
    razorpay_refund_id = entity.get("refund", {}).get("entity", {}).get("id")
    if not razorpay_refund_id:
        return

    refund = db.query(Refund).filter(Refund.razorpay_refund_id == razorpay_refund_id).first()
    if refund is None or refund.status != "Initiated":
        return  # unknown refund, or already confirmed -> safe no-op

    if event_type == "refund.failed":
        refund.status = "Failed"
        db.commit()
        return

    # refund.processed
    refund.status = "Completed"
    refund.completed_at = datetime.utcnow()

    if refund.booking_id is not None:
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == refund.booking_id).first()
        if financial is not None:
            financial.amount_refunded = Decimal(financial.amount_refunded) + Decimal(refund.final_amount)

    db.commit()


# -------------------------
# PHASE 8 — CANCELLATION REFUND CALCULATION (rule 2/15/16; ID-047)
# -------------------------

CANCELLATION_FULL_REFUND_HOURS = 48
CANCELLATION_PARTIAL_REFUND_HOURS = 24
CANCELLATION_PARTIAL_REFUND_PERCENTAGE = Decimal("50")


def calculate_cancellation_refund_percentage(hours_before_appointment: float) -> Decimal:
    """rule 2/15: applied to money ACTUALLY PAID, never the unpaid total."""
    if hours_before_appointment >= CANCELLATION_FULL_REFUND_HOURS:
        return Decimal("100")
    if hours_before_appointment >= CANCELLATION_PARTIAL_REFUND_HOURS:
        return CANCELLATION_PARTIAL_REFUND_PERCENTAGE
    return Decimal("0")


_REFUND_COMMITTED_STATUSES = ("Completed", "Initiated")  # everything except Failed counts as "spoken for"


def _total_captured_and_refunded(db: Session, booking_id: int):
    """Returns (total_captured, total_already_refunded) for a booking,
    across every payment method — the ceiling any refund (calculated or
    overridden) must never exceed (rule 16). Counts `Initiated` (a refund
    request Razorpay has accepted but not yet confirmed complete)
    alongside `Completed` — Razorpay refunds are asynchronous, so a
    still-pending refund has already committed that money; treating it as
    "not yet refunded" here would let a second, concurrent refund attempt
    exceed the true refundable ceiling before the first one's webhook
    confirmation ever arrives."""
    captured = db.query(Payment).filter(Payment.booking_id == booking_id, Payment.status == "Captured").all()
    total_captured = sum((Decimal(p.amount) for p in captured), Decimal("0"))
    committed_refunds = (
        db.query(Refund)
        .filter(Refund.booking_id == booking_id, Refund.status.in_(_REFUND_COMMITTED_STATUSES))
        .all()
    )
    total_refunded = sum((Decimal(r.final_amount) for r in committed_refunds), Decimal("0"))
    return total_captured, total_refunded


def _distribute_and_process_refund(
    db: Session, booking: Booking, refund_amount: Decimal, actor_id: int, role_snapshot: str, reason: str
) -> list:
    """
    Distributes `refund_amount` across the booking's Captured payments (in
    creation order), routing each portion per ID-053 (Gateway for
    RazorpayOnline, Manual for everything else — cash/external payments
    are refunded by staff outside the system and recorded here as
    Completed immediately, mirroring the same precedent
    `staff_cash_checkout` already established for recording cash
    collection). Never refunds more against any one payment than that
    payment's own remaining refundable amount (rule 16) — the caller is
    responsible for capping `refund_amount` at the booking-wide refundable
    ceiling (`_total_captured_and_refunded`) before calling this.

    Reverses the proportional platform fee earned on each affected online
    payment (ID-051/rule 20), using that payment's own snapshotted fee
    amount — never today's platform-fee configuration.
    """
    remaining = Decimal(refund_amount)
    refunds = []

    payments = db.query(Payment).filter(Payment.booking_id == booking.id, Payment.status == "Captured").order_by(Payment.id).all()
    for payment in payments:
        if remaining <= 0:
            break
        already_refunded_for_payment = (
            db.query(Refund)
            .filter(Refund.payment_id == payment.id, Refund.status.in_(_REFUND_COMMITTED_STATUSES))
            .all()
        )
        refunded_so_far = sum((Decimal(r.final_amount) for r in already_refunded_for_payment), Decimal("0"))
        refundable = Decimal(payment.amount) - refunded_so_far
        if refundable <= 0:
            continue
        portion = min(remaining, refundable)

        if payment.method == "RazorpayOnline" and payment.razorpay_payment_id:
            try:
                response = razorpay_service.create_refund(payment.razorpay_payment_id, portion)
                razorpay_refund_id = response.get("id")
                status, completed_at = _refund_status_from_response(response)
            except Exception:
                razorpay_refund_id = None
                status, completed_at = "Failed", None
            refund_method = "Gateway"
        else:
            # Cash/manual refunds are handed back by staff outside the
            # system, synchronously with recording them — there is no
            # asynchronous provider confirmation to await, matching the
            # existing `staff_cash_checkout` precedent for cash collection.
            razorpay_refund_id = None
            status, completed_at = "Completed", datetime.utcnow()
            refund_method = "Manual"

        # Fee reversal is calculated here regardless of status (it reflects
        # what this refund portion implies about earned fee), but the
        # BookingFinancial.amount_refunded accounting below only counts a
        # refund once its status is actually Completed, so a still-pending
        # (Initiated) online refund cannot double up with its own later
        # webhook confirmation.
        fee_reversal = None
        if payment.method == "RazorpayOnline" and payment.platform_fee_amount is not None:
            fee_reversal = (Decimal(payment.platform_fee_amount) * portion / Decimal(payment.amount)).quantize(TWO_PLACES)

        refund = Refund(
            business_id=booking.business_id, branch_id=booking.branch_id, booking_id=booking.id, payment_id=payment.id,
            calculated_amount=portion, final_amount=portion, reason=reason, actor_id=actor_id, role_snapshot=role_snapshot,
            refund_method=refund_method, razorpay_refund_id=razorpay_refund_id, status=status,
            platform_fee_reversal_amount=fee_reversal, completed_at=completed_at,
        )
        db.add(refund)
        db.flush()
        refunds.append(refund)

        if status in _REFUND_COMMITTED_STATUSES:
            # Committed (Completed now, or Initiated and awaiting the
            # provider's async confirmation) -> this portion of the
            # requested refund_amount is spoken for either way, so the
            # remaining shortfall must not be re-attempted against another
            # payment (that would risk over-refunding once a pending one
            # later confirms).
            remaining -= portion

    if refunds:
        financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking.id).first()
        if financial is not None:
            # Deliberately "Completed" only (not the wider committed-status
            # set used above) — amount_refunded is the confirmed-money
            # ledger. A still-Initiated refund's contribution is added
            # later, exactly once, by reconcile_refund_webhook_event when
            # its refund.processed confirmation arrives.
            completed_total = sum((Decimal(r.final_amount) for r in refunds if r.status == "Completed"), Decimal("0"))
            financial.amount_refunded = Decimal(financial.amount_refunded) + completed_total

    return refunds


def cancel_customer_booking_with_refund(db: Session, booking_id: int, payload, current_user: User) -> dict:
    """rule 2/3/15: customer cancellation, refund calculated against money
    actually paid using the frozen time-bracket percentages."""
    booking_before = crud_booking.get_booking_or_404(db, booking_id)
    hours_before = (appointment_datetime(booking_before.booking_date, booking_before.start_time) - datetime.utcnow()).total_seconds() / 3600.0

    booking = crud_booking.cancel_booking(db, booking_id, payload, current_user, actor_is_customer=True)

    refund_result = _apply_cancellation_refund(
        db, booking, hours_before, current_user.id, "CUSTOMER", refund_override_amount=None, reason=None,
    )
    return {"booking": crud_booking.serialize_booking(db, booking), "refund": refund_result}


def staff_cancel_booking_with_refund(db: Session, booking_id: int, payload, current_user: User) -> dict:
    """rule 4/16: staff cancellation is unrestricted and a reason is
    optional by default (PRD §20's baseline, unchanged) — a customer can
    always cancel, so a plain staff cancellation using the normal
    calculated refund is not "overriding" anything. A reason becomes
    mandatory only when actually overriding the calculated refund amount
    (enforced in `_apply_cancellation_refund`), matching rule 4/16's
    override-specific wording precisely."""
    booking_before = crud_booking.get_booking_or_404(db, booking_id)
    hours_before = (appointment_datetime(booking_before.booking_date, booking_before.start_time) - datetime.utcnow()).total_seconds() / 3600.0
    role_snapshot = _actor_role_label(db, booking_before.business_id, current_user.id)

    booking = crud_booking.cancel_booking(db, booking_id, payload, current_user, actor_is_customer=False)

    refund_result = _apply_cancellation_refund(
        db, booking, hours_before, current_user.id, role_snapshot,
        refund_override_amount=getattr(payload, "refund_override_amount", None), reason=payload.reason,
    )
    return {"booking": crud_booking.serialize_booking(db, booking), "refund": refund_result}


def _apply_cancellation_refund(
    db: Session, booking: Booking, hours_before: float, actor_id: int, role_snapshot: str,
    refund_override_amount, reason,
) -> Optional[dict]:
    # Phase 8 concurrency/idempotency guard: two concurrent (or retried)
    # cancellation requests for the same booking must never both process a
    # refund. The lock serializes them; the audit-log check makes whichever
    # arrives second (after the first has committed) a safe no-op replay
    # of the already-recorded outcome rather than a second refund.
    _acquire_booking_lock(db, booking.id)
    existing = _existing_cancellation_refund_result(db, booking.id)
    if existing is not None:
        refunds = db.query(Refund).filter(Refund.booking_id == booking.id).order_by(Refund.id).all()
        # Includes Initiated (pending provider confirmation) alongside
        # Completed, consistent with how committed-refund totals are
        # computed everywhere else in this module.
        final_amount = sum((Decimal(r.final_amount) for r in refunds if r.status in _REFUND_COMMITTED_STATUSES), Decimal("0"))
        return {
            "calculated_percentage": None, "calculated_amount": None,
            "final_amount": str(final_amount), "overridden": existing.action == "BOOKING_REFUND_OVERRIDDEN",
            "refund_ids": [r.id for r in refunds], "already_processed": True,
        }

    financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking.id).first()
    if financial is None or Decimal(financial.amount_paid) <= 0:
        return None  # nothing was ever paid (e.g. Reserve Without Payment) -> nothing to refund

    calculated_percentage = calculate_cancellation_refund_percentage(hours_before)
    calculated_amount = (Decimal(financial.amount_paid) * calculated_percentage / Decimal("100")).quantize(TWO_PLACES)

    total_captured, total_already_refunded = _total_captured_and_refunded(db, booking.id)
    max_refundable = total_captured - total_already_refunded

    final_amount = min(calculated_amount, max_refundable) if max_refundable > 0 else Decimal("0")
    overridden = False
    if refund_override_amount is not None:
        override_amount = Decimal(refund_override_amount)
        if override_amount != calculated_amount:
            if not reason:
                raise HTTPException(status_code=400, detail="A reason is required to override the calculated refund amount")
            if override_amount > max_refundable:
                raise HTTPException(status_code=400, detail=f"Refund override cannot exceed the refundable amount ({max_refundable})")
            if override_amount < 0:
                raise HTTPException(status_code=400, detail="Refund override cannot be negative")
            final_amount = override_amount
            overridden = True

    refunds = []
    if final_amount > 0:
        refunds = _distribute_and_process_refund(
            db, booking, final_amount, actor_id, role_snapshot,
            reason=reason or f"Customer cancellation ({hours_before:.1f}h notice, {calculated_percentage}% policy)",
        )

    write_audit(
        db, business_id=booking.business_id, entity_type="Booking", entity_id=booking.id,
        action="BOOKING_REFUND_OVERRIDDEN" if overridden else "BOOKING_CANCELLATION_REFUND_CALCULATED",
        performed_by=actor_id, previous_value=f"calculated={calculated_amount}", new_value=f"final={final_amount}",
        reason=reason, commit=False,
    )
    db.commit()

    return {
        "calculated_percentage": str(calculated_percentage), "calculated_amount": str(calculated_amount),
        "final_amount": str(final_amount), "overridden": overridden,
        "refund_ids": [r.id for r in refunds],
    }


# -------------------------
# PHASE 8 — RESCHEDULE PRICE DIFFERENCE (rule 14)
# -------------------------

def apply_reschedule_price_difference(db: Session, booking: Booking, actor_id: int, role_snapshot: str) -> Optional[dict]:
    """
    rule 14: rescheduling normally retains the same service, but if the
    service's current effective price differs from what this booking's
    amount was locked in at, the difference is collected (price increased)
    or refunded (price decreased). Called after `crud_booking.
    reschedule_booking` has already committed the schedule change — a
    separate, best-effort financial follow-on step, consistent with the
    rest of this module's multi-commit checkout flows.
    """
    financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking.id).first()
    if financial is None:
        return None

    branch_service = get_branch_service_or_404(db, booking.branch_service_id)
    new_effective_price = Decimal(branch_service.price)
    previous_total = Decimal(financial.total_amount)
    diff = (new_effective_price - previous_total).quantize(TWO_PLACES)
    if diff == 0:
        return None

    db.add(BookingPriceAdjustment(
        booking_id=booking.id, adjustment_type="ReschedulePriceDiff",
        previous_value=previous_total, new_value=new_effective_price,
        actor_id=actor_id, role_snapshot=role_snapshot, reason="Reschedule price difference (service price changed)",
    ))
    financial.total_amount = new_effective_price

    result = {"previous_amount": str(previous_total), "new_amount": str(new_effective_price), "difference": str(diff)}

    if diff > 0:
        order = razorpay_service.create_order(diff, "INR", receipt=f"reschedule-diff-{booking.id}")
        payment = Payment(
            business_id=booking.business_id, branch_id=booking.branch_id, booking_id=booking.id,
            payment_type="RescheduleCollection", method="RazorpayOnline", status="Created",
            amount=diff, currency="INR", razorpay_order_id=order["id"], created_by=actor_id,
        )
        db.add(payment)
        db.commit()
        settings = get_settings()
        result.update({
            "action": "CollectDifference", "amount_due": str(diff),
            "razorpay_order_id": order["id"], "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        })
    else:
        requested_refund = -diff
        total_captured, total_already_refunded = _total_captured_and_refunded(db, booking.id)
        max_refundable = total_captured - total_already_refunded
        refund_amount = min(requested_refund, max_refundable) if max_refundable > 0 else Decimal("0")
        refunds = []
        if refund_amount > 0:
            refunds = _distribute_and_process_refund(
                db, booking, refund_amount, actor_id, role_snapshot, reason="Reschedule price decrease"
            )
        db.commit()
        result.update({"action": "RefundIssued", "amount_refunded": str(refund_amount), "refund_ids": [r.id for r in refunds]})

    return result


def verify_reschedule_price_difference_payment(db: Session, booking_id: int, payload, current_user: User) -> dict:
    booking = crud_booking.get_booking_or_404(db, booking_id)
    crud_booking._require_owning_customer(db, booking, current_user)

    payment = (
        db.query(Payment)
        .filter(Payment.booking_id == booking.id, Payment.payment_type == "RescheduleCollection", Payment.status == "Created")
        .order_by(Payment.id.desc())
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="No reschedule price-difference payment found for this booking")

    _verify_and_capture_payment(db, payment, payload.razorpay_payment_id, payload.razorpay_signature)

    financial = db.query(BookingFinancial).filter(BookingFinancial.booking_id == booking.id).first()
    financial.amount_paid = Decimal(financial.amount_paid) + Decimal(payment.amount)
    _apply_platform_fee(db, payment, financial)

    write_audit(
        db, business_id=booking.business_id, entity_type="Booking", entity_id=booking.id,
        action="BOOKING_RESCHEDULE_DIFFERENCE_PAID", performed_by=current_user.id,
        new_value=f"amount={payment.amount}", commit=False,
    )
    db.commit()
    db.refresh(booking)
    return {"status": "Confirmed", "booking": crud_booking.serialize_booking(db, booking)}


def reschedule_customer_booking(db: Session, booking_id: int, payload, current_user: User) -> dict:
    booking = crud_booking.reschedule_booking(db, booking_id, payload, current_user, actor_is_customer=True)
    price_result = apply_reschedule_price_difference(db, booking, current_user.id, "CUSTOMER")
    return {"booking": crud_booking.serialize_booking(db, booking), "price_adjustment": price_result}


def reschedule_staff_booking(db: Session, booking_id: int, payload, current_user: User) -> dict:
    booking = crud_booking.reschedule_booking(db, booking_id, payload, current_user, actor_is_customer=False)
    role_snapshot = _actor_role_label(db, booking.business_id, current_user.id)
    price_result = apply_reschedule_price_difference(db, booking, current_user.id, role_snapshot)
    return {"booking": crud_booking.serialize_booking(db, booking), "price_adjustment": price_result}
