from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from datetime import datetime, date as DateType, time as TimeType


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

    model_config = ConfigDict(extra="forbid")


class BookingCancelRequest(BaseModel):
    reason: Optional[str] = None  # PRD §20: optional cancellation reason

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

    model_config = ConfigDict(from_attributes=True)


class BookingHistoryEntryResponse(BaseModel):
    id: int
    booking_id: int
    action: str
    previous_state: Optional[Any] = None
    new_state: Optional[Any] = None
    performed_by: int
    performed_at: datetime

    model_config = ConfigDict(from_attributes=True)
