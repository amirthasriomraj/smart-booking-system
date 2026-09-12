from datetime import date as DateType
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from database import SessionLocal
from schemas_admin import (
    PaginatedAuditLogs,
    AuditLogFilterOptionsResponse,
    PaginatedNotifications,
    PlatformAnalyticsResponse,
)
import crud_admin
from dependencies import get_current_platform_admin

router = APIRouter(prefix="/admin", tags=["Platform Admin"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------
# Audit Logs (M9 Phase 6)
# -----------------------------

@router.get("/audit-logs", response_model=PaginatedAuditLogs)
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    business_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    date_from: Optional[DateType] = None,
    date_to: Optional[DateType] = None,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_admin.list_audit_logs(db, page, page_size, business_id, entity_type, action, date_from, date_to)


@router.get("/audit-logs/filters", response_model=AuditLogFilterOptionsResponse)
def get_audit_log_filter_options(
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_admin.get_audit_log_filter_options(db)


# -----------------------------
# Notifications (M9 Phase 6)
# -----------------------------

@router.get("/notifications", response_model=PaginatedNotifications)
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    business_id: Optional[int] = None,
    notification_type: Optional[str] = None,
    status: Optional[str] = None,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_admin.list_notifications(db, page, page_size, business_id, notification_type, status)


# -----------------------------
# Platform Analytics (M9 Phase 6)
# -----------------------------

@router.get("/platform-analytics", response_model=PlatformAnalyticsResponse)
def get_platform_analytics(
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_admin.get_platform_analytics(db)
