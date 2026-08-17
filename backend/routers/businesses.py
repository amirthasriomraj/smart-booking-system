from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from database import SessionLocal
from schemas_business import (
    BusinessRegisterRequest,
    BusinessResponse,
    BusinessRejectRequest,
    BusinessCategoryResponse,
    CountryResponse,
)
from models import BusinessCategory, Country
import crud_business
from dependencies import get_current_platform_admin

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
# Registration
# -----------------------------

@router.post("/register", response_model=BusinessResponse)
def register_business(payload: BusinessRegisterRequest, db: Session = Depends(get_db)):
    return crud_business.register_business(db, payload)


# -----------------------------
# Platform Admin approval
# -----------------------------

@router.get("/", response_model=List[BusinessResponse])
def list_businesses(
    status: Optional[str] = None,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_business.get_businesses(db, status=status)


@router.post("/{business_id}/approve", response_model=BusinessResponse)
def approve_business(
    business_id: int,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_business.approve_business(db, business_id, current_admin)


@router.post("/{business_id}/reject", response_model=BusinessResponse)
def reject_business(
    business_id: int,
    payload: BusinessRejectRequest,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_business.reject_business(db, business_id, current_admin, reason=payload.reason)
