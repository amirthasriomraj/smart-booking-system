import secrets
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from fastapi import HTTPException

from models import (
    User,
    UserProfile,
    UserRole,
    Role,
    Business,
    BusinessMember,
    Branch,
    BranchService,
    ServiceTemplate,
    Country,
    PlatformCustomer,
    BusinessCustomer,
)
from audit import write_audit
from auth import hash_password, validate_password

# Milestone 6 (ID-030): mechanical placeholder identity for a staff-created
# walk-in customer with no existing platform identity, mirroring ID-005's
# staff-invitation placeholder exactly (random, never-disclosed username and
# password hash). The reserved prefix additionally lets self-registration
# (ID-031) recognize an *unclaimed* placeholder and safely distinguish it
# from a genuinely deactivated real account (crud.deactivate_user also sets
# is_active=False, but never uses this prefix) before overwriting credentials.
CUSTOMER_PLACEHOLDER_USERNAME_PREFIX = "cust_walkin_"
PLACEHOLDER_EMAIL_DOMAIN = "placeholder.smartbooking.local"

_PROFILE_FIELD_MAP = {
    "first_name": "first_name",
    "last_name": "last_name",
    "mobile_number": "phone",
    "gender": "gender",
    "date_of_birth": "date_of_birth",
    "address_line": "address_line",
    "city": "city",
    "state": "state",
    "country_id": "country_id",
    "postal_code": "postal_code",
}


# -------------------------
# LOOKUP HELPERS
# -------------------------

def _get_business_or_404(db: Session, business_id: int) -> Business:
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


def _get_role_by_code(db: Session, code: str) -> Role:
    role = db.query(Role).filter(Role.code == code).first()
    if not role:
        raise HTTPException(status_code=500, detail=f"{code} role is not seeded. Run database migrations first.")
    return role


def _get_business_customer_or_404(db: Session, business_customer_id: int) -> BusinessCustomer:
    bc = db.query(BusinessCustomer).filter(BusinessCustomer.id == business_customer_id).first()
    if not bc:
        raise HTTPException(status_code=404, detail="Customer not found")
    return bc


# -------------------------
# AUTHORIZATION HELPERS (ID-032)
# -------------------------

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


def _require_customer_access(db: Session, business_id: int, current_user: User) -> Business:
    """
    Customer Management (create/list/read/edit/status): Business Owner or
    Branch Manager, business-wide — Customer is a business-scoped entity
    with no branch_id (ID-032), so both roles get identical, unrestricted
    access across the whole business.
    """
    business = _get_business_or_404(db, business_id)
    if _has_active_role(db, business_id, current_user.id, "BUSINESS_OWNER"):
        return business
    if _has_active_role(db, business_id, current_user.id, "BRANCH_MANAGER"):
        return business
    raise HTTPException(status_code=403, detail="Not authorized to manage customers for this business")


def _require_customer_self(db: Session, current_user: User) -> PlatformCustomer:
    platform_customer = db.query(PlatformCustomer).filter(PlatformCustomer.user_id == current_user.id).first()
    if not platform_customer:
        raise HTTPException(status_code=403, detail="No Customer account for this user")
    return platform_customer


# -------------------------
# PLATFORM IDENTITY HELPERS (ID-028, ID-029, ID-030, ID-031)
# -------------------------

def _ensure_customer_role(db: Session, user_id: int) -> None:
    role = _get_role_by_code(db, "CUSTOMER")
    exists = (
        db.query(UserRole).filter(UserRole.user_id == user_id, UserRole.role_id == role.id).first()
    )
    if not exists:
        db.add(UserRole(user_id=user_id, role_id=role.id))


def _get_or_create_platform_customer(db: Session, user: User) -> PlatformCustomer:
    platform_customer = db.query(PlatformCustomer).filter(PlatformCustomer.user_id == user.id).first()
    if platform_customer:
        return platform_customer
    platform_customer = PlatformCustomer(user_id=user.id)
    db.add(platform_customer)
    db.flush()
    return platform_customer


