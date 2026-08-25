import secrets
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import User, UserProfile, Business, BusinessMember, Role, Branch, BranchAssignment, Resource
from audit import write_audit
from auth import hash_password, validate_password
from crud_branch import _require_active_owner_membership, get_branch_by_id

INVITATION_TOKEN_TTL = timedelta(days=7)  # IMPLEMENTATION_DECISIONS.md ID-009

# Milestone 4 (ID-014): RESOURCE_USER is added to the set of role codes that
# flow through this shared invitation mechanism (token hash/expiry,
# requires_credential_setup, /auth/accept-invitation — see accept_invitation
# below, which handles all three codes). Its invitation flow has a different
# authorization matrix (ID-016) and a different companion staging field
# (linked_resource_id, not branch_id/invited_branch_id), so *creating* a
# Resource User invitation goes through crud_resource.invite_resource_user,
# not invite_staff_member() below — that stays scoped to
# _STAFF_INVITE_ROLE_CODES (ID-006, unchanged from Milestone 3).
#
# Neither the PRD/TAS nor IMPLEMENTATION_DECISIONS.md says Resource Users
# should appear in the Milestone 3 Business Owner "Staff" list/UI — that
# surface (list_staff below, StaffManagement.jsx) was built for Branch
# Manager/HR onboarding. Resource Users are listed/managed through the
# dedicated Milestone 4 endpoints instead (crud_resource.list_resource_users,
# GET /businesses/{id}/resource-users). list_staff therefore filters on
# _STAFF_INVITE_ROLE_CODES, not the broader INVITABLE_ROLE_CODES.
INVITABLE_ROLE_CODES = {"BRANCH_MANAGER", "HR_USER", "RESOURCE_USER"}
_STAFF_INVITE_ROLE_CODES = {"BRANCH_MANAGER", "HR_USER"}


# -------------------------
# TOKEN HELPERS
# -------------------------

def _generate_invitation_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_invitation_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _get_role_by_code(db: Session, code: str) -> Role:
    role = db.query(Role).filter(Role.code == code).first()
    if not role:
        raise HTTPException(status_code=500, detail=f"{code} role is not seeded. Run database migrations first.")
    return role


# -------------------------
# SERIALIZATION
# -------------------------

def serialize_member(db: Session, member: BusinessMember) -> dict:
    user = db.query(User).filter(User.id == member.user_id).first()
    role = db.query(Role).filter(Role.id == member.role_id).first()

    current_assignment = (
        db.query(BranchAssignment)
        .filter(BranchAssignment.business_member_id == member.id, BranchAssignment.is_current == True)  # noqa: E712
        .first()
    )
    branch = None
    if current_assignment:
        branch = db.query(Branch).filter(Branch.id == current_assignment.branch_id).first()

    return {
        "id": member.id,
        "business_id": member.business_id,
        "user_id": member.user_id,
        "email": user.email,
        "role_code": role.code,
        "status": member.status,
        "current_branch_id": branch.id if branch else None,
        "current_branch_name": branch.branch_name if branch else None,
        "joined_at": member.joined_at,
        "left_at": member.left_at,
    }


# -------------------------
# LOOKUP HELPERS
# -------------------------

