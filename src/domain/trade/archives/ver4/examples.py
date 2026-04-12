from __future__ import annotations

from datetime import date

from .identity import ProductIdentity, UnderlyingRef
from .products import (
    AKOCouponSwapSpec,
    TARFSpec,
    make_gap_payoff,
    make_normal_payoff,
    make_two_stage_payoff,
)
from .schedules import (
    EventSchedule,
    ExplicitEventScheduleSpec,
    ObservationDates,
    ObservationWindowSpec,
    PeriodicScheduleSpec,
    RelativeStartSpec,
)
from .terms import ConstantTerm, StepByIndexTerm


# === EXAMPLE
def example_tarf_two_stage_unexpanded_schedule() -> TARFSpec:
    payoff = make_two_stage_payoff(
        underlying=UnderlyingRef("USDJPY", "FX"),
        schedule_spec=PeriodicScheduleSpec(
            start_date=date(2026, 1, 10),
            end_date=date(2026, 6, 10),
            frequency="monthly",
            settlement_lag_days=2,
            business_day_adjustment="following",
            holiday_calendar="TKY+NYC",
            role="tarf_fixing",
        ),
        settlement_currency="JPY",
        base_notional=ConstantTerm(1_000_000.0),
        strike_steps=StepByIndexTerm(((0, 145.0), (3, 147.0))),
        ratio=ConstantTerm(2.0),
    )
    return TARFSpec(
        identity=ProductIdentity("TARF", "TargetRedemptionForward", "1.1"),
        payoff=payoff,
        target=ConstantTerm(5_000_000.0),
        final_fixing_treatment="full",
    )


# === EXAMPLE
# AKO 観測開始が契約開始より後で、payoff index で始まるケース
def example_ako_gap_with_delayed_observation_by_index() -> AKOCouponSwapSpec:
    payoff = make_gap_payoff(
        underlying=UnderlyingRef("USDJPY", "FX"),
        schedule_spec=ExplicitEventScheduleSpec(
            schedule=EventSchedule(
                items=(
                    (0, date(2026, 1, 15), date(2026, 1, 20)),
                    (1, date(2026, 4, 15), date(2026, 4, 20)),
                    (2, date(2026, 7, 15), date(2026, 7, 21)),
                    (3, date(2026, 10, 15), date(2026, 10, 20)),
                ),
                role="coupon_fixing",
            )
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
                dates=(
                    date(2026, 1, 15),
                    date(2026, 4, 15),
                    date(2026, 7, 15),
                    date(2026, 10, 15),
                ),
                role="put_ki_observation",
            ),
            start_spec=RelativeStartSpec(mode="by_payoff_index", payoff_index=1),
            role="put_ki_window",
        ),
    )

    return AKOCouponSwapSpec(
        identity=ProductIdentity("AKO_COUPON_SWAP", "StructuredPayoffCouponSwapWithAKO", "1.1"),
        payoff=payoff,
        ako_trigger_level=ConstantTerm(128.0),
        ako_observation_window=ObservationWindowSpec(
            observation_dates=ObservationDates(
                dates=(
                    date(2026, 2, 1),
                    date(2026, 3, 1),
                    date(2026, 5, 1),
                    date(2026, 8, 1),
                ),
                role="ako_observation",
            ),
            start_spec=RelativeStartSpec(mode="by_payoff_index", payoff_index=1),
            role="ako_window",
        ),
        ako_breach_condition="spot_lte_level",
        ako_action_on_breach="cancel_remaining",
        redemption_on_ako=True,
        settlement_currency="JPY",
        accrual_factor_term=ConstantTerm(0.25),
    )


# === EXAMPLE
# AKO 観測開始を日付で直指定するケース
def example_ako_gap_with_delayed_observation_by_date() -> AKOCouponSwapSpec:
    payoff = make_normal_payoff(
        underlying=UnderlyingRef("USDJPY", "FX"),
        schedule_spec=PeriodicScheduleSpec(
            start_date=date(2026, 1, 15),
            end_date=date(2026, 10, 15),
            frequency="quarterly",
            settlement_lag_days=5,
            business_day_adjustment="modified_following",
            holiday_calendar="TKY",
            role="coupon_fixing",
        ),
        settlement_currency="JPY",
        base_notional=ConstantTerm(10_000_000.0),
        strike=ConstantTerm(145.0),
        ratio=ConstantTerm(2.0),
        forward_position="sell_base",
    )

    return AKOCouponSwapSpec(
        identity=ProductIdentity("AKO_COUPON_SWAP", "NormalPayoffCouponSwapWithAKO", "1.1"),
        payoff=payoff,
        ako_trigger_level=ConstantTerm(128.0),
        ako_observation_window=ObservationWindowSpec(
            observation_dates=ObservationDates(
                dates=(
                    date(2026, 2, 7),
                    date(2026, 3, 7),
                    date(2026, 4, 7),
                    date(2026, 5, 7),
                ),
                role="ako_observation",
            ),
            start_spec=RelativeStartSpec(mode="by_date", start_date=date(2026, 2, 7)),
            role="ako_window",
        ),
        ako_breach_condition="spot_lte_level",
        ako_action_on_breach="cancel_remaining",
        redemption_on_ako=True,
        settlement_currency="JPY",
        accrual_factor_term=ConstantTerm(0.25),
    )


if __name__ == "__main__":
    products = [
        example_tarf_two_stage_unexpanded_schedule().to_product_spec(),
        example_ako_gap_with_delayed_observation_by_index().to_product_spec(),
        example_ako_gap_with_delayed_observation_by_date().to_product_spec(),
    ]

    for i, spec in enumerate(products, start=1):
        data = spec.to_dict()
        restored = spec.__class__.from_dict(data) if hasattr(spec.__class__, "from_dict") else data
        print(f"--- Product {i} ---")
        print(spec.identity.family)
        print(data)
        print()