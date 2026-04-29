"""
ratio_forward_product_grammars_v2_full.py

Ratio-forward-like product grammar implemented on top of contract_model_v2_full.

Key design choices
------------------
- Same economics are not collapsed into a single canonical object.
- Coupon Swap form and FX Option Package form remain separate authoring forms.
- Observation is first-class.
- Coupon/option payoff determination is a DeterminationRule, not a generic Formula.
- WKO is Observation + BarrierCondition + LifecycleRule/Effect.
- TARGET is Accumulator + TargetReachedCondition + TargetLifecycleRule.
- MtM-style reset is represented in the common model as QuantityRule + LifecycleRule,
  not used directly in the ratio-forward examples but supported by the base model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional, Literal

from contract_model_v2_full import *


class RatioForwardScheme(str, Enum):
    NORMAL = "NORMAL"
    GAP = "GAP"
    RANGE_GAP = "RANGE_GAP"
    COLLAR = "COLLAR"
    TWO_STAGE = "TWO_STAGE"


class SoldOptionSelector(str, Enum):
    PUT = "PUT"
    CALL = "CALL"


@dataclass(frozen=True)
class OptionAmountSpec:
    notional_base: Decimal
    call_level: Decimal = ONE
    put_level: Decimal = ONE

    @property
    def call_amount_base(self) -> Decimal:
        return self.notional_base * self.call_level

    @property
    def put_amount_base(self) -> Decimal:
        return self.notional_base * self.put_level


@dataclass(frozen=True)
class TwoStageStrikeSpec:
    stage_switch_index: int
    stage1_strike: Decimal
    stage2_strike: Decimal


@dataclass(frozen=True)
class EuropeanKnockInSpec:
    barrier: Decimal
    direction: BarrierDirection
    observation_schedule: Optional[ScheduleRefLike] = None


@dataclass(frozen=True)
class WKOConfig:
    barrier: Decimal
    direction: BarrierDirection
    observation_schedule: ScheduleRefLike
    monitoring_start_index: int = 0
    affected_start_index: int = 0


@dataclass(frozen=True)
class TargetConfig:
    metric: TargetMetric
    target_value: Decimal
    accumulation_side: TargetAccumulationSide
    hit_action: TargetHitAction
    accumulation_currency: Optional[Currency] = None


@dataclass(frozen=True)
class RatioForwardSeriesSchedule:
    fixing_schedule: ScheduleRefLike
    payment_schedule: ScheduleRefLike
    accrual_start_schedule: Optional[ScheduleRefLike] = None
    accrual_end_schedule: Optional[ScheduleRefLike] = None
    ki_observation_schedule: Optional[ScheduleRefLike] = None


@dataclass(frozen=True)
class RatioForwardSeriesEconomicTerms:
    pair: FxPair
    scheme: RatioForwardScheme
    amount_spec: OptionAmountSpec
    call_strike: Decimal
    put_strike: Decimal
    two_stage: Optional[TwoStageStrikeSpec] = None
    sold_option_selector: SoldOptionSelector = SoldOptionSelector.PUT
    sold_option_knock_in: Optional[EuropeanKnockInSpec] = None

    def validate(self) -> None:
        if self.scheme is RatioForwardScheme.NORMAL:
            if self.call_strike != self.put_strike:
                raise ValueError("NORMAL requires K_call = K_put")
        elif self.scheme is RatioForwardScheme.GAP:
            if not (self.call_strike < self.put_strike):
                raise ValueError("GAP requires K_call < K_put")
            if self.sold_option_knock_in is None:
                raise ValueError("GAP requires sold-side KI")
        elif self.scheme is RatioForwardScheme.RANGE_GAP:
            if self.call_strike != self.put_strike:
                raise ValueError("RANGE_GAP requires K_call = K_put")
            if self.sold_option_knock_in is None:
                raise ValueError("RANGE_GAP requires sold-side KI")
        elif self.scheme is RatioForwardScheme.COLLAR:
            if not (self.put_strike < self.call_strike):
                raise ValueError("COLLAR requires K_put < K_call")
        elif self.scheme is RatioForwardScheme.TWO_STAGE:
            if self.two_stage is None:
                raise ValueError("TWO_STAGE requires two_stage")
            if self.call_strike != self.put_strike:
                raise ValueError("TWO_STAGE initial stage requires K_call = K_put")
        else:
            raise ValueError(self.scheme)


@dataclass(frozen=True)
class RatioForwardPeriodSpec:
    period_index: int
    fixing_date: date
    payment_date: date
    accrual_start_date: Optional[date]
    accrual_end_date: Optional[date]
    call_strike: Decimal
    put_strike: Decimal
    call_amount_base: Decimal
    put_amount_base: Decimal
    sold_option_selector: SoldOptionSelector
    sold_option_knock_in: Optional[EuropeanKnockInSpec]
    ki_observation_date: Optional[date]


@dataclass(frozen=True)
class CouponSwapRatioForwardGrammarV2:
    counterparties: CounterpartySpec
    schedule: RatioForwardSeriesSchedule
    economic_terms: RatioForwardSeriesEconomicTerms
    quote_currency: Currency
    base_currency: Currency
    pay_leg_role: Literal["CLIENT_PAYS_BASE", "CLIENT_PAYS_QUOTE"] = "CLIENT_PAYS_BASE"
    wko: Optional[WKOConfig] = None
    target: Optional[TargetConfig] = None

    def validate(self) -> None:
        self.economic_terms.validate()
        if self.schedule.accrual_start_schedule is None or self.schedule.accrual_end_schedule is None:
            raise ValueError("CouponSwap form requires accrual start/end schedules")
        if self.target and self.target.metric is TargetMetric.AMOUNT:
            if self.target.accumulation_currency is None:
                raise ValueError("TARGET amount metric requires currency")
            if self.target.accumulation_currency != self.quote_currency:
                raise ValueError("Current example supports TARGET amount accumulation only in quote currency")


@dataclass(frozen=True)
class FxOptionPackageRatioForwardGrammarV2:
    counterparties: CounterpartySpec
    schedule: RatioForwardSeriesSchedule
    economic_terms: RatioForwardSeriesEconomicTerms
    settlement_style: SettlementStyle = SettlementStyle.CASH
    settlement_currency: Optional[Currency] = None
    premium: Optional[Money] = None
    premium_payment_date: Optional[date] = None
    wko: Optional[WKOConfig] = None
    target: Optional[TargetConfig] = None

    def validate(self) -> None:
        self.economic_terms.validate()
        settlement_ccy = self.settlement_currency or self.economic_terms.pair.quote_currency
        if self.target and self.target.metric is TargetMetric.AMOUNT:
            if self.target.accumulation_currency is None:
                raise ValueError("TARGET amount metric requires currency")
            if self.target.accumulation_currency != settlement_ccy:
                raise ValueError("Current example supports TARGET amount accumulation only in settlement currency")
        if (self.premium is None) ^ (self.premium_payment_date is None):
            raise ValueError("premium and premium_payment_date must be given together")


@dataclass(frozen=True)
class BuiltRatioForwardContractV2:
    form: ContractFormV2
    form_variant: Literal["COUPON_SWAP", "FX_OPTION_PACKAGE"]
    pair: FxPair
    base_currency: Currency
    quote_currency: Currency
    client_party_id: str
    bank_party_id: str
    period_specs: tuple[RatioForwardPeriodSpec, ...]
    payment_dates_by_component: dict[str, date]
    wko: Optional[WKOConfig] = None
    target: Optional[TargetConfig] = None


# ---------------------------------------------------------------------------
# Expansion helpers
# ---------------------------------------------------------------------------

def _schedule_dates(schedule_like: ScheduleRefLike) -> tuple[date, ...]:
    if isinstance(schedule_like, DateListSchedule):
        return schedule_like.sorted_dates()
    raise TypeError("ratio-forward v2 builders expect materialized DateListSchedule inputs")


def _default_ki_schedule(schedule: RatioForwardSeriesSchedule, sold_ki: EuropeanKnockInSpec) -> ScheduleRefLike:
    if sold_ki.observation_schedule is not None:
        return sold_ki.observation_schedule
    if schedule.ki_observation_schedule is not None:
        return schedule.ki_observation_schedule
    return schedule.fixing_schedule


def _client_and_bank_ids(cp: CounterpartySpec) -> tuple[str, str]:
    return cp.counterparty.party_id, cp.book_party.party_id


def expand_period_specs(schedule: RatioForwardSeriesSchedule, terms: RatioForwardSeriesEconomicTerms) -> tuple[RatioForwardPeriodSpec, ...]:
    terms.validate()
    fixing_dates = _schedule_dates(schedule.fixing_schedule)
    payment_dates = _schedule_dates(schedule.payment_schedule)
    count = min(len(fixing_dates), len(payment_dates))

    if schedule.accrual_start_schedule is None:
        accrual_starts = tuple(None for _ in range(count))
    else:
        raw = _schedule_dates(schedule.accrual_start_schedule)
        accrual_starts = tuple(raw[i] if i < len(raw) else None for i in range(count))

    if schedule.accrual_end_schedule is None:
        accrual_ends = tuple(None for _ in range(count))
    else:
        raw = _schedule_dates(schedule.accrual_end_schedule)
        accrual_ends = tuple(raw[i] if i < len(raw) else None for i in range(count))

    if terms.sold_option_knock_in is None:
        ki_dates = tuple(None for _ in range(count))
    else:
        raw = _schedule_dates(_default_ki_schedule(schedule, terms.sold_option_knock_in))
        ki_dates = tuple(raw[i] if i < len(raw) else None for i in range(count))

    out: list[RatioForwardPeriodSpec] = []
    for i in range(count):
        if terms.scheme is RatioForwardScheme.TWO_STAGE:
            assert terms.two_stage is not None
            strike = terms.two_stage.stage1_strike if i < terms.two_stage.stage_switch_index else terms.two_stage.stage2_strike
            call_strike = strike
            put_strike = strike
        else:
            call_strike = terms.call_strike
            put_strike = terms.put_strike

        out.append(
            RatioForwardPeriodSpec(
                period_index=i,
                fixing_date=fixing_dates[i],
                payment_date=payment_dates[i],
                accrual_start_date=accrual_starts[i],
                accrual_end_date=accrual_ends[i],
                call_strike=call_strike,
                put_strike=put_strike,
                call_amount_base=terms.amount_spec.call_amount_base,
                put_amount_base=terms.amount_spec.put_amount_base,
                sold_option_selector=terms.sold_option_selector,
                sold_option_knock_in=terms.sold_option_knock_in,
                ki_observation_date=ki_dates[i],
            )
        )
    return tuple(out)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def build_coupon_swap_ratio_forward_contract_v2(
    grammar: CouponSwapRatioForwardGrammarV2,
    form_id: str = "FORM-V2-COUPON-SWAP-RATIO-FWD",
) -> BuiltRatioForwardContractV2:
    grammar.validate()
    client_id, bank_id = _client_and_bank_ids(grammar.counterparties)
    specs = expand_period_specs(grammar.schedule, grammar.economic_terms)
    pair = grammar.economic_terms.pair
    pair_ref = UnderlierRef(pair.symbol, "FX")

    pay_base = grammar.pay_leg_role == "CLIENT_PAYS_BASE"
    pay_payer = client_id if pay_base else bank_id
    pay_receiver = bank_id if pay_base else client_id
    recv_payer = bank_id if pay_base else client_id
    recv_receiver = client_id if pay_base else bank_id

    observables: list[ObservableRef] = [ObservableRef("obs_fx", pair_ref, ObservationKind.CLOSE, "FX spot/close for ratio forward")]
    observation_rules: list[ObservationRule] = [
        ObservationRule("obs_fixing", "obs_fx", grammar.schedule.fixing_schedule, ObservationStyle.BERMUDAN, ObservationKind.CLOSE)
    ]
    conditions: list[ConditionType] = []
    components: list[ComponentType] = []
    determination_rules: list[DeterminationRuleType] = []
    lifecycle_rules: list[LifecycleRuleType] = []
    accumulators: list[AccumulatorSpec] = []

    determination_rules.extend([
        FixedQuantityRule("q_base_notional", grammar.economic_terms.amount_spec.notional_base),
        CouponSwapExchangePayoffRule(
            "coupon_swap_pay_rule",
            pair=pair,
            side_role="BASE_DELIVERY" if pay_base else "QUOTE_DELIVERY",
            scheme=grammar.economic_terms.scheme.value,
            sold_option_selector=grammar.economic_terms.sold_option_selector.value,
        ),
        CouponSwapExchangePayoffRule(
            "coupon_swap_receive_rule",
            pair=pair,
            side_role="QUOTE_DELIVERY" if pay_base else "BASE_DELIVERY",
            scheme=grammar.economic_terms.scheme.value,
            sold_option_selector=grammar.economic_terms.sold_option_selector.value,
        ),
    ])

    components.extend([
        CouponStreamLeg(
            component_id="coupon_swap_pay_leg",
            payer_party_id=pay_payer,
            receiver_party_id=pay_receiver,
            reference=pair_ref,
            notional_rule_id="q_base_notional",
            coupon_rule_id="coupon_swap_pay_rule",
            payment_schedule=grammar.schedule.payment_schedule,
            accrual_start_schedule=grammar.schedule.accrual_start_schedule,  # type: ignore[arg-type]
            accrual_end_schedule=grammar.schedule.accrual_end_schedule,      # type: ignore[arg-type]
            currency=grammar.base_currency if pay_base else grammar.quote_currency,
            day_count=DayCount.ACT_365F,
        ),
        CouponStreamLeg(
            component_id="coupon_swap_receive_leg",
            payer_party_id=recv_payer,
            receiver_party_id=recv_receiver,
            reference=pair_ref,
            notional_rule_id="q_base_notional",
            coupon_rule_id="coupon_swap_receive_rule",
            payment_schedule=grammar.schedule.payment_schedule,
            accrual_start_schedule=grammar.schedule.accrual_start_schedule,  # type: ignore[arg-type]
            accrual_end_schedule=grammar.schedule.accrual_end_schedule,      # type: ignore[arg-type]
            currency=grammar.quote_currency if pay_base else grammar.base_currency,
            day_count=DayCount.ACT_365F,
        ),
    ])

    if grammar.wko is not None:
        observation_rules.append(ObservationRule("obs_wko", "obs_fx", grammar.wko.observation_schedule, ObservationStyle.AMERICAN, ObservationKind.CLOSE))
        conditions.append(BarrierCondition("cond_wko_hit", "obs_wko", grammar.wko.direction, grammar.wko.barrier))
        lifecycle_rules.append(
            EventLifecycleRule(
                lifecycle_rule_id="life_wko",
                trigger=Trigger("trigger_wko", "cond_wko_hit", grammar.wko.observation_schedule),
                effects=(
                    SetStateEffect("window_knocked_out", True),
                    DeactivateComponentsEffect(("coupon_swap_pay_leg", "coupon_swap_receive_leg")),
                ),
            )
        )

    if grammar.target is not None:
        accumulators.append(
            AccumulatorSpec(
                accumulator_id="acc_target",
                source_component_ids=("coupon_swap_pay_leg", "coupon_swap_receive_leg"),
                metric=grammar.target.metric,
                side=grammar.target.accumulation_side,
                currency=grammar.target.accumulation_currency,
            )
        )
        conditions.append(TargetReachedCondition("cond_target_reached", "acc_target", ComparisonOp.GE, grammar.target.target_value))
        lifecycle_rules.append(
            TargetLifecycleRule(
                lifecycle_rule_id="life_target",
                accumulator_id="acc_target",
                target_condition_id="cond_target_reached",
                hit_cashflow_action=grammar.target.hit_action,
                deactivate_component_ids=("coupon_swap_pay_leg", "coupon_swap_receive_leg"),
            )
        )

    form = ContractFormV2(
        form_id=form_id,
        form_kind="COUPON_SWAP_RATIO_FORWARD_V2",
        parties=grammar.counterparties.both(),
        party_roles=(PartyRoleAssignment("client", client_id), PartyRoleAssignment("bank", bank_id)),
        references=(pair_ref,),
        observables=tuple(observables),
        observation_rules=tuple(observation_rules),
        conditions=tuple(conditions),
        components=tuple(components),
        determination_rules=tuple(determination_rules),
        accumulators=tuple(accumulators),
        lifecycle_rules=tuple(lifecycle_rules),
        tags={
            "grammar_kind": "COUPON_SWAP_RATIO_FORWARD_V2",
            "scheme": grammar.economic_terms.scheme.value,
            "same_economics_as": "FX_OPTION_PACKAGE_RATIO_FORWARD_V2",
            "quote_currency": grammar.quote_currency.value,
        },
    )
    form.validate()
    return BuiltRatioForwardContractV2(
        form=form,
        form_variant="COUPON_SWAP",
        pair=pair,
        base_currency=grammar.base_currency,
        quote_currency=grammar.quote_currency,
        client_party_id=client_id,
        bank_party_id=bank_id,
        period_specs=specs,
        payment_dates_by_component={"coupon_swap_pay_leg": specs[0].payment_date if specs else date.min, "coupon_swap_receive_leg": specs[0].payment_date if specs else date.min},
        wko=grammar.wko,
        target=grammar.target,
    )


def build_fx_option_package_ratio_forward_contract_v2(
    grammar: FxOptionPackageRatioForwardGrammarV2,
    form_id: str = "FORM-V2-FX-OPTION-PACKAGE-RATIO-FWD",
) -> BuiltRatioForwardContractV2:
    grammar.validate()
    client_id, bank_id = _client_and_bank_ids(grammar.counterparties)
    specs = expand_period_specs(grammar.schedule, grammar.economic_terms)
    pair = grammar.economic_terms.pair
    pair_ref = UnderlierRef(pair.symbol, "FX")
    settlement_ccy = grammar.settlement_currency or pair.quote_currency

    observables: list[ObservableRef] = [ObservableRef("obs_fx", pair_ref, ObservationKind.CLOSE, "FX spot/close for ratio forward")]
    observation_rules: list[ObservationRule] = [ObservationRule("obs_fixing", "obs_fx", grammar.schedule.fixing_schedule, ObservationStyle.BERMUDAN, ObservationKind.CLOSE)]
    conditions: list[ConditionType] = []
    components: list[ComponentType] = []
    determination_rules: list[DeterminationRuleType] = []
    lifecycle_rules: list[LifecycleRuleType] = []
    accumulators: list[AccumulatorSpec] = []
    payment_dates_by_component: dict[str, date] = {}

    if grammar.premium is not None and grammar.premium_payment_date is not None:
        components.append(PremiumTransfer("premium", client_id, bank_id, grammar.premium, grammar.premium_payment_date))

    for spec in specs:
        p = spec.period_index + 1
        call_id = f"period_{p}_call"
        put_id = f"period_{p}_put"
        call_q_rule = f"q_period_{p}_call_base"
        put_q_rule = f"q_period_{p}_put_base"
        determination_rules.extend([
            FixedQuantityRule(call_q_rule, spec.call_amount_base),
            FixedQuantityRule(put_q_rule, spec.put_amount_base),
        ])
        components.extend([
            FxOptionExerciseLeg(
                component_id=call_id,
                buyer_party_id=client_id,
                seller_party_id=bank_id,
                pair=pair,
                side=Side.BUY,
                option_type=OptionType.CALL,
                base_quantity_rule_id=call_q_rule,
                strike=spec.call_strike,
                expiry_date=spec.fixing_date,
                settlement_style=grammar.settlement_style,
                settlement_currency=settlement_ccy,
            ),
            FxOptionExerciseLeg(
                component_id=put_id,
                buyer_party_id=bank_id,
                seller_party_id=client_id,
                pair=pair,
                side=Side.SELL,
                option_type=OptionType.PUT,
                base_quantity_rule_id=put_q_rule,
                strike=spec.put_strike,
                expiry_date=spec.fixing_date,
                settlement_style=grammar.settlement_style,
                settlement_currency=settlement_ccy,
            ),
        ])
        payment_dates_by_component[call_id] = spec.payment_date
        payment_dates_by_component[put_id] = spec.payment_date

        if spec.sold_option_knock_in is not None:
            sold_id = put_id if spec.sold_option_selector is SoldOptionSelector.PUT else call_id
            obs_date = spec.ki_observation_date or spec.fixing_date
            obs_rule_id = f"obs_period_{p}_sold_ki"
            cond_id = f"cond_period_{p}_sold_ki_hit"
            observation_rules.append(ObservationRule(obs_rule_id, "obs_fx", DateListSchedule((obs_date,)), ObservationStyle.EUROPEAN, ObservationKind.CLOSE))
            conditions.append(BarrierCondition(cond_id, obs_rule_id, spec.sold_option_knock_in.direction, spec.sold_option_knock_in.barrier))
            # The sold option is represented as a component from the start, but its lifecycle can be tracked separately.
            lifecycle_rules.append(
                EventLifecycleRule(
                    lifecycle_rule_id=f"life_period_{p}_sold_ki",
                    trigger=Trigger(f"trigger_period_{p}_sold_ki", cond_id, DateListSchedule((obs_date,))),
                    effects=(SetStateEffect(f"period_{p}_sold_option_knocked_in", True), ActivateComponentsEffect((sold_id,))),
                )
            )

    if grammar.wko is not None:
        observation_rules.append(ObservationRule("obs_wko", "obs_fx", grammar.wko.observation_schedule, ObservationStyle.AMERICAN, ObservationKind.CLOSE))
        conditions.append(BarrierCondition("cond_wko_hit", "obs_wko", grammar.wko.direction, grammar.wko.barrier))
        affected: list[str] = []
        for spec in specs:
            if spec.period_index >= grammar.wko.affected_start_index:
                p = spec.period_index + 1
                affected.extend([f"period_{p}_call", f"period_{p}_put"])
        lifecycle_rules.append(
            EventLifecycleRule(
                lifecycle_rule_id="life_wko",
                trigger=Trigger("trigger_wko", "cond_wko_hit", grammar.wko.observation_schedule),
                effects=(SetStateEffect("window_knocked_out", True), DeactivateComponentsEffect(tuple(affected))),
            )
        )

    if grammar.target is not None:
        source_ids = tuple(cid for cid in payment_dates_by_component)
        accumulators.append(
            AccumulatorSpec(
                accumulator_id="acc_target",
                source_component_ids=source_ids,
                metric=grammar.target.metric,
                side=grammar.target.accumulation_side,
                currency=grammar.target.accumulation_currency,
            )
        )
        conditions.append(TargetReachedCondition("cond_target_reached", "acc_target", ComparisonOp.GE, grammar.target.target_value))
        lifecycle_rules.append(
            TargetLifecycleRule(
                lifecycle_rule_id="life_target",
                accumulator_id="acc_target",
                target_condition_id="cond_target_reached",
                hit_cashflow_action=grammar.target.hit_action,
                deactivate_component_ids=source_ids,
            )
        )

    form = ContractFormV2(
        form_id=form_id,
        form_kind="FX_OPTION_PACKAGE_RATIO_FORWARD_V2",
        parties=grammar.counterparties.both(),
        party_roles=(PartyRoleAssignment("client", client_id), PartyRoleAssignment("bank", bank_id)),
        references=(pair_ref,),
        observables=tuple(observables),
        observation_rules=tuple(observation_rules),
        conditions=tuple(conditions),
        components=tuple(components),
        determination_rules=tuple(determination_rules),
        accumulators=tuple(accumulators),
        lifecycle_rules=tuple(lifecycle_rules),
        tags={
            "grammar_kind": "FX_OPTION_PACKAGE_RATIO_FORWARD_V2",
            "scheme": grammar.economic_terms.scheme.value,
            "same_economics_as": "COUPON_SWAP_RATIO_FORWARD_V2",
            "quote_currency": pair.quote_currency.value,
            "payment_dates_by_component": ";".join(f"{cid}:{dt.isoformat()}" for cid, dt in sorted(payment_dates_by_component.items())),
        },
    )
    form.validate()
    return BuiltRatioForwardContractV2(
        form=form,
        form_variant="FX_OPTION_PACKAGE",
        pair=pair,
        base_currency=pair.base_currency,
        quote_currency=pair.quote_currency,
        client_party_id=client_id,
        bank_party_id=bank_id,
        period_specs=specs,
        payment_dates_by_component=payment_dates_by_component,
        wko=grammar.wko,
        target=grammar.target,
    )


# ---------------------------------------------------------------------------
# Series economics / simulation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PeriodEconomics:
    period_index: int
    fixing_date: date
    payment_date: date
    spot: Decimal
    sold_option_knocked_in: bool
    bought_side_quote_amount: Decimal
    sold_option_quote_amount: Decimal
    client_net_quote_amount: Decimal
    client_gain_amount_quote: Decimal
    client_loss_amount_quote: Decimal
    client_gain_points: Decimal
    client_loss_points: Decimal


@dataclass(frozen=True)
class SimulatedPeriodResult:
    period_index: int
    fixing_date: date
    payment_date: date
    active_before: bool
    sold_option_knocked_in: bool
    economics: PeriodEconomics
    wko_hit: bool
    target_metric_used: Optional[TargetMetric]
    target_increment_before_scaling: Decimal
    target_increment_applied: Decimal
    target_accumulation_after: Decimal
    exchange_scale: Decimal
    client_net_quote_exchanged: Decimal
    terminated_after: bool
    reason: str


@dataclass(frozen=True)
class SeriesSimulationResult:
    built: BuiltRatioForwardContractV2
    periods: tuple[SimulatedPeriodResult, ...]
    terminated: bool
    termination_period_index: Optional[int]
    final_target_accumulation: Decimal


def _barrier_hit(direction: BarrierDirection, value: Decimal, level: Decimal) -> bool:
    return value >= level if direction is BarrierDirection.UP else value <= level


def evaluate_period_economics(spec: RatioForwardPeriodSpec, spot: Decimal, *, sold_option_knocked_in: Optional[bool] = None) -> PeriodEconomics:
    if sold_option_knocked_in is None:
        if spec.sold_option_knock_in is None:
            sold_option_knocked_in = True
        else:
            sold_option_knocked_in = _barrier_hit(spec.sold_option_knock_in.direction, spot, spec.sold_option_knock_in.barrier)

    call_intrinsic = max(spot - spec.call_strike, ZERO)
    put_intrinsic = max(spec.put_strike - spot, ZERO)

    if spec.sold_option_selector is SoldOptionSelector.PUT:
        bought_quote = q(call_intrinsic * spec.call_amount_base)
        sold_quote = q(put_intrinsic * spec.put_amount_base) if sold_option_knocked_in else ZERO
        net = q(bought_quote - sold_quote)
        denom = max(spec.call_amount_base, ONE)
        gain_points = max((spec.call_amount_base / denom) * call_intrinsic - (spec.put_amount_base / denom) * (put_intrinsic if sold_option_knocked_in else ZERO), ZERO)
        loss_points = max((spec.put_amount_base / denom) * (put_intrinsic if sold_option_knocked_in else ZERO) - (spec.call_amount_base / denom) * call_intrinsic, ZERO)
    else:
        bought_quote = q(put_intrinsic * spec.put_amount_base)
        sold_quote = q(call_intrinsic * spec.call_amount_base) if sold_option_knocked_in else ZERO
        net = q(bought_quote - sold_quote)
        denom = max(spec.put_amount_base, ONE)
        gain_points = max((spec.put_amount_base / denom) * put_intrinsic - (spec.call_amount_base / denom) * (call_intrinsic if sold_option_knocked_in else ZERO), ZERO)
        loss_points = max((spec.call_amount_base / denom) * (call_intrinsic if sold_option_knocked_in else ZERO) - (spec.put_amount_base / denom) * put_intrinsic, ZERO)

    return PeriodEconomics(
        period_index=spec.period_index,
        fixing_date=spec.fixing_date,
        payment_date=spec.payment_date,
        spot=spot,
        sold_option_knocked_in=sold_option_knocked_in,
        bought_side_quote_amount=q(bought_quote),
        sold_option_quote_amount=q(sold_quote),
        client_net_quote_amount=q(net),
        client_gain_amount_quote=q(max(net, ZERO)),
        client_loss_amount_quote=q(max(-net, ZERO)),
        client_gain_points=q(gain_points),
        client_loss_points=q(loss_points),
    )


def _target_contribution(econ: PeriodEconomics, target: TargetConfig) -> Decimal:
    if target.metric is TargetMetric.AMOUNT:
        return econ.client_gain_amount_quote if target.accumulation_side is TargetAccumulationSide.CLIENT_GAIN else econ.client_loss_amount_quote
    if target.metric is TargetMetric.POINTS:
        return econ.client_gain_points if target.accumulation_side is TargetAccumulationSide.CLIENT_GAIN else econ.client_loss_points
    raise ValueError(target.metric)


def simulate_ratio_forward_series_v2(
    built: BuiltRatioForwardContractV2,
    spot_by_fixing_date: dict[date, Decimal],
    *,
    ki_observation_by_date: Optional[dict[date, Decimal]] = None,
    wko_observation_by_date: Optional[dict[date, Decimal]] = None,
) -> SeriesSimulationResult:
    periods: list[SimulatedPeriodResult] = []
    terminated = False
    termination_idx: Optional[int] = None
    accumulation = ZERO
    wko_effective_from: int | None = None
    ki_observation_by_date = ki_observation_by_date or {}
    wko_observation_by_date = wko_observation_by_date or {}

    for spec in built.period_specs:
        if wko_effective_from is not None and spec.period_index >= wko_effective_from:
            terminated = True
            if termination_idx is None:
                termination_idx = spec.period_index
        active_before = not terminated
        wko_hit = False
        if built.wko is not None and spec.period_index >= built.wko.monitoring_start_index and wko_effective_from is None:
            obs_date = spec.fixing_date
            if isinstance(built.wko.observation_schedule, DateListSchedule):
                obs_dates = built.wko.observation_schedule.dates
                if spec.fixing_date not in obs_dates and spec.payment_date in obs_dates:
                    obs_date = spec.payment_date
            obs_val = wko_observation_by_date.get(obs_date)
            if obs_val is not None:
                wko_hit = _barrier_hit(built.wko.direction, obs_val, built.wko.barrier)

        sold_ki_hit = True
        if spec.sold_option_knock_in is not None:
            obs_date = spec.ki_observation_date or spec.fixing_date
            obs_val = ki_observation_by_date.get(obs_date, spot_by_fixing_date.get(spec.fixing_date))
            if obs_val is None:
                raise KeyError(f"Missing KI observation for {obs_date}")
            sold_ki_hit = _barrier_hit(spec.sold_option_knock_in.direction, obs_val, spec.sold_option_knock_in.barrier)

        spot = spot_by_fixing_date.get(spec.fixing_date)
        if spot is None:
            raise KeyError(f"Missing fixing spot for {spec.fixing_date}")
        econ = evaluate_period_economics(spec, spot, sold_option_knocked_in=sold_ki_hit)

        reason = "normal"
        exchange_scale = ONE
        increment_before = ZERO
        increment_applied = ZERO
        target_metric: TargetMetric | None = None

        if wko_hit and built.wko is not None:
            wko_effective_from = built.wko.affected_start_index
            if spec.period_index >= built.wko.affected_start_index and active_before:
                terminated = True
                termination_idx = spec.period_index
                reason = "wko_hit_current_and_future_cancelled"
                exchange_scale = ZERO

        if not active_before:
            reason = "already_terminated"
            exchange_scale = ZERO

        if active_before and not terminated and built.target is not None:
            target_metric = built.target.metric
            increment_before = _target_contribution(econ, built.target)
            remaining = built.target.target_value - accumulation
            if increment_before <= ZERO:
                increment_applied = ZERO
            elif increment_before < remaining:
                increment_applied = increment_before
                accumulation += increment_applied
            else:
                if built.target.hit_action is TargetHitAction.KNOCK_OUT_INCLUDING_HIT_CF:
                    exchange_scale = ZERO
                    increment_applied = ZERO
                    accumulation = built.target.target_value
                    terminated = True
                    termination_idx = spec.period_index
                    reason = "target_hit_cancel_hit_cf_and_stop"
                elif built.target.hit_action is TargetHitAction.PARTIAL_HIT_CF_TO_TARGET_THEN_STOP:
                    exchange_scale = q(remaining / increment_before) if increment_before > ZERO else ZERO
                    increment_applied = remaining
                    accumulation = built.target.target_value
                    terminated = True
                    termination_idx = spec.period_index
                    reason = "target_hit_partial_cf_then_stop"
                elif built.target.hit_action is TargetHitAction.FULL_HIT_CF_THEN_STOP:
                    exchange_scale = ONE
                    increment_applied = increment_before
                    accumulation += increment_applied
                    terminated = True
                    termination_idx = spec.period_index
                    reason = "target_hit_full_cf_then_stop"
                else:
                    raise ValueError(built.target.hit_action)

        net_exchanged = q(econ.client_net_quote_amount * exchange_scale)
        periods.append(
            SimulatedPeriodResult(
                period_index=spec.period_index,
                fixing_date=spec.fixing_date,
                payment_date=spec.payment_date,
                active_before=active_before,
                sold_option_knocked_in=sold_ki_hit,
                economics=econ,
                wko_hit=wko_hit,
                target_metric_used=target_metric,
                target_increment_before_scaling=q(increment_before),
                target_increment_applied=q(increment_applied),
                target_accumulation_after=q(accumulation),
                exchange_scale=q(exchange_scale),
                client_net_quote_exchanged=net_exchanged,
                terminated_after=terminated,
                reason=reason,
            )
        )

    return SeriesSimulationResult(built, tuple(periods), terminated, termination_idx, q(accumulation))


# ---------------------------------------------------------------------------
# Representative examples
# ---------------------------------------------------------------------------

def build_example_coupon_swap_gap_wko_v2() -> BuiltRatioForwardContractV2:
    cp = CounterpartySpec(PartyRef("BANK", "Bank"), PartyRef("CLIENT", "Client"))
    pair = FxPair(Currency.USD, Currency.JPY)
    schedule = RatioForwardSeriesSchedule(
        fixing_schedule=DateListSchedule((date(2026, 1, 28), date(2026, 2, 25), date(2026, 3, 25), date(2026, 4, 29))),
        payment_schedule=DateListSchedule((date(2026, 1, 30), date(2026, 2, 27), date(2026, 3, 27), date(2026, 4, 30))),
        accrual_start_schedule=DateListSchedule((date(2025, 12, 30), date(2026, 1, 30), date(2026, 2, 27), date(2026, 3, 27))),
        accrual_end_schedule=DateListSchedule((date(2026, 1, 30), date(2026, 2, 27), date(2026, 3, 27), date(2026, 4, 30))),
    )
    terms = RatioForwardSeriesEconomicTerms(
        pair=pair,
        scheme=RatioForwardScheme.GAP,
        amount_spec=OptionAmountSpec(D("1000000"), D("1.0"), D("2.0")),
        call_strike=D("148.00"),
        put_strike=D("152.00"),
        sold_option_selector=SoldOptionSelector.PUT,
        sold_option_knock_in=EuropeanKnockInSpec(D("158.00"), BarrierDirection.UP),
    )
    grammar = CouponSwapRatioForwardGrammarV2(
        counterparties=cp,
        schedule=schedule,
        economic_terms=terms,
        quote_currency=Currency.JPY,
        base_currency=Currency.USD,
        pay_leg_role="CLIENT_PAYS_BASE",
        wko=WKOConfig(D("160.00"), BarrierDirection.UP, schedule.fixing_schedule, monitoring_start_index=1, affected_start_index=2),
    )
    return build_coupon_swap_ratio_forward_contract_v2(grammar, "EXAMPLE-V2-COUPON-SWAP-GAP-WKO")


def build_example_fx_option_package_two_stage_target_v2() -> BuiltRatioForwardContractV2:
    cp = CounterpartySpec(PartyRef("BANK", "Bank"), PartyRef("CLIENT", "Client"))
    pair = FxPair(Currency.USD, Currency.JPY)
    schedule = RatioForwardSeriesSchedule(
        fixing_schedule=DateListSchedule((date(2026, 1, 28), date(2026, 2, 25), date(2026, 3, 25), date(2026, 4, 29))),
        payment_schedule=DateListSchedule((date(2026, 1, 30), date(2026, 2, 27), date(2026, 3, 27), date(2026, 4, 30))),
    )
    terms = RatioForwardSeriesEconomicTerms(
        pair=pair,
        scheme=RatioForwardScheme.TWO_STAGE,
        amount_spec=OptionAmountSpec(D("1000000"), D("1.0"), D("2.0")),
        call_strike=D("150.00"),
        put_strike=D("150.00"),
        two_stage=TwoStageStrikeSpec(2, D("150.00"), D("153.00")),
    )
    grammar = FxOptionPackageRatioForwardGrammarV2(
        counterparties=cp,
        schedule=schedule,
        economic_terms=terms,
        settlement_style=SettlementStyle.CASH,
        settlement_currency=Currency.JPY,
        premium=Money(D("2500000"), Currency.JPY),
        premium_payment_date=date(2025, 12, 30),
        target=TargetConfig(
            metric=TargetMetric.AMOUNT,
            target_value=D("10000000"),
            accumulation_side=TargetAccumulationSide.CLIENT_GAIN,
            hit_action=TargetHitAction.FULL_HIT_CF_THEN_STOP,
            accumulation_currency=Currency.JPY,
        ),
    )
    return build_fx_option_package_ratio_forward_contract_v2(grammar, "EXAMPLE-V2-FX-OPTION-PACKAGE-TWO-STAGE-TARGET")


if __name__ == "__main__":
    built = build_example_coupon_swap_gap_wko_v2()
    result = simulate_ratio_forward_series_v2(
        built,
        spot_by_fixing_date={
            built.period_specs[0].fixing_date: D("149"),
            built.period_specs[1].fixing_date: D("161"),
            built.period_specs[2].fixing_date: D("155"),
            built.period_specs[3].fixing_date: D("150"),
        },
        ki_observation_by_date={
            built.period_specs[0].ki_observation_date: D("149"),
            built.period_specs[1].ki_observation_date: D("161"),
            built.period_specs[2].ki_observation_date: D("155"),
            built.period_specs[3].ki_observation_date: D("150"),
        },
        wko_observation_by_date={built.period_specs[1].fixing_date: D("161")},
    )
    print(built.form.form_kind, result.terminated, result.termination_period_index)

    built2 = build_example_fx_option_package_two_stage_target_v2()
    result2 = simulate_ratio_forward_series_v2(
        built2,
        spot_by_fixing_date={
            built2.period_specs[0].fixing_date: D("153"),
            built2.period_specs[1].fixing_date: D("154"),
            built2.period_specs[2].fixing_date: D("156"),
            built2.period_specs[3].fixing_date: D("158"),
        },
    )
    print(built2.form.form_kind, result2.terminated, result2.termination_period_index)
