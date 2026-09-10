from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import PlatformFeeSetting, Business, User
from audit import write_audit

ENTITY_TYPE = "PlatformFeeSetting"


def _validate_percentage(fee_percentage: Decimal) -> None:
    if fee_percentage < 0 or fee_percentage > 100:
        raise HTTPException(status_code=400, detail="fee_percentage must be between 0 and 100")


def _business_or_404(db: Session, business_id: int) -> Business:
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


def get_platform_fee_settings(db: Session) -> dict:
    default_row = db.query(PlatformFeeSetting).filter(PlatformFeeSetting.business_id.is_(None)).first()
    override_rows = db.query(PlatformFeeSetting).filter(PlatformFeeSetting.business_id.isnot(None)).all()

    overrides = []
    for row in override_rows:
        business = db.query(Business).filter(Business.id == row.business_id).first()
        overrides.append({
            "business_id": row.business_id,
            "business_name": business.business_name if business else f"Business #{row.business_id}",
            "fee_percentage": row.fee_percentage,
            "updated_at": row.updated_at,
        })

    return {
        "default_fee_percentage": default_row.fee_percentage if default_row else Decimal("0"),
        "default_updated_at": default_row.updated_at if default_row else None,
        "overrides": overrides,
    }


def set_default_fee(db: Session, payload, current_admin: User) -> dict:
    _validate_percentage(payload.fee_percentage)

    row = db.query(PlatformFeeSetting).filter(PlatformFeeSetting.business_id.is_(None)).first()
    previous_value = str(row.fee_percentage) if row else None

    if row is None:
        row = PlatformFeeSetting(business_id=None, fee_percentage=payload.fee_percentage, updated_by=current_admin.id)
        db.add(row)
    else:
        row.fee_percentage = payload.fee_percentage
        row.updated_by = current_admin.id

    write_audit(
        db,
        entity_type=ENTITY_TYPE,
        entity_id=0,
        action="SET_DEFAULT_FEE",
        performed_by=current_admin.id,
        previous_value=previous_value,
        new_value=str(payload.fee_percentage),
        reason=payload.reason,
        commit=False,
    )
    db.commit()

    return get_platform_fee_settings(db)


def set_business_fee_override(db: Session, business_id: int, payload, current_admin: User) -> dict:
    _validate_percentage(payload.fee_percentage)
    business = _business_or_404(db, business_id)

    row = db.query(PlatformFeeSetting).filter(PlatformFeeSetting.business_id == business.id).first()
    previous_value = str(row.fee_percentage) if row else None

    if row is None:
        row = PlatformFeeSetting(business_id=business.id, fee_percentage=payload.fee_percentage, updated_by=current_admin.id)
        db.add(row)
    else:
        row.fee_percentage = payload.fee_percentage
        row.updated_by = current_admin.id

    write_audit(
        db,
        business_id=business.id,
        entity_type=ENTITY_TYPE,
        entity_id=business.id,
        action="SET_BUSINESS_FEE_OVERRIDE",
        performed_by=current_admin.id,
        previous_value=previous_value,
        new_value=str(payload.fee_percentage),
        reason=payload.reason,
        commit=False,
    )
    db.commit()

    return get_platform_fee_settings(db)


def remove_business_fee_override(db: Session, business_id: int, payload, current_admin: User) -> dict:
    business = _business_or_404(db, business_id)
    row = db.query(PlatformFeeSetting).filter(PlatformFeeSetting.business_id == business.id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="No fee override exists for this business")

    previous_value = str(row.fee_percentage)
    db.delete(row)

    write_audit(
        db,
        business_id=business.id,
        entity_type=ENTITY_TYPE,
        entity_id=business.id,
        action="REMOVE_BUSINESS_FEE_OVERRIDE",
        performed_by=current_admin.id,
        previous_value=previous_value,
        new_value=None,
        reason=payload.reason,
        commit=False,
    )
    db.commit()

    return get_platform_fee_settings(db)