def _is_unclaimed_placeholder(user: User) -> bool:
    """A walk-in placeholder identity (ID-030) never claimed with real credentials (ID-031)."""
    return user.is_active is False and user.username.startswith(CUSTOMER_PLACEHOLDER_USERNAME_PREFIX)


def _validate_country(db: Session, country_id: Optional[int]) -> None:
    if country_id is not None and not db.query(Country).filter(Country.id == country_id).first():
        raise HTTPException(status_code=400, detail="Invalid country")


def _apply_profile_updates(profile: UserProfile, updates: dict) -> None:
    for field, value in updates.items():
        column = _PROFILE_FIELD_MAP.get(field)
        if column:
            setattr(profile, column, value)


def _generate_customer_number(business_customer_id: int) -> str:
    """ID-033: collision-safe by construction — no counter, no locking."""
    return f"CUST-{business_customer_id:06d}"


# -------------------------
# SERIALIZATION
# -------------------------

def _serialize_platform_customer(user: User, platform_customer: PlatformCustomer, profile: Optional[UserProfile]) -> dict:
    return {
        "platform_customer_id": platform_customer.id,
        "user_id": user.id,
        "email": user.email,
        "first_name": profile.first_name if profile else None,
        "last_name": profile.last_name if profile else None,
        "mobile_number": profile.phone if profile else None,
        "gender": profile.gender if profile else None,
        "date_of_birth": profile.date_of_birth if profile else None,
        "address_line": profile.address_line if profile else None,
        "city": profile.city if profile else None,
        "state": profile.state if profile else None,
        "country_id": profile.country_id if profile else None,
        "postal_code": profile.postal_code if profile else None,
        "preferred_language": platform_customer.preferred_language,
        "preferred_timezone": platform_customer.preferred_timezone,
    }


def serialize_business_customer(db: Session, bc: BusinessCustomer) -> dict:
    platform_customer = db.query(PlatformCustomer).filter(PlatformCustomer.id == bc.platform_customer_id).first()
    user = db.query(User).filter(User.id == platform_customer.user_id).first()
    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()

    return {
        "id": bc.id,
        "business_id": bc.business_id,
        "platform_customer_id": platform_customer.id,
        "customer_number": bc.customer_number,
        "status": bc.status,
        "notes": bc.notes,
        "first_visit_at": bc.first_visit_at,
        "last_visit_at": bc.last_visit_at,
        "created_at": bc.created_at,
        "email": user.email,
        "first_name": profile.first_name if profile else None,
        "last_name": profile.last_name if profile else None,
        "mobile_number": profile.phone if profile else None,
        "gender": profile.gender if profile else None,
        "date_of_birth": profile.date_of_birth if profile else None,
        "address_line": profile.address_line if profile else None,
        "city": profile.city if profile else None,
        "state": profile.state if profile else None,
        "country_id": profile.country_id if profile else None,
        "postal_code": profile.postal_code if profile else None,
    }


def serialize_browse_service(db: Session, branch_service: BranchService) -> dict:
    template = db.query(ServiceTemplate).filter(ServiceTemplate.id == branch_service.service_template_id).first()
    return {
        "id": branch_service.id,
        "branch_id": branch_service.branch_id,
        "service_template_id": branch_service.service_template_id,
        "name": template.name if template else None,
        "description": template.description if template else None,
        "duration": branch_service.duration,
        "price": branch_service.price,
    }


# -------------------------
# CUSTOMER SELF-REGISTRATION (PRD §17.5, ID-034)
# -------------------------

