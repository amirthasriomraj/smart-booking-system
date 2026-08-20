from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional
from datetime import datetime


# -------------------------
# STAFF INVITATION (Milestone 3)
# -------------------------

class StaffInviteRequest(BaseModel):
    email: EmailStr
    role_code: str  # BRANCH_MANAGER or HR_USER
    branch_id: Optional[int] = None  # required for BRANCH_MANAGER, forbidden for HR_USER

    model_config = ConfigDict(extra="forbid")


class TransferBranchRequest(BaseModel):
    branch_id: int

    model_config = ConfigDict(extra="forbid")


class StaffMemberResponse(BaseModel):
    id: int
    business_id: int
    user_id: int
    email: EmailStr
    role_code: str
    status: str
    current_branch_id: Optional[int] = None
    current_branch_name: Optional[str] = None
    joined_at: datetime
    left_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# -------------------------
# ACCEPT INVITATION (public, token-authenticated)
# -------------------------

class AcceptInvitationStatusResponse(BaseModel):
    requires_credential_setup: bool
    business_name: str
    role_code: str
    branch_id: Optional[int] = None
    branch_name: Optional[str] = None


class AcceptInvitationRequest(BaseModel):
    token: str
    username: Optional[str] = None
    password: Optional[str] = None

    model_config = ConfigDict(extra="forbid")
