from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal
from schemas_staff import StaffInviteRequest, StaffMemberResponse, TransferBranchRequest
import crud_staff
from dependencies import get_current_user
from services.email_service import send_staff_invitation_email

router = APIRouter(tags=["Staff"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------
# Business Owner: Invite / Resend / List / Detail
# -----------------------------

@router.post("/businesses/{business_id}/staff/invite", response_model=StaffMemberResponse)
def invite_staff(
    business_id: int,
    payload: StaffInviteRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member, raw_token, email, role_code, business_name = crud_staff.invite_staff_member(
        db, business_id, payload, current_user
    )
    background_tasks.add_task(send_staff_invitation_email, email, raw_token, role_code, business_name)
    return crud_staff.serialize_member(db, member)


@router.post("/businesses/{business_id}/staff/{member_id}/resend-invite", response_model=StaffMemberResponse)
def resend_invite(
    business_id: int,
    member_id: int,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member, raw_token, email, role_code, business_name = crud_staff.resend_invitation(
        db, business_id, member_id, current_user
    )
    background_tasks.add_task(send_staff_invitation_email, email, raw_token, role_code, business_name)
    return crud_staff.serialize_member(db, member)


@router.get("/businesses/{business_id}/staff", response_model=List[StaffMemberResponse])
def list_staff(
    business_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    members = crud_staff.list_staff(db, business_id, current_user)
    return [crud_staff.serialize_member(db, member) for member in members]


@router.get("/business-members/{member_id}", response_model=StaffMemberResponse)
def get_staff_member(
    member_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = crud_staff.get_staff_member(db, member_id, current_user)
    return crud_staff.serialize_member(db, member)


# -----------------------------
# Business Owner: Transfer / Deactivate
# -----------------------------

@router.post("/business-members/{member_id}/transfer-branch", response_model=StaffMemberResponse)
def transfer_branch(
    member_id: int,
    payload: TransferBranchRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = crud_staff.transfer_branch(db, member_id, payload, current_user)
    return crud_staff.serialize_member(db, member)


@router.post("/business-members/{member_id}/deactivate", response_model=StaffMemberResponse)
def deactivate_member(
    member_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = crud_staff.deactivate_member(db, member_id, current_user)
    return crud_staff.serialize_member(db, member)
