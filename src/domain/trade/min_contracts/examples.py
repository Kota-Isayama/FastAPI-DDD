from __future__ import annotations

from datetime import date, datetime

from .common.identity import ProductIdentity
from .common.representations import CouponSwapRepresentation, OptionBundleRepresentation
from .common.schedules import ObservationWindow, PeriodicScheduleSpec
from .common.terms import ConstantTerm, StepByIndexTerm
from .products.coupon_swap import AKOCouponSwapSpec, CouponFormula, CouponSwapSpec
from .products.tarf import TARFLeg, TARFSpec
from .services.instantiate import instantiate_trade_draft
from .common.cashflows import CashflowOverride


def make_tarf_coupon_swap_view() -> TARFSpec:
    return TARFSpec(
        identity=ProductIdentity("TARF", "TargetRedemptionForward", "1.0"),
        underlying="USDJPY",
        settlement_currency="JPY",
        base_notional=ConstantTerm(1_000_000.0),
        payoff_style="two_stage",
        payoff_schedule=PeriodicScheduleSpec(
            start_date=date(2026, 1, 10),
            end_date=date(2026, 6, 10),
            frequency="monthly",
            settlement_lag_days=2,
            holiday_calendar="TKY+NYC",
            role="tarf_fixing",
        ),
        main_leg=TARFLeg(
            strike=StepByIndexTerm(((0, 145.0), (3, 147.0))),
            ratio=ConstantTerm(2.0),
            position="sell_base",
        ),
        target=ConstantTerm(5_000_000.0),
    )


def make_ako_coupon_swap() -> AKOCouponSwapSpec:
    return AKOCouponSwapSpec(
        identity=ProductIdentity("AKO_COUPON_SWAP", "StructuredCouponWithAKO", "1.0"),
        underlying="USDJPY",
        coupon_currency="JPY",
        notional=ConstantTerm(10_000_000.0),
        coupon_schedule=PeriodicScheduleSpec(
            start_date=date(2026, 1, 15),
            end_date=date(2026, 10, 15),
            frequency="quarterly",
            settlement_lag_days=5,
            holiday_calendar="TKY",
            role="coupon_fixing",
        ),
        coupon_formula=CouponFormula(
            payoff_style="gap",
            strike=ConstantTerm(145.0),
            ratio=ConstantTerm(2.0),
        ),
        ako_level=ConstantTerm(128.0),
        ako_window=ObservationWindow(
            observation_dates=(
                date(2026, 2, 7),
                date(2026, 3, 7),
                date(2026, 4, 7),
            ),
            start_date=date(2026, 2, 7),
            role="ako_window",
        ),
    )


def make_plain_coupon_swap() -> CouponSwapSpec:
    return CouponSwapSpec(
        identity=ProductIdentity("COUPON_SWAP", "FXCouponSwap", "1.0"),
        underlying="USDJPY",
        coupon_currency="JPY",
        notional=ConstantTerm(5_000_000.0),
        coupon_schedule=PeriodicScheduleSpec(
            start_date=date(2026, 1, 31),
            end_date=date(2026, 7, 31),
            frequency="monthly",
            settlement_lag_days=2,
            holiday_calendar="TKY",
            role="coupon_fixing",
        ),
        coupon_formula=CouponFormula(
            payoff_style="normal",
            strike=ConstantTerm(146.0),
            ratio=ConstantTerm(1.0),
        ),
    )


def demo() -> None:
    tarf = make_tarf_coupon_swap_view()
    draft = instantiate_trade_draft(
        draft_id="DRAFT-001",
        contract=tarf,
        representation=CouponSwapRepresentation(),
        indication_payload={"quote_id": "Q-1001", "source": "indication-ui"},
        captured_at=datetime(2026, 4, 9, 9, 0, 0),
    )
    draft.apply_cashflow_override(
        draft.cashflows[0].cashflow_id,
        CashflowOverride(
            edited_by="alice",
            edited_at=datetime(2026, 4, 9, 9, 30, 0),
            reason="first coupon manually adjusted after negotiation",
            new_amount_description="manually fixed coupon amount = 1,250,000 JPY",
        ),
    )
    print(draft.to_dict())


if __name__ == "__main__":
    demo()