def register_customer(db: Session, payload) -> dict:
    """
    Creates only the platform identity (User + UserProfile +
    UserRole(CUSTOMER) + PlatformCustomer). No BusinessCustomer is created
    here — that relationship is only created once the customer actually
    interacts with a specific business (a staff-created walk-in row, or,
    Milestone 7, their first booking).

    The `username` login handle is set to the customer's own email address:
    PRD §17.5 lists no separate username field, but the existing `User`
    schema requires one, and login is username-based (crud.authenticate_user)
    — using the email the customer already knows satisfies PRD §33.2's
    "Username/Email + Password Login" without changing the shared login
    endpoint or asking for a field the PRD doesn't define.
    """
    validate_password(payload.password)

    existing_user = db.query(User).filter(User.email == payload.email).first()

    if existing_user and not _is_unclaimed_placeholder(existing_user):
        raise HTTPException(status_code=409, detail="Email already registered")

    if existing_user:
        # ID-031: upgrade the unclaimed walk-in placeholder in place —
        # credentials are the only thing that change.
        user = existing_user
        user.username = payload.email
        user.hashed_password = hash_password(payload.password)
        user.is_active = True
        profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
        if profile is None:
            profile = UserProfile(user_id=user.id)
            db.add(profile)
    else:
        user = User(
            username=payload.email,
            email=payload.email,
            hashed_password=hash_password(payload.password),
            role="user",
            is_active=True,
        )
        db.add(user)
        db.flush()
        profile = UserProfile(user_id=user.id)
        db.add(profile)

    profile.first_name = payload.first_name
    profile.last_name = payload.last_name
    profile.phone = payload.mobile_number

    _ensure_customer_role(db, user.id)
    platform_customer = _get_or_create_platform_customer(db, user)
    db.flush()

    write_audit(
        db,
        entity_type="PlatformCustomer",
        entity_id=platform_customer.id,
        action="CUSTOMER_CREATED",
        performed_by=user.id,
        new_value=f"email={user.email}",
        commit=False,
    )

    db.commit()
    db.refresh(user)
    db.refresh(profile)
    db.refresh(platform_customer)
    return _serialize_platform_customer(user, platform_customer, profile)


# -------------------------
# CUSTOMER SELF PROFILE (BR-040)
# -------------------------

def get_own_customer_profile(db: Session, current_user: User) -> dict:
    platform_customer = _require_customer_self(db, current_user)
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    return _serialize_platform_customer(current_user, platform_customer, profile)


def update_own_customer_profile(db: Session, current_user: User, payload) -> dict:
    platform_customer = _require_customer_self(db, current_user)
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if profile is None:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)

    updates = payload.model_dump(exclude_unset=True)
    _validate_country(db, updates.get("country_id"))

    if "preferred_language" in updates:
        platform_customer.preferred_language = updates.pop("preferred_language")
    if "preferred_timezone" in updates:
        platform_customer.preferred_timezone = updates.pop("preferred_timezone")

    _apply_profile_updates(profile, updates)

    write_audit(
        db,
        entity_type="PlatformCustomer",
        entity_id=platform_customer.id,
        action="CUSTOMER_UPDATED",
        performed_by=current_user.id,
        commit=False,
    )

    db.commit()
    db.refresh(platform_customer)
    db.refresh(profile)
    return _serialize_platform_customer(current_user, platform_customer, profile)


# -------------------------
# STAFF-CREATED / WALK-IN CUSTOMER (PRD §17.4, BR-037, BR-038, ID-031)
# -------------------------

