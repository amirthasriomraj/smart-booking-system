from datetime import date as DateType
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database import SessionLocal
from schemas_branch import (
    BranchCreateRequest,
    BranchUpdateRequest,
    BranchRejectRequest,
    BranchResponse,
    PaginatedBranches,
    WorkingHoursUpsertRequest,
    WorkingHourResponse,
)
from schemas_admin import PaginatedAuditLogs, AuditLogFilterOptionsResponse, PaginatedNotifications
from models import Business, User
import crud_branch
import crud_admin
from dependencies import get_current_user, get_current_platform_admin
from services import notification_service
from services.email_service import send_branch_approved_email, send_branch_rejected_email

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


@router.get("/businesses/{business_id}/branches", response_model=PaginatedBranches)
def list_branches_for_business(
    business_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_branch.get_branches_for_business(db, business_id, current_user, page, page_size, search)


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
# Branch Manager Audit History / Notifications (M9 follow-up fix)
# -----------------------------

@router.get("/branches/{branch_id}/audit-logs", response_model=PaginatedAuditLogs)
def get_branch_audit_logs(
    branch_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    date_from: Optional[DateType] = None,
    date_to: Optional[DateType] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_admin.get_branch_audit_logs(
        db, branch_id, current_user, page, page_size, entity_type, action, date_from, date_to,
    )


@router.get("/branches/{branch_id}/audit-logs/filters", response_model=AuditLogFilterOptionsResponse)
def get_branch_audit_log_filter_options(
    branch_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_admin.get_branch_audit_log_filter_options(db, branch_id, current_user)


@router.get("/branches/{branch_id}/notifications", response_model=PaginatedNotifications)
def get_branch_notifications(
    branch_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    date_from: Optional[DateType] = None,
    date_to: Optional[DateType] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_admin.get_branch_notifications(db, branch_id, current_user, page, page_size, status, date_from, date_to)


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


def _branch_owner(db: Session, branch) -> User:
    business = db.query(Business).filter(Business.id == branch.business_id).first()
    return db.query(User).filter(User.id == business.owner_user_id).first()


@router.post("/branches/{branch_id}/approve", response_model=BranchResponse)
def approve_branch(
    branch_id: int,
    background_tasks: BackgroundTasks,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    branch = crud_branch.approve_branch(db, branch_id, current_admin)
    owner = _branch_owner(db, branch)
    business = db.query(Business).filter(Business.id == branch.business_id).first()
    background_tasks.add_task(
        notification_service.log_and_send,
        owner.id, "BranchApproved",
        lambda: send_branch_approved_email(owner.email, business.business_name, branch.branch_name),
        branch.business_id, "Branch", branch.id,
    )
    return branch


@router.post("/branches/{branch_id}/reject", response_model=BranchResponse)
def reject_branch(
    branch_id: int,
    payload: BranchRejectRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    branch = crud_branch.reject_branch(db, branch_id, current_admin, reason=payload.reason)
    owner = _branch_owner(db, branch)
    business = db.query(Business).filter(Business.id == branch.business_id).first()
    background_tasks.add_task(
        notification_service.log_and_send,
        owner.id, "BranchRejected",
        lambda: send_branch_rejected_email(owner.email, business.business_name, branch.branch_name, payload.reason),
        branch.business_id, "Branch", branch.id,
    )
    return branch
