from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime, date as DateType, time as TimeType


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


# -------------------------
# BOOKING SCHEMAS
# -------------------------

class BookingCreate(BaseModel):
    date: DateType
    time: TimeType

    model_config = ConfigDict(extra="forbid")


class BookingUpdate(BaseModel):
    date: Optional[DateType] = None
    time: Optional[TimeType] = None

    model_config = ConfigDict(extra="forbid")


class BookingResponse(BaseModel):
    id: int
    date: DateType
    time: TimeType
    user_id: int

    model_config = ConfigDict(from_attributes=True)


class PaginatedBookings(BaseModel):
    total: int
    limit: int
    offset: int
    data: list[BookingResponse]


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