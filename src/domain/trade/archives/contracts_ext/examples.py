from __future__ import annotations

from datetime import date

from .identity import CmsIndexRef, ProductIdentity, RateIndexRef, UnderlyingRef
from .products import (
    AKOCouponSwapSpec,
    InterestRateSwapSpec,
    PRDCNoteSpec,
    RangeAccrualNoteSpec,
    TARFSpec,
    TARNSpec,
    make_fixed_float_swap_payoff,
    make_gap_payoff,
    make_normal_payoff,
    make_prdc_payoff,
    make_two_stage_payoff,
)
from .components import RangeCouponPayoff
from .schedules import ObservationDates, ObservationWindowSpec, PeriodicScheduleSpec, RelativeStartSpec
from .terms import ConstantTerm, StepByIndexTerm


def example_tarf() -> TARFSpec:
    payoff = make_two_stage_payoff(
        underlying=UnderlyingRef("USDJPY", "FX"),
        schedule_spec=PeriodicScheduleSpec(
            start_date=date(2026, 1, 10),
            end_date=date(2026, 6, 10),
            frequency="monthly",
            settlement_lag_days=2,
            holiday_calendar="TKY+NYC",
            role="tarf_fixing",
        ),
        settlement_currency="JPY",
        base_notional=ConstantTerm(1_000_000.0),
        strike_steps=StepByIndexTerm(((0, 145.0), (3, 147.0))),
        ratio=ConstantTerm(2.0),
    )
    return TARFSpec(
        identity=ProductIdentity("TARF", "TargetRedemptionForward"),
        payoff=payoff,
        target=ConstantTerm(5_000_000.0),
    )


def example_tarn() -> TARNSpec:
    payoff = make_normal_payoff(
        underlying=UnderlyingRef("EURUSD", "FX"),
        schedule_spec=PeriodicScheduleSpec(
            start_date=date(2026, 1, 31),
            end_date=date(2026, 12, 31),
            frequency="monthly",
            settlement_lag_days=2,
            holiday_calendar="NYC+LON",
            role="tarn_fixing",
        ),
        settlement_currency="USD",
        base_notional=ConstantTerm(2_000_000.0),
        strike=ConstantTerm(1.11),
        ratio=ConstantTerm(1.5),
    )
    return TARNSpec(
        identity=ProductIdentity("TARN", "TargetRedemptionNote"),
        payoff=payoff,
        target=ConstantTerm(250_000.0),
        accrual_currency="USD",
    )


def example_irs() -> InterestRateSwapSpec:
    payoff = make_fixed_float_swap_payoff(
        schedule_spec=PeriodicScheduleSpec(
            start_date=date(2026, 1, 5),
            end_date=date(2031, 1, 5),
            frequency="semiannual",
            settlement_lag_days=2,
            holiday_calendar="NYC",
            role="irs_coupon",
        ),
        fixed_currency="USD",
        float_currency="USD",
        notional=ConstantTerm(100_000_000.0),
        fixed_rate=ConstantTerm(0.0325),
        float_index=RateIndexRef("SOFR", "USD", "3M", "ACT/360"),
        spread=ConstantTerm(0.0),
        leverage=ConstantTerm(1.0),
        pay_fixed=True,
    )
    return InterestRateSwapSpec(
        identity=ProductIdentity("INTEREST_RATE_SWAP", "FixedFloatIRS"),
        payoff=payoff,
        settlement_currency="USD",
    )


