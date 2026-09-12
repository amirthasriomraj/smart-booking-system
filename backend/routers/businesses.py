from datetime import date as DateType
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database import SessionLocal
from schemas_business import (
    BusinessRegisterRequest,
    BusinessResponse,
    PaginatedBusinesses,
    BusinessRejectRequest,
    BusinessUpdateRequest,
    BusinessCategoryResponse,
    BusinessCategoryCreateRequest,
    BusinessCategoryUpdateRequest,
    CountryResponse,
)
from models import BusinessCategory, Country, User
from schemas_admin import PaginatedAuditLogs, AuditLogFilterOptionsResponse, PaginatedNotifications
import crud_business
import crud_admin
from dependencies import get_current_platform_admin, get_current_user
from services import notification_service
from services.email_service import send_welcome_email, send_business_approved_email, send_business_rejected_email

router = APIRouter(prefix="/businesses", tags=["Businesses"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------
# Reference data (needed by the registration form)
# -----------------------------

@router.get("/categories", response_model=List[BusinessCategoryResponse])
def list_business_categories(db: Session = Depends(get_db)):
    return db.query(BusinessCategory).filter(BusinessCategory.is_active == True).all()  # noqa: E712


@router.get("/countries", response_model=List[CountryResponse])
def list_countries(db: Session = Depends(get_db)):
    return db.query(Country).order_by(Country.name).all()


# -----------------------------
# Business Category admin CRUD (M9 Phase 1, Platform Admin only)
# -----------------------------

@router.get("/categories/admin", response_model=List[BusinessCategoryResponse])
def list_business_categories_admin(
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_business.get_all_business_categories(db)


@router.post("/categories", response_model=BusinessCategoryResponse)
def create_business_category(
    payload: BusinessCategoryCreateRequest,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_business.create_business_category(db, payload, current_admin)


@router.patch("/categories/{category_id}", response_model=BusinessCategoryResponse)
def update_business_category(
    category_id: int,
    payload: BusinessCategoryUpdateRequest,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_business.update_business_category(db, category_id, payload, current_admin)


# -----------------------------
# Registration
# -----------------------------

@router.post("/register", response_model=BusinessResponse)
def register_business(payload: BusinessRegisterRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    business = crud_business.register_business(db, payload)
    owner = db.query(User).filter(User.id == business.owner_user_id).first()
    background_tasks.add_task(
        notification_service.log_and_send,
        owner.id, "Welcome",
        lambda: send_welcome_email(owner.email, owner.username),
        business.id, "Business", business.id,
    )
    return business


# -----------------------------
# Business Profile (M9 Phase 6, PRD §72, Business Owner only)
# -----------------------------

@router.get("/{business_id}", response_model=BusinessResponse)
def get_business_profile(
    business_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_business.get_business_for_viewer(db, business_id, current_user)


@router.patch("/{business_id}", response_model=BusinessResponse)
def update_business_profile(
    business_id: int,
    payload: BusinessUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_business.update_business_profile(db, business_id, payload, current_user)


@router.get("/{business_id}/audit-logs", response_model=PaginatedAuditLogs)
def get_business_audit_logs(
    business_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    branch_id: Optional[int] = None,
    date_from: Optional[DateType] = None,
    date_to: Optional[DateType] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_admin.get_business_audit_logs(
        db, business_id, current_user, page, page_size, entity_type, action, branch_id, date_from, date_to,
    )


@router.get("/{business_id}/audit-logs/filters", response_model=AuditLogFilterOptionsResponse)
def get_business_audit_log_filter_options(
    business_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_admin.get_business_audit_log_filter_options(db, business_id, current_user)


@router.get("/{business_id}/notifications", response_model=PaginatedNotifications)
def get_business_notifications(
    business_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    branch_id: Optional[int] = None,
    date_from: Optional[DateType] = None,
    date_to: Optional[DateType] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_admin.get_business_notifications(
        db, business_id, current_user, page, page_size, status, branch_id, date_from, date_to,
    )


# -----------------------------
# Platform Admin approval
# -----------------------------

@router.get("/", response_model=PaginatedBusinesses)
def list_businesses(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_business.get_businesses(db, status=status, page=page, page_size=page_size, search=search)


@router.post("/{business_id}/approve", response_model=BusinessResponse)
def approve_business(
    business_id: int,
    background_tasks: BackgroundTasks,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    business = crud_business.approve_business(db, business_id, current_admin)
    owner = db.query(User).filter(User.id == business.owner_user_id).first()
    background_tasks.add_task(
        notification_service.log_and_send,
        owner.id, "BusinessApproved",
        lambda: send_business_approved_email(owner.email, business.business_name),
        business.id, "Business", business.id,
    )
    return business


@router.post("/{business_id}/reject", response_model=BusinessResponse)
def reject_business(
    business_id: int,
    payload: BusinessRejectRequest,
    background_tasks: BackgroundTasks,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    business = crud_business.reject_business(db, business_id, current_admin, reason=payload.reason)
    owner = db.query(User).filter(User.id == business.owner_user_id).first()
    background_tasks.add_task(
        notification_service.log_and_send,
        owner.id, "BusinessRejected",
        lambda: send_business_rejected_email(owner.email, business.business_name, payload.reason),
        business.id, "Business", business.id,
    )
    return business


# -----------------------------
# Platform Admin suspend / reactivate (M9 Phase 1)
# -----------------------------

@router.post("/{business_id}/suspend", response_model=BusinessResponse)
def suspend_business(
    business_id: int,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_business.suspend_business(db, business_id, current_admin)


@router.post("/{business_id}/reactivate", response_model=BusinessResponse)
def reactivate_business(
    business_id: int,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_business.reactivate_business(db, business_id, current_admin)
