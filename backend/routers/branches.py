from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from database import SessionLocal
from schemas_branch import (
    BranchCreateRequest,
    BranchUpdateRequest,
    BranchRejectRequest,
    BranchResponse,
    WorkingHoursUpsertRequest,
    WorkingHourResponse,
)
import crud_branch
from dependencies import get_current_user, get_current_platform_admin

router = APIRouter(tags=["Branches"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------
# Business Owner: Branch CRUD
# -----------------------------

@router.post("/businesses/{business_id}/branches", response_model=BranchResponse)
def create_branch(
    business_id: int,
    payload: BranchCreateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_branch.create_branch(db, business_id, payload, current_user)


@router.get("/businesses/{business_id}/branches", response_model=List[BranchResponse])
def list_branches_for_business(
    business_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_branch.get_branches_for_business(db, business_id, current_user)


@router.get("/branches/{branch_id}", response_model=BranchResponse)
def get_branch(
    branch_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_branch.get_branch_for_viewer(db, branch_id, current_user)


@router.patch("/branches/{branch_id}", response_model=BranchResponse)
def update_branch(
    branch_id: int,
    payload: BranchUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_branch.update_branch(db, branch_id, payload, current_user)


@router.post("/branches/{branch_id}/activate", response_model=BranchResponse)
def activate_branch(
    branch_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_branch.activate_branch(db, branch_id, current_user)


@router.post("/branches/{branch_id}/deactivate", response_model=BranchResponse)
def deactivate_branch(
    branch_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_branch.deactivate_branch(db, branch_id, current_user)


# -----------------------------
# Branch Working Hours
# -----------------------------

@router.get("/branches/{branch_id}/working-hours", response_model=List[WorkingHourResponse])
def get_working_hours(
    branch_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_branch.get_working_hours(db, branch_id, current_user)


@router.put("/branches/{branch_id}/working-hours", response_model=List[WorkingHourResponse])
def upsert_working_hours(
    branch_id: int,
    payload: WorkingHoursUpsertRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_branch.upsert_working_hours(db, branch_id, payload, current_user)


# -----------------------------
# Platform Admin approval
# -----------------------------

@router.get("/branches", response_model=List[BranchResponse])
def list_branches(
    approval_status: Optional[str] = None,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_branch.get_branches(db, approval_status=approval_status)


@router.post("/branches/{branch_id}/approve", response_model=BranchResponse)
def approve_branch(
    branch_id: int,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_branch.approve_branch(db, branch_id, current_admin)


@router.post("/branches/{branch_id}/reject", response_model=BranchResponse)
def reject_branch(
    branch_id: int,
    payload: BranchRejectRequest,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_branch.reject_branch(db, branch_id, current_admin, reason=payload.reason)
