from __future__ import annotations

from datetime import date, datetime

from .common.identity import ProductIdentity
from .common.payoffs import (
    EventPayoffSpec,
    EuropeanKnockInBarrier,
    ForwardPayoffLeg,
    OptionPayoffLeg,
    PayoffProgram,
)
from .common.representations import CouponSwapRepresentation, OptionBundleRepresentation
from .common.schedules import ObservationWindow, PeriodicScheduleSpec
from .common.terms import ConstantTerm, StepByIndexTerm
from .outbound.id_allocator import UserSpecifiedPrefixAllocator
from .products.coupon_swap import AKOCouponSwapSpec, CouponSwapSpec
from .products.tarf import TARFSpec
from .services.instantiate import instantiate_trade_draft


def make_normal_tarf() -> TARFSpec:
    normal_event = EventPayoffSpec(
        scheme_name="normal",
        legs=(ForwardPayoffLeg(position="sell_base", strike=ConstantTerm(145.0), ratio=ConstantTerm(2.0)),),
    )
    return TARFSpec(
        identity=ProductIdentity("TARF", "TargetRedemptionForward", "2.0"),
        underlying="USDJPY",
        settlement_currency="JPY",
        base_notional=ConstantTerm(1_000_000.0),
        payoff_schedule=PeriodicScheduleSpec(date(2026, 1, 10), date(2026, 6, 10), "monthly", settlement_lag_days=2, holiday_calendar="TKY+NYC", role="tarf_fixing"),
        payoff_program=PayoffProgram(default_event_payoff=normal_event),
        target=ConstantTerm(5_000_000.0),
    )


def make_gap_coupon_swap() -> CouponSwapSpec:
    ki = EuropeanKnockInBarrier(
        trigger_level=ConstantTerm(130.0),
        observation_window=ObservationWindow((date(2026, 1, 15), date(2026, 2, 15), date(2026, 3, 15)), start_payoff_index=0, role="put_ki_window"),
        breach_condition="spot_lte_level",
    )
    gap_event = EventPayoffSpec(
        scheme_name="gap",
        legs=(
            OptionPayoffLeg(option_type="call", position="buy", strike=ConstantTerm(145.0), ratio=ConstantTerm(1.0)),
            OptionPayoffLeg(option_type="put", position="sell", strike=ConstantTerm(150.0), ratio=ConstantTerm(2.0), barrier=ki),
        ),
    )
    return CouponSwapSpec(
        identity=ProductIdentity("COUPON_SWAP", "FXCouponSwap", "2.0"),
        underlying="USDJPY",
        coupon_currency="JPY",
        notional=ConstantTerm(5_000_000.0),
        coupon_schedule=PeriodicScheduleSpec(date(2026, 1, 31), date(2026, 7, 31), "monthly", settlement_lag_days=2, holiday_calendar="TKY", role="coupon_fixing"),
        payoff_program=PayoffProgram(default_event_payoff=gap_event),
    )


def make_mixed_ako_coupon_swap() -> AKOCouponSwapSpec:
    ki = EuropeanKnockInBarrier(
        trigger_level=ConstantTerm(130.0),
        observation_window=ObservationWindow((date(2026, 1, 15), date(2026, 4, 15), date(2026, 7, 15)), start_payoff_index=0, role="put_ki_window"),
    )
    gap = EventPayoffSpec(
        scheme_name="gap",
        legs=(
            OptionPayoffLeg(option_type="call", position="buy", strike=ConstantTerm(145.0), ratio=ConstantTerm(1.0)),
            OptionPayoffLeg(option_type="put", position="sell", strike=ConstantTerm(150.0), ratio=ConstantTerm(2.0), barrier=ki),
        ),
    )
    collar = EventPayoffSpec(
        scheme_name="collar",
        legs=(
            OptionPayoffLeg(option_type="call", position="buy", strike=ConstantTerm(150.0), ratio=ConstantTerm(1.0)),
            OptionPayoffLeg(option_type="put", position="sell", strike=ConstantTerm(145.0), ratio=ConstantTerm(2.0)),
        ),
    )
    return AKOCouponSwapSpec(
        identity=ProductIdentity("AKO_COUPON_SWAP", "StructuredCouponWithAKO", "2.0"),
        underlying="USDJPY",
        coupon_currency="JPY",
        notional=ConstantTerm(10_000_000.0),
        coupon_schedule=PeriodicScheduleSpec(date(2026, 1, 15), date(2026, 10, 15), "quarterly", settlement_lag_days=5, holiday_calendar="TKY", role="coupon_fixing"),
        payoff_program=PayoffProgram(default_event_payoff=gap, event_overrides={2: collar}),
        ako_level=ConstantTerm(128.0),
        ako_window=ObservationWindow((date(2026, 2, 7), date(2026, 3, 7), date(2026, 4, 7)), start_date=date(2026, 2, 7), role="ako_window"),
    )


def demo() -> None:
    draft = instantiate_trade_draft(
        draft_id="DRAFT-2001",
        contract=make_gap_coupon_swap(),
        representation=OptionBundleRepresentation(),
        indication_payload={"quote_id": "Q-2001"},
        captured_at=datetime(2026, 4, 10, 9, 0, 0),
        created_by="alice",
    )
    allocator = UserSpecifiedPrefixAllocator()
    trade_ref = allocator.allocate_trade_ref(draft=draft, system_name="booking_x", user_prefix="USRBOOK", issued_at=datetime(2026, 4, 10, 9, 5, 0))
    allocator.allocate_component_refs_for_current_snapshot(
        draft=draft,
        system_name="booking_x",
        parent_external_trade_id=trade_ref.external_trade_id,
        user_prefix="OPT",
        issued_at=datetime(2026, 4, 10, 9, 5, 5),
    )
    print(draft.current_snapshot.trade_payoff_scheme)
    print(draft.to_dict())


if __name__ == "__main__":
    demo()
