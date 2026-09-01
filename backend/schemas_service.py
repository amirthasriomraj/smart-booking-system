from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List, Any
from datetime import datetime
from decimal import Decimal


# -------------------------
# SERVICE TEMPLATE (ID-018, ID-019, ID-024, ID-025)
# -------------------------

class ServiceTemplateCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    default_duration: int
    default_price: Decimal
    default_buffer_minutes: Optional[int] = None
    default_working_rules: Optional[Any] = None
    default_resource_category_ids: List[int] = []

    model_config = ConfigDict(extra="forbid")

    @field_validator("default_duration")
    @classmethod
    def duration_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("default_duration must be at least 1")
        return value

    @field_validator("default_price")
    @classmethod
    def price_non_negative(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("default_price cannot be negative")
        return value

    @field_validator("default_buffer_minutes")
    @classmethod
    def buffer_non_negative(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 0:
            raise ValueError("default_buffer_minutes cannot be negative")
        return value


class ServiceTemplateResponse(BaseModel):
    id: int
    business_id: int
    name: str
    description: Optional[str] = None
    default_duration: int
    default_price: Decimal
    default_buffer_minutes: Optional[int] = None
    default_working_rules: Optional[Any] = None
    default_resource_category_ids: List[int] = []
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# BRANCH SERVICE (ID-018, ID-020, ID-023, ID-024)
# -------------------------

class BranchServiceResponse(BaseModel):
    id: int
    branch_id: int
    business_id: int
    service_template_id: int
    service_name: Optional[str] = None
    duration: int
    price: Decimal
    resource_category_ids: List[int] = []
    status: str
    pending_approval: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BranchServiceConfiguration(BaseModel):
    """Shared shape for a direct update and an override proposal — the
    three fields ID-022 established as overridable (Price, Duration,
    Resource Category assignment). All optional/partial: an unset field
    keeps its current effective value."""
    duration: Optional[int] = None
    price: Optional[Decimal] = None
    resource_category_ids: Optional[List[int]] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("duration")
    @classmethod
    def duration_positive(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 1:
            raise ValueError("duration must be at least 1")
        return value

    @field_validator("price")
    @classmethod
    def price_non_negative(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is not None and value < 0:
            raise ValueError("price cannot be negative")
        return value


class BranchServiceUpdateRequest(BranchServiceConfiguration):
    """Business Owner direct edit (ID-027) — immediate effect, no approval.
    Deliberately exposes only price/duration/resource_category_ids; it is
    not possible to set business_id, branch_id, service_template_id,
    pending_approval, or status through this schema."""


class BranchServiceOverrideRequest(BranchServiceConfiguration):
    """Branch Manager override submission (ID-021, ID-027) — creates a
    ServiceApproval snapshot rather than modifying live values."""


# -------------------------
# SERVICE APPROVAL (ID-021, ID-027)
# -------------------------

class ServiceApprovalDecisionRequest(BaseModel):
    decision: str  # "Approved" or "Rejected"
    comments: Optional[str] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("decision")
    @classmethod
    def decision_valid(cls, value: str) -> str:
        if value not in ("Approved", "Rejected"):
            raise ValueError("decision must be 'Approved' or 'Rejected'")
        return value


class ServiceApprovalResponse(BaseModel):
    id: int
    branch_service_id: int
    branch_id: int
    service_template_id: int
    requested_by: int
    requested_by_email: str
    approved_by: Optional[int] = None
    approved_by_email: Optional[str] = None
    decision: str
    previous_configuration: Any
    proposed_configuration: Any
    comments: Optional[str] = None
    decided_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
