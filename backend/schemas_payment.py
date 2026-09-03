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


class StaffCashCheckoutRequest(StaffCheckoutRequestBase):
    cash_received: Decimal


class StaffEmailLinkCheckoutRequest(StaffCheckoutRequestBase):
    pass


class StaffExternalCheckoutRequest(StaffCheckoutRequestBase):
    pass


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

    model_config = ConfigDict(extra="allow")


class BalancePaymentInitiateResponse(BaseModel):
    razorpay_order_id: str
    razorpay_key_id: str
    amount_due: Decimal
    currency: str


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
