
"""
Full implementation for ratio-forward-like product grammars.

Goals
-----
- Same economics, two contract forms:
    1. Coupon Swap form
    2. FX Option Package form
- Dataclass-level product grammar
- Builder output with both ContractForm and period metadata
- WKO and TARGET semantics including exact hit-CF behavior
- Sold-side European KI for option-package form
- Coupon-swap form keeps coupon-exchange form and does not model KI as option mechanics
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional, Literal

from contract_model_schedule_semantic_graph_boundary_aligned import *


# ---------------------------------------------------------------------------
# Shared grammar enums / scalar helpers
# ---------------------------------------------------------------------------

ZERO = Decimal("0")
ONE = Decimal("1")


def _D(x: str | int | Decimal) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def _q(x: Decimal, digits: str = "0.00000001") -> Decimal:
    return x.quantize(Decimal(digits), rounding=ROUND_HALF_UP)


class RatioForwardScheme(str, Enum):
    NORMAL = "NORMAL"
    GAP = "GAP"
    RANGE_GAP = "RANGE_GAP"
    COLLAR = "COLLAR"
    TWO_STAGE = "TWO_STAGE"


class SoldOptionSelector(str, Enum):
    PUT = "PUT"
    CALL = "CALL"


class TargetMetric(str, Enum):
    AMOUNT = "AMOUNT"
    POINTS = "POINTS"


class TargetAccumulationSide(str, Enum):
    CLIENT_GAIN = "CLIENT_GAIN"
    CLIENT_LOSS = "CLIENT_LOSS"


class TargetHitAction(str, Enum):
    KNOCK_OUT_INCLUDING_HIT_CF = "KNOCK_OUT_INCLUDING_HIT_CF"
    PARTIAL_HIT_CF_TO_TARGET_THEN_STOP = "PARTIAL_HIT_CF_TO_TARGET_THEN_STOP"
    FULL_HIT_CF_THEN_STOP = "FULL_HIT_CF_THEN_STOP"


# ---------------------------------------------------------------------------
# Input-side economics
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OptionAmountSpec:
    """
    Input-layer ratio information.
    Product grammar / ContractForm side should usually store computed amounts.
    """
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
    observation_schedule: Optional[ScheduleRefLike] = None  # defaults to fixing or schedule default


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
    accumulation_currency: Optional[Currency] = None  # required for AMOUNT; quote ccy in current implementation


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
            raise ValueError(f"Unsupported scheme: {self.scheme}")


# ---------------------------------------------------------------------------
# Expanded period-level semantics
# ---------------------------------------------------------------------------

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

    def sold_option_is_put(self) -> bool:
        return self.sold_option_selector is SoldOptionSelector.PUT


def _schedule_dates(schedule_like: ScheduleRefLike) -> tuple[date, ...]:
    if isinstance(schedule_like, DateListSchedule):
        return schedule_like.sorted_dates()
    raise TypeError(
        "Ratio-forward full builders expect explicit DateListSchedule. "
        "Materialize semantic schedules before passing them here."
    )


def _default_ki_schedule(
    schedule: RatioForwardSeriesSchedule,
    sold_ki: EuropeanKnockInSpec,
) -> ScheduleRefLike:
    if sold_ki.observation_schedule is not None:
        return sold_ki.observation_schedule
    if schedule.ki_observation_schedule is not None:
        return schedule.ki_observation_schedule
    return schedule.fixing_schedule


def _client_and_bank_ids(cp: CounterpartySpec) -> tuple[str, str]:
    return cp.counterparty.party_id, cp.book_party.party_id


def expand_period_specs(
    schedule: RatioForwardSeriesSchedule,
    terms: RatioForwardSeriesEconomicTerms,
) -> tuple[RatioForwardPeriodSpec, ...]:
    terms.validate()

    fixing_dates = _schedule_dates(schedule.fixing_schedule)
    payment_dates = _schedule_dates(schedule.payment_schedule)
    count = min(len(fixing_dates), len(payment_dates))

    accrual_start_dates: tuple[date | None, ...]
    accrual_end_dates: tuple[date | None, ...]
    if schedule.accrual_start_schedule is None:
        accrual_start_dates = tuple(None for _ in range(count))
    else:
        raw = _schedule_dates(schedule.accrual_start_schedule)
        accrual_start_dates = tuple(raw[i] if i < len(raw) else None for i in range(count))
    if schedule.accrual_end_schedule is None:
        accrual_end_dates = tuple(None for _ in range(count))
    else:
        raw = _schedule_dates(schedule.accrual_end_schedule)
        accrual_end_dates = tuple(raw[i] if i < len(raw) else None for i in range(count))

    ki_obs_dates: tuple[date | None, ...]
    if terms.sold_option_knock_in is None:
        ki_obs_dates = tuple(None for _ in range(count))
    else:
        ki_sched = _schedule_dates(_default_ki_schedule(schedule, terms.sold_option_knock_in))
        ki_obs_dates = tuple(ki_sched[i] if i < len(ki_sched) else None for i in range(count))

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
                accrual_start_date=accrual_start_dates[i],
                accrual_end_date=accrual_end_dates[i],
                call_strike=call_strike,
                put_strike=put_strike,
                call_amount_base=terms.amount_spec.call_amount_base,
                put_amount_base=terms.amount_spec.put_amount_base,
                sold_option_selector=terms.sold_option_selector,
                sold_option_knock_in=terms.sold_option_knock_in,
                ki_observation_date=ki_obs_dates[i],
            )
        )
    return tuple(out)


# ---------------------------------------------------------------------------
# Declarative formula / mechanism objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CouponSwapExchangeFormula(Formula):
    """
    Grammar-level declarative coupon exchange formula.

    It is intentionally descriptive rather than fully executable by core runtime.
    """
    pair: FxPair
    side_role: Literal["BASE_DELIVERY", "QUOTE_DELIVERY"]
    scheme: RatioForwardScheme
    sold_option_selector: SoldOptionSelector


@dataclass(frozen=True)
class RatioForwardPeriodMetadata:
    period_index: int
    fixing_date: date
    payment_date: date
    call_strike: Decimal
    put_strike: Decimal
    call_amount_base: Decimal
    put_amount_base: Decimal
    ki_observation_date: Optional[date]
    sold_option_selector: SoldOptionSelector


@dataclass(frozen=True)
class WindowKnockOutMechanism(Mechanism):
    component_id: str
    predicate: Predicate
    deactivate_components: tuple[str, ...]
    monitoring_start_index: int = 0
    affected_start_index: int = 0
    state_flag_name: str = "window_knocked_out"
    kind: MechanismKind = MechanismKind.KNOCK_OUT


@dataclass(frozen=True)
class TargetTerminationMechanism(Mechanism):
    component_id: str
    source_component_ids: tuple[str, ...]
    metric: TargetMetric
    accumulation_side: TargetAccumulationSide
    target_value: Decimal
    hit_action: TargetHitAction
    accumulation_currency: Optional[Currency] = None
    state_key: str = "target_accumulation"
    kind: MechanismKind = MechanismKind.ACCUMULATE_UNTIL_TARGET


# ---------------------------------------------------------------------------
# Product grammar objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CouponSwapRatioForwardGrammar:
    """
    Coupon Swap form:
    - really exchanges currencies via 2 coupon legs
    - does NOT present option exercise as the form
    - sold-side KI economics is absorbed into coupon payoff rule
    """
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
            raise ValueError("CouponSwap grammar requires accrual_start_schedule and accrual_end_schedule")
        if self.target and self.target.metric is TargetMetric.AMOUNT and self.target.accumulation_currency is None:
            raise ValueError("TARGET amount metric requires accumulation_currency")
        if self.target and self.target.metric is TargetMetric.AMOUNT and self.target.accumulation_currency != self.quote_currency:
            raise ValueError("Current full implementation only supports TARGET amount accumulation in quote currency")


@dataclass(frozen=True)
class FxOptionPackageRatioForwardGrammar:
    """
    FX Option Package form:
    - each period builds a call/put package
    - sold-side KI is represented explicitly by KnockInMechanism on sold option
    """
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
        if self.target and self.target.metric is TargetMetric.AMOUNT and self.target.accumulation_currency is None:
            raise ValueError("TARGET amount metric requires accumulation_currency")
        settlement_ccy = self.settlement_currency or self.economic_terms.pair.quote
        if self.target and self.target.metric is TargetMetric.AMOUNT and self.target.accumulation_currency != settlement_ccy:
            raise ValueError("Current full implementation only supports TARGET amount accumulation in settlement/quote currency")
        if (self.premium is None) ^ (self.premium_payment_date is None):
            raise ValueError("premium and premium_payment_date must be given together")


# ---------------------------------------------------------------------------
# Build outputs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BuiltRatioForwardContract:
    form: ContractForm
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
# Builders
# ---------------------------------------------------------------------------

def build_coupon_swap_ratio_forward_contract(
    grammar: CouponSwapRatioForwardGrammar,
    form_id: str = "FORM-COUPON-SWAP-RATIO-FWD",
) -> BuiltRatioForwardContract:
    grammar.validate()
    client_id, bank_id = _client_and_bank_ids(grammar.counterparties)
    specs = expand_period_specs(grammar.schedule, grammar.economic_terms)

    pay_base = grammar.pay_leg_role == "CLIENT_PAYS_BASE"
    pay_payer = client_id if pay_base else bank_id
    pay_receiver = bank_id if pay_base else client_id
    recv_payer = bank_id if pay_base else client_id
    recv_receiver = client_id if pay_base else bank_id

    pay_formula = CouponSwapExchangeFormula(
        pair=grammar.economic_terms.pair,
        side_role="BASE_DELIVERY" if pay_base else "QUOTE_DELIVERY",
        scheme=grammar.economic_terms.scheme,
        sold_option_selector=grammar.economic_terms.sold_option_selector,
    )
    recv_formula = CouponSwapExchangeFormula(
        pair=grammar.economic_terms.pair,
        side_role="QUOTE_DELIVERY" if pay_base else "BASE_DELIVERY",
        scheme=grammar.economic_terms.scheme,
        sold_option_selector=grammar.economic_terms.sold_option_selector,
    )

    pay_leg = AccrualCouponLeg(
        component_id="coupon_swap_pay_leg",
        payer_party_id=pay_payer,
        receiver_party_id=pay_receiver,
        reference=UnderlierRef(grammar.economic_terms.pair.symbol(), "FX"),
        notional=SteppedDecimal(grammar.economic_terms.amount_spec.notional_base),
        payment_schedule=grammar.schedule.payment_schedule,
        accrual_start_schedule=grammar.schedule.accrual_start_schedule,
        accrual_end_schedule=grammar.schedule.accrual_end_schedule,
        fixing_schedule=grammar.schedule.fixing_schedule,
        rate_formula_name="coupon_swap_pay_formula",
        currency=grammar.base_currency if pay_base else grammar.quote_currency,
        day_count=DayCount.ACT_365F,
    )
    recv_leg = AccrualCouponLeg(
        component_id="coupon_swap_receive_leg",
        payer_party_id=recv_payer,
        receiver_party_id=recv_receiver,
        reference=UnderlierRef(grammar.economic_terms.pair.symbol(), "FX"),
        notional=SteppedDecimal(grammar.economic_terms.amount_spec.notional_base),
        payment_schedule=grammar.schedule.payment_schedule,
        accrual_start_schedule=grammar.schedule.accrual_start_schedule,
        accrual_end_schedule=grammar.schedule.accrual_end_schedule,
        fixing_schedule=grammar.schedule.fixing_schedule,
        rate_formula_name="coupon_swap_receive_formula",
        currency=grammar.quote_currency if pay_base else grammar.base_currency,
        day_count=DayCount.ACT_365F,
    )

    mechanisms: list[Mechanism] = []
    if grammar.wko is not None:
        affected = tuple(
            component_id
            for component_id in ("coupon_swap_pay_leg", "coupon_swap_receive_leg")
        )
        mechanisms.append(
            WindowKnockOutMechanism(
                component_id="wko_mech",
                predicate=BarrierPredicate(
                    underlier=UnderlierRef(grammar.economic_terms.pair.symbol(), "FX"),
                    direction=grammar.wko.direction,
                    level=grammar.wko.barrier,
                    observation_schedule=grammar.wko.observation_schedule,
                ),
                deactivate_components=affected,
                monitoring_start_index=grammar.wko.monitoring_start_index,
                affected_start_index=grammar.wko.affected_start_index,
            )
        )
    if grammar.target is not None:
        mechanisms.append(
            TargetTerminationMechanism(
                component_id="target_mech",
                source_component_ids=("coupon_swap_pay_leg", "coupon_swap_receive_leg"),
                metric=grammar.target.metric,
                accumulation_side=grammar.target.accumulation_side,
                target_value=grammar.target.target_value,
                hit_action=grammar.target.hit_action,
                accumulation_currency=grammar.target.accumulation_currency,
            )
        )

    form = ContractForm(
        form_id=form_id,
        form_kind="COUPON_SWAP_RATIO_FORWARD",
        parties=grammar.counterparties.both(),
        party_roles=(
            PartyRoleAssignment("client", client_id),
            PartyRoleAssignment("bank", bank_id),
        ),
        references=(UnderlierRef(grammar.economic_terms.pair.symbol(), "FX"),),
        transfers=(),
        legs=(pay_leg, recv_leg),
        formulas=(
            FormulaBinding("coupon_swap_pay_formula", pay_formula),
            FormulaBinding("coupon_swap_receive_formula", recv_formula),
        ),
        mechanisms=tuple(mechanisms),
        tags={
            "grammar_kind": "COUPON_SWAP_RATIO_FORWARD",
            "scheme": grammar.economic_terms.scheme.value,
            "same_economics_as": "FX_OPTION_PACKAGE_RATIO_FORWARD",
            "quote_currency": grammar.quote_currency.value,
        },
    )
    return BuiltRatioForwardContract(
        form=form,
        form_variant="COUPON_SWAP",
        pair=grammar.economic_terms.pair,
        base_currency=grammar.base_currency,
        quote_currency=grammar.quote_currency,
        client_party_id=client_id,
        bank_party_id=bank_id,
        period_specs=specs,
        payment_dates_by_component={
            "coupon_swap_pay_leg": specs[0].payment_date if specs else date.min,
            "coupon_swap_receive_leg": specs[0].payment_date if specs else date.min,
        },
        wko=grammar.wko,
        target=grammar.target,
    )


def build_fx_option_package_ratio_forward_contract(
    grammar: FxOptionPackageRatioForwardGrammar,
    form_id: str = "FORM-FX-OPTION-PACKAGE-RATIO-FWD",
) -> BuiltRatioForwardContract:
    grammar.validate()
    client_id, bank_id = _client_and_bank_ids(grammar.counterparties)
    specs = expand_period_specs(grammar.schedule, grammar.economic_terms)

    legs: list[Leg] = []
    mechanisms: list[Mechanism] = []
    transfers: list[Transfer] = []
    payment_dates_by_component: dict[str, date] = {}

    settlement_ccy = grammar.settlement_currency or grammar.economic_terms.pair.quote
    pair_ref = UnderlierRef(grammar.economic_terms.pair.symbol(), "FX")

    if grammar.premium is not None and grammar.premium_payment_date is not None:
        transfers.append(
            PremiumTransfer(
                component_id="premium",
                payer_party_id=client_id,
                receiver_party_id=bank_id,
                amount=grammar.premium,
                payment_date=grammar.premium_payment_date,
            )
        )

    for spec in specs:
        i = spec.period_index + 1
        call_id = f"period_{i}_call"
        put_id = f"period_{i}_put"

        call_leg = FxOptionExerciseLeg(
            component_id=call_id,
            buyer_party_id=client_id,
            seller_party_id=bank_id,
            pair=grammar.economic_terms.pair,
            side=Side.BUY,
            option_type=OptionType.CALL,
            base_notional=spec.call_amount_base,
            strike=spec.call_strike,
            expiry_date=spec.fixing_date,
            settlement_style=grammar.settlement_style,
            settlement_currency=settlement_ccy,
        )
        put_leg = FxOptionExerciseLeg(
            component_id=put_id,
            buyer_party_id=bank_id,
            seller_party_id=client_id,
            pair=grammar.economic_terms.pair,
            side=Side.SELL,
            option_type=OptionType.PUT,
            base_notional=spec.put_amount_base,
            strike=spec.put_strike,
            expiry_date=spec.fixing_date,
            settlement_style=grammar.settlement_style,
            settlement_currency=settlement_ccy,
        )
        legs.extend([call_leg, put_leg])
        payment_dates_by_component[call_id] = spec.payment_date
        payment_dates_by_component[put_id] = spec.payment_date

        if spec.sold_option_knock_in is not None:
            sold_leg_id = put_id if spec.sold_option_selector is SoldOptionSelector.PUT else call_id
            obs_date = spec.ki_observation_date or spec.fixing_date
            mechanisms.append(
                KnockInMechanism(
                    component_id=f"period_{i}_sold_option_ki",
                    predicate=BarrierPredicate(
                        underlier=pair_ref,
                        direction=spec.sold_option_knock_in.direction,
                        level=spec.sold_option_knock_in.barrier,
                        observation_schedule=DateListSchedule((obs_date,)),
                    ),
                    activate_components=(sold_leg_id,),
                )
            )

    if grammar.wko is not None:
        affected_ids = []
        for spec in specs:
            if spec.period_index >= grammar.wko.affected_start_index:
                p = spec.period_index + 1
                affected_ids.extend([f"period_{p}_call", f"period_{p}_put"])
        mechanisms.append(
            WindowKnockOutMechanism(
                component_id="wko_mech",
                predicate=BarrierPredicate(
                    underlier=pair_ref,
                    direction=grammar.wko.direction,
                    level=grammar.wko.barrier,
                    observation_schedule=grammar.wko.observation_schedule,
                ),
                deactivate_components=tuple(affected_ids),
                monitoring_start_index=grammar.wko.monitoring_start_index,
                affected_start_index=grammar.wko.affected_start_index,
            )
        )

    if grammar.target is not None:
        mechanisms.append(
            TargetTerminationMechanism(
                component_id="target_mech",
                source_component_ids=tuple(payment_dates_by_component.keys()),
                metric=grammar.target.metric,
                accumulation_side=grammar.target.accumulation_side,
                target_value=grammar.target.target_value,
                hit_action=grammar.target.hit_action,
                accumulation_currency=grammar.target.accumulation_currency,
            )
        )

    form = ContractForm(
        form_id=form_id,
        form_kind="FX_OPTION_PACKAGE_RATIO_FORWARD",
        parties=grammar.counterparties.both(),
        party_roles=(
            PartyRoleAssignment("client", client_id),
            PartyRoleAssignment("bank", bank_id),
        ),
        references=(pair_ref,),
        transfers=tuple(transfers),
        legs=tuple(legs),
        formulas=(),
        mechanisms=tuple(mechanisms),
        tags={
            "grammar_kind": "FX_OPTION_PACKAGE_RATIO_FORWARD",
            "scheme": grammar.economic_terms.scheme.value,
            "same_economics_as": "COUPON_SWAP_RATIO_FORWARD",
            "quote_currency": grammar.economic_terms.pair.quote.value,
            "payment_dates_by_component": ";".join(
                f"{cid}:{dt.isoformat()}" for cid, dt in sorted(payment_dates_by_component.items())
            ),
        },
    )
    return BuiltRatioForwardContract(
        form=form,
        form_variant="FX_OPTION_PACKAGE",
        pair=grammar.economic_terms.pair,
        base_currency=grammar.economic_terms.pair.base,
        quote_currency=grammar.economic_terms.pair.quote,
        client_party_id=client_id,
        bank_party_id=bank_id,
        period_specs=specs,
        payment_dates_by_component=payment_dates_by_component,
        wko=grammar.wko,
        target=grammar.target,
    )


# ---------------------------------------------------------------------------
# Compatibility wrappers returning ContractForm only
# ---------------------------------------------------------------------------

def build_coupon_swap_ratio_forward_grammar_contract(
    grammar: CouponSwapRatioForwardGrammar,
    form_id: str = "FORM-COUPON-SWAP-RATIO-FWD",
) -> ContractForm:
    return build_coupon_swap_ratio_forward_contract(grammar, form_id).form


def build_fx_option_package_ratio_forward_grammar_contract(
    grammar: FxOptionPackageRatioForwardGrammar,
    form_id: str = "FORM-FX-OPTION-PACKAGE-RATIO-FWD",
) -> ContractForm:
    return build_fx_option_package_ratio_forward_contract(grammar, form_id).form


# ---------------------------------------------------------------------------
# Economics evaluation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PeriodEconomics:
    period_index: int
    fixing_date: date
    payment_date: date
    spot: Decimal
    sold_option_knocked_in: bool
    call_quote_amount: Decimal
    sold_option_quote_amount: Decimal
    client_net_quote_amount: Decimal
    client_gain_amount_quote: Decimal
    client_loss_amount_quote: Decimal
    client_gain_points: Decimal
    client_loss_points: Decimal


def _barrier_hit(direction: BarrierDirection, value: Decimal, level: Decimal) -> bool:
    return value >= level if direction is BarrierDirection.UP else value <= level


def evaluate_period_economics(
    spec: RatioForwardPeriodSpec,
    spot: Decimal,
    *,
    sold_option_knocked_in: Optional[bool] = None,
) -> PeriodEconomics:
    sold_ki = spec.sold_option_knock_in
    if sold_option_knocked_in is None:
        if sold_ki is None:
            sold_option_knocked_in = True
        else:
            sold_option_knocked_in = _barrier_hit(sold_ki.direction, spot, sold_ki.barrier)

    call_intrinsic = max(spot - spec.call_strike, ZERO)
    put_intrinsic = max(spec.put_strike - spot, ZERO)

    call_quote = _q(call_intrinsic * spec.call_amount_base)
    if spec.sold_option_selector is SoldOptionSelector.PUT:
        sold_quote = _q(put_intrinsic * spec.put_amount_base) if sold_option_knocked_in else ZERO
        client_net_quote = _q(call_quote - sold_quote)
    else:
        sold_quote = _q(call_intrinsic * spec.call_amount_base) if sold_option_knocked_in else ZERO
        # if sold side is call, "buy leg" must be put side economically
        buy_put_quote = _q(put_intrinsic * spec.put_amount_base)
        client_net_quote = _q(buy_put_quote - sold_quote)
        call_quote = buy_put_quote  # descriptive field now denotes bought-side payout

    client_gain_amount = max(client_net_quote, ZERO)
    client_loss_amount = max(-client_net_quote, ZERO)

    # points: notional-free but level-sensitive
    gain_points = ZERO
    loss_points = ZERO
    if spec.sold_option_selector is SoldOptionSelector.PUT:
        gain_points = max(
            spec.call_amount_base / max(spec.call_amount_base, ONE) * call_intrinsic
            - spec.put_amount_base / max(spec.call_amount_base, ONE) * (put_intrinsic if sold_option_knocked_in else ZERO),
            ZERO,
        )
        loss_points = max(
            spec.put_amount_base / max(spec.call_amount_base, ONE) * (put_intrinsic if sold_option_knocked_in else ZERO)
            - spec.call_amount_base / max(spec.call_amount_base, ONE) * call_intrinsic,
            ZERO,
        )
    else:
        bought_put_points = spec.put_amount_base / max(spec.put_amount_base, ONE) * put_intrinsic
        sold_call_points = spec.call_amount_base / max(spec.put_amount_base, ONE) * (call_intrinsic if sold_option_knocked_in else ZERO)
        gain_points = max(bought_put_points - sold_call_points, ZERO)
        loss_points = max(sold_call_points - bought_put_points, ZERO)

    return PeriodEconomics(
        period_index=spec.period_index,
        fixing_date=spec.fixing_date,
        payment_date=spec.payment_date,
        spot=spot,
        sold_option_knocked_in=sold_option_knocked_in,
        call_quote_amount=call_quote,
        sold_option_quote_amount=sold_quote,
        client_net_quote_amount=client_net_quote,
        client_gain_amount_quote=client_gain_amount,
        client_loss_amount_quote=client_loss_amount,
        client_gain_points=_q(gain_points),
        client_loss_points=_q(loss_points),
    )


# ---------------------------------------------------------------------------
# WKO / TARGET full series simulation
# ---------------------------------------------------------------------------

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
    built: BuiltRatioForwardContract
    periods: tuple[SimulatedPeriodResult, ...]
    terminated: bool
    termination_period_index: Optional[int]
    final_target_accumulation: Decimal


def _target_contribution(econ: PeriodEconomics, target: TargetConfig) -> Decimal:
    if target.metric is TargetMetric.AMOUNT:
        return econ.client_gain_amount_quote if target.accumulation_side is TargetAccumulationSide.CLIENT_GAIN else econ.client_loss_amount_quote
    if target.metric is TargetMetric.POINTS:
        return econ.client_gain_points if target.accumulation_side is TargetAccumulationSide.CLIENT_GAIN else econ.client_loss_points
    raise ValueError(target.metric)


def simulate_ratio_forward_series(
    built: BuiltRatioForwardContract,
    spot_by_fixing_date: dict[date, Decimal],
    *,
    ki_observation_by_date: Optional[dict[date, Decimal]] = None,
    wko_observation_by_date: Optional[dict[date, Decimal]] = None,
) -> SeriesSimulationResult:
    periods: list[SimulatedPeriodResult] = []
    terminated = False
    termination_idx: Optional[int] = None
    accumulation = ZERO

    ki_observation_by_date = ki_observation_by_date or {}
    wko_observation_by_date = wko_observation_by_date or {}

    for spec in built.period_specs:
        active_before = not terminated

        # WKO monitoring
        wko_hit = False
        if active_before and built.wko is not None and spec.period_index >= built.wko.monitoring_start_index:
            obs_date = spec.fixing_date
            if isinstance(built.wko.observation_schedule, DateListSchedule):
                obs_dates = built.wko.observation_schedule.dates
                if spec.fixing_date not in obs_dates and spec.payment_date in obs_dates:
                    obs_date = spec.payment_date
            obs_val = wko_observation_by_date.get(obs_date)
            if obs_val is not None:
                wko_hit = _barrier_hit(built.wko.direction, obs_val, built.wko.barrier)

        # sold-side KI
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
        increment_before_scaling = ZERO
        increment_applied = ZERO
        target_metric_used: Optional[TargetMetric] = None

        # WKO effect
        if active_before and wko_hit and built.wko is not None and spec.period_index >= built.wko.affected_start_index:
            terminated = True
            termination_idx = spec.period_index
            reason = "wko_hit_future_and_current_cancelled"
            exchange_scale = ZERO

        # TARGET effect
        if active_before and not terminated and built.target is not None:
            target_metric_used = built.target.metric
            increment_before_scaling = _target_contribution(econ, built.target)
            remaining = built.target.target_value - accumulation

            if increment_before_scaling <= ZERO:
                increment_applied = ZERO
            elif increment_before_scaling < remaining:
                increment_applied = increment_before_scaling
            else:
                # hit period
                if built.target.hit_action is TargetHitAction.KNOCK_OUT_INCLUDING_HIT_CF:
                    exchange_scale = ZERO
                    increment_applied = ZERO
                    accumulation = built.target.target_value
                    terminated = True
                    termination_idx = spec.period_index
                    reason = "target_hit_cancel_hit_cf_and_stop"
                elif built.target.hit_action is TargetHitAction.PARTIAL_HIT_CF_TO_TARGET_THEN_STOP:
                    if increment_before_scaling > ZERO:
                        exchange_scale = _q(remaining / increment_before_scaling)
                    increment_applied = remaining
                    accumulation = built.target.target_value
                    terminated = True
                    termination_idx = spec.period_index
                    reason = "target_hit_partial_cf_then_stop"
                elif built.target.hit_action is TargetHitAction.FULL_HIT_CF_THEN_STOP:
                    exchange_scale = ONE
                    increment_applied = increment_before_scaling
                    accumulation = accumulation + increment_applied
                    terminated = True
                    termination_idx = spec.period_index
                    reason = "target_hit_full_cf_then_stop"
                else:
                    raise ValueError(built.target.hit_action)

            if built.target.hit_action not in {
                TargetHitAction.KNOCK_OUT_INCLUDING_HIT_CF,
                TargetHitAction.PARTIAL_HIT_CF_TO_TARGET_THEN_STOP,
                TargetHitAction.FULL_HIT_CF_THEN_STOP,
            }:
                raise ValueError("unsupported target action")

            if increment_before_scaling > ZERO and increment_before_scaling < remaining:
                accumulation = accumulation + increment_applied

        client_net_exchanged = _q(econ.client_net_quote_amount * exchange_scale)

        periods.append(
            SimulatedPeriodResult(
                period_index=spec.period_index,
                fixing_date=spec.fixing_date,
                payment_date=spec.payment_date,
                active_before=active_before,
                sold_option_knocked_in=sold_ki_hit,
                economics=econ,
                wko_hit=wko_hit,
                target_metric_used=target_metric_used,
                target_increment_before_scaling=_q(increment_before_scaling),
                target_increment_applied=_q(increment_applied),
                target_accumulation_after=_q(accumulation),
                exchange_scale=_q(exchange_scale),
                client_net_quote_exchanged=client_net_exchanged,
                terminated_after=terminated,
                reason=reason,
            )
        )

    return SeriesSimulationResult(
        built=built,
        periods=tuple(periods),
        terminated=terminated,
        termination_period_index=termination_idx,
        final_target_accumulation=_q(accumulation),
    )


# ---------------------------------------------------------------------------
# Representative examples
# ---------------------------------------------------------------------------

def build_example_coupon_swap_gap_wko() -> BuiltRatioForwardContract:
    cp = CounterpartySpec(
        book_party=PartyRef("BANK", "Bank"),
        counterparty=PartyRef("CLIENT", "Client"),
    )
    pair = FxPair(Currency.USD, Currency.JPY)
    schedule = RatioForwardSeriesSchedule(
        fixing_schedule=DateListSchedule((
            date(2026, 1, 28),
            date(2026, 2, 25),
            date(2026, 3, 25),
            date(2026, 4, 29),
        )),
        payment_schedule=DateListSchedule((
            date(2026, 1, 30),
            date(2026, 2, 27),
            date(2026, 3, 27),
            date(2026, 4, 30),
        )),
        accrual_start_schedule=DateListSchedule((
            date(2025, 12, 30),
            date(2026, 1, 30),
            date(2026, 2, 27),
            date(2026, 3, 27),
        )),
        accrual_end_schedule=DateListSchedule((
            date(2026, 1, 30),
            date(2026, 2, 27),
            date(2026, 3, 27),
            date(2026, 4, 30),
        )),
    )
    econ = RatioForwardSeriesEconomicTerms(
        pair=pair,
        scheme=RatioForwardScheme.GAP,
        amount_spec=OptionAmountSpec(
            notional_base=_D("1000000"),
            call_level=_D("1.0"),
            put_level=_D("2.0"),
        ),
        call_strike=_D("148.00"),
        put_strike=_D("152.00"),
        sold_option_selector=SoldOptionSelector.PUT,
        sold_option_knock_in=EuropeanKnockInSpec(
            barrier=_D("158.00"),
            direction=BarrierDirection.UP,
        ),
    )
    grammar = CouponSwapRatioForwardGrammar(
        counterparties=cp,
        schedule=schedule,
        economic_terms=econ,
        quote_currency=Currency.JPY,
        base_currency=Currency.USD,
        pay_leg_role="CLIENT_PAYS_BASE",
        wko=WKOConfig(
            barrier=_D("160.00"),
            direction=BarrierDirection.UP,
            observation_schedule=schedule.fixing_schedule,
            monitoring_start_index=1,
            affected_start_index=2,
        ),
    )
    return build_coupon_swap_ratio_forward_contract(grammar, "EXAMPLE-COUPON-SWAP-GAP-WKO")


def build_example_fx_option_package_two_stage_target() -> BuiltRatioForwardContract:
    cp = CounterpartySpec(
        book_party=PartyRef("BANK", "Bank"),
        counterparty=PartyRef("CLIENT", "Client"),
    )
    pair = FxPair(Currency.USD, Currency.JPY)
    schedule = RatioForwardSeriesSchedule(
        fixing_schedule=DateListSchedule((
            date(2026, 1, 28),
            date(2026, 2, 25),
            date(2026, 3, 25),
            date(2026, 4, 29),
        )),
        payment_schedule=DateListSchedule((
            date(2026, 1, 30),
            date(2026, 2, 27),
            date(2026, 3, 27),
            date(2026, 4, 30),
        )),
    )
    econ = RatioForwardSeriesEconomicTerms(
        pair=pair,
        scheme=RatioForwardScheme.TWO_STAGE,
        amount_spec=OptionAmountSpec(
            notional_base=_D("1000000"),
            call_level=_D("1.0"),
            put_level=_D("2.0"),
        ),
        call_strike=_D("150.00"),
        put_strike=_D("150.00"),
        two_stage=TwoStageStrikeSpec(
            stage_switch_index=2,
            stage1_strike=_D("150.00"),
            stage2_strike=_D("153.00"),
        ),
    )
    grammar = FxOptionPackageRatioForwardGrammar(
        counterparties=cp,
        schedule=schedule,
        economic_terms=econ,
        settlement_style=SettlementStyle.CASH,
        settlement_currency=Currency.JPY,
        premium=Money(_D("2500000"), Currency.JPY),
        premium_payment_date=date(2025, 12, 30),
        target=TargetConfig(
            metric=TargetMetric.AMOUNT,
            target_value=_D("10000000"),
            accumulation_side=TargetAccumulationSide.CLIENT_GAIN,
            hit_action=TargetHitAction.FULL_HIT_CF_THEN_STOP,
            accumulation_currency=Currency.JPY,
        ),
    )
    return build_fx_option_package_ratio_forward_contract(
        grammar,
        "EXAMPLE-FX-OPTION-PACKAGE-TWO-STAGE-TARGET",
    )
