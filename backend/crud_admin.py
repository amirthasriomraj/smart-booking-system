from datetime import date as DateType, datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from fastapi import HTTPException

from models import AuditLog, Notification, Business, Branch, Booking, Resource, BranchService, ServiceApproval, User
from pagination import paginate
from crud_branch import _require_active_owner_membership, get_branch_by_id
from crud_reports import _require_branch_report_access


# -------------------------
# SHARED: scope an AuditLog/Notification query to one branch (M9 follow-up
# fix). Neither table has a branch_id column, so scoping is done by
# matching (entity_type, entity_id) / (related_entity_type,
# related_entity_id) against the branch-owned rows of the entity types
# that are meaningfully branch-scoped.
# -------------------------

def _branch_scoped_condition(db: Session, branch_id: int, entity_type_col, entity_id_col):
    booking_ids = db.query(Booking.id).filter(Booking.branch_id == branch_id).scalar_subquery()
    resource_ids = db.query(Resource.id).filter(Resource.branch_id == branch_id).scalar_subquery()
    branch_service_ids = db.query(BranchService.id).filter(BranchService.branch_id == branch_id).scalar_subquery()
    approval_ids = (
        db.query(ServiceApproval.id)
        .join(BranchService, ServiceApproval.branch_service_id == BranchService.id)
        .filter(BranchService.branch_id == branch_id)
        .scalar_subquery()
    )
    return or_(
        and_(entity_type_col == "Branch", entity_id_col == branch_id),
        and_(entity_type_col == "Booking", entity_id_col.in_(booking_ids)),
        and_(entity_type_col == "Resource", entity_id_col.in_(resource_ids)),
        and_(entity_type_col == "BranchService", entity_id_col.in_(branch_service_ids)),
        and_(entity_type_col == "ServiceApproval", entity_id_col.in_(approval_ids)),
    )


def _distinct_entity_types_and_actions(query) -> dict:
    entity_types = sorted({row[0] for row in query.with_entities(AuditLog.entity_type).distinct().all()})
    actions = sorted({row[0] for row in query.with_entities(AuditLog.action).distinct().all()})
    return {"entity_types": entity_types, "actions": actions}


# -------------------------
# PLATFORM ADMIN AUDIT LOGS (M9 Phase 6, PRD §35/§26.1)
# -------------------------

