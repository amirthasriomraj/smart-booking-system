from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from datetime import date as DateType, time as TimeType, datetime
from decimal import Decimal


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
