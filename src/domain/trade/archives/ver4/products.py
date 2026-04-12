from __future__ import annotations

from dataclasses import dataclass, field

from .barriers import (
    AKOBarrier,
    BarrierTriggeredRedemption,
    EuropeanKnockInLegBarrier,
    NoBarrier,
    NoLegBarrier,
)
from .components import (
    CouponAccrual,
    FinalFixingSettlement,
    FXStructuredPayoff,
    NoRedemption,
    PositivePnLAccrual,
    ProductSpec,
    RangeCouponPayoff,
    StandardSettlement,
    TargetHitRedemption,
)
from .identity import ProductIdentity, UnderlyingRef
from .payoff_legs import FXForwardLegSpec, FXOptionLegSpec
from .schedules import (
    ObservationWindowSpec,
    ScheduleSpec,
)
from .terms import StepByIndexTerm, Term


def make_normal_payoff(
    *,
    underlying: UnderlyingRef,
    schedule_spec: ScheduleSpec,
    settlement_currency: str,
    base_notional: Term[float],
    strike: Term[float],
    ratio: Term[float],
    forward_position: str = "sell_base",
) -> FXStructuredPayoff:
    payoff = FXStructuredPayoff(
        underlying=underlying,
        payoff_style="normal",
        schedule_spec=schedule_spec,
        settlement_currency=settlement_currency,
        base_notional=base_notional,
        legs=(
            FXForwardLegSpec(
                position=forward_position,
                strike=strike,
                quantity_multiplier=ratio,
            ),
        ),
    )
    payoff.validate()
    return payoff


def make_two_stage_payoff(
    *,
    underlying: UnderlyingRef,
    schedule_spec: ScheduleSpec,
    settlement_currency: str,
    base_notional: Term[float],
    strike_steps: StepByIndexTerm[float],
    ratio: Term[float],
    forward_position: str = "sell_base",
) -> FXStructuredPayoff:
    payoff = FXStructuredPayoff(
        underlying=underlying,
        payoff_style="two_stage",
        schedule_spec=schedule_spec,
        settlement_currency=settlement_currency,
        base_notional=base_notional,
        legs=(
            FXForwardLegSpec(
                position=forward_position,
                strike=strike_steps,
                quantity_multiplier=ratio,
            ),
        ),
    )
    payoff.validate()
    return payoff


def make_gap_payoff(
    *,
    underlying: UnderlyingRef,
    schedule_spec: ScheduleSpec,
    settlement_currency: str,
    base_notional: Term[float],
    call_strike: Term[float],
    put_strike: Term[float],
    call_ratio: Term[float],
    put_ratio: Term[float],
    put_ki_trigger: Term[float],
    put_ki_observation_window: ObservationWindowSpec,
    put_ki_breach_condition: str = "spot_lte_level",
) -> FXStructuredPayoff:
    payoff = FXStructuredPayoff(
        underlying=underlying,
        payoff_style="gap",
        schedule_spec=schedule_spec,
        settlement_currency=settlement_currency,
        base_notional=base_notional,
        legs=(
            FXOptionLegSpec(
                option_type="call",
                position="buy",
                strike=call_strike,
                quantity_multiplier=call_ratio,
                barrier=NoLegBarrier(),
            ),
            FXOptionLegSpec(
                option_type="put",
                position="sell",
                strike=put_strike,
                quantity_multiplier=put_ratio,
                barrier=EuropeanKnockInLegBarrier(
                    trigger_level=put_ki_trigger,
                    observation_window=put_ki_observation_window,
                    breach_condition=put_ki_breach_condition,
                ),
            ),
        ),
    )
    payoff.validate()
    return payoff


def make_range_gap_payoff(
    *,
    underlying: UnderlyingRef,
    schedule_spec: ScheduleSpec,
    settlement_currency: str,
    base_notional: Term[float],
    shared_strike: Term[float],
    call_ratio: Term[float],
    put_ratio: Term[float],
    put_ki_trigger: Term[float],
    put_ki_observation_window: ObservationWindowSpec,
    put_ki_breach_condition: str = "spot_lte_level",
) -> FXStructuredPayoff:
    payoff = FXStructuredPayoff(
        underlying=underlying,
        payoff_style="range_gap",
        schedule_spec=schedule_spec,
        settlement_currency=settlement_currency,
        base_notional=base_notional,
        legs=(
            FXOptionLegSpec(
                option_type="call",
                position="buy",
                strike=shared_strike,
                quantity_multiplier=call_ratio,
                barrier=NoLegBarrier(),
            ),
            FXOptionLegSpec(
                option_type="put",
                position="sell",
                strike=shared_strike,
                quantity_multiplier=put_ratio,
                barrier=EuropeanKnockInLegBarrier(
                    trigger_level=put_ki_trigger,
                    observation_window=put_ki_observation_window,
                    breach_condition=put_ki_breach_condition,
                ),
            ),
        ),
    )
    payoff.validate()
    return payoff


def make_collar_payoff(
    *,
    underlying: UnderlyingRef,
    schedule_spec: ScheduleSpec,
    settlement_currency: str,
    base_notional: Term[float],
    call_strike: Term[float],
    put_strike: Term[float],
    call_ratio: Term[float],
    put_ratio: Term[float],
) -> FXStructuredPayoff:
    payoff = FXStructuredPayoff(
        underlying=underlying,
        payoff_style="collar",
        schedule_spec=schedule_spec,
        settlement_currency=settlement_currency,
        base_notional=base_notional,
        legs=(
            FXOptionLegSpec(
                option_type="call",
                position="buy",
                strike=call_strike,
                quantity_multiplier=call_ratio,
                barrier=NoLegBarrier(),
            ),
            FXOptionLegSpec(
                option_type="put",
                position="sell",
                strike=put_strike,
                quantity_multiplier=put_ratio,
                barrier=NoLegBarrier(),
            ),
        ),
    )
    payoff.validate()
    return payoff


