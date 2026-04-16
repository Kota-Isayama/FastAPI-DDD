
"""
definition_to_contract_generator.py

Generator layer from typical product definitions into the CDM-like contract model.

Supported inputs
----------------
- FxTarfDefinition
- CouponSwapDefinition
- DigitalCouponSwapDefinition (via the same coupon-swap path)

Output
------
- GeneratedProductBundle with:
  * original typical product definition
  * generated Trade object from cdm_contract_model_v2
  * generation metadata

Important scope note
--------------------
This generator performs *structural normalization* only:
- expands rule-based or explicit definitions into contract-model structures
- creates payouts, periods, features, and target-accrual terms

It does NOT:
- evaluate market conditions
- generate lifecycle state
- determine realized target redemption
- perform schedule-business-day roll calculations beyond what is already
  represented in the definition objects

This is deliberate: contract generation is separate from lifecycle/evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Tuple, Sequence

from typical_product_definitions import (
    ProductDefinition,
    FxTarfDefinition,
    CouponSwapDefinition,
    DigitalCouponSwapDefinition,
    CouponComponentDefinition,
    FixedCouponFormulaDefinition,
    FloatingCouponFormulaDefinition,
    DigitalCouponFormulaDefinition,
    RuleBasedScheduleDefinition,
    ExplicitScheduleDefinition,
    MixedScheduleDefinition,
    ExplicitSchedulePeriod,
    RuleBasedStepDefinition,
    ExplicitStepDefinition,
    MixedStepDefinition,
    ExplicitStepPoint,
    schedule_definition_kind,
    step_definition_kind,
    TargetAccrualMethod,
    KnockOutScope,
    ComparisonOperator,
    CouponDirection,
    GenerationMetadata,
    GeneratedProductBundle,
)

from cdm_contract_model_v2 import (
    Identifier,
    Taxonomy,
    Party,
    Counterparty,
    CounterpartyRole,
    Trade,
    TradeIdentifier,
    TradableProduct,
    NonTransferableProduct,
    EconomicTerms,
    SettlementPayout,
    SettlementTerms,
    SettlementType,
    TransferSettlementType,
    SettlementDate,
    PayerReceiver,
    BuyerSeller,
    PriceQuantity,
    AdjustableDate,
    AdjustableOrRelativeDate,
    PriceSchedule,
    NonNegativeQuantitySchedule,
    PriceType,
    PriceExpression,
    currency_unit,
    Observable,
    AssetClass,
    ObservationTerms,
    TriggerCondition,
    TriggerLevel,
    ObservationOperator,
    TriggerType,
    ContingentFeature,
    FeatureEffect,
    FeatureEffectType,
    FeatureTargetReference,
    FeatureTargetScope,
    TargetAccrualTerms,
    AccrualMethod,
    SettlementFormulaType,
    FxRatioForwardFormula,
    SettlementPeriod,
    InterestRatePayout,
    FixedRateSpecification,
    FloatingRateIndex,
    FloatingRateSpecification,
    CalculationPeriodDates,
    PaymentDates,
    ResetDates,
    Frequency,
    PeriodUnit,
    DayCountConvention,
    flat_price,
    flat_quantity,
    decimal_measure,
)


# ============================================================================
# Generator input support classes
# ============================================================================

@dataclass(frozen=True)
class GeneratorPartySet:
    """The minimal party set required to generate a bilateral trade."""
    party1_name: str
    party2_name: str
    party1_id: str = "PARTY1"
    party2_id: str = "PARTY2"
    id_issuer: str = "INTERNAL"

    def make_counterparties(self) -> tuple[Counterparty, Counterparty]:
        p1 = Party(
            party_ids=(Identifier(issuer=self.id_issuer, value=self.party1_id),),
            name=self.party1_name,
        )
        p2 = Party(
            party_ids=(Identifier(issuer=self.id_issuer, value=self.party2_id),),
            name=self.party2_name,
        )
        return (
            Counterparty(role=CounterpartyRole.PARTY_1, party=p1),
            Counterparty(role=CounterpartyRole.PARTY_2, party=p2),
        )


# ============================================================================
# Small helpers
# ============================================================================

def _aor(d: date) -> AdjustableOrRelativeDate:
    return AdjustableOrRelativeDate(adjustable_date=AdjustableDate(d))


def _period_frequency_to_v2(freq) -> Frequency:
    return Frequency(period_multiplier=freq.multiplier, period=PeriodUnit(freq.unit.value))


def _bday_convention_to_str(bdc) -> str:
    return bdc.value


def _comparison_operator_to_v2(op: ComparisonOperator) -> ObservationOperator:
    mapping = {
        ComparisonOperator.GT: ObservationOperator.GREATER_THAN,
        ComparisonOperator.GTE: ObservationOperator.GREATER_THAN_OR_EQUAL,
        ComparisonOperator.LT: ObservationOperator.LESS_THAN,
        ComparisonOperator.LTE: ObservationOperator.LESS_THAN_OR_EQUAL,
        ComparisonOperator.EQ: ObservationOperator.EQUAL,
    }
    return mapping[op]


def _coupon_direction_to_roles(direction: CouponDirection) -> tuple[CounterpartyRole, CounterpartyRole]:
    # Convention for this example generator:
    # - RECEIVE means Party1 receives / Party2 pays
    # - PAY means Party1 pays / Party2 receives
    if direction == CouponDirection.RECEIVE:
        return CounterpartyRole.PARTY_2, CounterpartyRole.PARTY_1
    return CounterpartyRole.PARTY_1, CounterpartyRole.PARTY_2


def _month_add(base: date, months: int) -> date:
    year = base.year + (base.month - 1 + months) // 12
    month = (base.month - 1 + months) % 12 + 1
    day = min(base.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def _generate_rule_based_periods(schedule: RuleBasedScheduleDefinition) -> tuple[ExplicitSchedulePeriod, ...]:
    """Generate a simple explicit schedule from a rule-based one.

    This intentionally keeps generation lightweight:
    - no detailed business-day rolling
    - no stub calculation engine
    - simple arithmetic progression based on frequency
    """
    periods = []
    current_fixing = schedule.start_date
    idx = 1

    # We treat each schedule node as fixing/payment anchor.
    while current_fixing < schedule.end_date:
        if schedule.frequency.unit == schedule.frequency.unit.MONTH:
            next_fixing = _month_add(current_fixing, schedule.frequency.multiplier)
        elif schedule.frequency.unit == schedule.frequency.unit.YEAR:
            next_fixing = _month_add(current_fixing, 12 * schedule.frequency.multiplier)
        elif schedule.frequency.unit == schedule.frequency.unit.WEEK:
            next_fixing = current_fixing + timedelta(weeks=schedule.frequency.multiplier)
        else:
            next_fixing = current_fixing + timedelta(days=schedule.frequency.multiplier)

        payment_date = current_fixing + timedelta(days=schedule.payment_lag_days)

        periods.append(
            ExplicitSchedulePeriod(
                period_id=f"p{idx:02d}",
                fixing_date=current_fixing,
                payment_date=payment_date,
                accrual_start=current_fixing,
                accrual_end=min(next_fixing, schedule.end_date),
                description="Generated from rule-based schedule.",
            )
        )

        idx += 1
        current_fixing = next_fixing

    return tuple(periods)


def _expand_schedule(schedule) -> tuple[ExplicitSchedulePeriod, ...]:
    if isinstance(schedule, ExplicitScheduleDefinition):
        return schedule.periods
    if isinstance(schedule, RuleBasedScheduleDefinition):
        return _generate_rule_based_periods(schedule)
    if isinstance(schedule, MixedScheduleDefinition):
        # Generate base periods and then override by period_id if explicit ones are provided.
        base_periods = {p.period_id: p for p in _generate_rule_based_periods(schedule.base_rule)}
        for p in schedule.explicit_overrides:
            base_periods[p.period_id] = p
        # keep deterministic ordering by period_id
        return tuple(base_periods[k] for k in sorted(base_periods.keys()))
    raise TypeError(f"Unsupported schedule type: {type(schedule)!r}")


def _value_from_explicit_points(points: Sequence[ExplicitStepPoint], period_id: str, effective_date: date | None) -> Decimal:
    by_period = [p for p in points if p.period_id == period_id]
    if by_period:
        return by_period[0].value
    by_date = [p for p in points if effective_date is not None and p.effective_date == effective_date]
    if by_date:
        return by_date[0].value
    raise KeyError(f"No explicit step value found for period_id={period_id!r}, effective_date={effective_date!r}.")


def _expand_step(step, periods: Sequence[ExplicitSchedulePeriod]) -> tuple[Decimal, ...]:
    """Expand a StepDefinition into one value per schedule period.

    This is intentionally simple and deterministic:
    - explicit points are matched by period_id, then by effective date
    - rule-based step_values are applied in sequence
    - mixed starts from rule-based expansion and then overrides explicit points
    """
    if isinstance(step, ExplicitStepDefinition):
        result = []
        for p in periods:
            result.append(_value_from_explicit_points(step.points, p.period_id, p.fixing_date or p.accrual_start))
        return tuple(result)

    if isinstance(step, RuleBasedStepDefinition):
        values = [step.initial_value]
        values.extend(step.step_values)
        if len(values) < len(periods):
            values.extend([values[-1]] * (len(periods) - len(values)))
        return tuple(values[:len(periods)])

    if isinstance(step, MixedStepDefinition):
        base = list(_expand_step(step.base_rule, periods))
        for i, p in enumerate(periods):
            try:
                base[i] = _value_from_explicit_points(step.explicit_points, p.period_id, p.fixing_date or p.accrual_start)
            except KeyError:
                pass
        return tuple(base)

    raise TypeError(f"Unsupported step type: {type(step)!r}")


def _target_accrual_method_to_v2(method: TargetAccrualMethod) -> AccrualMethod:
    mapping = {
        TargetAccrualMethod.SUM_POSITIVE_PAYOFF: AccrualMethod.SUM_POSITIVE_PAYOFF,
        TargetAccrualMethod.SUM_ABSOLUTE_PAYOFF: AccrualMethod.SUM_ABSOLUTE_PAYOFF,
        TargetAccrualMethod.SUM_COUPON_AMOUNT: AccrualMethod.SUM_COUPON_AMOUNT,
        TargetAccrualMethod.CUSTOM: AccrualMethod.CUSTOM,
    }
    return mapping[method]


def _make_basic_trade(
    definition: ProductDefinition,
    payouts: tuple,
    parties: GeneratorPartySet,
    product_id: str,
    trade_date: date,
    extra_taxonomies: tuple[Taxonomy, ...] = (),
    extra_notes: tuple[str, ...] = (),
) -> Trade:
    cp1, cp2 = parties.make_counterparties()

    product = NonTransferableProduct(
        identifiers=(Identifier(issuer="INTERNAL", value=product_id),),
        taxonomies=extra_taxonomies,
        economic_terms=EconomicTerms(
            payouts=payouts,
            non_standardised_terms=extra_notes,
        ),
    )

    tradable = TradableProduct(
        product=product,
        counterparties=(cp1, cp2),
    )

    return Trade(
        trade_date=trade_date,
        tradable_product=tradable,
        trade_identifiers=(
            TradeIdentifier(identifier=Identifier(issuer="INTERNAL", value=f"TRADE-{product_id}")),
        ),
    )


# ============================================================================
# FX TARF generation
# ============================================================================

def _generate_fx_tarf(defn: FxTarfDefinition, parties: GeneratorPartySet, trade_date: date) -> Trade:
    periods = _expand_schedule(defn.payoff_schedule)
    strike_values = _expand_step(defn.ratio_forward_terms.strike, periods)
    notional_values = _expand_step(defn.ratio_forward_terms.bought_notional, periods)

    observable_name = f"{defn.currency_pair.base_currency}{defn.currency_pair.quote_currency}"
    observable = Observable(
        name=observable_name,
        asset_class=AssetClass.FX,
        identifier=Identifier(issuer="PAIR", value=observable_name),
    )

    formula = FxRatioForwardFormula(
        formula_type=SettlementFormulaType.FX_RATIO_FORWARD,
        reference_observable=observable,
        strike=flat_price(
            value=strike_values[0],
            unit=currency_unit(defn.currency_pair.quote_currency),
            per_unit_of=currency_unit(defn.currency_pair.base_currency),
            price_type=PriceType.FX_RATE,
            price_expression=PriceExpression.NET,
        ),
        bought_currency=defn.ratio_forward_terms.bought_currency,
        sold_currency=defn.ratio_forward_terms.sold_currency,
        bought_quantity=flat_quantity(notional_values[0], currency_unit(defn.ratio_forward_terms.bought_currency)),
        ratio_multiplier=decimal_measure(defn.ratio_forward_terms.ratio),
        description="Generated from FxTarfDefinition ratio-forward terms.",
    )

    settlement_periods = []
    for idx, (p, strike, notion) in enumerate(zip(periods, strike_values, notional_values), start=1):
        settlement_periods.append(
            SettlementPeriod(
                period_id=p.period_id,
                fixing_date=_aor(p.fixing_date) if p.fixing_date else None,
                settlement_date=_aor(p.payment_date) if p.payment_date else None,
                strike_override=flat_price(
                    value=strike,
                    unit=currency_unit(defn.currency_pair.quote_currency),
                    per_unit_of=currency_unit(defn.currency_pair.base_currency),
                    price_type=PriceType.FX_RATE,
                    price_expression=PriceExpression.NET,
                ),
                bought_quantity_override=flat_quantity(
                    notion,
                    currency_unit(defn.ratio_forward_terms.bought_currency),
                ),
                description=p.description,
            )
        )

    target_terms = TargetAccrualTerms(
        target_amount=defn.target_redemption.target_amount,
        accrual_currency=defn.target_redemption.accrual_currency,
        accrual_method=_target_accrual_method_to_v2(defn.target_redemption.accrual_method),
        include_negative_amounts=defn.target_redemption.include_negative_amounts,
        observation_terms=ObservationTerms(
            observable=observable,
            description="Generated target observation terms from TARF definition.",
        ),
        description=defn.target_redemption.description,
    )

    features = []
    # TARF always gets a target feature placeholder that applies to the payout group.
    features.append(
        ContingentFeature(
            name="TargetRedemptionFeature",
            trigger=TriggerCondition(
                observable=observable,
                operator=ObservationOperator.GREATER_THAN_OR_EQUAL,
                level=TriggerLevel(
                    value=Decimal("0"),
                    unit=currency_unit(defn.target_redemption.accrual_currency),
                ),
                observation_terms=ObservationTerms(
                    observable=observable,
                    description="Placeholder target trigger; realized state evaluation is external.",
                ),
                trigger_type=TriggerType.TARGET,
            ),
            effect=FeatureEffect(
                effect_type=FeatureEffectType.TERMINATE_PAYOUT,
                target=FeatureTargetReference(
                    scope=FeatureTargetScope.REMAINING_PAYOUTS_IN_GROUP,
                    payout_group="tarf_stream",
                    description="Terminate remaining TARF stream after target redemption.",
                ),
                description="Generated placeholder feature for TARF target redemption.",
            ),
        )
    )

    if defn.knock_out_rule is not None:
        ko = defn.knock_out_rule
        ko_observable = Observable(
            name=ko.condition.observable_name,
            asset_class=AssetClass.OTHER,
            identifier=Identifier(issuer="OBS", value=ko.condition.observable_name),
        )
        scope_map = {
            KnockOutScope.THIS_COMPONENT: FeatureTargetScope.THIS_PAYOUT,
            KnockOutScope.REMAINING_COMPONENT: FeatureTargetScope.REMAINING_PAYOUTS_IN_GROUP,
            KnockOutScope.REMAINING_PRODUCT: FeatureTargetScope.PAYOUT_GROUP,
            KnockOutScope.NAMED_COMPONENTS: FeatureTargetScope.NAMED_PAYOUTS,
            KnockOutScope.CUSTOM: FeatureTargetScope.CUSTOM,
        }
        target_ref = FeatureTargetReference(
            scope=scope_map[ko.scope],
            payout_group="tarf_stream" if ko.scope in (KnockOutScope.REMAINING_COMPONENT, KnockOutScope.REMAINING_PRODUCT) else None,
            payout_ids=ko.target_component_names if ko.scope == KnockOutScope.NAMED_COMPONENTS else (),
            description=ko.description,
        )
        features.append(
            ContingentFeature(
                name="KnockOutFeature",
                trigger=TriggerCondition(
                    observable=ko_observable,
                    operator=_comparison_operator_to_v2(ko.condition.operator),
                    level=TriggerLevel(
                        value=ko.condition.level,
                        unit=currency_unit(defn.currency_pair.quote_currency),
                    ),
                    observation_terms=ObservationTerms(
                        observable=ko_observable,
                        description="Generated from KnockOutRuleDefinition.",
                    ),
                    trigger_type=TriggerType.KNOCK_OUT,
                ),
                effect=FeatureEffect(
                    effect_type=FeatureEffectType.TERMINATE_PAYOUT,
                    target=target_ref,
                    description=ko.description or "Generated knockout effect.",
                ),
            )
        )

    payout = SettlementPayout(
        payout_id="tarf_ratio_forward_stream",
        payout_group="tarf_stream",
        payer_receiver=PayerReceiver(
            payer=CounterpartyRole.PARTY_1,
            receiver=CounterpartyRole.PARTY_2,
        ),
        settlement_terms=SettlementTerms(
            settlement_type=SettlementType.CASH,
            transfer_settlement_type=TransferSettlementType.PAYMENT_VS_PAYMENT,
            settlement_currency=defn.currency_pair.quote_currency,
        ),
        settlement_formula=formula,
        settlement_periods=tuple(settlement_periods),
        target_accrual_terms=target_terms,
        features=tuple(features),
        description=f"Generated from {defn.template_name}.",
    )

    notes = (
        f"payoff_schedule_kind={schedule_definition_kind(defn.payoff_schedule).value}",
        f"strike_step_kind={step_definition_kind(defn.ratio_forward_terms.strike).value}",
        f"notional_step_kind={step_definition_kind(defn.ratio_forward_terms.bought_notional).value}",
    )

    return _make_basic_trade(
        definition=defn,
        payouts=(payout,),
        parties=parties,
        product_id=f"{defn.template_name}-001",
        trade_date=trade_date,
        extra_taxonomies=(
            Taxonomy(scheme="ASSET_CLASS", value="FX"),
            Taxonomy(scheme="PRODUCT_FAMILY", value="TARF"),
            Taxonomy(scheme="PRODUCT_STYLE", value="RATIO_FORWARD"),
        ),
        extra_notes=notes,
    )


# ============================================================================
# Coupon swap generation
# ============================================================================

def _make_coupon_schedule_structures(component: CouponComponentDefinition):
    periods = _expand_schedule(component.coupon_schedule)
    return periods


def _make_component_feature(component: CouponComponentDefinition) -> tuple[ContingentFeature, ...]:
    if component.knock_out_rule is None:
        return ()

    ko = component.knock_out_rule
    observable = Observable(
        name=ko.condition.observable_name,
        asset_class=AssetClass.OTHER,
        identifier=Identifier(issuer="OBS", value=ko.condition.observable_name),
    )

    scope_map = {
        KnockOutScope.THIS_COMPONENT: FeatureTargetScope.THIS_PAYOUT,
        KnockOutScope.REMAINING_COMPONENT: FeatureTargetScope.THIS_PAYOUT,
        KnockOutScope.REMAINING_PRODUCT: FeatureTargetScope.PAYOUT_GROUP,
        KnockOutScope.NAMED_COMPONENTS: FeatureTargetScope.NAMED_PAYOUTS,
        KnockOutScope.CUSTOM: FeatureTargetScope.CUSTOM,
    }

    target_ref = FeatureTargetReference(
        scope=scope_map[ko.scope],
        payout_group="coupon_swap_stream" if ko.scope == KnockOutScope.REMAINING_PRODUCT else None,
        payout_ids=ko.target_component_names if ko.scope == KnockOutScope.NAMED_COMPONENTS else (),
        description=ko.description,
    )

    effect_type = FeatureEffectType.TERMINATE_PAYOUT
    if ko.scope == KnockOutScope.THIS_COMPONENT:
        effect_type = FeatureEffectType.TERMINATE_PAYOUT
    elif ko.scope == KnockOutScope.REMAINING_COMPONENT:
        effect_type = FeatureEffectType.TERMINATE_PAYOUT

    return (
        ContingentFeature(
            name=f"{component.component_name}_knockout",
            trigger=TriggerCondition(
                observable=observable,
                operator=_comparison_operator_to_v2(ko.condition.operator),
                level=TriggerLevel(
                    value=ko.condition.level,
                    unit=currency_unit("USD"),  # generic placeholder in absence of richer observable typing
                ),
                observation_terms=ObservationTerms(
                    observable=observable,
                    description="Generated from coupon component KO rule.",
                ),
                trigger_type=TriggerType.KNOCK_OUT,
            ),
            effect=FeatureEffect(
                effect_type=effect_type,
                target=target_ref,
                description=ko.description or f"KO for component {component.component_name}",
            ),
        ),
    )


def _generate_coupon_component_payout(component: CouponComponentDefinition) -> InterestRatePayout:
    periods = _make_coupon_schedule_structures(component)
    notional_values = _expand_step(component.notional, periods)

    payer, receiver = _coupon_direction_to_roles(component.direction)

    # Use first/last periods as the high-level contract dates.
    first = periods[0]
    last = periods[-1]
    start_date = first.accrual_start or first.fixing_date or first.payment_date
    end_date = last.accrual_end or last.payment_date or last.fixing_date

    if start_date is None or end_date is None:
        raise ValueError(f"Component {component.component_name} schedule lacks enough date anchors.")

    if isinstance(component.formula, FixedCouponFormulaDefinition):
        rate_values = _expand_step(component.formula.rate, periods)
        rate_spec = FixedRateSpecification(
            rate=flat_price(
                value=rate_values[0],
                unit=currency_unit("USD"),
                per_unit_of=currency_unit("USD"),
                price_type=PriceType.INTEREST_RATE,
            )
        )
    elif isinstance(component.formula, FloatingCouponFormulaDefinition):
        spread = None
        if component.formula.spread is not None:
            spread_values = _expand_step(component.formula.spread, periods)
            spread = flat_price(
                value=spread_values[0],
                unit=currency_unit("USD"),
                per_unit_of=currency_unit("USD"),
                price_type=PriceType.SPREAD,
            )
        rate_spec = FloatingRateSpecification(
            rate_index=FloatingRateIndex(name=component.formula.index_name),
            spread=spread,
            reset_dates=ResetDates(reset_frequency=Frequency(3, PeriodUnit.MONTH)) if component.formula.reset_schedule is not None else None,
            day_count_convention=DayCountConvention.ACT_360,
        )
    elif isinstance(component.formula, DigitalCouponFormulaDefinition):
        # We map digital coupon into an interest-rate-like payout with a feature placeholder.
        payoff_values = _expand_step(component.formula.payoff_amount, periods)
        rate_spec = FixedRateSpecification(
            rate=flat_price(
                value=payoff_values[0],
                unit=currency_unit("USD"),
                per_unit_of=currency_unit("USD"),
                price_type=PriceType.INTEREST_RATE,
            )
        )
    else:
        raise TypeError(f"Unsupported coupon formula type: {type(component.formula)!r}")

    features = list(_make_component_feature(component))

    if isinstance(component.formula, DigitalCouponFormulaDefinition):
        strike_values = _expand_step(component.formula.strike, periods)
        obs = Observable(
            name=component.formula.underlying_observable,
            asset_class=AssetClass.OTHER,
            identifier=Identifier(issuer="OBS", value=component.formula.underlying_observable),
        )
        direction_map = {
            "UP": ObservationOperator.GREATER_THAN_OR_EQUAL,
            "DOWN": ObservationOperator.LESS_THAN_OR_EQUAL,
        }
        features.append(
            ContingentFeature(
                name=f"{component.component_name}_digital_coupon_condition",
                trigger=TriggerCondition(
                    observable=obs,
                    operator=direction_map[component.formula.direction.value],
                    level=TriggerLevel(value=strike_values[0], unit=currency_unit("USD")),
                    observation_terms=ObservationTerms(
                        observable=obs,
                        description="Generated digital coupon observation terms.",
                    ),
                    trigger_type=TriggerType.DIGITAL,
                ),
                effect=FeatureEffect(
                    effect_type=FeatureEffectType.FLAG_ONLY,
                    target=FeatureTargetReference(
                        scope=FeatureTargetScope.THIS_PAYOUT,
                        description="Digital coupon condition applies to this component.",
                    ),
                    description="Generated placeholder digital coupon feature.",
                ),
            )
        )

    payout = InterestRatePayout(
        payout_id=component.component_name,
        payout_group="coupon_swap_stream",
        payer_receiver=PayerReceiver(payer=payer, receiver=receiver),
        notional_schedule=flat_quantity(notional_values[0], currency_unit("USD")),
        rate_specification=rate_spec,
        day_count_convention=DayCountConvention.ACT_360,
        calculation_period_dates=CalculationPeriodDates(
            effective_date=_aor(start_date),
            termination_date=_aor(end_date),
            frequency=Frequency(3, PeriodUnit.MONTH),
        ),
        payment_dates=PaymentDates(payment_frequency=Frequency(3, PeriodUnit.MONTH)),
        features=tuple(features),
        description=component.description,
    )
    return payout


def _generate_coupon_swap(defn: CouponSwapDefinition | DigitalCouponSwapDefinition, parties: GeneratorPartySet, trade_date: date) -> Trade:
    payouts = tuple(_generate_coupon_component_payout(c) for c in defn.components)
    notes = []
    for c in defn.components:
        notes.append(f"{c.component_name}.schedule_kind={schedule_definition_kind(c.coupon_schedule).value}")
        notes.append(f"{c.component_name}.notional_kind={step_definition_kind(c.notional).value}")

    taxonomies = [Taxonomy(scheme="ASSET_CLASS", value="INTEREST_RATE")]
    if isinstance(defn, DigitalCouponSwapDefinition):
        taxonomies.append(Taxonomy(scheme="PRODUCT_FAMILY", value="DIGITAL_COUPON_SWAP"))
    else:
        taxonomies.append(Taxonomy(scheme="PRODUCT_FAMILY", value="COUPON_SWAP"))

    return _make_basic_trade(
        definition=defn,
        payouts=payouts,
        parties=parties,
        product_id=f"{defn.template_name}-001",
        trade_date=trade_date,
        extra_taxonomies=tuple(taxonomies),
        extra_notes=tuple(notes),
    )


# ============================================================================
# Public API
# ============================================================================

class DefinitionToContractGenerator:
    """Public generator facade.

    Typical usage:
        generator = DefinitionToContractGenerator(...)
        bundle = generator.generate(definition)
    """

    def __init__(self, parties: GeneratorPartySet, generator_name: str = "definition-to-contract", generator_version: str = "1.0"):
        self.parties = parties
        self.generator_name = generator_name
        self.generator_version = generator_version

    def generate(self, definition: ProductDefinition, trade_date: date | None = None) -> GeneratedProductBundle:
        if trade_date is None:
            trade_date = date.today()

        if isinstance(definition, FxTarfDefinition):
            trade = _generate_fx_tarf(definition, self.parties, trade_date)
        elif isinstance(definition, (CouponSwapDefinition, DigitalCouponSwapDefinition)):
            trade = _generate_coupon_swap(definition, self.parties, trade_date)
        else:
            raise TypeError(f"Unsupported definition type: {type(definition)!r}")

        metadata = GenerationMetadata(
            generator_name=self.generator_name,
            generator_version=self.generator_version,
            notes=(
                f"definition_type={type(definition).__name__}",
                f"template_name={definition.template_name}",
            ),
        )

        return GeneratedProductBundle(
            definition=definition,
            generated_trade=trade,
            metadata=metadata,
        )


# ============================================================================
# Examples
# ============================================================================

if __name__ == "__main__":
    from typical_product_definitions import (
        example_irregular_tarf_definition,
        example_rule_based_tarf_definition,
        example_ako_coupon_swap_definition,
    )

    gen = DefinitionToContractGenerator(
        parties=GeneratorPartySet(
            party1_name="Bank A",
            party2_name="Client B",
            party1_id="BANKA",
            party2_id="CLIENTB",
        ),
        generator_version="1.0-demo",
    )

    for d in (
        example_irregular_tarf_definition(),
        example_rule_based_tarf_definition(),
        example_ako_coupon_swap_definition(),
    ):
        bundle = gen.generate(d, trade_date=date(2026, 1, 20))
        trade = bundle.generated_trade
        print(type(d).__name__, "=>", type(trade).__name__)
        print("  template:", d.template_name)
        print("  trade date:", trade.trade_date)
        print("  payout count:", len(trade.tradable_product.product.economic_terms.payouts))