def create_walk_in_customer(db: Session, business_id: int, payload, current_user: User) -> BusinessCustomer:
    business = _require_customer_access(db, business_id, current_user)
    _validate_country(db, payload.country_id)

    target_user = None
    if payload.email:
        target_user = db.query(User).filter(User.email == payload.email).first()  # ID-031: reuse as-is

    if target_user is None:
        placeholder_username = f"{CUSTOMER_PLACEHOLDER_USERNAME_PREFIX}{secrets.token_hex(8)}"
        placeholder_email = payload.email or f"{placeholder_username}@{PLACEHOLDER_EMAIL_DOMAIN}"
        target_user = User(
            username=placeholder_username,
            email=placeholder_email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            role="user",
            is_active=False,
        )
        db.add(target_user)
        db.flush()
        profile = UserProfile(user_id=target_user.id)
        db.add(profile)
    else:
        # SessionLocal has autoflush=False (database.py) — target_user here
        # is always a pre-existing, already-committed row, so this query is
        # safe (unlike the newly-created branch above, where the just-added
        # UserProfile isn't visible to a query without an explicit flush).
        profile = db.query(UserProfile).filter(UserProfile.user_id == target_user.id).first()
        if profile is None:
            profile = UserProfile(user_id=target_user.id)
            db.add(profile)

    _apply_profile_updates(profile, payload.model_dump(exclude={"email", "notes"}, exclude_unset=True))

    _ensure_customer_role(db, target_user.id)
    platform_customer = _get_or_create_platform_customer(db, target_user)

    existing_bc = (
        db.query(BusinessCustomer)
        .filter(
            BusinessCustomer.business_id == business.id,
            BusinessCustomer.platform_customer_id == platform_customer.id,
        )
        .first()
    )
    if existing_bc:
        raise HTTPException(status_code=409, detail="This customer already exists for this business")

    business_customer = BusinessCustomer(
        business_id=business.id,
        platform_customer_id=platform_customer.id,
        customer_number="PENDING",
        notes=payload.notes,
        status="Active",
    )
    db.add(business_customer)
    db.flush()  # ID-033: assign id before generating customer_number
    business_customer.customer_number = _generate_customer_number(business_customer.id)

    write_audit(
        db,
        business_id=business.id,
        entity_type="BusinessCustomer",
        entity_id=business_customer.id,
        action="CUSTOMER_CREATED",
        performed_by=current_user.id,
        new_value=f"customer_number={business_customer.customer_number}",
        commit=False,
    )

    db.commit()
    db.refresh(business_customer)
    return business_customer


# -------------------------
# BUSINESS CUSTOMER MANAGEMENT (PRD §17.6, ID-032)
# -------------------------

def list_business_customers(
    db: Session,
    business_id: int,
    current_user: User,
    limit: int,
    offset: int,
    sort: str,
    search: Optional[str],
) -> dict:
    business = _require_customer_access(db, business_id, current_user)

    query = (
        db.query(BusinessCustomer)
        .join(PlatformCustomer, BusinessCustomer.platform_customer_id == PlatformCustomer.id)
        .join(User, PlatformCustomer.user_id == User.id)
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
        .filter(BusinessCustomer.business_id == business.id)
    )

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                User.email.ilike(like),
                UserProfile.first_name.ilike(like),
                UserProfile.last_name.ilike(like),
                UserProfile.phone.ilike(like),
                BusinessCustomer.customer_number.ilike(like),
            )
        )

    total = query.count()

    sort_field = sort[1:] if sort.startswith("-") else sort
    sort_column = {
        "created_at": BusinessCustomer.created_at,
        "customer_number": BusinessCustomer.customer_number,
        "status": BusinessCustomer.status,
    }.get(sort_field, BusinessCustomer.created_at)
    query = query.order_by(desc(sort_column) if sort.startswith("-") else sort_column)

    rows = query.limit(limit).offset(offset).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [serialize_business_customer(db, bc) for bc in rows],
    }


def get_business_customer(db: Session, business_customer_id: int, current_user: User) -> BusinessCustomer:
    bc = _get_business_customer_or_404(db, business_customer_id)
    _require_customer_access(db, bc.business_id, current_user)
    return bc


