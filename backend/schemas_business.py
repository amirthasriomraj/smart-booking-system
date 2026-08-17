from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime


# -------------------------
# BUSINESS CATEGORY / COUNTRY (reference data)
# -------------------------

class BusinessCategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CountryResponse(BaseModel):
    id: int
    iso_code: str
    name: str

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# BUSINESS REGISTRATION
# -------------------------

class BusinessRegisterRequest(BaseModel):
    # Owner (PRD §12 Step 1 — Personal Information)
    username: str
    email: EmailStr
    password: str

    # Business (PRD §12 Step 1 — Business Information)
    business_name: str
    business_category_id: int
    country_id: int

    model_config = ConfigDict(extra="forbid")


class BusinessRejectRequest(BaseModel):
    reason: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class BusinessResponse(BaseModel):
    id: int
    business_name: str
    business_category_id: int
    owner_user_id: int
    country_id: int
    status: str
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
