from datetime import date as DateType
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import User, Business, Branch, Resource, Booking, BranchService, ServiceTemplate
from crud_branch import _require_active_owner_membership, get_branch_by_id
from crud_service import _has_active_role, _get_manager_current_branch_id


# -------------------------
# BUSINESS OWNER REPORTS (M9 Phase 6, PRD §36 — 5 basic metrics only;
# "advanced analytics and visual dashboards" is explicitly Future)
# -------------------------

def get_business_reports(db: Session, business_id: int, current_user: User) -> dict:
    _require_active_owner_membership(db, business_id, current_user)

    total_bookings = db.query(Booking).filter(Booking.business_id == business_id).count()
    completed_bookings = db.query(Booking).filter(
        Booking.business_id == business_id, Booking.status == "Completed"
    ).count()
    cancelled_bookings = db.query(Booking).filter(
        Booking.business_id == business_id, Booking.status == "Cancelled"
    ).count()
    active_branches = db.query(Branch).filter(
        Branch.business_id == business_id, Branch.approval_status == "Approved", Branch.is_active == True  # noqa: E712
    ).count()
    active_resources = db.query(Resource).filter(
        Resource.business_id == business_id, Resource.status == "Active"
    ).count()

    return {
        "total_bookings": total_bookings,
        "completed_bookings": completed_bookings,
        "cancelled_bookings": cancelled_bookings,
        "active_branches": active_branches,
        "active_resources": active_resources,
    }


# -------------------------
# BRANCH MANAGER DAILY REPORTS (M9 Phase 6, PRD §36 — 3 basic metrics only)
# -------------------------

def _require_branch_report_access(db: Session, branch: Branch, current_user: User) -> None:
    """Business Owner (business-wide, BR-015) or Branch Manager restricted
    to their currently assigned branch (PRD §10.3 'View branch reports')."""
    if _has_active_role(db, branch.business_id, current_user.id, "BUSINESS_OWNER"):
        return
    if _get_manager_current_branch_id(db, branch.business_id, current_user.id) == branch.id:
        return
    raise HTTPException(status_code=403, detail="Not authorized to view reports for this branch")


def get_branch_daily_report(
    db: Session, branch_id: int, current_user: User, report_date: Optional[DateType] = None
) -> dict:
    branch = get_branch_by_id(db, branch_id)
    _require_branch_report_access(db, branch, current_user)

    target_date = report_date or DateType.today()

    daily_bookings = db.query(Booking).filter(
        Booking.branch_id == branch_id, Booking.booking_date == target_date
    ).count()

    resource_rows = (
        db.query(Resource.id, Resource.resource_name, Booking.id)
        .join(Booking, Booking.resource_id == Resource.id)
        .filter(Booking.branch_id == branch_id, Booking.booking_date == target_date)
        .all()
    )
    resource_counts: dict = {}
    for resource_id, resource_name, _booking_id in resource_rows:
        entry = resource_counts.setdefault(resource_id, {"resource_id": resource_id, "resource_name": resource_name, "booking_count": 0})
        entry["booking_count"] += 1
    resource_utilization = sorted(resource_counts.values(), key=lambda e: -e["booking_count"])

    service_rows = (
        db.query(BranchService.id, ServiceTemplate.name, Booking.id)
        .join(Booking, Booking.branch_service_id == BranchService.id)
        .join(ServiceTemplate, BranchService.service_template_id == ServiceTemplate.id)
        .filter(Booking.branch_id == branch_id, Booking.booking_date == target_date)
        .all()
    )
    service_counts: dict = {}
    for branch_service_id, service_name, _booking_id in service_rows:
        entry = service_counts.setdefault(branch_service_id, {"branch_service_id": branch_service_id, "service_name": service_name, "booking_count": 0})
        entry["booking_count"] += 1
    service_popularity = sorted(service_counts.values(), key=lambda e: -e["booking_count"])

    return {
        "report_date": target_date,
        "daily_bookings": daily_bookings,
        "resource_utilization": resource_utilization,
        "service_popularity": service_popularity,
    }
