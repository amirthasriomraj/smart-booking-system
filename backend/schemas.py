from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime


# -------------------------
# USER SCHEMAS
# -------------------------

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

    model_config = ConfigDict(extra="forbid")


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# CURRENT USER CONTEXT (Milestone 2 — drives frontend role-gating)
# -------------------------

class BusinessContext(BaseModel):
    id: int
    business_name: str
    status: str
    role_code: str
    branch_id: Optional[int] = None
    branch_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CustomerContext(BaseModel):
    """Milestone 6 — present when the user has a PlatformCustomer identity (ID-028)."""
    platform_customer_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserContextResponse(BaseModel):
    user_id: int
    username: str
    email: EmailStr
    is_platform_admin: bool
    business: Optional[BusinessContext] = None
    customer: Optional[CustomerContext] = None


# -------------------------
# PROFILE SCHEMAS
# -------------------------

class UserProfileCreate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class UserProfileResponse(BaseModel):
    id: int
    user_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]

    model_config = ConfigDict(from_attributes=True)


# NOTE: legacy flat Booking schemas removed — see schemas_booking.py
# (Milestone 7, IMPLEMENTATION_PLAN.md M7 scope bullet 1).


# -------------------------
# TOKEN SCHEMAS
# -------------------------

class Token(BaseModel):
    access_token: str
    token_type: str


# -------------------------
# PASSWORD RESET SCHEMAS
# -------------------------

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    model_config = ConfigDict(extra="forbid")


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    model_config = ConfigDict(extra="forbid")


# -------------------------
# LOGOUT SCHEMAS
# -------------------------

class LogoutRequest(BaseModel):
    refresh_token: str