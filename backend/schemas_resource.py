from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime, time as TimeType


# -------------------------
# RESOURCE CATEGORY (ID-015)
# -------------------------

class ResourceCategoryCreateRequest(BaseModel):
    category_name: str
    description: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class ResourceCategoryUpdateRequest(BaseModel):
    category_name: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class ResourceCategoryResponse(BaseModel):
    id: int
    business_id: int
    category_name: str
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# RESOURCE (PRD §14.3-14.5, ID-012, ID-013)
# -------------------------

class ResourceCreateRequest(BaseModel):
    resource_name: str
    resource_category_id: int
    code: Optional[str] = None
    description: Optional[str] = None
    requires_login: bool = False
    max_bookings_per_day: Optional[int] = None
    booking_buffer_minutes: Optional[int] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("max_bookings_per_day")
    @classmethod
    def max_bookings_positive(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 1:
            raise ValueError("max_bookings_per_day must be at least 1")
        return value

    @field_validator("booking_buffer_minutes")
    @classmethod
    def buffer_non_negative(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 0:
            raise ValueError("booking_buffer_minutes cannot be negative")
        return value


class ResourceUpdateRequest(BaseModel):
    resource_name: Optional[str] = None
    resource_category_id: Optional[int] = None
    code: Optional[str] = None
    description: Optional[str] = None
    max_bookings_per_day: Optional[int] = None
    booking_buffer_minutes: Optional[int] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("max_bookings_per_day")
    @classmethod
    def max_bookings_positive(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 1:
            raise ValueError("max_bookings_per_day must be at least 1")
        return value

    @field_validator("booking_buffer_minutes")
    @classmethod
    def buffer_non_negative(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 0:
            raise ValueError("booking_buffer_minutes cannot be negative")
        return value


class ResourceResponse(BaseModel):
    id: int
    branch_id: int
    business_id: int
    resource_category_id: int
    linked_user_id: Optional[int] = None
    resource_name: str
    code: Optional[str] = None
    description: Optional[str] = None
    status: str
    requires_login: bool
    max_bookings_per_day: Optional[int] = None
    booking_buffer_minutes: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# RESOURCE WORKING HOURS (ID-013)
# -------------------------

class ResourceWorkingHourEntry(BaseModel):
    weekday: int
    opening_time: Optional[TimeType] = None
    closing_time: Optional[TimeType] = None
    is_closed: bool = False
    break_start_time: Optional[TimeType] = None
    break_end_time: Optional[TimeType] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("weekday")
    @classmethod
    def weekday_in_range(cls, value: int) -> int:
        if value < 0 or value > 6:
            raise ValueError("weekday must be between 0 (Monday) and 6 (Sunday)")
        return value


class ResourceWorkingHoursUpsertRequest(BaseModel):
    hours: List[ResourceWorkingHourEntry]

    model_config = ConfigDict(extra="forbid")

    @field_validator("hours")
    @classmethod
    def no_duplicate_weekdays(cls, value: List[ResourceWorkingHourEntry]) -> List[ResourceWorkingHourEntry]:
        if not value:
            raise ValueError("At least one working-hours entry is required")
        weekdays = [entry.weekday for entry in value]
        if len(weekdays) != len(set(weekdays)):
            raise ValueError("Duplicate weekday entries are not allowed")
        return value


class ResourceWorkingHourResponse(BaseModel):
    id: int
    resource_id: int
    weekday: int
    opening_time: Optional[TimeType] = None
    closing_time: Optional[TimeType] = None
    is_closed: bool
    break_start_time: Optional[TimeType] = None
    break_end_time: Optional[TimeType] = None

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# RESOURCE USER INVITATION (ID-014, ID-016)
# -------------------------

class ResourceUserInviteRequest(BaseModel):
    email: EmailStr

    model_config = ConfigDict(extra="forbid")


class ResourceUserMemberResponse(BaseModel):
    id: int
    business_id: int
    resource_id: Optional[int] = None
    user_id: int
    email: EmailStr
    role_code: str
    status: str
    joined_at: datetime
    left_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
