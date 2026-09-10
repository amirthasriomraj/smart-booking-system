from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from datetime import date as DateType, time as TimeType, datetime
from decimal import Decimal

from schemas_booking import BookingResponse


class CustomerCheckoutRequest(BaseModel):
    branch_service_id: int
    booking_date: DateType
    start_time: TimeType
    resource_id: Optional[int] = None
    coupon_code: Optional[str] = None
    payment_option: str = "Full"  # Full / Deposit

    model_config = ConfigDict(extra="forbid")


class CustomerCheckoutSummaryResponse(BaseModel):
    """Phase 1 of the customer checkout review flow (manual-acceptance
    fix): the server-authoritative price/coupon/deposit breakdown for the
    selected slot — selecting a slot never creates a Booking, and never
    contacts Razorpay. `kind` is "Hold" (a real 6-minute CustomerCheckout
    hold was created, no payment attempt yet; the customer clicks
    Proceed to Pay next, which calls `create_customer_checkout_payment` to
    create the Razorpay order, then finalizes via the existing verify
    endpoint using `hold_id`) or "NoPaymentRequired" (a 100%-off coupon
    made the amount due ₹0 — rule 10/13 — so no hold was created at all;
    confirm via the existing one-shot /customer/checkout endpoint, which
    already implements that frozen "skip Razorpay entirely" path
    unchanged). `razorpay_order_id`/`razorpay_key_id` are always null here
    — they are only ever populated by `create_customer_checkout_payment`'s
    own response."""
    kind: str
    hold_id: Optional[int] = None
    expires_at: Optional[datetime] = None
    branch_service_id: int
    resource_id: Optional[int] = None
    booking_date: DateType
    start_time: TimeType
    calculated_price: Decimal
    discount_amount: Decimal
    coupon_code: Optional[str] = None
    final_amount: Decimal
    payment_option: str
    amount_due_now: Decimal
    deposit_amount: Optional[Decimal] = None
    deposit_percentage: Optional[Decimal] = None
    balance_due: Optional[Decimal] = None
    balance_due_at: Optional[datetime] = None
    currency: str
    razorpay_order_id: Optional[str] = None
    razorpay_key_id: Optional[str] = None


class CustomerCheckoutRefreshRequest(BaseModel):
    """Recomputes the customer checkout summary for the SAME slot after a
    pricing-affecting input changes (coupon, payment option) — the slot
    itself is always taken from the hold being refreshed, never from this
    request."""
    coupon_code: Optional[str] = None
    payment_option: str = "Full"  # Full / Deposit

    model_config = ConfigDict(extra="forbid")


class StaffCheckoutRequestBase(BaseModel):
    customer_id: int
    branch_service_id: int
    booking_date: DateType
    start_time: TimeType
    resource_id: Optional[int] = None
    coupon_code: Optional[str] = None
    payment_option: str = "Full"  # Full / Deposit
    deposit_percentage_override: Optional[Decimal] = None
    base_price_override: Optional[Decimal] = None
    final_price_override: Optional[Decimal] = None
    price_override_reason: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class StaffCheckoutSummaryResponse(BaseModel):
    """Phase 1 of the staff checkout review flow: the server-authoritative
    breakdown for an already-acquired 10-minute StaffCheckout hold —
    selecting a slot never creates a Booking by itself. The staff member
    reviews this (payment method is chosen next), then finalizes via one
    of the hold-based finalize endpoints using this same hold_id."""
    hold_id: int
    expires_at: datetime
    customer_id: int
    branch_service_id: int
    resource_id: int
    booking_date: DateType
    start_time: TimeType
    end_time: TimeType
    calculated_price: Decimal
    base_price_override: Optional[Decimal] = None
    discount_amount: Decimal
    coupon_code: Optional[str] = None
    final_price_override: Optional[Decimal] = None
    final_amount: Decimal
    payment_option: str
    amount_due_now: Decimal
    deposit_amount: Optional[Decimal] = None
    balance_due: Optional[Decimal] = None
    balance_due_at: Optional[datetime] = None
    currency: str


class StaffCheckoutRefreshRequest(BaseModel):
    """Recomputes the Booking & Payment Summary for an already-acquired
    StaffCheckout hold after a pricing-affecting input changes (coupon,
    base/final price override, payment option) — the slot itself
    (customer/service/date/time/resource) is always taken from the hold
    being refreshed, never from this request."""
    coupon_code: Optional[str] = None
    payment_option: str = "Full"  # Full / Deposit
    deposit_percentage_override: Optional[Decimal] = None
    base_price_override: Optional[Decimal] = None
    final_price_override: Optional[Decimal] = None
    price_override_reason: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class StaffCashFinalizeRequest(BaseModel):
    cash_received: Decimal

    model_config = ConfigDict(extra="forbid")


class StaffReserveWithoutPaymentRequest(BaseModel):
    customer_id: int
    branch_service_id: int
    booking_date: DateType
    start_time: TimeType
    resource_id: Optional[int] = None

    model_config = ConfigDict(extra="forbid")


class PaymentVerifyRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_signature: str

    model_config = ConfigDict(extra="forbid")


class CheckoutResponse(BaseModel):
    status: str
    hold_id: Optional[int] = None
    expires_at: Optional[datetime] = None
    razorpay_order_id: Optional[str] = None
    razorpay_key_id: Optional[str] = None
    payment_link: Optional[str] = None
    amount_due: Optional[Decimal] = None
    currency: Optional[str] = None
    booking: Optional[Any] = None
    # Cash finalize only — read back from the Payment row the backend just
    # persisted, never recomputed in the browser.
    cash_received: Optional[Decimal] = None
    amount_charged: Optional[Decimal] = None
    change_returned: Optional[Decimal] = None

    model_config = ConfigDict(extra="allow")


class BalancePaymentInitiateResponse(BaseModel):
    razorpay_order_id: str
    razorpay_key_id: str
    amount_due: Decimal
    currency: str


class PaymentHistoryEntry(BaseModel):
    id: int
    payment_type: str
    method: str
    status: str
    amount: Decimal
    currency: str
    cash_received: Optional[Decimal] = None
    change_returned: Optional[Decimal] = None
    created_at: datetime
    verified_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RefundHistoryEntry(BaseModel):
    id: int
    payment_id: int
    calculated_amount: Decimal
    overridden_amount: Optional[Decimal] = None
    final_amount: Decimal
    reason: Optional[str] = None
    refund_method: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BookingPaymentHistoryResponse(BaseModel):
    payments: list[PaymentHistoryEntry]
    refunds: list[RefundHistoryEntry]


class StaffRefundRequest(BaseModel):
    """Standalone refund, independent of cancellation (partial or full)."""
    amount: Decimal
    reason: str

    model_config = ConfigDict(extra="forbid")


class StandaloneRefundResponse(BaseModel):
    """The booking is echoed back unchanged (status/cancellation_reason are
    never touched by a standalone refund) alongside the refund outcome."""
    booking: BookingResponse
    refund: dict


class BookingActionResponse(BookingResponse):
    """Cancellation/reschedule response. Extends `BookingResponse` (the
    booking's own fields stay top-level, exactly as the pre-Milestone-8
    cancel/reschedule endpoints already returned them, for backward
    compatibility) with whatever financial consequence resulted (refund
    calculation/override, or a reschedule price-difference collect/refund)
    — both `None` for actions with no financial effect (e.g. a Reserve
    Without Payment booking, or a reschedule with no price change)."""
    refund: Optional[dict] = None
    price_adjustment: Optional[dict] = None
