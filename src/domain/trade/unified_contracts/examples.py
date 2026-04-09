from __future__ import annotations

from datetime import date, datetime

from .common.cashflows import CashflowRecord
from .common.identity import ProductIdentity
from .common.representations import CouponSwapRepresentation, OptionBundleRepresentation
from .common.schedules import ObservationWindow, PeriodicScheduleSpec
from .common.terms import ConstantTerm, StepByIndexTerm
from .outbound.id_allocator import ExternalIdAllocator
from .products.coupon_swap import AKOCouponSwapSpec, CouponFormula, CouponSwapSpec
from .products.tarf import TARFLeg, TARFSpec
from .services.instantiate import instantiate_trade_draft


def make_tarf() -> TARFSpec:
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
            observation_dates=(date(2026, 2, 7), date(2026, 3, 7), date(2026, 4, 7)),
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
    tarf = make_tarf()
    draft = instantiate_trade_draft(
        draft_id="DRAFT-001",
        contract=tarf,
        representation=CouponSwapRepresentation(),
        indication_payload={"quote_id": "Q-1001", "source": "indication-ui"},
        captured_at=datetime(2026, 4, 9, 9, 0, 0),
        created_by="alice",
    )

    updated_cashflows = list(draft.cashflows)
    first = updated_cashflows[0]
    updated_cashflows[0] = CashflowRecord(
        cashflow_id=first.cashflow_id,
        source_schedule_id=first.source_schedule_id,
        source_event_index=first.source_event_index,
        view_kind=first.view_kind,
        leg_label=first.leg_label,
        currency=first.currency,
        amount_description="manually fixed coupon amount = 1,250,000 JPY",
        payment_date=first.payment_date,
        active=first.active,
        metadata={**first.metadata, "manual_edit": True},
    )

    draft.add_snapshot(
        created_by="alice",
        reason="manually adjusted first coupon after client negotiation",
        created_at=datetime(2026, 4, 9, 9, 30, 0),
        cashflows=updated_cashflows,
    )

    option_view_cashflows = instantiate_trade_draft(
        draft_id="TEMP",
        contract=tarf,
        representation=OptionBundleRepresentation(),
        indication_payload={},
        captured_at=datetime(2026, 4, 9, 10, 0, 0),
    ).cashflows
    draft.add_snapshot(
        created_by="bob",
        reason="re-book as option bundle view",
        created_at=datetime(2026, 4, 9, 10, 0, 0),
        representation=OptionBundleRepresentation(),
        cashflows=option_view_cashflows,
    )

    allocator = ExternalIdAllocator()
    trade_ref = allocator.allocate_trade_ref(system_name="BOOKING_A", trade=draft, issued_at=datetime(2026, 4, 9, 10, 5, 0))
    allocator.allocate_component_refs_for_option_bundle(
        system_name="BOOKING_A",
        trade=draft,
        parent_external_trade_id=trade_ref.external_trade_id,
        issued_at=datetime(2026, 4, 9, 10, 5, 0),
    )

    print(draft.to_dict())


if __name__ == "__main__":
    demo()