def _get_member_in_business(db: Session, member_id: int, business_id: int) -> BusinessMember:
    member = (
        db.query(BusinessMember)
        .filter(BusinessMember.id == member_id, BusinessMember.business_id == business_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Business member not found")
    return member


def _get_member_any_business(db: Session, member_id: int) -> BusinessMember:
    member = db.query(BusinessMember).filter(BusinessMember.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Business member not found")
    return member


# -------------------------
# INVITE (ID-005, ID-006, ID-007, ID-010)
# -------------------------

def invite_staff_member(db: Session, business_id: int, payload, current_user: User) -> Tuple[BusinessMember, str, str, str, str]:
    """
    Returns (member, raw_token, invitee_email, role_code, business_name) so
    the router can schedule the invitation email as a background task.
    """
    business = _require_active_owner_membership(db, business_id, current_user)  # ID-006: Business Owner only

    if business.status != "Active":
        raise HTTPException(status_code=409, detail="Business must be Active before inviting staff")

    if payload.role_code not in _STAFF_INVITE_ROLE_CODES:
        raise HTTPException(status_code=400, detail="role_code must be BRANCH_MANAGER or HR_USER")

    role = _get_role_by_code(db, payload.role_code)

    branch = None
    if payload.role_code == "BRANCH_MANAGER":
        if not payload.branch_id:
            raise HTTPException(status_code=400, detail="branch_id is required for a Branch Manager invitation")
        branch = get_branch_by_id(db, payload.branch_id)
        if branch.business_id != business.id:
            raise HTTPException(status_code=400, detail="Branch does not belong to this business")
        if branch.approval_status != "Approved":  # Decision 3 / ID-010
            raise HTTPException(
                status_code=409,
                detail="Branch must be Approved before a Branch Manager can be invited to it",
            )
    elif payload.branch_id is not None:
        raise HTTPException(status_code=400, detail="branch_id is not allowed for an HR User invitation")

    existing_user = db.query(User).filter(User.email == payload.email).first()

    if existing_user:
        # ID-007: block if this email already has an Active/Pending membership anywhere.
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

        # ID-007: same-business rehire is explicitly unsupported, regardless of status.
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
        # ID-005: mechanical placeholder, never disclosed, overwritten at acceptance.
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

        # Every User row created elsewhere in this codebase (crud.create_user,
        # crud_business.register_business) unconditionally pairs a UserProfile
        # in the same transaction. Case A must preserve that invariant too.
        db.add(UserProfile(user_id=target_user.id))
    else:
        target_user = existing_user  # ID-007: reused as-is, never modified here.

    raw_token = _generate_invitation_token()

    member = BusinessMember(
        business_id=business.id,
        user_id=target_user.id,
        role_id=role.id,
        status="Pending",
        requires_credential_setup=requires_credential_setup,
        invited_branch_id=branch.id if branch else None,
        invitation_token_hash=_hash_invitation_token(raw_token),
        invitation_token_expiry=datetime.utcnow() + INVITATION_TOKEN_TTL,
    )
    db.add(member)
    db.flush()

    write_audit(
        db,
        business_id=business.id,
        entity_type="BusinessMember",
        entity_id=member.id,
        action="EMPLOYEE_INVITED",
        performed_by=current_user.id,
        new_value=f"role={role.code};email={payload.email}",
        commit=False,
    )

    db.commit()
    db.refresh(member)

    return member, raw_token, target_user.email, role.code, business.business_name


# -------------------------
# RESEND (ID-009)
# -------------------------

def resend_invitation(db: Session, business_id: int, member_id: int, current_user: User) -> Tuple[BusinessMember, str, str, str, str]:
    business = _require_active_owner_membership(db, business_id, current_user)
    member = _get_member_in_business(db, member_id, business.id)

    if member.status != "Pending":
        raise HTTPException(status_code=409, detail="Only a Pending invitation can be resent")

    raw_token = _generate_invitation_token()
    member.invitation_token_hash = _hash_invitation_token(raw_token)
    member.invitation_token_expiry = datetime.utcnow() + INVITATION_TOKEN_TTL

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
    role = db.query(Role).filter(Role.id == member.role_id).first()

    return member, raw_token, user.email, role.code, business.business_name


# -------------------------
# LIST / DETAIL
# -------------------------

def list_staff(db: Session, business_id: int, current_user: User) -> List[BusinessMember]:
    """
    Milestone 3's Staff list — Branch Manager / HR User only (unchanged).
    Resource Users are listed separately via
    crud_resource.list_resource_users (ID-016).
    """
    _require_active_owner_membership(db, business_id, current_user)
    return (
        db.query(BusinessMember)
        .join(Role, BusinessMember.role_id == Role.id)
        .filter(BusinessMember.business_id == business_id, Role.code.in_(_STAFF_INVITE_ROLE_CODES))
        .order_by(BusinessMember.joined_at.desc())
        .all()
    )


def get_staff_member(db: Session, member_id: int, current_user: User) -> BusinessMember:
    member = _get_member_any_business(db, member_id)
    _require_active_owner_membership(db, member.business_id, current_user)
    return member


# -------------------------
# TRANSFER (Decision 11 / ID-011, ID-004)
# -------------------------

def transfer_branch(db: Session, member_id: int, payload, current_user: User) -> BusinessMember:
    member = _get_member_any_business(db, member_id)
    business = _require_active_owner_membership(db, member.business_id, current_user)

    role = db.query(Role).filter(Role.id == member.role_id).first()
    if role.code != "BRANCH_MANAGER":
        raise HTTPException(status_code=409, detail="Only Branch Manager members can be transferred between branches")

    if member.status != "Active":
        raise HTTPException(status_code=409, detail="Only an Active member has a current branch assignment to transfer")

    new_branch = get_branch_by_id(db, payload.branch_id)
    if new_branch.business_id != business.id:
        raise HTTPException(status_code=400, detail="Branch does not belong to this business")
    if new_branch.approval_status != "Approved":
        raise HTTPException(status_code=409, detail="Target branch must be Approved")

    current_assignment = (
        db.query(BranchAssignment)
        .filter(BranchAssignment.business_member_id == member.id, BranchAssignment.is_current == True)  # noqa: E712
        .first()
    )
    if not current_assignment:
        raise HTTPException(status_code=409, detail="No current branch assignment found to transfer")

    if current_assignment.branch_id == new_branch.id:
        raise HTTPException(status_code=409, detail="Member is already assigned to this branch")

    previous_branch_id = current_assignment.branch_id
    now = datetime.utcnow()

    current_assignment.is_current = False
    current_assignment.assigned_to = now
    db.flush()  # close the old row before inserting the new one (partial unique index)

    db.add(BranchAssignment(
        business_member_id=member.id,
        branch_id=new_branch.id,
        assigned_from=now,
        is_current=True,
    ))

    write_audit(
        db,
        business_id=business.id,
        entity_type="BranchAssignment",
        entity_id=member.id,
        action="EMPLOYEE_TRANSFER",
        performed_by=current_user.id,
        previous_value=f"branch_id={previous_branch_id}",
        new_value=f"branch_id={new_branch.id}",
        commit=False,
    )

    db.commit()
    db.refresh(member)
    return member


# -------------------------
# DEACTIVATE (Decision 8 / ID-008)
# -------------------------

def deactivate_member(db: Session, member_id: int, current_user: User) -> BusinessMember:
    member = _get_member_any_business(db, member_id)
    business = _require_active_owner_membership(db, member.business_id, current_user)

    if member.status == "Inactive":
        raise HTTPException(status_code=409, detail="Membership is already inactive")

    previous_status = member.status
    member.status = "Inactive"
    member.left_at = datetime.utcnow()

    role = db.query(Role).filter(Role.id == member.role_id).first()
    if role.code == "BRANCH_MANAGER":
        current_assignment = (
            db.query(BranchAssignment)
            .filter(BranchAssignment.business_member_id == member.id, BranchAssignment.is_current == True)  # noqa: E712
            .first()
        )
        if current_assignment:  # None for a still-Pending invite (ID-010) — nothing to close
            current_assignment.is_current = False
            current_assignment.assigned_to = datetime.utcnow()

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


# -------------------------
# ACCEPT INVITATION (public, token-authenticated)
# -------------------------

def _find_pending_member_by_token(db: Session, token: str) -> BusinessMember:
    token_hash = _hash_invitation_token(token)
    member = db.query(BusinessMember).filter(BusinessMember.invitation_token_hash == token_hash).first()

    invalid = HTTPException(status_code=400, detail="Invalid or expired invitation token")

    if not member or member.status != "Pending":
        raise invalid
    if not member.invitation_token_expiry or member.invitation_token_expiry < datetime.utcnow():
        raise invalid

    return member


def get_invitation_status(db: Session, token: str) -> Tuple[BusinessMember, Business, Role, Optional[Branch]]:
    member = _find_pending_member_by_token(db, token)
    business = db.query(Business).filter(Business.id == member.business_id).first()
    role = db.query(Role).filter(Role.id == member.role_id).first()

    branch = None
    if member.invited_branch_id is not None:  # ID-010: HR invitations never set this
        branch = db.query(Branch).filter(Branch.id == member.invited_branch_id).first()

    return member, business, role, branch


def accept_invitation(db: Session, payload) -> BusinessMember:
    member = _find_pending_member_by_token(db, payload.token)
    user = db.query(User).filter(User.id == member.user_id).first()

    if member.requires_credential_setup:
        # Case A: brand-new invitee — must set real credentials now.
        if not payload.username or not payload.password:
            raise HTTPException(
                status_code=400,
                detail="username and password are required to accept this invitation",
            )
        clashing_username = (
            db.query(User).filter(User.username == payload.username, User.id != user.id).first()
        )
        if clashing_username:
            raise HTTPException(status_code=409, detail="Username already exists")
        validate_password(payload.password)

        user.username = payload.username
        user.hashed_password = hash_password(payload.password)
        user.is_active = True
    else:
        # Case B: existing user — credentials are never touched (ID-005).
        if payload.username or payload.password:
            raise HTTPException(
                status_code=400,
                detail="This account already has credentials; username/password are not accepted",
            )

    role = db.query(Role).filter(Role.id == member.role_id).first()

    if role.code == "BRANCH_MANAGER":
        branch = db.query(Branch).filter(Branch.id == member.invited_branch_id).first()
        if not branch or branch.approval_status != "Approved":
            # Re-validated at acceptance per ID-010 — the branch may have sat Pending for up to 7 days.
            raise HTTPException(
                status_code=409,
                detail="The assigned branch is no longer eligible; contact your Business Owner",
            )
        db.add(BranchAssignment(
            business_member_id=member.id,
            branch_id=branch.id,
            assigned_from=datetime.utcnow(),
            is_current=True,
        ))
        member.invited_branch_id = None  # ID-010: cleared once the real assignment exists
    elif role.code == "RESOURCE_USER":
        # ID-014: mirrors the BRANCH_MANAGER staging pattern above, using
        # linked_resource_id/Resource.linked_user_id instead of
        # invited_branch_id/BranchAssignment.
        resource = db.query(Resource).filter(Resource.id == member.linked_resource_id).first()
        if not resource:
            raise HTTPException(status_code=409, detail="The linked Resource no longer exists")
        resource.linked_user_id = user.id
        member.linked_resource_id = None

    previous_status = member.status
    member.status = "Active"
    member.invitation_token_hash = None
    member.invitation_token_expiry = None

    write_audit(
        db,
        business_id=member.business_id,
        entity_type="BusinessMember",
        entity_id=member.id,
        action="INVITATION_ACCEPTED",
        performed_by=user.id,
        previous_value=f"status={previous_status}",
        new_value="status=Active",
        commit=False,
    )

    db.commit()
    db.refresh(member)
    return member
