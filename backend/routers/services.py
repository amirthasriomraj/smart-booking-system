from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal
from schemas_service import (
    ServiceTemplateCreateRequest,
    ServiceTemplateResponse,
    BranchServiceResponse,
    BranchServiceUpdateRequest,
    BranchServiceOverrideRequest,
    ServiceApprovalDecisionRequest,
    ServiceApprovalResponse,
)
import crud_service
from dependencies import get_current_user
from services.email_service import (
    send_service_override_submitted_email,
    send_service_override_decision_email,
)

router = APIRouter(tags=["Services"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------
# Service Template (ID-018, ID-019, ID-025)
# -----------------------------

@router.post("/businesses/{business_id}/service-templates", response_model=ServiceTemplateResponse)
def create_service_template(
    business_id: int,
    payload: ServiceTemplateCreateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = crud_service.create_service_template(db, business_id, payload, current_user)
    return crud_service.serialize_service_template(db, template)


@router.get("/businesses/{business_id}/service-templates", response_model=List[ServiceTemplateResponse])
def list_service_templates(
    business_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    templates = crud_service.list_service_templates(db, business_id, current_user)
    return [crud_service.serialize_service_template(db, t) for t in templates]


@router.get("/service-templates/{template_id}", response_model=ServiceTemplateResponse)
def get_service_template(
    template_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = crud_service.get_service_template(db, template_id, current_user)
    return crud_service.serialize_service_template(db, template)


@router.post("/service-templates/{template_id}/activate", response_model=ServiceTemplateResponse)
def activate_service_template(
    template_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = crud_service.set_service_template_status(db, template_id, "Active", current_user)
    return crud_service.serialize_service_template(db, template)


@router.post("/service-templates/{template_id}/deactivate", response_model=ServiceTemplateResponse)
def deactivate_service_template(
    template_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    template = crud_service.set_service_template_status(db, template_id, "Inactive", current_user)
    return crud_service.serialize_service_template(db, template)


# -----------------------------
# Branch Service (ID-018, ID-020, ID-024)
# -----------------------------

@router.get("/branches/{branch_id}/branch-services", response_model=List[BranchServiceResponse])
def list_branch_services_for_branch(
    branch_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    branch_services = crud_service.list_branch_services_for_branch(db, branch_id, current_user)
    return [crud_service.serialize_branch_service(db, bs) for bs in branch_services]


@router.get("/businesses/{business_id}/branch-services", response_model=List[BranchServiceResponse])
def list_branch_services_for_business(
    business_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    branch_services = crud_service.list_branch_services_for_business(db, business_id, current_user)
    return [crud_service.serialize_branch_service(db, bs) for bs in branch_services]


@router.get("/branch-services/{branch_service_id}", response_model=BranchServiceResponse)
def get_branch_service(
    branch_service_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    branch_service = crud_service.get_branch_service(db, branch_service_id, current_user)
    return crud_service.serialize_branch_service(db, branch_service)


@router.patch("/branch-services/{branch_service_id}", response_model=BranchServiceResponse)
def update_branch_service(
    branch_service_id: int,
    payload: BranchServiceUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    branch_service = crud_service.update_branch_service_direct(db, branch_service_id, payload, current_user)
    return crud_service.serialize_branch_service(db, branch_service)


# -----------------------------
# Service Approval (ID-021, ID-022, ID-027)
# -----------------------------

@router.post("/branch-services/{branch_service_id}/submit-override", response_model=ServiceApprovalResponse)
def submit_branch_service_override(
    branch_service_id: int,
    payload: BranchServiceOverrideRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    approval, owner_email, business_name, branch_name, service_name = crud_service.submit_branch_service_override(
        db, branch_service_id, payload, current_user
    )
    background_tasks.add_task(
        send_service_override_submitted_email, owner_email, business_name, branch_name, service_name
    )
    return crud_service.serialize_service_approval(db, approval)


@router.post("/service-approvals/{approval_id}/decide", response_model=ServiceApprovalResponse)
def decide_service_approval(
    approval_id: int,
    payload: ServiceApprovalDecisionRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    approval, submitter_email, business_name, branch_name, service_name = crud_service.decide_service_approval(
        db, approval_id, payload, current_user
    )
    background_tasks.add_task(
        send_service_override_decision_email,
        submitter_email, business_name, branch_name, service_name, approval.decision, approval.comments,
    )
    return crud_service.serialize_service_approval(db, approval)


@router.get("/businesses/{business_id}/service-approvals", response_model=List[ServiceApprovalResponse])
def list_service_approvals(
    business_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    approvals = crud_service.list_service_approvals(db, business_id, current_user)
    return [crud_service.serialize_service_approval(db, a) for a in approvals]
