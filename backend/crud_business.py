from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException
from datetime import datetime
from typing import Optional

from models import User, UserProfile, Business, BusinessCategory, Country, BusinessMember, Role
from auth import hash_password, validate_password
from audit import write_audit

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

def get_businesses(db: Session, status: Optional[str] = None):
    query = db.query(Business)
    if status:
        query = query.filter(Business.status == status)
    return query.order_by(Business.created_at.desc()).all()


def get_business_by_id(db: Session, business_id: int) -> Business:
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
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
