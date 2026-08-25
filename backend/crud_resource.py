import secrets
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import (
    User,
    UserProfile,
    Business,
    BusinessMember,
    Role,
    Branch,
    BranchAssignment,
    ResourceCategory,
    Resource,
    ResourceWorkingHours,
)
from audit import write_audit
from auth import hash_password
from crud_branch import get_branch_by_id
import crud_staff

RESOURCE_INVITABLE_ROLE_CODE = "RESOURCE_USER"


# -------------------------
# LOOKUP HELPERS
# -------------------------

def _get_business_or_404(db: Session, business_id: int) -> Business:
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


def get_resource_or_404(db: Session, resource_id: int) -> Resource:
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource


def _get_category_or_404(db: Session, category_id: int) -> ResourceCategory:
    category = db.query(ResourceCategory).filter(ResourceCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Resource Category not found")
    return category


def _has_active_role(db: Session, business_id: int, user_id: int, role_code: str) -> bool:
    return (
        db.query(BusinessMember)
        .join(Role, BusinessMember.role_id == Role.id)
        .filter(
            BusinessMember.business_id == business_id,
            BusinessMember.user_id == user_id,
            BusinessMember.status == "Active",
            Role.code == role_code,
        )
        .first()
        is not None
    )


def _get_manager_current_branch_id(db: Session, business_id: int, user_id: int) -> Optional[int]:
    member = (
        db.query(BusinessMember)
        .join(Role, BusinessMember.role_id == Role.id)
        .filter(
            BusinessMember.business_id == business_id,
            BusinessMember.user_id == user_id,
            BusinessMember.status == "Active",
            Role.code == "BRANCH_MANAGER",
        )
        .first()
    )
    if not member:
        return None
    assignment = (
        db.query(BranchAssignment)
        .filter(BranchAssignment.business_member_id == member.id, BranchAssignment.is_current == True)  # noqa: E712
        .first()
    )
    return assignment.branch_id if assignment else None


def _get_resource_for_member(db: Session, member: BusinessMember) -> Optional[Resource]:
    if member.linked_resource_id is not None:
        return db.query(Resource).filter(Resource.id == member.linked_resource_id).first()
    return (
        db.query(Resource)
        .filter(Resource.linked_user_id == member.user_id, Resource.business_id == member.business_id)
        .first()
    )


# -------------------------
# AUTHORIZATION HELPERS (ID-016)
# -------------------------

def _require_category_write_access(db: Session, business_id: int, current_user: User) -> Business:
    """Resource Category create/update: Business Owner only (ID-015)."""
    business = _get_business_or_404(db, business_id)
    if not _has_active_role(db, business_id, current_user.id, "BUSINESS_OWNER"):
        raise HTTPException(status_code=403, detail="Business Owner privileges required for this business")
    return business


def _require_category_read_access(db: Session, business_id: int, current_user: User) -> Business:
    """Resource Category read: Business Owner or Branch Manager (ID-015)."""
    business = _get_business_or_404(db, business_id)
    if _has_active_role(db, business_id, current_user.id, "BUSINESS_OWNER"):
        return business
    if _get_manager_current_branch_id(db, business_id, current_user.id) is not None:
        return business
    raise HTTPException(status_code=403, detail="Not authorized to view Resource Categories for this business")


def _require_resource_record_access(db: Session, branch: Branch, current_user: User) -> Business:
    """
    Resource record CRUD/configuration/status: Business Owner (business-wide)
    or Branch Manager restricted to their currently assigned branch (ID-016).
    """
    business = _get_business_or_404(db, branch.business_id)
    if _has_active_role(db, business.id, current_user.id, "BUSINESS_OWNER"):
        return business
    if _get_manager_current_branch_id(db, business.id, current_user.id) == branch.id:
        return business
    raise HTTPException(status_code=403, detail="Not authorized to manage resources for this branch")


def _require_resource_read_access(db: Session, branch: Branch, current_user: User) -> Business:
    """
    Resource read: Business Owner (business-wide), HR User (business-wide,
    read only, for the Resource User workflow), or Branch Manager restricted
    to their currently assigned branch (ID-016).
    """
    business = _get_business_or_404(db, branch.business_id)
    if _has_active_role(db, business.id, current_user.id, "BUSINESS_OWNER"):
        return business
    if _has_active_role(db, business.id, current_user.id, "HR_USER"):
        return business
    if _get_manager_current_branch_id(db, business.id, current_user.id) == branch.id:
        return business
    raise HTTPException(status_code=403, detail="Not authorized to view resources for this branch")


def _require_business_wide_resource_read_access(db: Session, business_id: int, current_user: User) -> Business:
    """Business-wide resource listing: Business Owner or HR User (ID-016)."""
    business = _get_business_or_404(db, business_id)
    if _has_active_role(db, business_id, current_user.id, "BUSINESS_OWNER"):
        return business
    if _has_active_role(db, business_id, current_user.id, "HR_USER"):
        return business
    raise HTTPException(status_code=403, detail="Not authorized to view resources for this business")


def _require_resource_user_admin_access(
    db: Session, business_id: int, resource: Optional[Resource], current_user: User
) -> Business:
    """
    Resource User invite/resend/deactivate: Business Owner (business-wide),
    HR User (business-wide), or Branch Manager restricted to the resource's
    branch (ID-016).
    """
    business = _get_business_or_404(db, business_id)
    if _has_active_role(db, business_id, current_user.id, "BUSINESS_OWNER"):
        return business
    if _has_active_role(db, business_id, current_user.id, "HR_USER"):
        return business
    manager_branch_id = _get_manager_current_branch_id(db, business_id, current_user.id)
    if manager_branch_id is not None and resource is not None and resource.branch_id == manager_branch_id:
        return business
    raise HTTPException(status_code=403, detail="Not authorized to manage Resource Users for this business")


# -------------------------
# RESOURCE CATEGORY (ID-015)
# -------------------------

def create_resource_category(db: Session, business_id: int, payload, current_user: User) -> ResourceCategory:
    business = _require_category_write_access(db, business_id, current_user)

    category = ResourceCategory(
        business_id=business.id,
        category_name=payload.category_name,
        description=payload.description,
    )
    db.add(category)
    db.flush()

    write_audit(
        db,
        business_id=business.id,
        entity_type="ResourceCategory",
        entity_id=category.id,
        action="RESOURCE_CATEGORY_CREATED",
        performed_by=current_user.id,
        new_value=f"category_name={category.category_name}",
        commit=False,
    )

    db.commit()
    db.refresh(category)
    return category


def list_resource_categories(db: Session, business_id: int, current_user: User) -> List[ResourceCategory]:
    _require_category_read_access(db, business_id, current_user)
    return (
        db.query(ResourceCategory)
        .filter(ResourceCategory.business_id == business_id)
        .order_by(ResourceCategory.created_at.desc())
        .all()
    )


def update_resource_category(db: Session, category_id: int, payload, current_user: User) -> ResourceCategory:
    category = _get_category_or_404(db, category_id)
    _require_category_write_access(db, category.business_id, current_user)

    updates = payload.model_dump(exclude_unset=True)
    previous_name = category.category_name
    for field, value in updates.items():
        setattr(category, field, value)

    write_audit(
        db,
        business_id=category.business_id,
        entity_type="ResourceCategory",
        entity_id=category.id,
        action="RESOURCE_CATEGORY_UPDATED",
        performed_by=current_user.id,
        previous_value=f"category_name={previous_name}",
        new_value=f"category_name={category.category_name}",
        commit=False,
    )

    db.commit()
    db.refresh(category)
    return category


# -------------------------
# RESOURCE (PRD §14.3-14.5, ID-012, ID-013, ID-016)
# -------------------------

def create_resource(db: Session, branch_id: int, payload, current_user: User) -> Resource:
    # No branch approval_status/is_active gate here: PRD §13 "Pending
    # Approval" explicitly lists "Resources may be configured" among what is
    # allowed while a branch is still Pending Approval (only bookings are
    # blocked at that stage). Any existing branch is therefore a valid target
    # for resource creation regardless of its approval/activation state.
    branch = get_branch_by_id(db, branch_id)
    business = _require_resource_record_access(db, branch, current_user)

    category = _get_category_or_404(db, payload.resource_category_id)
    if category.business_id != business.id:
        raise HTTPException(status_code=400, detail="Resource Category does not belong to this business")

    resource = Resource(
        branch_id=branch.id,
        business_id=business.id,  # ID-012: denormalized at creation, immutable thereafter
        resource_category_id=category.id,
        resource_name=payload.resource_name,
        code=payload.code,
        description=payload.description,
        status="Pending",
        requires_login=payload.requires_login,
        max_bookings_per_day=payload.max_bookings_per_day,
        booking_buffer_minutes=payload.booking_buffer_minutes,
    )
    db.add(resource)
    db.flush()

    write_audit(
        db,
        business_id=business.id,
        entity_type="Resource",
        entity_id=resource.id,
        action="RESOURCE_CREATED",
        performed_by=current_user.id,
        new_value=f"resource_name={resource.resource_name};status=Pending",
        commit=False,
    )

    db.commit()
    db.refresh(resource)
    return resource


def list_resources_for_branch(db: Session, branch_id: int, current_user: User) -> List[Resource]:
    branch = get_branch_by_id(db, branch_id)
    _require_resource_read_access(db, branch, current_user)
    return (
        db.query(Resource)
        .filter(Resource.branch_id == branch_id)
        .order_by(Resource.created_at.desc())
        .all()
    )


def list_resources_for_business(db: Session, business_id: int, current_user: User) -> List[Resource]:
    _require_business_wide_resource_read_access(db, business_id, current_user)
    return (
        db.query(Resource)
        .filter(Resource.business_id == business_id)
        .order_by(Resource.created_at.desc())
        .all()
    )


def get_resource(db: Session, resource_id: int, current_user: User) -> Resource:
    resource = get_resource_or_404(db, resource_id)
    branch = get_branch_by_id(db, resource.branch_id)
    _require_resource_read_access(db, branch, current_user)
    return resource


def update_resource(db: Session, resource_id: int, payload, current_user: User) -> Resource:
    resource = get_resource_or_404(db, resource_id)
    branch = get_branch_by_id(db, resource.branch_id)
    business = _require_resource_record_access(db, branch, current_user)

    updates = payload.model_dump(exclude_unset=True)

    if "resource_category_id" in updates and updates["resource_category_id"] is not None:
        category = _get_category_or_404(db, updates["resource_category_id"])
        if category.business_id != business.id:
            raise HTTPException(status_code=400, detail="Resource Category does not belong to this business")

    previous_name = resource.resource_name
    for field, value in updates.items():
        setattr(resource, field, value)

    write_audit(
        db,
        business_id=business.id,
        entity_type="Resource",
        entity_id=resource.id,
        action="RESOURCE_UPDATED",
        performed_by=current_user.id,
        previous_value=f"resource_name={previous_name}",
        new_value=f"resource_name={resource.resource_name}",
        commit=False,
    )

    db.commit()
    db.refresh(resource)
    return resource


def activate_resource(db: Session, resource_id: int, current_user: User) -> Resource:
    resource = get_resource_or_404(db, resource_id)
    branch = get_branch_by_id(db, resource.branch_id)
    business = _require_resource_record_access(db, branch, current_user)

    if resource.status not in ("Pending", "Suspended"):
        raise HTTPException(
            status_code=409,
            detail=f"Resource cannot be activated from status {resource.status}",
        )
    if resource.requires_login and resource.linked_user_id is None:
        # ID-014: a login-required Resource cannot activate before the invited
        # Resource User has accepted.
        raise HTTPException(
            status_code=409,
            detail="Resource requires a linked Resource User before it can be activated",
        )

    previous_status = resource.status
    resource.status = "Active"

    write_audit(
        db,
        business_id=business.id,
        entity_type="Resource",
        entity_id=resource.id,
        action="RESOURCE_ACTIVATED",
        performed_by=current_user.id,
        previous_value=f"status={previous_status}",
        new_value="status=Active",
        commit=False,
    )

    db.commit()
    db.refresh(resource)
    return resource


def suspend_resource(db: Session, resource_id: int, current_user: User) -> Resource:
    resource = get_resource_or_404(db, resource_id)
    branch = get_branch_by_id(db, resource.branch_id)
    business = _require_resource_record_access(db, branch, current_user)

    if resource.status != "Active":
        raise HTTPException(status_code=409, detail="Only an Active resource can be suspended")

    resource.status = "Suspended"

    write_audit(
        db,
        business_id=business.id,
        entity_type="Resource",
        entity_id=resource.id,
        action="RESOURCE_SUSPENDED",
        performed_by=current_user.id,
        previous_value="status=Active",
        new_value="status=Suspended",
        commit=False,
    )

    db.commit()
    db.refresh(resource)
    return resource


# -------------------------
# RESOURCE WORKING HOURS (ID-013)
# -------------------------

def get_working_hours(db: Session, resource_id: int, current_user: User) -> List[ResourceWorkingHours]:
    resource = get_resource_or_404(db, resource_id)
    branch = get_branch_by_id(db, resource.branch_id)
    _require_resource_record_access(db, branch, current_user)
    return (
        db.query(ResourceWorkingHours)
        .filter(ResourceWorkingHours.resource_id == resource_id)
        .order_by(ResourceWorkingHours.weekday)
        .all()
    )


def upsert_working_hours(db: Session, resource_id: int, payload, current_user: User) -> List[ResourceWorkingHours]:
    resource = get_resource_or_404(db, resource_id)
    branch = get_branch_by_id(db, resource.branch_id)
    business = _require_resource_record_access(db, branch, current_user)

    existing = {
        row.weekday: row
        for row in db.query(ResourceWorkingHours).filter(ResourceWorkingHours.resource_id == resource_id).all()
    }

    for entry in payload.hours:
        row = existing.get(entry.weekday)
        if row:
            row.opening_time = entry.opening_time
            row.closing_time = entry.closing_time
            row.is_closed = entry.is_closed
            row.break_start_time = entry.break_start_time
            row.break_end_time = entry.break_end_time
        else:
            db.add(ResourceWorkingHours(
                resource_id=resource_id,
                weekday=entry.weekday,
                opening_time=entry.opening_time,
                closing_time=entry.closing_time,
                is_closed=entry.is_closed,
                break_start_time=entry.break_start_time,
                break_end_time=entry.break_end_time,
            ))

    write_audit(
        db,
        business_id=business.id,
        entity_type="Resource",
        entity_id=resource.id,
        action="RESOURCE_WORKING_HOURS_UPDATED",
        performed_by=current_user.id,
        new_value=f"weekdays={sorted(e.weekday for e in payload.hours)}",
        commit=False,
    )

    db.commit()

    return (
        db.query(ResourceWorkingHours)
        .filter(ResourceWorkingHours.resource_id == resource_id)
        .order_by(ResourceWorkingHours.weekday)
        .all()
    )


# -------------------------
# RESOURCE USER INVITATION (ID-014, ID-016)
# -------------------------

def serialize_resource_member(db: Session, member: BusinessMember) -> dict:
    user = db.query(User).filter(User.id == member.user_id).first()
    role = db.query(Role).filter(Role.id == member.role_id).first()
    resource = _get_resource_for_member(db, member)

    return {
        "id": member.id,
        "business_id": member.business_id,
        "resource_id": resource.id if resource else None,
        "user_id": member.user_id,
        "email": user.email,
        "role_code": role.code,
        "status": member.status,
        "joined_at": member.joined_at,
        "left_at": member.left_at,
    }


def invite_resource_user(
    db: Session, business_id: int, resource_id: int, payload, current_user: User
) -> Tuple[BusinessMember, str, str, str, str]:
    """
    Returns (member, raw_token, invitee_email, role_code, business_name),
    same shape as crud_staff.invite_staff_member, so the router can schedule
    the same invitation email as a background task (ID-014).
    """
    business = _get_business_or_404(db, business_id)
    if business.status != "Active":
        raise HTTPException(status_code=409, detail="Business must be Active before inviting a Resource User")

    resource = get_resource_or_404(db, resource_id)
    if resource.business_id != business.id:
        raise HTTPException(status_code=400, detail="Resource does not belong to this business")

    _require_resource_user_admin_access(db, business.id, resource, current_user)

    if not resource.requires_login:
        raise HTTPException(status_code=409, detail="This Resource does not require login")
    if resource.linked_user_id is not None:
        raise HTTPException(status_code=409, detail="This Resource already has a linked Resource User")

    existing_pending = (
        db.query(BusinessMember)
        .filter(BusinessMember.linked_resource_id == resource.id, BusinessMember.status == "Pending")
        .first()
    )
    if existing_pending:
        raise HTTPException(status_code=409, detail="An invitation for this Resource is already pending")

    role = crud_staff._get_role_by_code(db, RESOURCE_INVITABLE_ROLE_CODE)

    existing_user = db.query(User).filter(User.email == payload.email).first()

    if existing_user:
        # ID-007's rule applies unmodified: any Active/Pending membership anywhere blocks a new invite.
        blocking = (
            db.query(BusinessMember)
            .filter(
                BusinessMember.user_id == existing_user.id,
                BusinessMember.status.in_(["Active", "Pending"]),
            )
            .first()
        )
        if blocking:
            raise HTTPException(
                status_code=409,
                detail="This email already has an active or pending staff membership",
            )

        same_business_row = (
            db.query(BusinessMember)
            .filter(BusinessMember.business_id == business.id, BusinessMember.user_id == existing_user.id)
            .first()
        )
        if same_business_row:
            raise HTTPException(
                status_code=409,
                detail=(
                    "A prior membership exists for this person at this business; "
                    "same-business re-activation is not supported"
                ),
            )

    requires_credential_setup = existing_user is None

    if existing_user is None:
        placeholder_username = f"invite_{secrets.token_hex(8)}"
        placeholder_password_hash = hash_password(secrets.token_urlsafe(32))
        target_user = User(
            username=placeholder_username,
            email=payload.email,
            hashed_password=placeholder_password_hash,
            role="user",
            is_active=False,
        )
        db.add(target_user)
        db.flush()
        db.add(UserProfile(user_id=target_user.id))
    else:
        target_user = existing_user

    raw_token = crud_staff._generate_invitation_token()

    member = BusinessMember(
        business_id=business.id,
        user_id=target_user.id,
        role_id=role.id,
        status="Pending",
        requires_credential_setup=requires_credential_setup,
        linked_resource_id=resource.id,
        invitation_token_hash=crud_staff._hash_invitation_token(raw_token),
        invitation_token_expiry=datetime.utcnow() + crud_staff.INVITATION_TOKEN_TTL,
    )
    db.add(member)
    db.flush()

    write_audit(
        db,
        business_id=business.id,
        entity_type="BusinessMember",
        entity_id=member.id,
        action="RESOURCE_USER_INVITED",
        performed_by=current_user.id,
        new_value=f"resource_id={resource.id};email={payload.email}",
        commit=False,
    )

    db.commit()
    db.refresh(member)

    return member, raw_token, target_user.email, role.code, business.business_name


def resend_resource_invite(db: Session, member_id: int, current_user: User) -> Tuple[BusinessMember, str, str, str, str]:
    member = crud_staff._get_member_any_business(db, member_id)
    business = _get_business_or_404(db, member.business_id)

    role = db.query(Role).filter(Role.id == member.role_id).first()
    if role.code != RESOURCE_INVITABLE_ROLE_CODE:
        raise HTTPException(status_code=409, detail="Only a Resource User invitation can be resent here")
    if member.status != "Pending":
        raise HTTPException(status_code=409, detail="Only a Pending invitation can be resent")

    resource = _get_resource_for_member(db, member)
    _require_resource_user_admin_access(db, business.id, resource, current_user)

    raw_token = crud_staff._generate_invitation_token()
    member.invitation_token_hash = crud_staff._hash_invitation_token(raw_token)
    member.invitation_token_expiry = datetime.utcnow() + crud_staff.INVITATION_TOKEN_TTL

    write_audit(
        db,
        business_id=business.id,
        entity_type="BusinessMember",
        entity_id=member.id,
        action="INVITATION_RESENT",
        performed_by=current_user.id,
        commit=False,
    )

    db.commit()
    db.refresh(member)

    user = db.query(User).filter(User.id == member.user_id).first()
    return member, raw_token, user.email, role.code, business.business_name


def list_resource_users(db: Session, business_id: int, current_user: User) -> List[BusinessMember]:
    business = _get_business_or_404(db, business_id)

    is_owner_or_hr = _has_active_role(db, business_id, current_user.id, "BUSINESS_OWNER") or _has_active_role(
        db, business_id, current_user.id, "HR_USER"
    )
    manager_branch_id = None
    if not is_owner_or_hr:
        manager_branch_id = _get_manager_current_branch_id(db, business_id, current_user.id)
        if manager_branch_id is None:
            raise HTTPException(status_code=403, detail="Not authorized to view Resource Users for this business")

    members = (
        db.query(BusinessMember)
        .join(Role, BusinessMember.role_id == Role.id)
        .filter(BusinessMember.business_id == business.id, Role.code == RESOURCE_INVITABLE_ROLE_CODE)
        .order_by(BusinessMember.joined_at.desc())
        .all()
    )

    if manager_branch_id is None:
        return members

    scoped = []
    for m in members:
        resource = _get_resource_for_member(db, m)
        if resource is not None and resource.branch_id == manager_branch_id:
            scoped.append(m)
    return scoped


def deactivate_resource_user(db: Session, member_id: int, current_user: User) -> BusinessMember:
    member = crud_staff._get_member_any_business(db, member_id)
    business = _get_business_or_404(db, member.business_id)

    role = db.query(Role).filter(Role.id == member.role_id).first()
    if role.code != RESOURCE_INVITABLE_ROLE_CODE:
        raise HTTPException(status_code=409, detail="Only a Resource User membership can be deactivated here")
    if member.status == "Inactive":
        raise HTTPException(status_code=409, detail="Membership is already inactive")

    resource = _get_resource_for_member(db, member)
    _require_resource_user_admin_access(db, business.id, resource, current_user)

    previous_status = member.status
    member.status = "Inactive"
    member.left_at = datetime.utcnow()
    # ID-014: deactivating the membership never changes Resource.status —
    # login access and Resource schedulability are tracked independently.

    write_audit(
        db,
        business_id=business.id,
        entity_type="BusinessMember",
        entity_id=member.id,
        action="EMPLOYEE_DEACTIVATED",
        performed_by=current_user.id,
        previous_value=f"status={previous_status}",
        new_value="status=Inactive",
        commit=False,
    )

    db.commit()
    db.refresh(member)
    return member
