from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from datetime import datetime, date as DateType, time as TimeType
from decimal import Decimal


# -------------------------
# AVAILABILITY (PRD §14.6, §16.3; TAS Part 4 §3)
# -------------------------

class AvailabilitySlot(BaseModel):
    start_time: TimeType
    end_time: TimeType
    available_resource_ids: List[int]

    model_config = ConfigDict(from_attributes=True)


class AvailabilityResponse(BaseModel):
    branch_id: int
    branch_service_id: int
    date: DateType
    slots: List[AvailabilitySlot]


# -------------------------
# BOOKING CREATION (PRD §18.4)
# -------------------------

class StaffBookingCreateRequest(BaseModel):
    """Staff-created booking (walk-in or on behalf of an existing BusinessCustomer)."""
    customer_id: int  # BusinessCustomer.id
    branch_service_id: int
    booking_date: DateType
    start_time: TimeType
    resource_id: Optional[int] = None  # ID-039: omitted -> automatic "First Available"

    model_config = ConfigDict(extra="forbid")


class CustomerBookingCreateRequest(BaseModel):
    """Customer self-booking; the caller's own BusinessCustomer is used (auto-provisioned per ID-040)."""
    branch_service_id: int
    booking_date: DateType
    start_time: TimeType
    resource_id: Optional[int] = None  # ID-039

    model_config = ConfigDict(extra="forbid")


# -------------------------
# RESCHEDULE / CANCEL / REASSIGN (PRD §19, §20, §21)
# -------------------------

class BookingRescheduleRequest(BaseModel):
    booking_date: DateType
    start_time: TimeType
    resource_id: Optional[int] = None  # PRD §19.1: date, time and/or resource
    reason: Optional[str] = None  # Milestone 8 ID-047: mandatory when a staff actor overrides the customer policy

    model_config = ConfigDict(extra="forbid")


class StaffRescheduleRequest(BookingRescheduleRequest):
    """Staff-only: lets an authorized staff member explicitly choose the
    payment method used to collect/refund a genuine reschedule price
    difference (rule 14), instead of defaulting to the booking's existing
    payment method. `payment_method` mirrors the existing collection
    vocabulary — "RazorpayOnline" (order + checkout widget), "EmailPaymentLink"
    (a Razorpay payment link emailed to the customer; still stored as a
    RazorpayOnline Payment, exactly like the existing staff checkout
    email-link flow), "Cash", or "ExternalManual" (Direct UPI/Bank
    Transfer) — only for a genuine INCREASE; a decrease is always refunded
    against the booking's actual captured payment(s), unaffected by this
    field. `override_reason` is required whenever `payment_method` differs
    from the booking's existing default method (or when there is no prior
    payment to default from, e.g. Reserve Without Payment) and is recorded
    in the audit log. `cash_received` is required when `payment_method` is
    "Cash". This is deliberately NOT part of `BookingRescheduleRequest` —
    customer self-reschedule must never be able to choose a payment
    method."""
    payment_method: Optional[str] = None
    override_reason: Optional[str] = None
    cash_received: Optional[Decimal] = None

    model_config = ConfigDict(extra="forbid")


class BookingCancelRequest(BaseModel):
    reason: Optional[str] = None  # PRD §20: optional for customers; Milestone 8 ID-047 makes it mandatory for staff
    refund_override_amount: Optional[Decimal] = None  # Milestone 8 rule 16: Owner/Branch Manager only

    model_config = ConfigDict(extra="forbid")


class BookingReassignResourceRequest(BaseModel):
    resource_id: int  # PRD §21: manual override, no date/time change

    model_config = ConfigDict(extra="forbid")


# -------------------------
# RESPONSES
# -------------------------

class BookingResponse(BaseModel):
    id: int
    business_id: int
    branch_id: int
    branch_name: Optional[str] = None
    customer_id: int
    customer_number: Optional[str] = None
    customer_name: Optional[str] = None
    branch_service_id: int
    service_name: Optional[str] = None
    resource_id: int
    resource_name: Optional[str] = None
    booking_date: DateType
    start_time: TimeType
    end_time: TimeType
    status: str
    cancellation_reason: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_by: int
    created_at: datetime
    updated_at: datetime

    # Milestone 8 financial state (None for a pre-M8/legacy booking that
    # never went through checkout and has no BookingFinancial row at all —
    # distinct from a real financial_status value like
    # "ReserveWithoutPayment"). See BookingFinancial's docstring for the
    # financial_status transition table.
    financial_status: Optional[str] = None
    total_amount: Optional[Decimal] = None
    amount_paid: Optional[Decimal] = None
    amount_refunded: Optional[Decimal] = None
    deposit_amount: Optional[Decimal] = None
    balance_due: Optional[Decimal] = None
    balance_due_at: Optional[datetime] = None
    # How much of what was actually captured could still be refunded right
    # now (captured payments minus committed refunds) — 0 for a booking
    # with no BookingFinancial row (e.g. pre-M8/legacy). Lets the UI
    # hide/disable a standalone Refund action once nothing remains.
    refundable_amount: Decimal = Decimal("0")

    model_config = ConfigDict(from_attributes=True)


class PaginatedBookings(BaseModel):
    items: List[BookingResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class BookingHistoryEntryResponse(BaseModel):
    id: int
    booking_id: int
    action: str
    previous_state: Optional[Any] = None
    new_state: Optional[Any] = None
    performed_by: int
    performed_at: datetime

    model_config = ConfigDict(from_attributes=True)
