"""
Milestone 8 Phase 3 — Pricing Engine (rule 9/10/14; ID-054).

Pure calculation logic, no DB access — the frozen M8 calculation order:

    calculated price
    -> optional BASE PRICE override
    -> coupon
    -> discounted amount
    -> optional FINAL PRICE override
    -> final booking amount
    -> deposit calculation/payment

Kept deliberately free of any ORM/session dependency so it can be unit
tested in isolation and reused identically by every future M8 checkout
flow (customer, staff walk-in, staff email-link, staff external, reschedule
price-difference) without re-deriving the order each time.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


TWO_PLACES = Decimal("0.01")


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass
class PriceBreakdown:
    calculated_price: Decimal
    base_price_override: Optional[Decimal]
    effective_base_price: Decimal
    coupon_id: Optional[int]
    discount_amount: Decimal
    final_price_override: Optional[Decimal]
    final_amount: Decimal


def compute_price(
    calculated_price: Decimal,
    base_price_override: Optional[Decimal] = None,
    coupon=None,
    final_price_override: Optional[Decimal] = None,
) -> PriceBreakdown:
    """
    `coupon` is any object exposing `.id`, `.discount_type` ("Fixed" or
    "Percentage"), `.discount_value`, and `.max_discount` (nullable) — a
    `models.Coupon` row in practice, but not imported here to keep this
    module DB-free.
    """
    effective_base = base_price_override if base_price_override is not None else calculated_price

    discount_amount = Decimal("0")
    coupon_id = None
    after_coupon = effective_base

    if coupon is not None:
        coupon_id = coupon.id
        if coupon.discount_type == "Fixed":
            discount_amount = min(Decimal(coupon.discount_value), effective_base)
        elif coupon.discount_type == "Percentage":
            discount_amount = _round(effective_base * Decimal(coupon.discount_value) / Decimal("100"))
            if coupon.max_discount is not None:
                discount_amount = min(discount_amount, Decimal(coupon.max_discount))
            discount_amount = min(discount_amount, effective_base)
        else:
            raise ValueError(f"Unknown coupon discount_type: {coupon.discount_type!r}")
        after_coupon = effective_base - discount_amount

    final_amount = final_price_override if final_price_override is not None else after_coupon
    if final_amount < 0:
        final_amount = Decimal("0")

    return PriceBreakdown(
        calculated_price=calculated_price,
        base_price_override=base_price_override,
        effective_base_price=effective_base,
        coupon_id=coupon_id,
        discount_amount=discount_amount,
        final_price_override=final_price_override,
        final_amount=_round(final_amount),
    )


def compute_deposit(final_amount: Decimal, deposit_percentage: Decimal) -> "tuple[Decimal, Decimal]":
    """Deposit percentage is applied AFTER coupon/final-price calculation
    (rule 10's explicit ordering). Returns (deposit_amount, balance_due)."""
    deposit_amount = _round(final_amount * Decimal(deposit_percentage) / Decimal("100"))
    balance_due = _round(final_amount - deposit_amount)
    return deposit_amount, balance_due


def is_deposit_eligible(appointment_datetime, now, min_days: int = 7) -> bool:
    """Deposit payment requires the appointment to be >= min_days x 24h
    away at booking-creation time (rule 5). `min_days`x24h is interpreted
    literally as a timedelta, not a calendar-day count."""
    from datetime import timedelta
    return (appointment_datetime - now) >= timedelta(days=min_days)
