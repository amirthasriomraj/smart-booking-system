"""Milestone 8 Phase 3 — Pricing Engine unit tests (no DB, pure functions)."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from pricing import compute_price, compute_deposit, is_deposit_eligible


@dataclass
class FakeCoupon:
    id: int
    discount_type: str
    discount_value: Decimal
    max_discount: Optional[Decimal] = None


def test_no_overrides_no_coupon_final_equals_calculated():
    result = compute_price(Decimal("4000.00"))
    assert result.effective_base_price == Decimal("4000.00")
    assert result.discount_amount == Decimal("0")
    assert result.final_amount == Decimal("4000.00")


def test_base_price_override_applies_before_coupon():
    result = compute_price(Decimal("4000.00"), base_price_override=Decimal("3500.00"))
    assert result.effective_base_price == Decimal("3500.00")
    assert result.final_amount == Decimal("3500.00")


def test_fixed_coupon_discount():
    coupon = FakeCoupon(id=1, discount_type="Fixed", discount_value=Decimal("500.00"))
    result = compute_price(Decimal("4000.00"), coupon=coupon)
    assert result.discount_amount == Decimal("500.00")
    assert result.final_amount == Decimal("3500.00")
    assert result.coupon_id == 1


def test_fixed_coupon_never_exceeds_effective_base():
    coupon = FakeCoupon(id=1, discount_type="Fixed", discount_value=Decimal("9999.00"))
    result = compute_price(Decimal("100.00"), coupon=coupon)
    assert result.discount_amount == Decimal("100.00")
    assert result.final_amount == Decimal("0.00")


def test_percentage_coupon_discount():
    coupon = FakeCoupon(id=2, discount_type="Percentage", discount_value=Decimal("10"))
    result = compute_price(Decimal("4000.00"), coupon=coupon)
    assert result.discount_amount == Decimal("400.00")
    assert result.final_amount == Decimal("3600.00")


def test_percentage_coupon_respects_max_discount_cap():
    coupon = FakeCoupon(id=3, discount_type="Percentage", discount_value=Decimal("50"), max_discount=Decimal("300.00"))
    result = compute_price(Decimal("4000.00"), coupon=coupon)
    # 50% of 4000 = 2000, capped to 300
    assert result.discount_amount == Decimal("300.00")
    assert result.final_amount == Decimal("3700.00")


def test_100_percent_coupon_yields_zero_payable():
    coupon = FakeCoupon(id=4, discount_type="Percentage", discount_value=Decimal("100"))
    result = compute_price(Decimal("4000.00"), coupon=coupon)
    assert result.final_amount == Decimal("0.00")


def test_final_price_override_applies_after_coupon():
    coupon = FakeCoupon(id=5, discount_type="Fixed", discount_value=Decimal("500.00"))
    result = compute_price(Decimal("4000.00"), coupon=coupon, final_price_override=Decimal("3000.00"))
    assert result.discount_amount == Decimal("500.00")  # still recorded, not overwritten
    assert result.final_amount == Decimal("3000.00")


def test_full_calculation_order_base_override_coupon_final_override():
    coupon = FakeCoupon(id=6, discount_type="Percentage", discount_value=Decimal("10"))
    result = compute_price(
        calculated_price=Decimal("4000.00"),
        base_price_override=Decimal("4500.00"),
        coupon=coupon,
        final_price_override=Decimal("4000.00"),
    )
    assert result.effective_base_price == Decimal("4500.00")
    assert result.discount_amount == Decimal("450.00")  # 10% of the overridden base, not the calculated price
    assert result.final_amount == Decimal("4000.00")  # final override wins


def test_deposit_calculation_matches_worked_example():
    deposit_amount, balance_due = compute_deposit(Decimal("4000.00"), Decimal("25"))
    assert deposit_amount == Decimal("1000.00")
    assert balance_due == Decimal("3000.00")


def test_deposit_eligible_at_exactly_7_days():
    now = datetime(2026, 1, 1, 10, 0, 0)
    appointment = now + timedelta(days=7)
    assert is_deposit_eligible(appointment, now) is True


def test_deposit_not_eligible_under_7_days():
    now = datetime(2026, 1, 1, 10, 0, 0)
    appointment = now + timedelta(days=6, hours=23, minutes=59)
    assert is_deposit_eligible(appointment, now) is False