def example_prdc() -> PRDCNoteSpec:
    payoff = make_prdc_payoff(
        schedule_spec=PeriodicScheduleSpec(
            start_date=date(2026, 4, 15),
            end_date=date(2036, 4, 15),
            frequency="annual",
            settlement_lag_days=2,
            holiday_calendar="TKY+NYC",
            role="prdc_coupon",
        ),
        coupon_currency="JPY",
        redemption_currency="USD",
        notional=ConstantTerm(1_000_000_000.0),
        domestic_index=CmsIndexRef("JPY CMS", "JPY", "10Y"),
        fx_underlying=UnderlyingRef("USDJPY", "FX"),
        coupon_floor=ConstantTerm(0.0),
        coupon_cap=ConstantTerm(0.12),
    )
    return PRDCNoteSpec(
        identity=ProductIdentity("PRDC", "PRDCNote"),
        payoff=payoff,
        settlement_currency="JPY",
        callable_style="bermudan",
    )


def example_ako_coupon_swap() -> AKOCouponSwapSpec:
    payoff = make_gap_payoff(
        underlying=UnderlyingRef("USDJPY", "FX"),
        schedule_spec=PeriodicScheduleSpec(
            start_date=date(2026, 1, 15),
            end_date=date(2026, 10, 15),
            frequency="quarterly",
            settlement_lag_days=5,
            holiday_calendar="TKY",
            role="coupon_fixing",
        ),
        settlement_currency="JPY",
        base_notional=ConstantTerm(10_000_000.0),
        call_strike=ConstantTerm(145.0),
        put_strike=ConstantTerm(150.0),
        call_ratio=ConstantTerm(1.0),
        put_ratio=ConstantTerm(2.0),
        put_ki_trigger=ConstantTerm(130.0),
        put_ki_observation_window=ObservationWindowSpec(
            observation_dates=ObservationDates(
                dates=(date(2026, 1, 15), date(2026, 4, 15), date(2026, 7, 15), date(2026, 10, 15)),
                role="put_ki_obs",
            ),
            start_spec=RelativeStartSpec(mode="by_payoff_index", payoff_index=1),
        ),
    )
    return AKOCouponSwapSpec(
        identity=ProductIdentity("AKO_COUPON_SWAP", "StructuredPayoffCouponSwapWithAKO"),
        payoff=payoff,
        ako_trigger_level=ConstantTerm(128.0),
        ako_observation_window=ObservationWindowSpec(
            observation_dates=ObservationDates(
                dates=(date(2026, 2, 7), date(2026, 3, 7), date(2026, 4, 7), date(2026, 5, 7)),
                role="ako_obs",
            ),
            start_spec=RelativeStartSpec(mode="by_date", start_date=date(2026, 2, 7)),
        ),
        settlement_currency="JPY",
        accrual_factor_term=ConstantTerm(0.25),
    )


def example_range_accrual_note() -> RangeAccrualNoteSpec:
    payoff = RangeCouponPayoff(
        underlying=UnderlyingRef("SOFR", "RATE"),
        pay_receive="receive",
        notional=ConstantTerm(50_000_000.0),
        coupon_schedule_spec=PeriodicScheduleSpec(
            start_date=date(2026, 1, 1),
            end_date=date(2028, 1, 1),
            frequency="quarterly",
            settlement_lag_days=2,
            holiday_calendar="NYC",
            role="range_accrual",
        ),
        coupon_currency="USD",
        base_rate=ConstantTerm(0.025),
        spread=ConstantTerm(0.001),
        leverage=ConstantTerm(1.0),
        lower_bound=ConstantTerm(0.0),
        upper_bound=ConstantTerm(0.06),
        accrual_factor_term=ConstantTerm(0.25),
    )
    return RangeAccrualNoteSpec(
        identity=ProductIdentity("RANGE_ACCRUAL_NOTE", "RangeAccrualNote"),
        payoff=payoff,
        settlement_currency="USD",
    )


if __name__ == "__main__":
    for builder in [
        example_tarf,
        example_tarn,
        example_irs,
        example_prdc,
        example_ako_coupon_swap,
        example_range_accrual_note,
    ]:
        obj = builder().to_product_spec()
        data = obj.to_dict()
        restored = obj.__class__.from_dict(data)
        print("---", obj.identity.family, "---")
        print(restored.to_dict())
