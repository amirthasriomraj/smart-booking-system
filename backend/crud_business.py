from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException
from datetime import datetime
from typing import Optional

from models import User, UserProfile, Business, BusinessCategory, Country, BusinessMember, Role
from auth import hash_password, validate_password
from audit import write_audit
from pagination import paginate
from crud_branch import _require_active_owner_membership

OWNER_ROLE_CODE = "BUSINESS_OWNER"


# -------------------------
# BUSINESS REGISTRATION
# -------------------------

def register_business(db: Session, payload):
    """
    Frozen registration transaction (PRD §12 Steps 1-3).

    Creates the owner User + UserProfile, the Business in Pending status,
    and the owner's BUSINESS_OWNER BusinessMember row, all in a single
    atomic transaction. Does NOT create a Branch (PRD §12 Step 5 is explicit
    that branch creation happens later, by the Business Owner, after
    approval).
    """
    validate_password(payload.password)

    existing_user = db.query(User).filter(
        or_(User.username == payload.username, User.email == payload.email)
    ).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="Username or email already exists")

    category = db.query(BusinessCategory).filter(
        BusinessCategory.id == payload.business_category_id,
        BusinessCategory.is_active == True,  # noqa: E712
    ).first()
    if not category:
        raise HTTPException(status_code=400, detail="Invalid business category")

    country = db.query(Country).filter(Country.id == payload.country_id).first()
    if not country:
        raise HTTPException(status_code=400, detail="Invalid country")

    owner_role = db.query(Role).filter(Role.code == OWNER_ROLE_CODE).first()
    if not owner_role:
        raise HTTPException(
            status_code=500,
            detail="BUSINESS_OWNER role is not seeded. Run database migrations first.",
        )

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role="user",
    )
    db.add(user)
    db.flush()  # assign user.id without committing

    db.add(UserProfile(user_id=user.id))

    business = Business(
        business_name=payload.business_name,
        business_category_id=category.id,
        owner_user_id=user.id,
        country_id=country.id,
        status="Pending",
    )
    db.add(business)
    db.flush()  # assign business.id without committing

    db.add(BusinessMember(
        business_id=business.id,
        user_id=user.id,
        role_id=owner_role.id,
        status="Active",
    ))

    write_audit(
        db,
        business_id=business.id,
        entity_type="Business",
        entity_id=business.id,
        action="BUSINESS_REGISTERED",
        performed_by=user.id,
        new_value="status=Pending",
        commit=False,
    )

    db.commit()
    db.refresh(business)

    return business


# -------------------------
# PLATFORM ADMIN APPROVAL (PRD §25.3)
# -------------------------

