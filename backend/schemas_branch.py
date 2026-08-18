from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime, time as TimeType


# -------------------------
# BRANCH
# -------------------------

class BranchCreateRequest(BaseModel):
    branch_name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country_id: int
    phone: Optional[str] = None
    email: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class BranchUpdateRequest(BaseModel):
    branch_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country_id: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class BranchRejectRequest(BaseModel):
    reason: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class BranchResponse(BaseModel):
    id: int
    business_id: int
    branch_name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country_id: int
    phone: Optional[str] = None
    email: Optional[str] = None
    approval_status: str
    is_active: bool
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# BRANCH WORKING HOURS
# -------------------------

class WorkingHourEntry(BaseModel):
    weekday: int
    opening_time: Optional[TimeType] = None
    closing_time: Optional[TimeType] = None
    is_closed: bool = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("weekday")
    @classmethod
    def weekday_in_range(cls, value: int) -> int:
        if value < 0 or value > 6:
            raise ValueError("weekday must be between 0 (Monday) and 6 (Sunday)")
        return value


class WorkingHoursUpsertRequest(BaseModel):
    hours: List[WorkingHourEntry]

    model_config = ConfigDict(extra="forbid")

    @field_validator("hours")
    @classmethod
    def no_duplicate_weekdays(cls, value: List[WorkingHourEntry]) -> List[WorkingHourEntry]:
        if not value:
            raise ValueError("At least one working-hours entry is required")
        weekdays = [entry.weekday for entry in value]
        if len(weekdays) != len(set(weekdays)):
            raise ValueError("Duplicate weekday entries are not allowed")
        return value


class WorkingHourResponse(BaseModel):
    id: int
    branch_id: int
    weekday: int
    opening_time: Optional[TimeType] = None
    closing_time: Optional[TimeType] = None
    is_closed: bool

    model_config = ConfigDict(from_attributes=True)