def update_business_customer(db: Session, business_customer_id: int, payload, current_user: User) -> BusinessCustomer:
    """
    Staff-side edit (PRD §17.4). `email` is a special case: it lives on
    `User`, not `UserProfile`, and is only settable while the linked identity
    is still an unclaimed walk-in placeholder (ID-030) — this is the fix for
    the workflow gap where an email-less walk-in had no path to ever become
    login-capable, since the ID-030/ID-031 self-registration upgrade is keyed
    on an email match. Once the identity is claimed (real credentials exist),
    staff must not be able to change the customer's login email through this
    endpoint. No new claim mechanism is introduced — this only lets staff
    back-fill the email a Case A walk-in never had, converting it into the
    already-working Case B path.
    """
    bc = _get_business_customer_or_404(db, business_customer_id)
    business = _require_customer_access(db, bc.business_id, current_user)

    platform_customer = db.query(PlatformCustomer).filter(PlatformCustomer.id == bc.platform_customer_id).first()
    user = db.query(User).filter(User.id == platform_customer.user_id).first()
    profile = db.query(UserProfile).filter(UserProfile.user_id == platform_customer.user_id).first()
    if profile is None:
        profile = UserProfile(user_id=platform_customer.user_id)
        db.add(profile)

    updates = payload.model_dump(exclude_unset=True)
    _validate_country(db, updates.get("country_id"))

    if "notes" in updates:
        bc.notes = updates.pop("notes")

    previous_email = None
    if "email" in updates:
        candidate_email = updates.pop("email")
        if candidate_email is not None:
            if not _is_unclaimed_placeholder(user):
                raise HTTPException(
                    status_code=409,
                    detail="Cannot change email after the customer has claimed their account",
                )
            clashing = db.query(User).filter(User.email == candidate_email, User.id != user.id).first()
            if clashing:
                raise HTTPException(status_code=409, detail="Email already in use")
            previous_email = user.email
            user.email = candidate_email

    _apply_profile_updates(profile, updates)

    write_audit(
        db,
        business_id=business.id,
        entity_type="BusinessCustomer",
        entity_id=bc.id,
        action="CUSTOMER_UPDATED",
        performed_by=current_user.id,
        previous_value=f"email={previous_email}" if previous_email is not None else None,
        new_value=f"customer_number={bc.customer_number};email={user.email}",
        commit=False,
    )

    db.commit()
    db.refresh(bc)
    return bc


def set_customer_status(db: Session, business_customer_id: int, status: str, current_user: User) -> BusinessCustomer:
    bc = _get_business_customer_or_404(db, business_customer_id)
    business = _require_customer_access(db, bc.business_id, current_user)

    if bc.status == status:
        raise HTTPException(status_code=409, detail=f"Customer is already {status}")

    previous = bc.status
    bc.status = status

    write_audit(
        db,
        business_id=business.id,
        entity_type="BusinessCustomer",
        entity_id=bc.id,
        action="CUSTOMER_UPDATED",
        performed_by=current_user.id,
        previous_value=f"status={previous}",
        new_value=f"status={status}",
        commit=False,
    )

    db.commit()
    db.refresh(bc)
    return bc


# -------------------------
# CUSTOMER BROWSE (workflow 90.3 — Select Business/Branch/Service, stops
# before Availability Engine / Booking — Milestone 7)
# -------------------------

def browse_businesses(db: Session, current_user: User) -> List[Business]:
    _require_customer_self(db, current_user)
    return db.query(Business).filter(Business.status == "Active").order_by(Business.business_name).all()


def browse_branches(db: Session, business_id: int, current_user: User) -> List[Branch]:
    _require_customer_self(db, current_user)
    business = _get_business_or_404(db, business_id)
    if business.status != "Active":
        raise HTTPException(status_code=404, detail="Business not found")
    return (
        db.query(Branch)
        .filter(
            Branch.business_id == business.id,
            Branch.approval_status == "Approved",
            Branch.is_active == True,  # noqa: E712
        )
        .order_by(Branch.branch_name)
        .all()
    )


def browse_services(db: Session, branch_id: int, current_user: User) -> List[BranchService]:
    _require_customer_self(db, current_user)
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch or branch.approval_status != "Approved" or not branch.is_active:
        raise HTTPException(status_code=404, detail="Branch not found")
    return (
        db.query(BranchService)
        .filter(BranchService.branch_id == branch.id, BranchService.status == "Approved")
        .order_by(BranchService.id)
        .all()
    )