def get_businesses(
    db: Session,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
) -> dict:
    """Platform Admin business listing: search/pagination per PRD §38-40
    (search by Business Name, Category, Country)."""
    query = db.query(Business)
    if status:
        query = query.filter(Business.status == status)

    if search:
        like = f"%{search}%"
        query = (
            query
            .outerjoin(BusinessCategory, Business.business_category_id == BusinessCategory.id)
            .outerjoin(Country, Business.country_id == Country.id)
            .filter(
                or_(
                    Business.business_name.ilike(like),
                    BusinessCategory.name.ilike(like),
                    Country.name.ilike(like),
                )
            )
        )

    total = query.count()
    rows = (
        query.order_by(Business.created_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
        .all()
    )

    return paginate(rows, total, page, page_size)


def get_business_by_id(db: Session, business_id: int) -> Business:
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


# -------------------------
# BUSINESS PROFILE (M9 Phase 6, PRD §72)
# -------------------------

def get_business_for_viewer(db: Session, business_id: int, current_user: User) -> Business:
    """Business Owner viewing their own business profile."""
    return _require_active_owner_membership(db, business_id, current_user)


def update_business_profile(db: Session, business_id: int, payload, current_user: User) -> Business:
    business = _require_active_owner_membership(db, business_id, current_user)
    updates = payload.model_dump(exclude_unset=True)

    previous_value = f"business_name={business.business_name}"

    if "business_category_id" in updates and updates["business_category_id"] is not None:
        category = db.query(BusinessCategory).filter(
            BusinessCategory.id == updates["business_category_id"],
            BusinessCategory.is_active == True,  # noqa: E712
        ).first()
        if not category:
            raise HTTPException(status_code=400, detail="Invalid business category")
        business.business_category_id = updates["business_category_id"]

    if "country_id" in updates and updates["country_id"] is not None:
        country = db.query(Country).filter(Country.id == updates["country_id"]).first()
        if not country:
            raise HTTPException(status_code=400, detail="Invalid country")
        business.country_id = updates["country_id"]

    if "business_name" in updates and updates["business_name"] is not None:
        business.business_name = updates["business_name"]

    write_audit(
        db,
        business_id=business.id,
        entity_type="Business",
        entity_id=business.id,
        action="BUSINESS_PROFILE_UPDATED",
        performed_by=current_user.id,
        previous_value=previous_value,
        new_value=f"business_name={business.business_name}",
        commit=False,
    )

    db.commit()
    db.refresh(business)
    return business


def approve_business(db: Session, business_id: int, admin_user: User) -> Business:
    business = get_business_by_id(db, business_id)

    if business.status != "Pending":
        raise HTTPException(
            status_code=409,
            detail=f"Business is not pending approval (current status: {business.status})",
        )

    previous_status = business.status
    business.status = "Active"
    business.approved_by = admin_user.id
    business.approved_at = datetime.utcnow()

    write_audit(
        db,
        business_id=business.id,
        entity_type="Business",
        entity_id=business.id,
        action="BUSINESS_APPROVED",
        performed_by=admin_user.id,
        previous_value=f"status={previous_status}",
        new_value="status=Active",
        commit=False,
    )

    db.commit()
    db.refresh(business)

    return business


def reject_business(db: Session, business_id: int, admin_user: User, reason: Optional[str] = None) -> Business:
    business = get_business_by_id(db, business_id)

    if business.status != "Pending":
        raise HTTPException(
            status_code=409,
            detail=f"Business is not pending approval (current status: {business.status})",
        )

    previous_status = business.status
    business.status = "Rejected"

    write_audit(
        db,
        business_id=business.id,
        entity_type="Business",
        entity_id=business.id,
        action="BUSINESS_REJECTED",
        performed_by=admin_user.id,
        previous_value=f"status={previous_status}",
        new_value="status=Rejected",
        reason=reason,
        commit=False,
    )

    db.commit()
    db.refresh(business)

    return business


# -------------------------
# PLATFORM ADMIN SUSPEND / REACTIVATE (M9 Phase 1, PRD §10.1/§26.1, BR-009/BR-010)
# -------------------------

def suspend_business(db: Session, business_id: int, admin_user: User) -> Business:
    business = get_business_by_id(db, business_id)

    if business.status != "Active":
        raise HTTPException(
            status_code=409,
            detail=f"Only an Active business can be suspended (current status: {business.status})",
        )

    previous_status = business.status
    business.status = "Suspended"

    write_audit(
        db,
        business_id=business.id,
        entity_type="Business",
        entity_id=business.id,
        action="BUSINESS_SUSPENDED",
        performed_by=admin_user.id,
        previous_value=f"status={previous_status}",
        new_value="status=Suspended",
        commit=False,
    )

    db.commit()
    db.refresh(business)

    return business


def reactivate_business(db: Session, business_id: int, admin_user: User) -> Business:
    business = get_business_by_id(db, business_id)

    if business.status != "Suspended":
        raise HTTPException(
            status_code=409,
            detail=f"Only a Suspended business can be reactivated (current status: {business.status})",
        )

    previous_status = business.status
    business.status = "Active"

    write_audit(
        db,
        business_id=business.id,
        entity_type="Business",
        entity_id=business.id,
        action="BUSINESS_REACTIVATED",
        performed_by=admin_user.id,
        previous_value=f"status={previous_status}",
        new_value="status=Active",
        commit=False,
    )

    db.commit()
    db.refresh(business)

    return business


# -------------------------
# PLATFORM ADMIN BUSINESS CATEGORY CRUD (M9 Phase 1, PRD line 675, ID-015 precedent)
# -------------------------

def get_all_business_categories(db: Session):
    return db.query(BusinessCategory).order_by(BusinessCategory.name).all()


def create_business_category(db: Session, payload, admin_user: User) -> BusinessCategory:
    existing = db.query(BusinessCategory).filter(BusinessCategory.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="A business category with this name already exists")

    category = BusinessCategory(
        name=payload.name,
        description=payload.description,
        is_active=True,
    )
    db.add(category)
    db.flush()

    write_audit(
        db,
        business_id=None,
        entity_type="BusinessCategory",
        entity_id=category.id,
        action="BUSINESS_CATEGORY_CREATED",
        performed_by=admin_user.id,
        new_value=f"name={category.name}, is_active=True",
        commit=False,
    )

    db.commit()
    db.refresh(category)

    return category


def update_business_category(db: Session, category_id: int, payload, admin_user: User) -> BusinessCategory:
    category = db.query(BusinessCategory).filter(BusinessCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Business category not found")

    previous_value = f"name={category.name}, is_active={category.is_active}"

    if payload.name is not None:
        clash = db.query(BusinessCategory).filter(
            BusinessCategory.name == payload.name,
            BusinessCategory.id != category_id,
        ).first()
        if clash:
            raise HTTPException(status_code=409, detail="A business category with this name already exists")
        category.name = payload.name

    if payload.description is not None:
        category.description = payload.description

    if payload.is_active is not None:
        category.is_active = payload.is_active

    write_audit(
        db,
        business_id=None,
        entity_type="BusinessCategory",
        entity_id=category.id,
        action="BUSINESS_CATEGORY_UPDATED",
        performed_by=admin_user.id,
        previous_value=previous_value,
        new_value=f"name={category.name}, is_active={category.is_active}",
        commit=False,
    )

    db.commit()
    db.refresh(category)

    return category
