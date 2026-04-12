from __future__ import annotations

from dataclasses import dataclass, field

from .barriers import AKOBarrier, NoBarrier, EuropeanKnockInLegBarrier, NoLegBarrier, Barrier
from .components import (
    CouponAccrual,
    FinalFixingSettlement,
    FXStructuredPayoff,
    GenericMultiLegPayoff,
    NoRedemption,
    PositivePnLAccrual,
    ProductSpec,
    RangeCouponPayoff,
    StandardSettlement,
    TargetHitRedemption,
    BarrierTriggeredRedemption,
)
from .identity import CmsIndexRef, ProductIdentity, RateIndexRef, UnderlyingRef
from .legs import FixedRateLegSpec, FloatingRateLegSpec, FormulaLegSpec, FXForwardLegSpec, FXOptionLegSpec
from .schedules import ObservationWindowSpec, ScheduleSpec
from .terms import AnyTerm, ConstantTerm, StepByIndexTerm


def make_normal_payoff(
    *,
    underlying: UnderlyingRef,
    schedule_spec: ScheduleSpec,
    settlement_currency: str,
    base_notional: AnyTerm,
    strike: AnyTerm,
    ratio: AnyTerm,
    forward_position: str = "sell_base",
) -> FXStructuredPayoff:
    payoff = FXStructuredPayoff(
        underlying=underlying,
        payoff_style="normal",
        schedule_spec=schedule_spec,
        settlement_currency=settlement_currency,
        base_notional=base_notional,
        legs=(FXForwardLegSpec(position=forward_position, strike=strike, quantity_multiplier=ratio),),
    )
    payoff.validate()
    return payoff


def make_two_stage_payoff(
    *,
    underlying: UnderlyingRef,
    schedule_spec: ScheduleSpec,
    settlement_currency: str,
    base_notional: AnyTerm,
    strike_steps: StepByIndexTerm,
    ratio: AnyTerm,
    forward_position: str = "sell_base",
) -> FXStructuredPayoff:
    return make_normal_payoff(
        underlying=underlying,
        schedule_spec=schedule_spec,
        settlement_currency=settlement_currency,
        base_notional=base_notional,
        strike=strike_steps,
        ratio=ratio,
        forward_position=forward_position,
    ).__class__(
        underlying=underlying,
        payoff_style="two_stage",
        schedule_spec=schedule_spec,
        settlement_currency=settlement_currency,
        base_notional=base_notional,
        legs=(FXForwardLegSpec(position=forward_position, strike=strike_steps, quantity_multiplier=ratio),),
    )


