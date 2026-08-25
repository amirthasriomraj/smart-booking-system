from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal
from schemas_resource import (
    ResourceCategoryCreateRequest,
    ResourceCategoryUpdateRequest,
    ResourceCategoryResponse,
    ResourceCreateRequest,
    ResourceUpdateRequest,
    ResourceResponse,
    ResourceWorkingHoursUpsertRequest,
    ResourceWorkingHourResponse,
    ResourceUserInviteRequest,
    ResourceUserMemberResponse,
)
import crud_resource
from dependencies import get_current_user
from services.email_service import send_staff_invitation_email

router = APIRouter(tags=["Resources"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------
# Resource Category (ID-015)
# -----------------------------

@router.post("/businesses/{business_id}/resource-categories", response_model=ResourceCategoryResponse)
def create_resource_category(
    business_id: int,
    payload: ResourceCategoryCreateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_resource.create_resource_category(db, business_id, payload, current_user)


@router.get("/businesses/{business_id}/resource-categories", response_model=List[ResourceCategoryResponse])
def list_resource_categories(
    business_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_resource.list_resource_categories(db, business_id, current_user)


@router.patch("/resource-categories/{category_id}", response_model=ResourceCategoryResponse)
def update_resource_category(
    category_id: int,
    payload: ResourceCategoryUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_resource.update_resource_category(db, category_id, payload, current_user)


# -----------------------------
# Resource (PRD §14.3-14.5)
# -----------------------------

@router.post("/branches/{branch_id}/resources", response_model=ResourceResponse)
def create_resource(
    branch_id: int,
    payload: ResourceCreateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_resource.create_resource(db, branch_id, payload, current_user)


@router.get("/branches/{branch_id}/resources", response_model=List[ResourceResponse])
def list_resources_for_branch(
    branch_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_resource.list_resources_for_branch(db, branch_id, current_user)


@router.get("/businesses/{business_id}/resources", response_model=List[ResourceResponse])
def list_resources_for_business(
    business_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_resource.list_resources_for_business(db, business_id, current_user)


@router.get("/resources/{resource_id}", response_model=ResourceResponse)
def get_resource(
    resource_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_resource.get_resource(db, resource_id, current_user)


@router.patch("/resources/{resource_id}", response_model=ResourceResponse)
def update_resource(
    resource_id: int,
    payload: ResourceUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_resource.update_resource(db, resource_id, payload, current_user)


@router.post("/resources/{resource_id}/activate", response_model=ResourceResponse)
def activate_resource(
    resource_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_resource.activate_resource(db, resource_id, current_user)


@router.post("/resources/{resource_id}/suspend", response_model=ResourceResponse)
def suspend_resource(
    resource_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_resource.suspend_resource(db, resource_id, current_user)


# -----------------------------
# Resource Working Hours (ID-013)
# -----------------------------

@router.get("/resources/{resource_id}/working-hours", response_model=List[ResourceWorkingHourResponse])
def get_working_hours(
    resource_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_resource.get_working_hours(db, resource_id, current_user)


@router.put("/resources/{resource_id}/working-hours", response_model=List[ResourceWorkingHourResponse])
def upsert_working_hours(
    resource_id: int,
    payload: ResourceWorkingHoursUpsertRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_resource.upsert_working_hours(db, resource_id, payload, current_user)


# -----------------------------
# Resource User invitation (ID-014, ID-016)
# -----------------------------

@router.post(
    "/businesses/{business_id}/resources/{resource_id}/invite-user",
    response_model=ResourceUserMemberResponse,
)
def invite_resource_user(
    business_id: int,
    resource_id: int,
    payload: ResourceUserInviteRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member, raw_token, email, role_code, business_name = crud_resource.invite_resource_user(
        db, business_id, resource_id, payload, current_user
    )
    background_tasks.add_task(send_staff_invitation_email, email, raw_token, role_code, business_name)
    return crud_resource.serialize_resource_member(db, member)


@router.post("/business-members/{member_id}/resend-resource-invite", response_model=ResourceUserMemberResponse)
def resend_resource_invite(
    member_id: int,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member, raw_token, email, role_code, business_name = crud_resource.resend_resource_invite(
        db, member_id, current_user
    )
    background_tasks.add_task(send_staff_invitation_email, email, raw_token, role_code, business_name)
    return crud_resource.serialize_resource_member(db, member)


@router.get("/businesses/{business_id}/resource-users", response_model=List[ResourceUserMemberResponse])
def list_resource_users(
    business_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    members = crud_resource.list_resource_users(db, business_id, current_user)
    return [crud_resource.serialize_resource_member(db, member) for member in members]


@router.post("/business-members/{member_id}/deactivate-resource-user", response_model=ResourceUserMemberResponse)
def deactivate_resource_user(
    member_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = crud_resource.deactivate_resource_user(db, member_id, current_user)
    return crud_resource.serialize_resource_member(db, member)
