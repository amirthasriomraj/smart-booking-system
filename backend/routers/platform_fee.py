from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import SessionLocal
from schemas_platform_fee import (
    PlatformFeeSettingsResponse,
    SetDefaultFeeRequest,
    SetBusinessFeeOverrideRequest,
    RemoveBusinessFeeOverrideRequest,
)
import crud_platform_fee
from dependencies import get_current_platform_admin

router = APIRouter(tags=["Platform Fee"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/platform-fee-settings", response_model=PlatformFeeSettingsResponse)
def get_platform_fee_settings(
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_platform_fee.get_platform_fee_settings(db)


@router.post("/platform-fee-settings/default", response_model=PlatformFeeSettingsResponse)
def set_default_fee(
    payload: SetDefaultFeeRequest,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_platform_fee.set_default_fee(db, payload, current_admin)


@router.post("/businesses/{business_id}/fee-override", response_model=PlatformFeeSettingsResponse)
def set_business_fee_override(
    business_id: int,
    payload: SetBusinessFeeOverrideRequest,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_platform_fee.set_business_fee_override(db, business_id, payload, current_admin)


@router.post("/businesses/{business_id}/fee-override/remove", response_model=PlatformFeeSettingsResponse)
def remove_business_fee_override(
    business_id: int,
    payload: RemoveBusinessFeeOverrideRequest,
    current_admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    return crud_platform_fee.remove_business_fee_override(db, business_id, payload, current_admin)
