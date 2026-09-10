from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal
from schemas_coupon import (
    CouponCreateRequest,
    CouponStatusUpdateRequest,
    CouponDecisionRequest,
    CouponResponse,
)
import crud_coupon
from dependencies import get_current_user

router = APIRouter(tags=["Coupons"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/businesses/{business_id}/coupons", response_model=CouponResponse)
def create_coupon(
    business_id: int,
    payload: CouponCreateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    coupon = crud_coupon.create_coupon(db, business_id, payload, current_user)
    return crud_coupon.serialize_coupon(db, coupon)


@router.get("/businesses/{business_id}/coupons", response_model=List[CouponResponse])
def list_coupons(
    business_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    coupons = crud_coupon.list_coupons_for_business(db, business_id, current_user)
    return [crud_coupon.serialize_coupon(db, c) for c in coupons]


@router.get("/coupons/{coupon_id}", response_model=CouponResponse)
def get_coupon(
    coupon_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    coupon = crud_coupon.get_coupon_for_read(db, coupon_id, current_user)
    return crud_coupon.serialize_coupon(db, coupon)


@router.post("/coupons/{coupon_id}/approve", response_model=CouponResponse)
def approve_coupon(
    coupon_id: int,
    payload: CouponDecisionRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    coupon = crud_coupon.decide_coupon_approval(db, coupon_id, "Approved", payload, current_user)
    return crud_coupon.serialize_coupon(db, coupon)


@router.post("/coupons/{coupon_id}/reject", response_model=CouponResponse)
def reject_coupon(
    coupon_id: int,
    payload: CouponDecisionRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    coupon = crud_coupon.decide_coupon_approval(db, coupon_id, "Rejected", payload, current_user)
    return crud_coupon.serialize_coupon(db, coupon)


@router.patch("/coupons/{coupon_id}/status", response_model=CouponResponse)
def set_coupon_status(
    coupon_id: int,
    payload: CouponStatusUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    coupon = crud_coupon.set_coupon_status(db, coupon_id, payload, current_user)
    return crud_coupon.serialize_coupon(db, coupon)
