"""
ratio_forward_product_grammars_v2_2_full.py

Ratio-forward / TARF product grammar on top of contract_model_v2_2_full.

v2.2 focus:
- Target is no longer TargetMetric + ClientGain/ClientLoss.
- Target accumulation uses AccumulationValueRule:
    * AmountAccumulationValueRule wraps a general AmountRule.
    * FxPipSpreadAccumulationValueRule directly models pips/points.
    * CountAccumulationValueRule directly models count TARF.
    * PackageNetAmountAccumulationValueRule models package-level net payoff.
- ContractPeriod / PeriodComponentGroup are first-class. A period is a semantic
  economic episode, not a guarantee of a single fixing date.
- KO/deactivation target is expressed with ComponentSelector.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional, Literal

from contract_model_v2_2_full import *


class RatioForwardScheme(str, Enum):
    NORMAL = "NORMAL"
    GAP = "GAP"
    RANGE_GAP = "RANGE_GAP"
    COLLAR = "COLLAR"
    TWO_STAGE = "TWO_STAGE"


class SoldOptionSelector(str, Enum):
    PUT = "PUT"
    CALL = "CALL"


class TargetAccumulationBasis(str, Enum):
    PACKAGE_NET_AMOUNT = "PACKAGE_NET_AMOUNT"
    FX_PIPS = "FX_PIPS"
    COUNT = "COUNT"


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
    basis: TargetAccumulationBasis
    target_value: Decimal
    selection: MetricSelection
    hit_action: TargetHitAction
    accumulation_currency: Optional[Currency] = None
    pip_size: Optional[Decimal] = None
    spread_direction: SpreadDirection = SpreadDirection.LEFT_MINUS_RIGHT
    affected_start_index: int | None = None
    affected_end_index: int | None = None
    count_condition_level: Decimal | None = None


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
class CouponSwapRatioForwardGrammarV22:
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


@dataclass(frozen=True)
class FxOptionPackageRatioForwardGrammarV22:
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
        if (self.premium is None) ^ (self.premium_payment_date is None):
            raise ValueError("premium and premium_payment_date must be given together")


@dataclass(frozen=True)
class BuiltRatioForwardContractV22:
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


def _schedule_dates(schedule_like: ScheduleRefLike) -> tuple[date, ...]:
    if isinstance(schedule_like, DateListSchedule):
        return schedule_like.sorted_dates()
    raise TypeError("ratio-forward v2.2 builders expect materialized DateListSchedule inputs")


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
    accrual_starts = tuple(None for _ in range(count)) if schedule.accrual_start_schedule is None else tuple(_schedule_dates(schedule.accrual_start_schedule)[i] if i < len(_schedule_dates(schedule.accrual_start_schedule)) else None for i in range(count))
    accrual_ends = tuple(None for _ in range(count)) if schedule.accrual_end_schedule is None else tuple(_schedule_dates(schedule.accrual_end_schedule)[i] if i < len(_schedule_dates(schedule.accrual_end_schedule)) else None for i in range(count))
    if terms.sold_option_knock_in is None:
        ki_dates = tuple(None for _ in range(count))
    else:
        raw = _schedule_dates(_default_ki_schedule(schedule, terms.sold_option_knock_in))
        ki_dates = tuple(raw[i] if i < len(raw) else None for i in range(count))

    out = []
    for i in range(count):
        if terms.scheme is RatioForwardScheme.TWO_STAGE:
            assert terms.two_stage is not None
            strike = terms.two_stage.stage1_strike if i < terms.two_stage.stage_switch_index else terms.two_stage.stage2_strike
            call_strike = put_strike = strike
        else:
            call_strike, put_strike = terms.call_strike, terms.put_strike
        out.append(RatioForwardPeriodSpec(
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
        ))
    return tuple(out)


def _make_periods_and_bindings(specs: tuple[RatioForwardPeriodSpec, ...], period_kind: str) -> tuple[tuple[ContractPeriod, ...], tuple[PeriodDateBinding, ...]]:
    periods = []
    bindings = []
    for spec in specs:
        pid = f"period_{spec.period_index + 1}"
        periods.append(ContractPeriod(pid, spec.period_index, period_kind))
        bindings.append(PeriodDateBinding(pid, pid, "GROUP", DateRole.FIXING, "period_fx_fixing", spec.fixing_date))
        bindings.append(PeriodDateBinding(pid, pid, "GROUP", DateRole.PAYMENT, "period_payment", spec.payment_date))
        if spec.ki_observation_date is not None:
            bindings.append(PeriodDateBinding(pid, pid, "GROUP", DateRole.OBSERVATION, "period_sold_side_ki_observation", spec.ki_observation_date))
        if spec.accrual_start_date is not None:
            bindings.append(PeriodDateBinding(pid, pid, "GROUP", DateRole.ACCRUAL_START, "period_accrual_start", spec.accrual_start_date))
        if spec.accrual_end_date is not None:
            bindings.append(PeriodDateBinding(pid, pid, "GROUP", DateRole.ACCRUAL_END, "period_accrual_end", spec.accrual_end_date))
    return tuple(periods), tuple(bindings)


def _target_selector(group_kind: str, target: TargetConfig, fallback_ids: tuple[str, ...]) -> ComponentSelectorType:
    if target.affected_start_index is not None or target.affected_end_index is not None:
        return GroupComponentSelector(group_kind=group_kind, start_period_index=target.affected_start_index, end_period_index=target.affected_end_index)
    return ExplicitComponentSelector(fallback_ids)


def _build_target_objects(
    *,
    target: TargetConfig,
    pair: FxPair,
    fx_observation_rule: FxObservationRule,
    reference_strike: Decimal,
    group_kind: str,
    sign_convention: AmountSignConventionType,
    deactivate_fallback_ids: tuple[str, ...],
) -> tuple[tuple[AccumulatorSpec, ...], tuple[ConditionType, ...], tuple[LifecycleRuleType, ...]]:
    if target.basis is TargetAccumulationBasis.PACKAGE_NET_AMOUNT:
        unit = AccumulationUnit.currency_unit(target.accumulation_currency or pair.quote_currency)
        value_rule = PackageNetAmountAccumulationValueRule(
            group_selector=GroupComponentSelector(group_kind=group_kind),
            sign_convention=sign_convention,
            currency=target.accumulation_currency or pair.quote_currency,
        )
    elif target.basis is TargetAccumulationBasis.FX_PIPS:
        pip_size = target.pip_size or (D("0.01") if pair.quote_currency is Currency.JPY else D("0.0001"))
        unit = AccumulationUnit.fx_pip(pair, pip_size)
        value_rule = FxPipSpreadAccumulationValueRule(
            observed_fx=fx_observation_rule,
            reference=reference_strike,
            direction=target.spread_direction,
            pip_size=pip_size,
        )
    elif target.basis is TargetAccumulationBasis.COUNT:
        level = target.count_condition_level if target.count_condition_level is not None else reference_strike
        obs_condition = BarrierCondition("cond_count_target_event", "obs_fixing", BarrierDirection.UP, level)
        unit = AccumulationUnit.count("hit_count")
        value_rule = CountAccumulationValueRule(condition=obs_condition)
    else:
        raise ValueError(target.basis)

    accumulator = AccumulatorSpec("acc_target", value_rule=value_rule, selection=target.selection, unit=unit)
    condition = TargetReachedCondition("cond_target_reached", "acc_target", ComparisonOp.GE, target.target_value)
    selector = _target_selector(group_kind, target, deactivate_fallback_ids)
    lifecycle = TargetLifecycleRule(
        lifecycle_rule_id="life_target",
        accumulator_id="acc_target",
        target_condition_id="cond_target_reached",
        hit_cashflow_action=target.hit_action,
        effects=(DeactivateComponentsEffect(selector),),
    )
    conditions: tuple[ConditionType, ...]
    if target.basis is TargetAccumulationBasis.COUNT:
        conditions = (value_rule.condition, condition)  # type: ignore[attr-defined]
    else:
        conditions = (condition,)
    return (accumulator,), conditions, (lifecycle,)


def build_coupon_swap_ratio_forward_contract_v2_2(
    grammar: CouponSwapRatioForwardGrammarV22,
    form_id: str = "FORM-V2-2-COUPON-SWAP-RATIO-FWD",
) -> BuiltRatioForwardContractV22:
    grammar.validate()
    client_id, bank_id = _client_and_bank_ids(grammar.counterparties)
    specs = expand_period_specs(grammar.schedule, grammar.economic_terms)
    pair = grammar.economic_terms.pair
    pair_ref = UnderlierRef(pair.symbol, "FX")
    pay_base = grammar.pay_leg_role == "CLIENT_PAYS_BASE"

    pay_leg = CouponStreamLeg(
        "coupon_swap_pay_leg",
        client_id if pay_base else bank_id,
        bank_id if pay_base else client_id,
        pair_ref,
        grammar.schedule.payment_schedule,
        AmountBasedCouponCalculation("amount_pay_leg"),
        grammar.base_currency if pay_base else grammar.quote_currency,
    )
    recv_leg = CouponStreamLeg(
        "coupon_swap_receive_leg",
        bank_id if pay_base else client_id,
        client_id if pay_base else bank_id,
        pair_ref,
        grammar.schedule.payment_schedule,
        AmountBasedCouponCalculation("amount_receive_leg"),
        grammar.quote_currency if pay_base else grammar.base_currency,
    )

    observables = [ObservableRef("obs_fx", pair_ref, ObservationKind.CLOSE)]
    observation_rules = [ObservationRule("obs_fixing", "obs_fx", grammar.schedule.fixing_schedule, ObservationStyle.BERMUDAN, ObservationKind.CLOSE)]
    fx_obs_direct = FxObservationRule(FxObservable(pair), grammar.schedule.fixing_schedule, ObservationStyle.BERMUDAN, ObservationKind.SPOT)

    conditions: list[ConditionType] = []
    determination_rules: list[DeterminationRuleType] = [
        FixedQuantityRule("q_call_amount_base", grammar.economic_terms.amount_spec.call_amount_base),
        FixedQuantityRule("q_put_amount_base", grammar.economic_terms.amount_spec.put_amount_base),
    ]

    sold_condition_id: str | None = None
    if grammar.economic_terms.sold_option_knock_in is not None:
        ki_rule_id = "obs_sold_side_ki_for_coupon_determination"
        ki_schedule = _default_ki_schedule(grammar.schedule, grammar.economic_terms.sold_option_knock_in)
        observation_rules.append(ObservationRule(ki_rule_id, "obs_fx", ki_schedule, ObservationStyle.BERMUDAN, ObservationKind.CLOSE))
        sold_condition_id = "cond_sold_side_ki_for_coupon_determination"
        conditions.append(BarrierCondition(sold_condition_id, ki_rule_id, grammar.economic_terms.sold_option_knock_in.direction, grammar.economic_terms.sold_option_knock_in.barrier))

    determination_rules.extend([
        RatioForwardCouponAmountRule("amount_pay_leg", pair, grammar.economic_terms.scheme.value, "BASE_DELIVERY" if pay_base else "QUOTE_DELIVERY", "q_call_amount_base", "q_put_amount_base", grammar.economic_terms.sold_option_selector.value, sold_condition_id),
        RatioForwardCouponAmountRule("amount_receive_leg", pair, grammar.economic_terms.scheme.value, "QUOTE_DELIVERY" if pay_base else "BASE_DELIVERY", "q_call_amount_base", "q_put_amount_base", grammar.economic_terms.sold_option_selector.value, sold_condition_id),
    ])

    periods, date_bindings = _make_periods_and_bindings(specs, "COUPON_SWAP_PERIOD")
    groups = tuple(PeriodComponentGroup(f"period_{s.period_index+1}_coupon_swap_group", f"period_{s.period_index+1}", "COUPON_SWAP_PERIOD", ("coupon_swap_pay_leg", "coupon_swap_receive_leg"), {"coupon_swap_pay_leg": "pay_leg", "coupon_swap_receive_leg": "receive_leg"}) for s in specs)

    lifecycle_rules: list[LifecycleRuleType] = []
    accumulators: list[AccumulatorSpec] = []
    if grammar.wko is not None:
        observation_rules.append(ObservationRule("obs_wko", "obs_fx", grammar.wko.observation_schedule, ObservationStyle.BERMUDAN, ObservationKind.CLOSE))
        conditions.append(BarrierCondition("cond_wko_hit", "obs_wko", grammar.wko.direction, grammar.wko.barrier))
        lifecycle_rules.append(EventLifecycleRule("life_wko", Trigger("trigger_wko", "cond_wko_hit", grammar.wko.observation_schedule), (DeactivateComponentsEffect(GroupComponentSelector("COUPON_SWAP_PERIOD", grammar.wko.affected_start_index, None)), SetStateEffect("window_knocked_out", True))))

    if grammar.target is not None:
        accs, conds, lifes = _build_target_objects(
            target=grammar.target,
            pair=pair,
            fx_observation_rule=fx_obs_direct,
            reference_strike=grammar.economic_terms.call_strike,
            group_kind="COUPON_SWAP_PERIOD",
            sign_convention=SignedByParty(client_id),
            deactivate_fallback_ids=("coupon_swap_pay_leg", "coupon_swap_receive_leg"),
        )
        accumulators.extend(accs)
        conditions.extend(conds)
        lifecycle_rules.extend(lifes)

    form = ContractFormV2(
        form_id=form_id,
        form_kind="COUPON_SWAP_RATIO_FORWARD_V2_2",
        parties=grammar.counterparties.both(),
        party_roles=(PartyRoleAssignment("client", client_id), PartyRoleAssignment("bank", bank_id)),
        references=(pair_ref,),
        periods=periods,
        period_date_bindings=date_bindings,
        period_component_groups=groups,
        observables=tuple(observables),
        observation_rules=tuple(observation_rules),
        conditions=tuple(conditions),
        components=(pay_leg, recv_leg),
        determination_rules=tuple(determination_rules),
        accumulators=tuple(accumulators),
        lifecycle_rules=tuple(lifecycle_rules),
        tags={"grammar_kind": "COUPON_SWAP_RATIO_FORWARD_V2_2", "scheme": grammar.economic_terms.scheme.value},
    )
    form.validate()
    return BuiltRatioForwardContractV22(form, "COUPON_SWAP", pair, grammar.base_currency, grammar.quote_currency, client_id, bank_id, specs, {"coupon_swap_pay_leg": specs[0].payment_date if specs else date.min, "coupon_swap_receive_leg": specs[0].payment_date if specs else date.min}, grammar.wko, grammar.target)


def build_fx_option_package_ratio_forward_contract_v2_2(
    grammar: FxOptionPackageRatioForwardGrammarV22,
    form_id: str = "FORM-V2-2-FX-OPTION-PACKAGE-RATIO-FWD",
) -> BuiltRatioForwardContractV22:
    grammar.validate()
    client_id, bank_id = _client_and_bank_ids(grammar.counterparties)
    specs = expand_period_specs(grammar.schedule, grammar.economic_terms)
    pair = grammar.economic_terms.pair
    pair_ref = UnderlierRef(pair.symbol, "FX")
    settlement_ccy = grammar.settlement_currency or pair.quote_currency

    observables = [ObservableRef("obs_fx", pair_ref, ObservationKind.CLOSE)]
    observation_rules = [ObservationRule("obs_fixing", "obs_fx", grammar.schedule.fixing_schedule, ObservationStyle.BERMUDAN, ObservationKind.CLOSE)]
    fx_obs_direct = FxObservationRule(FxObservable(pair), grammar.schedule.fixing_schedule, ObservationStyle.BERMUDAN, ObservationKind.SPOT)

    components: list[ComponentType] = []
    determination_rules: list[DeterminationRuleType] = []
    conditions: list[ConditionType] = []
    lifecycle_rules: list[LifecycleRuleType] = []
    payment_dates_by_component: dict[str, date] = {}

    if grammar.premium is not None and grammar.premium_payment_date is not None:
        components.append(PremiumTransfer("premium", client_id, bank_id, grammar.premium, grammar.premium_payment_date))

    group_list: list[PeriodComponentGroup] = []
    for spec in specs:
        i = spec.period_index + 1
        call_id = f"period_{i}_call"
        put_id = f"period_{i}_put"
        q_call = f"q_period_{i}_call"
        q_put = f"q_period_{i}_put"
        determination_rules.append(FixedQuantityRule(q_call, spec.call_amount_base))
        determination_rules.append(FixedQuantityRule(q_put, spec.put_amount_base))
        components.append(FxOptionExerciseLeg(call_id, client_id, bank_id, pair, Side.BUY, OptionType.CALL, q_call, spec.call_strike, spec.fixing_date, grammar.settlement_style, settlement_ccy))
        components.append(FxOptionExerciseLeg(put_id, bank_id, client_id, pair, Side.SELL, OptionType.PUT, q_put, spec.put_strike, spec.fixing_date, grammar.settlement_style, settlement_ccy))
        payment_dates_by_component[call_id] = spec.payment_date
        payment_dates_by_component[put_id] = spec.payment_date
        group_list.append(PeriodComponentGroup(f"period_{i}_option_package", f"period_{i}", "FX_OPTION_PACKAGE", (call_id, put_id), {call_id: "long_call", put_id: "short_put"}))
        if spec.sold_option_knock_in is not None:
            sold_leg_id = put_id if spec.sold_option_selector is SoldOptionSelector.PUT else call_id
            obs_date = spec.ki_observation_date or spec.fixing_date
            obs_rule_id = f"obs_period_{i}_sold_ki"
            observation_rules.append(ObservationRule(obs_rule_id, "obs_fx", DateListSchedule((obs_date,)), ObservationStyle.EUROPEAN, ObservationKind.CLOSE))
            cond_id = f"cond_period_{i}_sold_ki"
            conditions.append(BarrierCondition(cond_id, obs_rule_id, spec.sold_option_knock_in.direction, spec.sold_option_knock_in.barrier))
            lifecycle_rules.append(EventLifecycleRule(f"life_period_{i}_sold_ki", Trigger(f"trigger_period_{i}_sold_ki", cond_id), (ActivateComponentsEffect(ExplicitComponentSelector((sold_leg_id,))),)))

    periods, date_bindings = _make_periods_and_bindings(specs, "FX_OPTION_PACKAGE_PERIOD")

    if grammar.wko is not None:
        observation_rules.append(ObservationRule("obs_wko", "obs_fx", grammar.wko.observation_schedule, ObservationStyle.BERMUDAN, ObservationKind.CLOSE))
        conditions.append(BarrierCondition("cond_wko_hit", "obs_wko", grammar.wko.direction, grammar.wko.barrier))
        lifecycle_rules.append(EventLifecycleRule("life_wko", Trigger("trigger_wko", "cond_wko_hit", grammar.wko.observation_schedule), (DeactivateComponentsEffect(GroupComponentSelector("FX_OPTION_PACKAGE", grammar.wko.affected_start_index, None)), SetStateEffect("window_knocked_out", True))))

    accumulators: list[AccumulatorSpec] = []
    if grammar.target is not None:
        accs, conds, lifes = _build_target_objects(
            target=grammar.target,
            pair=pair,
            fx_observation_rule=fx_obs_direct,
            reference_strike=grammar.economic_terms.call_strike,
            group_kind="FX_OPTION_PACKAGE",
            sign_convention=SignedByParty(client_id),
            deactivate_fallback_ids=tuple(payment_dates_by_component),
        )
        accumulators.extend(accs)
        conditions.extend(conds)
        lifecycle_rules.extend(lifes)

    form = ContractFormV2(
        form_id=form_id,
        form_kind="FX_OPTION_PACKAGE_RATIO_FORWARD_V2_2",
        parties=grammar.counterparties.both(),
        party_roles=(PartyRoleAssignment("client", client_id), PartyRoleAssignment("bank", bank_id)),
        references=(pair_ref,),
        periods=periods,
        period_date_bindings=date_bindings,
        period_component_groups=tuple(group_list),
        observables=tuple(observables),
        observation_rules=tuple(observation_rules),
        conditions=tuple(conditions),
        components=tuple(components),
        determination_rules=tuple(determination_rules),
        accumulators=tuple(accumulators),
        lifecycle_rules=tuple(lifecycle_rules),
        tags={"grammar_kind": "FX_OPTION_PACKAGE_RATIO_FORWARD_V2_2", "scheme": grammar.economic_terms.scheme.value},
    )
    form.validate()
    return BuiltRatioForwardContractV22(form, "FX_OPTION_PACKAGE", pair, pair.base_currency, pair.quote_currency, client_id, bank_id, specs, payment_dates_by_component, grammar.wko, grammar.target)


# ---------------------------------------------------------------------------
# Simplified series simulation for examples
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PeriodEconomics:
    period_index: int
    fixing_date: date
    payment_date: date
    spot: Decimal
    sold_option_knocked_in: bool
    client_net_quote_amount: Decimal
    client_gain_amount_quote: Decimal
    client_loss_amount_quote: Decimal
    client_gain_pips: Decimal
    client_loss_pips: Decimal


@dataclass(frozen=True)
class SimulatedPeriodResult:
    period_index: int
    active_before: bool
    economics: PeriodEconomics
    target_increment_applied: Decimal
    target_accumulation_after: Decimal
    exchange_scale: Decimal
    terminated_after: bool
    reason: str


@dataclass(frozen=True)
class SeriesSimulationResult:
    built: BuiltRatioForwardContractV22
    periods: tuple[SimulatedPeriodResult, ...]
    terminated: bool
    termination_period_index: Optional[int]
    final_target_accumulation: Decimal


def _barrier_hit(direction: BarrierDirection, value: Decimal, level: Decimal) -> bool:
    return value >= level if direction is BarrierDirection.UP else value <= level


def evaluate_period_economics(spec: RatioForwardPeriodSpec, spot: Decimal, *, sold_option_knocked_in: Optional[bool] = None) -> PeriodEconomics:
    if sold_option_knocked_in is None:
        sold_option_knocked_in = True if spec.sold_option_knock_in is None else _barrier_hit(spec.sold_option_knock_in.direction, spot, spec.sold_option_knock_in.barrier)
    call_intrinsic = max(spot - spec.call_strike, ZERO)
    put_intrinsic = max(spec.put_strike - spot, ZERO)
    if spec.sold_option_selector is SoldOptionSelector.PUT:
        net = q(call_intrinsic * spec.call_amount_base - ((put_intrinsic * spec.put_amount_base) if sold_option_knocked_in else ZERO))
    else:
        net = q(put_intrinsic * spec.put_amount_base - ((call_intrinsic * spec.call_amount_base) if sold_option_knocked_in else ZERO))
    pip_size = D("0.01")
    pip_spread = (spot - spec.call_strike) / pip_size
    return PeriodEconomics(spec.period_index, spec.fixing_date, spec.payment_date, spot, sold_option_knocked_in, q(net), q(max(net, ZERO)), q(max(-net, ZERO)), q(max(pip_spread, ZERO)), q(max(-pip_spread, ZERO)))


def _target_increment(econ: PeriodEconomics, target: TargetConfig) -> Decimal:
    if target.basis is TargetAccumulationBasis.PACKAGE_NET_AMOUNT:
        raw = econ.client_net_quote_amount
    elif target.basis is TargetAccumulationBasis.FX_PIPS:
        pip_size = target.pip_size or D("0.01")
        raw = (econ.spot - D("0")) / pip_size  # replaced below using economics pips
        if target.spread_direction is SpreadDirection.LEFT_MINUS_RIGHT:
            raw = econ.client_gain_pips - econ.client_loss_pips
        else:
            raw = econ.client_loss_pips - econ.client_gain_pips
    elif target.basis is TargetAccumulationBasis.COUNT:
        raw = ONE if (target.count_condition_level is None or econ.spot >= target.count_condition_level) else ZERO
    else:
        raise ValueError(target.basis)

    if target.selection is MetricSelection.POSITIVE_PART:
        return max(raw, ZERO)
    if target.selection is MetricSelection.NEGATIVE_PART:
        return max(-raw, ZERO)
    if target.selection is MetricSelection.SIGNED:
        return raw
    if target.selection is MetricSelection.ABSOLUTE:
        return abs(raw)
    raise ValueError(target.selection)


def simulate_ratio_forward_series_v2_2(
    built: BuiltRatioForwardContractV22,
    spot_by_fixing_date: dict[date, Decimal],
    *,
    ki_observation_by_date: Optional[dict[date, Decimal]] = None,
) -> SeriesSimulationResult:
    periods: list[SimulatedPeriodResult] = []
    terminated = False
    termination_idx = None
    accumulation = ZERO
    ki_observation_by_date = ki_observation_by_date or {}

    for spec in built.period_specs:
        active_before = not terminated
        sold_ki_hit = True
        if spec.sold_option_knock_in is not None:
            obs_date = spec.ki_observation_date or spec.fixing_date
            obs_val = ki_observation_by_date.get(obs_date, spot_by_fixing_date.get(spec.fixing_date))
            if obs_val is None:
                raise KeyError(f"Missing KI observation for {obs_date}")
            sold_ki_hit = _barrier_hit(spec.sold_option_knock_in.direction, obs_val, spec.sold_option_knock_in.barrier)
        spot = spot_by_fixing_date[spec.fixing_date]
        econ = evaluate_period_economics(spec, spot, sold_option_knocked_in=sold_ki_hit)

        reason = "normal"
        exchange_scale = ONE
        increment_applied = ZERO
        if active_before and built.target is not None:
            inc = _target_increment(econ, built.target)
            remaining = built.target.target_value - accumulation
            if inc <= ZERO:
                increment_applied = ZERO
            elif inc < remaining:
                increment_applied = inc
                accumulation += inc
            else:
                if built.target.hit_action is TargetHitAction.KNOCK_OUT_INCLUDING_HIT_CF:
                    exchange_scale = ZERO
                    accumulation = built.target.target_value
                    terminated = True
                    termination_idx = spec.period_index
                    reason = "target_hit_cancel_hit_cf_and_stop"
                elif built.target.hit_action is TargetHitAction.PARTIAL_HIT_CF_TO_TARGET_THEN_STOP:
                    exchange_scale = q(remaining / inc) if inc > ZERO else ZERO
                    increment_applied = remaining
                    accumulation = built.target.target_value
                    terminated = True
                    termination_idx = spec.period_index
                    reason = "target_hit_partial_cf_then_stop"
                elif built.target.hit_action is TargetHitAction.FULL_HIT_CF_THEN_STOP:
                    increment_applied = inc
                    accumulation += inc
                    terminated = True
                    termination_idx = spec.period_index
                    reason = "target_hit_full_cf_then_stop"
                else:
                    raise ValueError(built.target.hit_action)
        elif not active_before:
            reason = "already_terminated"

        periods.append(SimulatedPeriodResult(spec.period_index, active_before, econ, q(increment_applied), q(accumulation), q(exchange_scale), terminated, reason))

    return SeriesSimulationResult(built, tuple(periods), terminated, termination_idx, q(accumulation))


# ---------------------------------------------------------------------------
# Representative examples
# ---------------------------------------------------------------------------

def build_example_coupon_swap_gap_wko_v2_2() -> BuiltRatioForwardContractV22:
    cp = CounterpartySpec(PartyRef("BANK", "Bank"), PartyRef("CLIENT", "Client"))
    pair = FxPair(Currency.USD, Currency.JPY)
    schedule = RatioForwardSeriesSchedule(
        fixing_schedule=DateListSchedule((date(2026, 1, 28), date(2026, 2, 25), date(2026, 3, 25), date(2026, 4, 29))),
        payment_schedule=DateListSchedule((date(2026, 1, 30), date(2026, 2, 27), date(2026, 3, 27), date(2026, 4, 30))),
        accrual_start_schedule=DateListSchedule((date(2025, 12, 30), date(2026, 1, 30), date(2026, 2, 27), date(2026, 3, 27))),
        accrual_end_schedule=DateListSchedule((date(2026, 1, 30), date(2026, 2, 27), date(2026, 3, 27), date(2026, 4, 30))),
    )
    econ = RatioForwardSeriesEconomicTerms(pair, RatioForwardScheme.GAP, OptionAmountSpec(D("1000000"), D("1.0"), D("2.0")), D("148.00"), D("152.00"), sold_option_knock_in=EuropeanKnockInSpec(D("158.00"), BarrierDirection.UP))
    grammar = CouponSwapRatioForwardGrammarV22(
        cp, schedule, econ, Currency.JPY, Currency.USD,
        target=TargetConfig(TargetAccumulationBasis.FX_PIPS, D("1000"), MetricSelection.POSITIVE_PART, TargetHitAction.FULL_HIT_CF_THEN_STOP, pip_size=D("0.01")),
    )
    return build_coupon_swap_ratio_forward_contract_v2_2(grammar, "EXAMPLE-V2-2-COUPON-SWAP-GAP-POINT-TARGET")


def build_example_fx_option_package_two_stage_target_v2_2() -> BuiltRatioForwardContractV22:
    cp = CounterpartySpec(PartyRef("BANK", "Bank"), PartyRef("CLIENT", "Client"))
    pair = FxPair(Currency.USD, Currency.JPY)
    schedule = RatioForwardSeriesSchedule(
        fixing_schedule=DateListSchedule((date(2026, 1, 28), date(2026, 2, 25), date(2026, 3, 25), date(2026, 4, 29))),
        payment_schedule=DateListSchedule((date(2026, 1, 30), date(2026, 2, 27), date(2026, 3, 27), date(2026, 4, 30))),
    )
    econ = RatioForwardSeriesEconomicTerms(pair, RatioForwardScheme.TWO_STAGE, OptionAmountSpec(D("1000000"), D("1.0"), D("2.0")), D("150.00"), D("150.00"), two_stage=TwoStageStrikeSpec(2, D("150.00"), D("153.00")))
    grammar = FxOptionPackageRatioForwardGrammarV22(
        cp, schedule, econ, SettlementStyle.CASH, Currency.JPY,
        premium=Money(D("2500000"), Currency.JPY), premium_payment_date=date(2025, 12, 30),
        target=TargetConfig(TargetAccumulationBasis.PACKAGE_NET_AMOUNT, D("10000000"), MetricSelection.POSITIVE_PART, TargetHitAction.FULL_HIT_CF_THEN_STOP, accumulation_currency=Currency.JPY, affected_start_index=2),
    )
    return build_fx_option_package_ratio_forward_contract_v2_2(grammar, "EXAMPLE-V2-2-FX-OPTION-PACKAGE-TWO-STAGE-AMOUNT-TARGET")


def build_example_fx_option_package_count_tarf_v2_2() -> BuiltRatioForwardContractV22:
    cp = CounterpartySpec(PartyRef("BANK", "Bank"), PartyRef("CLIENT", "Client"))
    pair = FxPair(Currency.USD, Currency.JPY)
    schedule = RatioForwardSeriesSchedule(
        fixing_schedule=DateListSchedule((date(2026, 1, 28), date(2026, 2, 25), date(2026, 3, 25), date(2026, 4, 29))),
        payment_schedule=DateListSchedule((date(2026, 1, 30), date(2026, 2, 27), date(2026, 3, 27), date(2026, 4, 30))),
    )
    econ = RatioForwardSeriesEconomicTerms(pair, RatioForwardScheme.NORMAL, OptionAmountSpec(D("1000000"), D("1.0"), D("1.0")), D("150.00"), D("150.00"))
    grammar = FxOptionPackageRatioForwardGrammarV22(
        cp, schedule, econ, SettlementStyle.CASH, Currency.JPY,
        target=TargetConfig(TargetAccumulationBasis.COUNT, D("2"), MetricSelection.SIGNED, TargetHitAction.KNOCK_OUT_INCLUDING_HIT_CF, count_condition_level=D("151.00")),
    )
    return build_fx_option_package_ratio_forward_contract_v2_2(grammar, "EXAMPLE-V2-2-FX-OPTION-PACKAGE-COUNT-TARF")


if __name__ == "__main__":
    built1 = build_example_coupon_swap_gap_wko_v2_2()
    built2 = build_example_fx_option_package_two_stage_target_v2_2()
    built3 = build_example_fx_option_package_count_tarf_v2_2()
    print(built1.form.form_kind, bool(built1.form.accumulators), len(built1.form.periods))
    print(built2.form.form_kind, bool(built2.form.accumulators), len(built2.form.period_component_groups))
    print(built3.form.form_kind, built3.form.accumulators[0].unit.kind, len(built3.form.conditions))
