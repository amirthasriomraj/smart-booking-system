from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime
from typing import Optional, List

from models import User, Business, BusinessMember, Role, Branch, BranchWorkingHours, Country
from audit import write_audit
from dependencies import user_has_role

BUSINESS_OWNER_ROLE_CODE = "BUSINESS_OWNER"


# -------------------------
# AUTHORIZATION HELPERS
# -------------------------

def _require_active_owner_membership(db: Session, business_id: int, current_user: User) -> Business:
    """
    Confirms current_user is the Active BUSINESS_OWNER member of business_id.
    Not a FastAPI Depends() since it needs the path business_id, same style
    as crud_business.get_business_by_id.
    """
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    membership = (
        db.query(BusinessMember)
        .join(Role, BusinessMember.role_id == Role.id)
        .filter(
            BusinessMember.business_id == business_id,
            BusinessMember.user_id == current_user.id,
            BusinessMember.status == "Active",
            Role.code == BUSINESS_OWNER_ROLE_CODE,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Business Owner privileges required for this business")

    return business


def get_branch_by_id(db: Session, branch_id: int) -> Branch:
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch


def get_branch_for_viewer(db: Session, branch_id: int, current_user: User) -> Branch:
    """Platform Admin may view any branch; otherwise must own the branch's business."""
    branch = get_branch_by_id(db, branch_id)
    if user_has_role(db, current_user.id, "PLATFORM_ADMIN"):
        return branch
    _require_active_owner_membership(db, branch.business_id, current_user)
    return branch


# -------------------------
# BUSINESS OWNER: BRANCH CRUD (PRD §12 Step 5, BR-011, BR-015)
# -------------------------

def create_branch(db: Session, business_id: int, payload, current_user: User) -> Branch:
    business = _require_active_owner_membership(db, business_id, current_user)

    if business.status != "Active":
        raise HTTPException(
            status_code=409,
            detail="Business must be approved and active before creating a branch",
        )

    country = db.query(Country).filter(Country.id == payload.country_id).first()
    if not country:
        raise HTTPException(status_code=400, detail="Invalid country")

    branch = Branch(
        business_id=business.id,
        branch_name=payload.branch_name,
        address=payload.address,
        city=payload.city,
        state=payload.state,
        postal_code=payload.postal_code,
        country_id=country.id,
        phone=payload.phone,
        email=payload.email,
        approval_status="Pending",
        is_active=False,
    )
    db.add(branch)
    db.flush()

    write_audit(
        db,
        business_id=business.id,
        entity_type="Branch",
        entity_id=branch.id,
        action="BRANCH_CREATED",
        performed_by=current_user.id,
        new_value="approval_status=Pending",
        commit=False,
    )

    db.commit()
    db.refresh(branch)
    return branch


def get_branches_for_business(db: Session, business_id: int, current_user: User) -> List[Branch]:
    """BR-015: Business Owners have complete visibility across every branch of their business."""
    _require_active_owner_membership(db, business_id, current_user)
    return (
        db.query(Branch)
        .filter(Branch.business_id == business_id)
        .order_by(Branch.created_at.desc())
        .all()
    )


def update_branch(db: Session, branch_id: int, payload, current_user: User) -> Branch:
    branch = get_branch_by_id(db, branch_id)
    _require_active_owner_membership(db, branch.business_id, current_user)

    updates = payload.model_dump(exclude_unset=True)

    if updates.get("country_id") is not None:
        country = db.query(Country).filter(Country.id == updates["country_id"]).first()
        if not country:
            raise HTTPException(status_code=400, detail="Invalid country")

    previous_name = branch.branch_name
    for field, value in updates.items():
        setattr(branch, field, value)

    write_audit(
        db,
        business_id=branch.business_id,
        entity_type="Branch",
        entity_id=branch.id,
        action="BRANCH_UPDATED",
        performed_by=current_user.id,
        previous_value=f"branch_name={previous_name}",
        new_value=f"branch_name={branch.branch_name}",
        commit=False,
    )

    db.commit()
    db.refresh(branch)
    return branch


def activate_branch(db: Session, branch_id: int, current_user: User) -> Branch:
    branch = get_branch_by_id(db, branch_id)
    _require_active_owner_membership(db, branch.business_id, current_user)

    if branch.approval_status != "Approved":
        raise HTTPException(
            status_code=409,
            detail=f"Branch must be Approved before activation (current approval_status: {branch.approval_status})",
        )
    if branch.is_active:
        raise HTTPException(status_code=409, detail="Branch is already active")

    branch.is_active = True

    write_audit(
        db,
        business_id=branch.business_id,
        entity_type="Branch",
        entity_id=branch.id,
        action="BRANCH_ACTIVATED",
        performed_by=current_user.id,
        previous_value="is_active=False",
        new_value="is_active=True",
        commit=False,
    )

    db.commit()
    db.refresh(branch)
    return branch


def deactivate_branch(db: Session, branch_id: int, current_user: User) -> Branch:
    branch = get_branch_by_id(db, branch_id)
    _require_active_owner_membership(db, branch.business_id, current_user)

    if not branch.is_active:
        raise HTTPException(status_code=409, detail="Branch is already inactive")

    branch.is_active = False

    write_audit(
        db,
        business_id=branch.business_id,
        entity_type="Branch",
        entity_id=branch.id,
        action="BRANCH_DEACTIVATED",
        performed_by=current_user.id,
        previous_value="is_active=True",
        new_value="is_active=False",
        commit=False,
    )

    db.commit()
    db.refresh(branch)
    return branch


# -------------------------
# PLATFORM ADMIN: BRANCH APPROVAL (BR-012, BR-013)
# -------------------------

def get_branches(db: Session, approval_status: Optional[str] = None) -> List[Branch]:
    query = db.query(Branch)
    if approval_status:
        query = query.filter(Branch.approval_status == approval_status)
    return query.order_by(Branch.created_at.desc()).all()


def approve_branch(db: Session, branch_id: int, admin_user: User) -> Branch:
    branch = get_branch_by_id(db, branch_id)

    if branch.approval_status != "Pending":
        raise HTTPException(
            status_code=409,
            detail=f"Branch is not pending approval (current approval_status: {branch.approval_status})",
        )

    previous_status = branch.approval_status
    branch.approval_status = "Approved"
    branch.approved_by = admin_user.id
    branch.approved_at = datetime.utcnow()

    write_audit(
        db,
        business_id=branch.business_id,
        entity_type="Branch",
        entity_id=branch.id,
        action="BRANCH_APPROVED",
        performed_by=admin_user.id,
        previous_value=f"approval_status={previous_status}",
        new_value="approval_status=Approved",
        commit=False,
    )

    db.commit()
    db.refresh(branch)
    return branch


def reject_branch(db: Session, branch_id: int, admin_user: User, reason: Optional[str] = None) -> Branch:
    branch = get_branch_by_id(db, branch_id)

    if branch.approval_status != "Pending":
        raise HTTPException(
            status_code=409,
            detail=f"Branch is not pending approval (current approval_status: {branch.approval_status})",
        )

    previous_status = branch.approval_status
    branch.approval_status = "Rejected"

    write_audit(
        db,
        business_id=branch.business_id,
        entity_type="Branch",
        entity_id=branch.id,
        action="BRANCH_REJECTED",
        performed_by=admin_user.id,
        previous_value=f"approval_status={previous_status}",
        new_value="approval_status=Rejected",
        reason=reason,
        commit=False,
    )

    db.commit()
    db.refresh(branch)
    return branch


# -------------------------
# BRANCH WORKING HOURS (BR-014)
# -------------------------

def get_working_hours(db: Session, branch_id: int, current_user: User) -> List[BranchWorkingHours]:
    branch = get_branch_by_id(db, branch_id)
    _require_active_owner_membership(db, branch.business_id, current_user)
    return (
        db.query(BranchWorkingHours)
        .filter(BranchWorkingHours.branch_id == branch_id)
        .order_by(BranchWorkingHours.weekday)
        .all()
    )


def upsert_working_hours(db: Session, branch_id: int, payload, current_user: User) -> List[BranchWorkingHours]:
    branch = get_branch_by_id(db, branch_id)
    _require_active_owner_membership(db, branch.business_id, current_user)

    existing = {
        row.weekday: row
        for row in db.query(BranchWorkingHours).filter(BranchWorkingHours.branch_id == branch_id).all()
    }

    for entry in payload.hours:
        row = existing.get(entry.weekday)
        if row:
            row.opening_time = entry.opening_time
            row.closing_time = entry.closing_time
            row.is_closed = entry.is_closed
        else:
            db.add(BranchWorkingHours(
                branch_id=branch_id,
                weekday=entry.weekday,
                opening_time=entry.opening_time,
                closing_time=entry.closing_time,
                is_closed=entry.is_closed,
            ))

    write_audit(
        db,
        business_id=branch.business_id,
        entity_type="Branch",
        entity_id=branch.id,
        action="BRANCH_WORKING_HOURS_UPDATED",
        performed_by=current_user.id,
        new_value=f"weekdays={sorted(e.weekday for e in payload.hours)}",
        commit=False,
    )

    db.commit()

    return (
        db.query(BranchWorkingHours)
        .filter(BranchWorkingHours.branch_id == branch_id)
        .order_by(BranchWorkingHours.weekday)
        .all()
    )
