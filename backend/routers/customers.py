from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database import SessionLocal
from schemas_customer import (
    CustomerRegisterRequest,
    CustomerProfileResponse,
    CustomerProfileUpdateRequest,
    WalkInCustomerCreateRequest,
    BusinessCustomerResponse,
    BusinessCustomerUpdateRequest,
    CustomerStatusUpdateRequest,
    PaginatedBusinessCustomers,
    BrowseBusinessResponse,
    BrowseBranchResponse,
    BrowseServiceResponse,
)
import crud_customer
from dependencies import get_current_user

router = APIRouter(tags=["Customers"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------
# Customer self-registration (public) — PRD §17.5, ID-034
# -----------------------------

@router.post("/customers/register", response_model=CustomerProfileResponse)
def register_customer(payload: CustomerRegisterRequest, db: Session = Depends(get_db)):
    return crud_customer.register_customer(db, payload)


# -----------------------------
# Customer self profile — BR-040
# -----------------------------

@router.get("/customers/me", response_model=CustomerProfileResponse)
def get_own_profile(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return crud_customer.get_own_customer_profile(db, current_user)


@router.patch("/customers/me", response_model=CustomerProfileResponse)
def update_own_profile(
    payload: CustomerProfileUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_customer.update_own_customer_profile(db, current_user, payload)


# -----------------------------
# Business-scoped Customer Management (PRD §17.4, §17.6, ID-032)
# -----------------------------

@router.post("/businesses/{business_id}/customers", response_model=BusinessCustomerResponse)
def create_walk_in_customer(
    business_id: int,
    payload: WalkInCustomerCreateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bc = crud_customer.create_walk_in_customer(db, business_id, payload, current_user)
    return crud_customer.serialize_business_customer(db, bc)


@router.get("/businesses/{business_id}/customers", response_model=PaginatedBusinessCustomers)
def list_business_customers(
    business_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    sort: str = "-created_at",
    search: Optional[str] = None,
):
    return crud_customer.list_business_customers(db, business_id, current_user, limit, offset, sort, search)


@router.get("/business-customers/{business_customer_id}", response_model=BusinessCustomerResponse)
def get_business_customer(
    business_customer_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bc = crud_customer.get_business_customer(db, business_customer_id, current_user)
    return crud_customer.serialize_business_customer(db, bc)


@router.patch("/business-customers/{business_customer_id}", response_model=BusinessCustomerResponse)
def update_business_customer(
    business_customer_id: int,
    payload: BusinessCustomerUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bc = crud_customer.update_business_customer(db, business_customer_id, payload, current_user)
    return crud_customer.serialize_business_customer(db, bc)


@router.patch("/business-customers/{business_customer_id}/status", response_model=BusinessCustomerResponse)
def set_customer_status(
    business_customer_id: int,
    payload: CustomerStatusUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bc = crud_customer.set_customer_status(db, business_customer_id, payload.status, current_user)
    return crud_customer.serialize_business_customer(db, bc)


# -----------------------------
# Customer Browse — workflow 90.3 (Select Business/Branch/Service; stops
# before Availability Engine / Booking, Milestone 7)
# -----------------------------

@router.get("/customer/businesses", response_model=List[BrowseBusinessResponse])
def browse_businesses(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return crud_customer.browse_businesses(db, current_user)


@router.get("/customer/businesses/{business_id}/branches", response_model=List[BrowseBranchResponse])
def browse_branches(
    business_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud_customer.browse_branches(db, business_id, current_user)


@router.get("/customer/branches/{branch_id}/services", response_model=List[BrowseServiceResponse])
def browse_services(
    branch_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    branch_services = crud_customer.browse_services(db, branch_id, current_user)
    return [crud_customer.serialize_browse_service(db, bs) for bs in branch_services]
