from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime, date as DateType
from decimal import Decimal


# -------------------------
# CUSTOMER SELF-REGISTRATION (PRD §17.5, ID-034)
# -------------------------

class CustomerRegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    mobile_number: str
    password: str

    model_config = ConfigDict(extra="forbid")


# -------------------------
# CUSTOMER SELF PROFILE (PRD §17.2, BR-040)
# -------------------------

class CustomerProfileUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    mobile_number: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[DateType] = None
    address_line: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country_id: Optional[int] = None
    postal_code: Optional[str] = None
    preferred_language: Optional[str] = None
    preferred_timezone: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class CustomerProfileResponse(BaseModel):
    platform_customer_id: int
    user_id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    mobile_number: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[DateType] = None
    address_line: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country_id: Optional[int] = None
    postal_code: Optional[str] = None
    preferred_language: Optional[str] = None
    preferred_timezone: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# STAFF-CREATED / WALK-IN CUSTOMER (PRD §17.4, BR-037, BR-038)
# -------------------------

class WalkInCustomerCreateRequest(BaseModel):
    first_name: str
    last_name: str
    mobile_number: str
    email: Optional[EmailStr] = None
    gender: Optional[str] = None
    date_of_birth: Optional[DateType] = None
    address_line: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country_id: Optional[int] = None
    postal_code: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class BusinessCustomerUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    mobile_number: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[DateType] = None
    address_line: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country_id: Optional[int] = None
    postal_code: Optional[str] = None
    notes: Optional[str] = None
    # Settable only while the linked identity is still an unclaimed walk-in
    # placeholder (ID-030/ID-031) — see crud_customer.update_business_customer.
    email: Optional[EmailStr] = None

    model_config = ConfigDict(extra="forbid")


class CustomerStatusUpdateRequest(BaseModel):
    status: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("status")
    @classmethod
    def status_valid(cls, value: str) -> str:
        if value not in ("Active", "Inactive"):
            raise ValueError("status must be Active or Inactive")
        return value


class BusinessCustomerResponse(BaseModel):
    id: int
    business_id: int
    platform_customer_id: int
    customer_number: str
    status: str
    notes: Optional[str] = None
    first_visit_at: Optional[datetime] = None
    last_visit_at: Optional[datetime] = None
    created_at: datetime
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    mobile_number: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[DateType] = None
    address_line: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country_id: Optional[int] = None
    postal_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedBusinessCustomers(BaseModel):
    total: int
    limit: int
    offset: int
    data: List[BusinessCustomerResponse]


# -------------------------
# CUSTOMER BROWSE (PRD §17.1 workflow 90.3 — Select Business/Branch/Service)
# -------------------------

class BrowseBusinessResponse(BaseModel):
    id: int
    business_name: str

    model_config = ConfigDict(from_attributes=True)


class BrowseBranchResponse(BaseModel):
    id: int
    business_id: int
    branch_name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BrowseServiceResponse(BaseModel):
    id: int
    branch_id: int
    service_template_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    duration: int
    price: Decimal

    model_config = ConfigDict(from_attributes=True)