@dataclass(frozen=True)
class TARFSpec:
    identity: ProductIdentity
    payoff: FXStructuredPayoff
    target: Term[float]
    final_fixing_treatment: str = "full"
    product_barrier: object = field(default_factory=NoBarrier)

    def __post_init__(self) -> None:
        if self.identity.family != "TARF":
            raise ValueError("TARFSpec.identity.family must be 'TARF'")

    def to_product_spec(self) -> ProductSpec:
        spec = ProductSpec(
            identity=self.identity,
            payoff=self.payoff,
            barrier=self.product_barrier,
            accrual=PositivePnLAccrual(
                accrual_currency=self.payoff.settlement_currency,
                metric="positive_pnl_only",
            ),
            redemption=TargetHitRedemption(
                target=self.target,
                comparison="accrued_gte_target",
                action_on_hit="terminate",
            ),
            settlement=FinalFixingSettlement(
                settlement_mode="cash",
                final_fixing_treatment=self.final_fixing_treatment,
                settlement_currency=self.payoff.settlement_currency,
            ),
            tags=("fx", "target_redemption", "tarf", self.payoff.payoff_style),
            metadata={},
        )
        spec.validate()
        return spec

    def to_dict(self) -> dict:
        return self.to_product_spec().to_dict()

    @classmethod
    def from_product_spec(cls, spec: ProductSpec) -> "TARFSpec":
        spec.validate()
        if not isinstance(spec.payoff, FXStructuredPayoff):
            raise ValueError("unexpected payoff for TARF")
        if not isinstance(spec.redemption, TargetHitRedemption):
            raise ValueError("unexpected redemption for TARF")
        if not isinstance(spec.settlement, FinalFixingSettlement):
            raise ValueError("unexpected settlement for TARF")

        return cls(
            identity=spec.identity,
            payoff=spec.payoff,
            target=spec.redemption.target,
            final_fixing_treatment=spec.settlement.final_fixing_treatment,
            product_barrier=spec.barrier,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "TARFSpec":
        return cls.from_product_spec(ProductSpec.from_dict(data))


@dataclass(frozen=True)
class AKOCouponSwapSpec:
    identity: ProductIdentity
    payoff: object
    ako_trigger_level: Term[float]
    ako_observation_window: ObservationWindowSpec
    ako_breach_condition: str = "spot_lte_level"
    ako_action_on_breach: str = "cancel_remaining"
    redemption_on_ako: bool = True
    settlement_currency: str | None = None
    accrual_factor_term: Term[float] | None = None

    def __post_init__(self) -> None:
        if self.identity.family != "AKO_COUPON_SWAP":
            raise ValueError("AKOCouponSwapSpec.identity.family must be 'AKO_COUPON_SWAP'")
        if not isinstance(self.payoff, (FXStructuredPayoff, RangeCouponPayoff)):
            raise ValueError("AKOCouponSwapSpec.payoff must be FXStructuredPayoff or RangeCouponPayoff")

    def _infer_currency(self) -> str | None:
        if self.settlement_currency is not None:
            return self.settlement_currency
        if isinstance(self.payoff, FXStructuredPayoff):
            return self.payoff.settlement_currency
        if isinstance(self.payoff, RangeCouponPayoff):
            return self.payoff.coupon_currency
        return None

    def to_product_spec(self) -> ProductSpec:
        barrier = AKOBarrier(
            underlying=self.payoff.underlying,
            trigger_level=self.ako_trigger_level,
            observation_window=self.ako_observation_window,
            breach_condition=self.ako_breach_condition,
            action_on_breach=self.ako_action_on_breach,
        )

        spec = ProductSpec(
            identity=self.identity,
            payoff=self.payoff,
            barrier=barrier,
            accrual=CouponAccrual(
                observation_basis="formula_based",
                accrual_factor_term=self.accrual_factor_term,
            ),
            redemption=(
                BarrierTriggeredRedemption(action_on_barrier=self.ako_action_on_breach)
                if self.redemption_on_ako
                else NoRedemption()
            ),
            settlement=StandardSettlement(
                settlement_mode="cash",
                settlement_currency=self._infer_currency(),
            ),
            tags=("fx", "coupon_swap", "ako"),
            metadata={},
        )
        spec.validate()
        return spec

    def to_dict(self) -> dict:
        return self.to_product_spec().to_dict()

    @classmethod
    def from_product_spec(cls, spec: ProductSpec) -> "AKOCouponSwapSpec":
        spec.validate()
        if not isinstance(spec.barrier, AKOBarrier):
            raise ValueError("unexpected barrier for AKO_COUPON_SWAP")

        settlement_currency = None
        if isinstance(spec.settlement, StandardSettlement):
            settlement_currency = spec.settlement.settlement_currency

        accrual_factor_term = None
        if isinstance(spec.accrual, CouponAccrual):
            accrual_factor_term = spec.accrual.accrual_factor_term

        return cls(
            identity=spec.identity,
            payoff=spec.payoff,
            ako_trigger_level=spec.barrier.trigger_level,
            ako_observation_window=spec.barrier.observation_window,
            ako_breach_condition=spec.barrier.breach_condition,
            ako_action_on_breach=spec.barrier.action_on_breach,
            redemption_on_ako=isinstance(spec.redemption, BarrierTriggeredRedemption),
            settlement_currency=settlement_currency,
            accrual_factor_term=accrual_factor_term,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "AKOCouponSwapSpec":
        return cls.from_product_spec(ProductSpec.from_dict(data))