def list_audit_logs(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    business_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    date_from: Optional[DateType] = None,
    date_to: Optional[DateType] = None,
) -> dict:
    query = db.query(AuditLog)
    if business_id is not None:
        query = query.filter(AuditLog.business_id == business_id)
    if entity_type is not None:
        query = query.filter(AuditLog.entity_type == entity_type)
    if action is not None:
        query = query.filter(AuditLog.action == action)
    if date_from is not None:
        query = query.filter(AuditLog.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to is not None:
        query = query.filter(AuditLog.created_at <= datetime.combine(date_to, datetime.max.time()))

    total = query.count()
    rows = query.order_by(AuditLog.created_at.desc()).limit(page_size).offset((page - 1) * page_size).all()
    return paginate(rows, total, page, page_size)


def get_audit_log_filter_options(db: Session) -> dict:
    """Distinct entity_type/action values actually present in AuditLog, so
    the admin UI's filters are dropdowns of real values rather than free
    text the caller has to guess (M9 Phase 6 follow-up fix)."""
    return _distinct_entity_types_and_actions(db.query(AuditLog))


# -------------------------
# BUSINESS OWNER AUDIT HISTORY (M9 Phase 6c, PRD §35 dashboard module list —
# read-only, business-scoped only; the write path already exists and is
# unaffected. Distinct from the Platform Admin's platform-wide audit view.)
# -------------------------

def get_business_audit_logs(
    db: Session,
    business_id: int,
    current_user: User,
    page: int = 1,
    page_size: int = 20,
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    branch_id: Optional[int] = None,
    date_from: Optional[DateType] = None,
    date_to: Optional[DateType] = None,
) -> dict:
    _require_active_owner_membership(db, business_id, current_user)

    query = db.query(AuditLog).filter(AuditLog.business_id == business_id)
    if entity_type is not None:
        query = query.filter(AuditLog.entity_type == entity_type)
    if action is not None:
        query = query.filter(AuditLog.action == action)
    if date_from is not None:
        query = query.filter(AuditLog.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to is not None:
        query = query.filter(AuditLog.created_at <= datetime.combine(date_to, datetime.max.time()))
    if branch_id is not None:
        branch = db.query(Branch).filter(Branch.id == branch_id, Branch.business_id == business_id).first()
        if not branch:
            raise HTTPException(status_code=400, detail="Branch does not belong to this business")
        query = query.filter(_branch_scoped_condition(db, branch_id, AuditLog.entity_type, AuditLog.entity_id))

    total = query.count()
    rows = query.order_by(AuditLog.created_at.desc()).limit(page_size).offset((page - 1) * page_size).all()
    return paginate(rows, total, page, page_size)


def get_business_audit_log_filter_options(db: Session, business_id: int, current_user: User) -> dict:
    _require_active_owner_membership(db, business_id, current_user)
    return _distinct_entity_types_and_actions(db.query(AuditLog).filter(AuditLog.business_id == business_id))


# -------------------------
# BRANCH MANAGER AUDIT HISTORY (M9 follow-up fix)
# -------------------------

def get_branch_audit_logs(
    db: Session,
    branch_id: int,
    current_user: User,
    page: int = 1,
    page_size: int = 20,
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    date_from: Optional[DateType] = None,
    date_to: Optional[DateType] = None,
) -> dict:
    branch = get_branch_by_id(db, branch_id)
    _require_branch_report_access(db, branch, current_user)

    query = db.query(AuditLog).filter(AuditLog.business_id == branch.business_id)
    query = query.filter(_branch_scoped_condition(db, branch_id, AuditLog.entity_type, AuditLog.entity_id))
    if entity_type is not None:
        query = query.filter(AuditLog.entity_type == entity_type)
    if action is not None:
        query = query.filter(AuditLog.action == action)
    if date_from is not None:
        query = query.filter(AuditLog.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to is not None:
        query = query.filter(AuditLog.created_at <= datetime.combine(date_to, datetime.max.time()))

    total = query.count()
    rows = query.order_by(AuditLog.created_at.desc()).limit(page_size).offset((page - 1) * page_size).all()
    return paginate(rows, total, page, page_size)


def get_branch_audit_log_filter_options(db: Session, branch_id: int, current_user: User) -> dict:
    branch = get_branch_by_id(db, branch_id)
    _require_branch_report_access(db, branch, current_user)
    query = db.query(AuditLog).filter(AuditLog.business_id == branch.business_id).filter(
        _branch_scoped_condition(db, branch_id, AuditLog.entity_type, AuditLog.entity_id)
    )
    return _distinct_entity_types_and_actions(query)


# -------------------------
# PLATFORM ADMIN NOTIFICATIONS (M9 Phase 6, PRD §35/§83)
# -------------------------

def list_notifications(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    business_id: Optional[int] = None,
    notification_type: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    query = db.query(Notification)
    if business_id is not None:
        query = query.filter(Notification.business_id == business_id)
    if notification_type is not None:
        query = query.filter(Notification.notification_type == notification_type)
    if status is not None:
        query = query.filter(Notification.status == status)

    total = query.count()
    rows = query.order_by(Notification.created_at.desc()).limit(page_size).offset((page - 1) * page_size).all()
    return paginate(rows, total, page, page_size)


# -------------------------
# BUSINESS OWNER NOTIFICATIONS (M9 follow-up fix)
# -------------------------

def get_business_notifications(
    db: Session,
    business_id: int,
    current_user: User,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    branch_id: Optional[int] = None,
    date_from: Optional[DateType] = None,
    date_to: Optional[DateType] = None,
) -> dict:
    _require_active_owner_membership(db, business_id, current_user)

    query = db.query(Notification).filter(Notification.business_id == business_id)
    if status is not None:
        query = query.filter(Notification.status == status)
    if date_from is not None:
        query = query.filter(Notification.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to is not None:
        query = query.filter(Notification.created_at <= datetime.combine(date_to, datetime.max.time()))
    if branch_id is not None:
        branch = db.query(Branch).filter(Branch.id == branch_id, Branch.business_id == business_id).first()
        if not branch:
            raise HTTPException(status_code=400, detail="Branch does not belong to this business")
        query = query.filter(_branch_scoped_condition(db, branch_id, Notification.related_entity_type, Notification.related_entity_id))

    total = query.count()
    rows = query.order_by(Notification.created_at.desc()).limit(page_size).offset((page - 1) * page_size).all()
    return paginate(rows, total, page, page_size)


# -------------------------
# BRANCH MANAGER NOTIFICATIONS (M9 follow-up fix)
# -------------------------

def get_branch_notifications(
    db: Session,
    branch_id: int,
    current_user: User,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    date_from: Optional[DateType] = None,
    date_to: Optional[DateType] = None,
) -> dict:
    branch = get_branch_by_id(db, branch_id)
    _require_branch_report_access(db, branch, current_user)

    query = db.query(Notification).filter(Notification.business_id == branch.business_id)
    query = query.filter(_branch_scoped_condition(db, branch_id, Notification.related_entity_type, Notification.related_entity_id))
    if status is not None:
        query = query.filter(Notification.status == status)
    if date_from is not None:
        query = query.filter(Notification.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to is not None:
        query = query.filter(Notification.created_at <= datetime.combine(date_to, datetime.max.time()))

    total = query.count()
    rows = query.order_by(Notification.created_at.desc()).limit(page_size).offset((page - 1) * page_size).all()
    return paginate(rows, total, page, page_size)


# -------------------------
# PLATFORM ANALYTICS (M9 Phase 6, PRD §35 — basic counts only;
# "advanced analytics and visual dashboards" is explicitly Future, PRD §36)
# -------------------------

def get_platform_analytics(db: Session) -> dict:
    return {
        "total_businesses": db.query(Business).count(),
        "pending_business_approvals": db.query(Business).filter(Business.status == "Pending").count(),
        "active_businesses": db.query(Business).filter(Business.status == "Active").count(),
        "active_branches": db.query(Branch).filter(
            Branch.approval_status == "Approved", Branch.is_active == True  # noqa: E712
        ).count(),
    }
