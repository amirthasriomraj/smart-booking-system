"""
Milestone 8 Phase 3 — Coupon Engine (rule 10; ID-056).

Configuration (create/approve/status) plus the concurrency-safe
validate-and-reserve check used at checkout. There is no separate
"reservation" table (ID-046/ID-056): an Active `BookingHold` whose
`price_snapshot` references a coupon IS that coupon's soft reservation of
one unit of capacity, counted here alongside completed `CouponRedemption`
rows. Permanent redemption (`redeem_coupon`) is written only at checkout
finalization — not exercised by any endpoint yet in this phase (Phase
5/6 checkout flows call it), but implemented and unit-tested now.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from models import Branch, BranchService, Coupon, CouponService, CouponRedemption, BookingHold
from audit import write_audit
from crud_booking import _has_active_role, _get_manager_current_branch_id, _get_business_or_404
from crud_branch import get_branch_by_id


def get_coupon_or_404(db: Session, coupon_id: int) -> Coupon:
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return coupon


def _require_coupon_management_access(db: Session, business_id: int, coupon_branch_id: Optional[int], current_user):
    """
    Owner: manages any coupon in their business (business-wide or any
    branch). Branch Manager: manages only branch-specific coupons for
    their own currently assigned branch (rule 10/28) — a business-wide
    coupon (`coupon_branch_id is None`) can never match a Branch Manager's
    own branch id, so they are correctly excluded from managing those.
    """
    business = _get_business_or_404(db, business_id)
    if _has_active_role(db, business_id, current_user.id, "BUSINESS_OWNER"):
        return business, "BUSINESS_OWNER"
    manager_branch_id = _get_manager_current_branch_id(db, business_id, current_user.id)
    if manager_branch_id is not None and coupon_branch_id == manager_branch_id:
        return business, "BRANCH_MANAGER"
    raise HTTPException(status_code=403, detail="Not authorized to manage coupons for this scope")


def create_coupon(db: Session, business_id: int, payload, current_user) -> Coupon:
    if payload.discount_type not in ("Fixed", "Percentage"):
        raise HTTPException(status_code=400, detail="discount_type must be Fixed or Percentage")
    if payload.discount_type == "Percentage" and not (Decimal("1") <= payload.discount_value <= Decimal("100")):
        raise HTTPException(status_code=400, detail="Percentage discount_value must be between 1 and 100")
    if payload.valid_until < payload.valid_from:
        raise HTTPException(status_code=400, detail="valid_until must not be before valid_from")
    if payload.applicable_weekdays and any(d < 0 or d > 6 for d in payload.applicable_weekdays):
        raise HTTPException(status_code=400, detail="applicable_weekdays values must be 0-6")

    if payload.branch_id is None:
        # Business-wide coupon: Business Owner only (rule 10).
        business = _get_business_or_404(db, business_id)
        if not _has_active_role(db, business_id, current_user.id, "BUSINESS_OWNER"):
            raise HTTPException(status_code=403, detail="Only the Business Owner may create a business-wide coupon")
        approval_status = None
        auto_approved = False
    else:
        branch = get_branch_by_id(db, payload.branch_id)
        if branch.business_id != business_id:
            raise HTTPException(status_code=400, detail="Branch does not belong to this business")
        business, role_code = _require_coupon_management_access(db, business_id, payload.branch_id, current_user)
        # Owner-created branch coupons need no self-approval; a Branch
        # Manager's requires Business Owner approval (rule 10).
        auto_approved = role_code == "BUSINESS_OWNER"
        approval_status = "Approved" if auto_approved else "Pending"

    coupon = Coupon(
        business_id=business_id,
        branch_id=payload.branch_id,
        code=payload.code,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        min_booking_amount=payload.min_booking_amount,
        max_discount=payload.max_discount,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        applicable_weekdays=payload.applicable_weekdays or None,
        total_usage_limit=payload.total_usage_limit,
        per_customer_usage_limit=payload.per_customer_usage_limit,
        status="Active",
        approval_status=approval_status,
        approved_by=current_user.id if auto_approved else None,
        approved_at=datetime.utcnow() if auto_approved else None,
        created_by=current_user.id,
    )
    db.add(coupon)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A coupon with this code already exists for this business")

    for bs_id in (payload.branch_service_ids or []):
        branch_service = db.query(BranchService).filter(BranchService.id == bs_id).first()
        if not branch_service or branch_service.business_id != business_id:
            raise HTTPException(status_code=400, detail=f"branch_service_id {bs_id} does not belong to this business")
        db.add(CouponService(coupon_id=coupon.id, branch_service_id=bs_id))

    write_audit(
        db, business_id=business_id, entity_type="Coupon", entity_id=coupon.id,
        action="COUPON_CREATED", performed_by=current_user.id, new_value=f"code={coupon.code}", commit=False,
    )
    db.commit()
    db.refresh(coupon)
    return coupon


def decide_coupon_approval(db: Session, coupon_id: int, decision: str, payload, current_user) -> Coupon:
    """decision: 'Approved' or 'Rejected'. Business Owner only (rule 10/28)."""
    coupon = get_coupon_or_404(db, coupon_id)
    if not _has_active_role(db, coupon.business_id, current_user.id, "BUSINESS_OWNER"):
        raise HTTPException(status_code=403, detail="Only the Business Owner may decide coupon approval")
    if coupon.approval_status != "Pending":
        raise HTTPException(status_code=409, detail="Coupon is not awaiting approval")

    coupon.approval_status = decision
    coupon.approved_by = current_user.id
    coupon.approved_at = datetime.utcnow()

    write_audit(
        db, business_id=coupon.business_id, entity_type="Coupon", entity_id=coupon.id,
        action=f"COUPON_{decision.upper()}", performed_by=current_user.id, reason=payload.comments, commit=False,
    )
    db.commit()
    db.refresh(coupon)
    return coupon


def set_coupon_status(db: Session, coupon_id: int, payload, current_user) -> Coupon:
    coupon = get_coupon_or_404(db, coupon_id)
    _require_coupon_management_access(db, coupon.business_id, coupon.branch_id, current_user)
    if payload.status not in ("Active", "Inactive"):
        raise HTTPException(status_code=400, detail="status must be Active or Inactive")

    coupon.status = payload.status
    write_audit(
        db, business_id=coupon.business_id, entity_type="Coupon", entity_id=coupon.id,
        action="COUPON_STATUS_CHANGED", performed_by=current_user.id, new_value=payload.status, commit=False,
    )
    db.commit()
    db.refresh(coupon)
    return coupon


def list_coupons_for_business(db: Session, business_id: int, current_user) -> List[Coupon]:
    _get_business_or_404(db, business_id)
    if _has_active_role(db, business_id, current_user.id, "BUSINESS_OWNER"):
        return db.query(Coupon).filter(Coupon.business_id == business_id).order_by(Coupon.id.desc()).all()
    manager_branch_id = _get_manager_current_branch_id(db, business_id, current_user.id)
    if manager_branch_id is not None:
        return (
            db.query(Coupon)
            .filter(
                Coupon.business_id == business_id,
                (Coupon.branch_id.is_(None)) | (Coupon.branch_id == manager_branch_id),
            )
            .order_by(Coupon.id.desc())
            .all()
        )
    raise HTTPException(status_code=403, detail="Not authorized to view coupons for this business")


def get_coupon_for_read(db: Session, coupon_id: int, current_user) -> Coupon:
    coupon = get_coupon_or_404(db, coupon_id)
    if _has_active_role(db, coupon.business_id, current_user.id, "BUSINESS_OWNER"):
        return coupon
    manager_branch_id = _get_manager_current_branch_id(db, coupon.business_id, current_user.id)
    if manager_branch_id is not None and (coupon.branch_id is None or coupon.branch_id == manager_branch_id):
        return coupon
    raise HTTPException(status_code=403, detail="Not authorized to view this coupon")


def coupon_service_ids(db: Session, coupon_id: int) -> List[int]:
    return [cs.branch_service_id for cs in db.query(CouponService).filter(CouponService.coupon_id == coupon_id).all()]


def serialize_coupon(db: Session, coupon: Coupon) -> dict:
    return {
        "id": coupon.id,
        "business_id": coupon.business_id,
        "branch_id": coupon.branch_id,
        "code": coupon.code,
        "discount_type": coupon.discount_type,
        "discount_value": coupon.discount_value,
        "min_booking_amount": coupon.min_booking_amount,
        "max_discount": coupon.max_discount,
        "valid_from": coupon.valid_from,
        "valid_until": coupon.valid_until,
        "applicable_weekdays": coupon.applicable_weekdays,
        "total_usage_limit": coupon.total_usage_limit,
        "per_customer_usage_limit": coupon.per_customer_usage_limit,
        "status": coupon.status,
        "approval_status": coupon.approval_status,
        "branch_service_ids": coupon_service_ids(db, coupon.id),
        "created_by": coupon.created_by,
        "created_at": coupon.created_at,
        "updated_at": coupon.updated_at,
    }


# -------------------------
# VALIDATE & RESERVE (checkout-time; ID-056)
# -------------------------

def validate_and_reserve_coupon(
    db: Session,
    code: str,
    business_id: int,
    branch_id: int,
    branch_service_id: int,
    customer_id: int,
    booking_amount: Decimal,
    booking_date: date,
    exclude_hold_id: Optional[int] = None,
) -> Coupon:
    """
    Full condition chain from rule 10, plus the ID-056 concurrency-safe
    capacity check. Locks the `Coupon` row (`SELECT ... FOR UPDATE`, a
    no-op on SQLite — see ID-056/Phase 3 completion notes) so concurrent
    checkouts against a scarce coupon cannot both observe capacity as
    available. Does not itself create any row — "reservation" happens when
    the caller embeds this coupon's id in the `BookingHold.price_snapshot`
    it creates immediately afterward, in the same transaction/lock.

    `exclude_hold_id` (manual-acceptance fix): a hold refresh re-validates
    the coupon terms BEFORE releasing the hold it is about to replace (so
    an invalid new coupon/payment-option leaves that still-good hold
    untouched — see `refresh_customer_checkout_hold`). Without this
    exclusion, a hold that already carries this same coupon in its own
    `price_snapshot` would count as a reservation against itself when its
    own refresh re-validates the identical coupon, permanently exhausting
    a `per_customer_usage_limit` of 1 on the very first re-refresh. Only
    the one named hold is excluded — every other Active hold (including
    every other customer's, and any other genuinely separate hold of this
    same customer) still counts exactly as before.
    """
    coupon = (
        db.query(Coupon)
        .filter(Coupon.business_id == business_id, Coupon.code == code)
        .with_for_update()
        .first()
    )
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    if coupon.status != "Active":
        raise HTTPException(status_code=409, detail="Coupon is not Active")
    if coupon.branch_id is not None and coupon.branch_id != branch_id:
        raise HTTPException(status_code=409, detail="Coupon is not valid for this branch")
    if coupon.branch_id is not None and coupon.approval_status != "Approved":
        raise HTTPException(status_code=409, detail="Coupon is not yet approved for this branch")
    if not (coupon.valid_from <= booking_date <= coupon.valid_until):
        raise HTTPException(status_code=409, detail="Coupon is not valid on this date")
    if coupon.applicable_weekdays and booking_date.weekday() not in coupon.applicable_weekdays:
        raise HTTPException(status_code=409, detail="Coupon is not valid on this weekday")

    allowed_service_ids = coupon_service_ids(db, coupon.id)
    if allowed_service_ids and branch_service_id not in allowed_service_ids:
        raise HTTPException(status_code=409, detail="Coupon does not apply to this service")
    if booking_amount < coupon.min_booking_amount:
        raise HTTPException(status_code=409, detail="Booking amount is below the coupon's minimum")

    active_holds_query = db.query(BookingHold).filter(
        BookingHold.status == "Active", BookingHold.expires_at > datetime.utcnow()
    )
    if exclude_hold_id is not None:
        active_holds_query = active_holds_query.filter(BookingHold.id != exclude_hold_id)
    active_holds = active_holds_query.all()
    reservations_for_coupon = [h for h in active_holds if (h.price_snapshot or {}).get("coupon_id") == coupon.id]

    if coupon.total_usage_limit is not None:
        redeemed_count = db.query(CouponRedemption).filter(CouponRedemption.coupon_id == coupon.id).count()
        if redeemed_count + len(reservations_for_coupon) >= coupon.total_usage_limit:
            raise HTTPException(status_code=409, detail="Coupon usage limit has been reached")

    per_customer_redeemed = (
        db.query(CouponRedemption)
        .filter(CouponRedemption.coupon_id == coupon.id, CouponRedemption.customer_id == customer_id)
        .count()
    )
    per_customer_reserved = sum(1 for h in reservations_for_coupon if h.customer_id == customer_id)
    if per_customer_redeemed + per_customer_reserved >= coupon.per_customer_usage_limit:
        raise HTTPException(status_code=409, detail="You have already used this coupon the maximum number of times")

    return coupon


def redeem_coupon(
    db: Session, coupon: Coupon, booking_id: int, customer_id: int, discount_applied_amount: Decimal, performed_by: int
) -> CouponRedemption:
    """Permanent redemption record, written only at checkout finalization
    (not at hold creation) — see module docstring. `UniqueConstraint
    (coupon_id, booking_id)` makes a double-redemption for the same
    booking a clean 409 rather than a raw IntegrityError."""
    redemption = CouponRedemption(
        business_id=coupon.business_id,
        coupon_id=coupon.id,
        booking_id=booking_id,
        customer_id=customer_id,
        discount_applied_amount=discount_applied_amount,
    )
    db.add(redemption)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Coupon has already been redeemed for this booking")

    write_audit(
        db, business_id=coupon.business_id, entity_type="Coupon", entity_id=coupon.id,
        action="COUPON_REDEEMED", performed_by=performed_by,
        new_value=f"booking_id={booking_id} discount={discount_applied_amount}", commit=False,
    )
    return redemption