def make_gap_payoff(
    *,
    underlying: UnderlyingRef,
    schedule_spec: ScheduleSpec,
    settlement_currency: str,
    base_notional: AnyTerm,
    call_strike: AnyTerm,
    put_strike: AnyTerm,
    call_ratio: AnyTerm,
    put_ratio: AnyTerm,
    put_ki_trigger: AnyTerm,
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


def make_fixed_float_swap_payoff(
    *,
    schedule_spec: ScheduleSpec,
    fixed_currency: str,
    float_currency: str,
    notional: AnyTerm,
    fixed_rate: AnyTerm,
    float_index: RateIndexRef | CmsIndexRef,
    spread: AnyTerm = ConstantTerm(0.0),
    leverage: AnyTerm = ConstantTerm(1.0),
    fixed_day_count: str = "30/360",
    float_day_count: str = "ACT/360",
    pay_fixed: bool = True,
) -> GenericMultiLegPayoff:
    return GenericMultiLegPayoff(
        payoff_style="swap",
        schedule_spec=schedule_spec,
        legs=(
            FixedRateLegSpec(
                pay_receive="pay" if pay_fixed else "receive",
                currency=fixed_currency,
                notional=notional,
                fixed_rate=fixed_rate,
                day_count=fixed_day_count,
            ),
            FloatingRateLegSpec(
                pay_receive="receive" if pay_fixed else "pay",
                currency=float_currency,
                notional=notional,
                index=float_index,
                spread=spread,
                leverage=leverage,
                day_count=float_day_count,
            ),
        ),
        principal_exchange="none",
    )


def make_prdc_payoff(
    *,
    schedule_spec: ScheduleSpec,
    coupon_currency: str,
    redemption_currency: str,
    notional: AnyTerm,
    domestic_index: CmsIndexRef | RateIndexRef,
    fx_underlying: UnderlyingRef,
    coupon_formula_name: str = "prdc_coupon",
    coupon_floor: AnyTerm | None = None,
    coupon_cap: AnyTerm | None = None,
) -> GenericMultiLegPayoff:
    return GenericMultiLegPayoff(
        payoff_style="prdc",
        schedule_spec=schedule_spec,
        principal_exchange="final_redemption_only",
        legs=(
            FormulaLegSpec(
                leg_role="coupon_leg",
                pay_receive="receive",
                currency=coupon_currency,
                notional=notional,
                formula_name=coupon_formula_name,
                formula_inputs={
                    "domestic_index": domestic_index.to_dict(),
                    "fx_underlying": fx_underlying.to_dict(),
                },
                day_count="30/360",
                cap=coupon_cap,
                floor=coupon_floor,
            ),
            FormulaLegSpec(
                leg_role="redemption_leg",
                pay_receive="receive",
                currency=redemption_currency,
                notional=notional,
                formula_name="bullet_redemption",
                formula_inputs={"redemption_currency": redemption_currency},
            ),
        ),
        metadata={"product_subtype": "prdc"},
    )


@dataclass(frozen=True)
class TARFSpec:
    identity: ProductIdentity
    payoff: FXStructuredPayoff
    target: AnyTerm
    final_fixing_treatment: str = "full"
    product_barrier: Barrier = field(default_factory=NoBarrier)

    def __post_init__(self) -> None:
        if self.identity.family != "TARF":
            raise ValueError("TARFSpec.identity.family must be 'TARF'")

    def to_product_spec(self) -> ProductSpec:
        spec = ProductSpec(
            identity=self.identity,
            payoff=self.payoff,
            barrier=self.product_barrier,
            accrual=PositivePnLAccrual(accrual_currency=self.payoff.settlement_currency),
            redemption=TargetHitRedemption(target=self.target),
            settlement=FinalFixingSettlement(
                settlement_mode="cash",
                final_fixing_treatment=self.final_fixing_treatment,
                settlement_currency=self.payoff.settlement_currency,
            ),
            tags=("fx", "target_redemption", "tarf", self.payoff.payoff_style),
        )
        spec.validate()
        return spec

    @classmethod
    def from_dict(cls, data: dict) -> "TARFSpec":
        spec = ProductSpec.from_dict(data)
        return cls(
            identity=spec.identity,
            payoff=spec.payoff,
            target=spec.redemption.target,
            final_fixing_treatment=spec.settlement.final_fixing_treatment,
            product_barrier=spec.barrier,
        )


@dataclass(frozen=True)
class TARNSpec:
    identity: ProductIdentity
    payoff: FXStructuredPayoff | GenericMultiLegPayoff | RangeCouponPayoff
    target: AnyTerm
    accrual_currency: str
    target_metric: str = "positive_pnl_only"

    def __post_init__(self) -> None:
        if self.identity.family != "TARN":
            raise ValueError("TARNSpec.identity.family must be 'TARN'")

    def to_product_spec(self) -> ProductSpec:
        spec = ProductSpec(
            identity=self.identity,
            payoff=self.payoff,
            barrier=NoBarrier(),
            accrual=PositivePnLAccrual(accrual_currency=self.accrual_currency, metric=self.target_metric),
            redemption=TargetHitRedemption(target=self.target),
            settlement=StandardSettlement(settlement_mode="cash", settlement_currency=self.accrual_currency),
            tags=("target_redemption", "tarn"),
        )
        spec.validate()
        return spec


@dataclass(frozen=True)
class AKOCouponSwapSpec:
    identity: ProductIdentity
    payoff: FXStructuredPayoff | RangeCouponPayoff | GenericMultiLegPayoff
    ako_trigger_level: AnyTerm
    ako_observation_window: ObservationWindowSpec
    ako_breach_condition: str = "spot_lte_level"
    ako_action_on_breach: str = "cancel_remaining"
    redemption_on_ako: bool = True
    settlement_currency: str | None = None
    accrual_factor_term: AnyTerm | None = None

    def __post_init__(self) -> None:
        if self.identity.family != "AKO_COUPON_SWAP":
            raise ValueError("AKOCouponSwapSpec.identity.family must be 'AKO_COUPON_SWAP'")

    def _infer_underlying(self) -> UnderlyingRef:
        if isinstance(self.payoff, FXStructuredPayoff):
            return self.payoff.underlying
        if isinstance(self.payoff, RangeCouponPayoff):
            return self.payoff.underlying
        for leg in self.payoff.legs:
            if isinstance(leg, FormulaLegSpec):
                raw = leg.formula_inputs.get("fx_underlying")
                if isinstance(raw, dict):
                    return UnderlyingRef.from_dict(raw)
        return UnderlyingRef(name="GENERIC", asset_class="GENERIC")

    def to_product_spec(self) -> ProductSpec:
        barrier = AKOBarrier(
            underlying=self._infer_underlying(),
            trigger_level=self.ako_trigger_level,
            observation_window=self.ako_observation_window,
            breach_condition=self.ako_breach_condition,
            action_on_breach=self.ako_action_on_breach,
        )
        spec = ProductSpec(
            identity=self.identity,
            payoff=self.payoff,
            barrier=barrier,
            accrual=CouponAccrual(observation_basis="formula_based", accrual_factor_term=self.accrual_factor_term),
            redemption=BarrierTriggeredRedemption(self.ako_action_on_breach) if self.redemption_on_ako else NoRedemption(),
            settlement=StandardSettlement(settlement_mode="cash", settlement_currency=self.settlement_currency),
            tags=("coupon_swap", "ako"),
        )
        spec.validate()
        return spec


@dataclass(frozen=True)
class InterestRateSwapSpec:
    identity: ProductIdentity
    payoff: GenericMultiLegPayoff
    settlement_currency: str | None = None

    def __post_init__(self) -> None:
        if self.identity.family != "INTEREST_RATE_SWAP":
            raise ValueError("InterestRateSwapSpec.identity.family must be 'INTEREST_RATE_SWAP'")

    def to_product_spec(self) -> ProductSpec:
        spec = ProductSpec(
            identity=self.identity,
            payoff=self.payoff,
            barrier=NoBarrier(),
            accrual=CouponAccrual(observation_basis="rate_fixing"),
            redemption=NoRedemption(),
            settlement=StandardSettlement(settlement_mode="cash", settlement_currency=self.settlement_currency),
            tags=("rates", "swap", "irs"),
        )
        spec.validate()
        return spec


@dataclass(frozen=True)
class PRDCNoteSpec:
    identity: ProductIdentity
    payoff: GenericMultiLegPayoff
    settlement_currency: str
    callable_style: str | None = None

    def __post_init__(self) -> None:
        if self.identity.family != "PRDC":
            raise ValueError("PRDCNoteSpec.identity.family must be 'PRDC'")

    def to_product_spec(self) -> ProductSpec:
        spec = ProductSpec(
            identity=self.identity,
            payoff=self.payoff,
            barrier=NoBarrier(),
            accrual=CouponAccrual(observation_basis="formula_based"),
            redemption=NoRedemption(),
            settlement=StandardSettlement(settlement_mode="cash", settlement_currency=self.settlement_currency),
            tags=("rates", "fx_linked", "prdc"),
            metadata={} if self.callable_style is None else {"callable_style": self.callable_style},
        )
        spec.validate()
        return spec


@dataclass(frozen=True)
class RangeAccrualNoteSpec:
    identity: ProductIdentity
    payoff: RangeCouponPayoff
    settlement_currency: str

    def __post_init__(self) -> None:
        if self.identity.family != "RANGE_ACCRUAL_NOTE":
            raise ValueError("RangeAccrualNoteSpec.identity.family must be 'RANGE_ACCRUAL_NOTE'")

    def to_product_spec(self) -> ProductSpec:
        spec = ProductSpec(
            identity=self.identity,
            payoff=self.payoff,
            barrier=NoBarrier(),
            accrual=CouponAccrual(observation_basis="range_accrual", accrual_factor_term=self.payoff.accrual_factor_term),
            redemption=NoRedemption(),
            settlement=StandardSettlement(settlement_mode="cash", settlement_currency=self.settlement_currency),
            tags=("rates", "range_accrual"),
        )
        spec.validate()
        return spec
