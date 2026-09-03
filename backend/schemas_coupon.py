from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date as DateType, datetime
from decimal import Decimal


class CouponCreateRequest(BaseModel):
    code: str
    branch_id: Optional[int] = None  # None = business-wide (Owner only, rule 10)
    discount_type: str  # Fixed / Percentage
    discount_value: Decimal
    min_booking_amount: Decimal = Decimal("0")
    max_discount: Optional[Decimal] = None
    valid_from: DateType
    valid_until: DateType
    applicable_weekdays: Optional[List[int]] = None  # 0=Mon..6=Sun; None/empty = all
    total_usage_limit: Optional[int] = None
    per_customer_usage_limit: int = 1
    branch_service_ids: Optional[List[int]] = None  # None/empty = applies to all services

    model_config = ConfigDict(extra="forbid")


class CouponStatusUpdateRequest(BaseModel):
    status: str  # Active / Inactive

    model_config = ConfigDict(extra="forbid")


class CouponDecisionRequest(BaseModel):
    comments: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class CouponResponse(BaseModel):
    id: int
    business_id: int
    branch_id: Optional[int] = None
    code: str
    discount_type: str
    discount_value: Decimal
    min_booking_amount: Decimal
    max_discount: Optional[Decimal] = None
    valid_from: DateType
    valid_until: DateType
    applicable_weekdays: Optional[List[int]] = None
    total_usage_limit: Optional[int] = None
    per_customer_usage_limit: int
    status: str
    approval_status: Optional[str] = None
    branch_service_ids: List[int] = []
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
