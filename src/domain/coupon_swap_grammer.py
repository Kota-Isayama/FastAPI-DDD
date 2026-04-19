"""
Product Grammar layer for ratio-forward-like Coupon Swap / FX Option Package structures.

This module builds on top of:
    contract_model_schedule_semantic_graph_boundary_aligned.py

Focus:
- Same economics, two contract forms
    1. Coupon Swap form
    2. FX Option Package form
- Declarative product-grammar level structures
- KO / TARGET / sold-option European KI handling
- Schedule-rich authoring, not full valuation runtime
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional, Literal

from contract_model_schedule_semantic_graph_boundary_aligned import *


# ---------------------------------------------------------------------------
# Shared grammar enums / dataclasses
# ---------------------------------------------------------------------------

class RatioForwardScheme(str, Enum):
    NORMAL = "NORMAL"
    GAP = "GAP"
    RANGE_GAP = "RANGE_GAP"
    COLLAR = "COLLAR"
    TWO_STAGE = "TWO_STAGE"


class SoldOptionSelector(str, Enum):
    PUT = "PUT"
    CALL = "CALL"


class KnockOutStyle(str, Enum):
    NONE = "NONE"
    WKO = "WKO"
    TARGET = "TARGET"


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


@dataclass(frozen=True)
class OptionAmountSpec:
    """
    User-input level information.

    ProductGrammar / ContractForm side should usually store computed option amounts
    rather than call_level / put_level themselves.
    """
    notional_base: Decimal
    call_level: Decimal = Decimal("1")
    put_level: Decimal = Decimal("1")

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
    # if None, builder defaults to fixing schedule


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
    accumulation_currency: Optional[Currency] = None  # required for AMOUNT
    source_component_role: Literal["CLIENT_RECEIVE", "CLIENT_PAY", "NET_CLIENT"] = "NET_CLIENT"


@dataclass(frozen=True)
class RatioForwardSeriesSchedule:
    """
    Shared schedule information for one economic series.

    fixing/payment are mandatory.
    KI observation is optional and defaults to fixing when KI exists.
    """
    fixing_schedule: ScheduleRefLike
    payment_schedule: ScheduleRefLike
    accrual_start_schedule: Optional[ScheduleRefLike] = None
    accrual_end_schedule: Optional[ScheduleRefLike] = None
    ki_observation_schedule: Optional[ScheduleRefLike] = None


@dataclass(frozen=True)
class RatioForwardSeriesEconomicTerms:
    """
    Economic meaning of one per-period series.

    Convention adopted here:
    - 'Normal': K_call = K_put
    - GAP: K_call < K_put, sold option only gets European KI
    - Range GAP: K_call = K_put, sold option only gets European KI
    - Collar: K_put < K_call, no KI
    - Two-stage: same strike on call and put inside each CF, but strike changes once
    """
    pair: FxPair
    scheme: RatioForwardScheme
    amount_spec: OptionAmountSpec

    # primary strikes
    call_strike: Decimal
    put_strike: Decimal

    # optional two-stage
    two_stage: Optional[TwoStageStrikeSpec] = None

    # generic "sold option gets KI" definition
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
                raise ValueError("GAP requires KI on sold option")
        elif self.scheme is RatioForwardScheme.RANGE_GAP:
            if self.call_strike != self.put_strike:
                raise ValueError("RANGE_GAP requires K_call = K_put")
            if self.sold_option_knock_in is None:
                raise ValueError("RANGE_GAP requires KI on sold option")
        elif self.scheme is RatioForwardScheme.COLLAR:
            if not (self.put_strike < self.call_strike):
                raise ValueError("COLLAR requires K_put < K_call")
        elif self.scheme is RatioForwardScheme.TWO_STAGE:
            if self.two_stage is None:
                raise ValueError("TWO_STAGE requires two_stage spec")
            if self.call_strike != self.put_strike:
                raise ValueError("TWO_STAGE stage1 requires K_call = K_put")
        else:
            raise ValueError(f"Unsupported scheme: {self.scheme}")


@dataclass(frozen=True)
class RatioForwardPeriodProfile:
    period_index: int
    call_strike: Decimal
    put_strike: Decimal
    call_amount_base: Decimal
    put_amount_base: Decimal
    sold_option_selector: SoldOptionSelector
    sold_option_knock_in: Optional[EuropeanKnockInSpec]


def expand_period_profiles(
    terms: RatioForwardSeriesEconomicTerms,
    period_count: int,
) -> tuple[RatioForwardPeriodProfile, ...]:
    terms.validate()
    out: list[RatioForwardPeriodProfile] = []
    for i in range(period_count):
        if terms.scheme is RatioForwardScheme.TWO_STAGE:
            assert terms.two_stage is not None
            strike = (
                terms.two_stage.stage1_strike
                if i < terms.two_stage.stage_switch_index
                else terms.two_stage.stage2_strike
            )
            call_strike = strike
            put_strike = strike
        else:
            call_strike = terms.call_strike
            put_strike = terms.put_strike

        out.append(
            RatioForwardPeriodProfile(
                period_index=i,
                call_strike=call_strike,
                put_strike=put_strike,
                call_amount_base=terms.amount_spec.call_amount_base,
                put_amount_base=terms.amount_spec.put_amount_base,
                sold_option_selector=terms.sold_option_selector,
                sold_option_knock_in=terms.sold_option_knock_in,
            )
        )
    return tuple(out)


# ---------------------------------------------------------------------------
# Grammar-level formulas / mechanisms
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CouponSwapExchangeFormula(Formula):
    """
    Declarative formula for one currency side of coupon-swap-style exchange.

    side_role:
        - "BASE_DELIVERY": base currency amount side
        - "QUOTE_DELIVERY": quote currency amount side

    economics are intentionally stored at grammar level rather than directly executable.
    """
    pair: FxPair
    side_role: Literal["BASE_DELIVERY", "QUOTE_DELIVERY"]
    call_strike: Decimal
    put_strike: Decimal
    call_amount_base: Decimal
    put_amount_base: Decimal
    sold_option_selector: SoldOptionSelector
    sold_option_has_knock_in: bool = False


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
    Contract form:
    - really exchanges currencies
    - represented as two AccrualCouponLeg streams
    - does NOT internally think in terms of option exercise
    - KI, if present economically, is absorbed into digital/range coupon style formula
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


@dataclass(frozen=True)
class FxOptionPackageRatioForwardGrammar:
    """
    Contract form:
    - per CF, option package (call + put) is created
    - economic KI is represented explicitly as sold-option European KI
    - same economics as coupon swap version can be preserved, but form remains different
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _schedule_dates(schedule_like: ScheduleRefLike) -> tuple[date, ...]:
    if isinstance(schedule_like, DateListSchedule):
        return schedule_like.sorted_dates()
    raise TypeError(
        "This grammar builder expects explicit DateListSchedule for period expansion. "
        "Use materialized schedules or pass explicit schedules."
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


# ---------------------------------------------------------------------------
# Builders: Coupon Swap form
# ---------------------------------------------------------------------------

def build_coupon_swap_ratio_forward_grammar_contract(
    grammar: CouponSwapRatioForwardGrammar,
    form_id: str = "FORM-COUPON-SWAP-RATIO-FWD",
) -> ContractForm:
    grammar.validate()
    client_id, bank_id = _client_and_bank_ids(grammar.counterparties)

    fixing_dates = _schedule_dates(grammar.schedule.fixing_schedule)
    payment_dates = _schedule_dates(grammar.schedule.payment_schedule)
    accrual_start_dates = _schedule_dates(grammar.schedule.accrual_start_schedule)  # validated non-None
    accrual_end_dates = _schedule_dates(grammar.schedule.accrual_end_schedule)      # validated non-None

    period_count = min(len(fixing_dates), len(payment_dates), len(accrual_start_dates), len(accrual_end_dates))
    profiles = expand_period_profiles(grammar.economic_terms, period_count)

    pay_base = grammar.pay_leg_role == "CLIENT_PAYS_BASE"
    pay_payer = client_id if pay_base else bank_id
    pay_receiver = bank_id if pay_base else client_id
    recv_payer = bank_id if pay_base else client_id
    recv_receiver = client_id if pay_base else bank_id

    pay_formula = CouponSwapExchangeFormula(
        pair=grammar.economic_terms.pair,
        side_role="BASE_DELIVERY" if pay_base else "QUOTE_DELIVERY",
        call_strike=profiles[0].call_strike,
        put_strike=profiles[0].put_strike,
        call_amount_base=profiles[0].call_amount_base,
        put_amount_base=profiles[0].put_amount_base,
        sold_option_selector=profiles[0].sold_option_selector,
        sold_option_has_knock_in=profiles[0].sold_option_knock_in is not None,
    )
    recv_formula = CouponSwapExchangeFormula(
        pair=grammar.economic_terms.pair,
        side_role="QUOTE_DELIVERY" if pay_base else "BASE_DELIVERY",
        call_strike=profiles[0].call_strike,
        put_strike=profiles[0].put_strike,
        call_amount_base=profiles[0].call_amount_base,
        put_amount_base=profiles[0].put_amount_base,
        sold_option_selector=profiles[0].sold_option_selector,
        sold_option_has_knock_in=profiles[0].sold_option_knock_in is not None,
    )

    legs: tuple[Leg, ...] = (
        AccrualCouponLeg(
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
        ),
        AccrualCouponLeg(
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
        ),
    )

    mechanisms: list[Mechanism] = []

    if grammar.wko is not None:
        future_components = ("coupon_swap_pay_leg", "coupon_swap_receive_leg")
        mechanisms.append(
            WindowKnockOutMechanism(
                component_id="wko_mech",
                predicate=BarrierPredicate(
                    underlier=UnderlierRef(grammar.economic_terms.pair.symbol(), "FX"),
                    direction=grammar.wko.direction,
                    level=grammar.wko.barrier,
                    observation_schedule=grammar.wko.observation_schedule,
                ),
                deactivate_components=future_components,
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

    tags = {
        "grammar_kind": "COUPON_SWAP_RATIO_FORWARD",
        "scheme": grammar.economic_terms.scheme.value,
        "same_economics_as": "FX_OPTION_PACKAGE_RATIO_FORWARD",
    }

    return ContractForm(
        form_id=form_id,
        form_kind="COUPON_SWAP_RATIO_FORWARD",
        parties=grammar.counterparties.both(),
        party_roles=(
            PartyRoleAssignment("client", client_id),
            PartyRoleAssignment("bank", bank_id),
        ),
        references=(UnderlierRef(grammar.economic_terms.pair.symbol(), "FX"),),
        transfers=(),
        legs=legs,
        formulas=(
            FormulaBinding("coupon_swap_pay_formula", pay_formula),
            FormulaBinding("coupon_swap_receive_formula", recv_formula),
        ),
        mechanisms=tuple(mechanisms),
        tags=tags,
    )


# ---------------------------------------------------------------------------
# Builders: FX option package form
# ---------------------------------------------------------------------------

def build_fx_option_package_ratio_forward_grammar_contract(
    grammar: FxOptionPackageRatioForwardGrammar,
    form_id: str = "FORM-FX-OPTION-PACKAGE-RATIO-FWD",
) -> ContractForm:
    grammar.validate()
    client_id, bank_id = _client_and_bank_ids(grammar.counterparties)

    fixing_dates = _schedule_dates(grammar.schedule.fixing_schedule)
    payment_dates = _schedule_dates(grammar.schedule.payment_schedule)
    period_count = min(len(fixing_dates), len(payment_dates))
    profiles = expand_period_profiles(grammar.economic_terms, period_count)

    legs: list[Leg] = []
    mechanisms: list[Mechanism] = []
    transfers: list[Transfer] = []

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

    for i, profile in enumerate(profiles):
        expiry_date = fixing_dates[i]
        settlement_ccy = grammar.settlement_currency or grammar.economic_terms.pair.quote

        call_leg_id = f"period_{i+1}_call"
        put_leg_id = f"period_{i+1}_put"

        call_leg = FxOptionExerciseLeg(
            component_id=call_leg_id,
            buyer_party_id=client_id,
            seller_party_id=bank_id,
            pair=grammar.economic_terms.pair,
            side=Side.BUY,
            option_type=OptionType.CALL,
            base_notional=profile.call_amount_base,
            strike=profile.call_strike,
            expiry_date=expiry_date,
            settlement_style=grammar.settlement_style,
            settlement_currency=settlement_ccy,
        )
        put_leg = FxOptionExerciseLeg(
            component_id=put_leg_id,
            buyer_party_id=bank_id,
            seller_party_id=client_id,
            pair=grammar.economic_terms.pair,
            side=Side.SELL,
            option_type=OptionType.PUT,
            base_notional=profile.put_amount_base,
            strike=profile.put_strike,
            expiry_date=expiry_date,
            settlement_style=grammar.settlement_style,
            settlement_currency=settlement_ccy,
        )

        legs.extend([call_leg, put_leg])

        sold_selector = profile.sold_option_selector
        sold_leg_id = put_leg_id if sold_selector is SoldOptionSelector.PUT else call_leg_id
        sold_ki = profile.sold_option_knock_in
        if sold_ki is not None:
            mechanisms.append(
                KnockInMechanism(
                    component_id=f"period_{i+1}_sold_option_ki",
                    predicate=BarrierPredicate(
                        underlier=UnderlierRef(grammar.economic_terms.pair.symbol(), "FX"),
                        direction=sold_ki.direction,
                        level=sold_ki.barrier,
                        observation_schedule=_default_ki_schedule(grammar.schedule, sold_ki),
                    ),
                    activate_components=(sold_leg_id,),
                )
            )

    if grammar.wko is not None:
        deactivate_components = tuple(
            leg.component_id
            for leg in legs
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
                deactivate_components=deactivate_components,
                monitoring_start_index=grammar.wko.monitoring_start_index,
                affected_start_index=grammar.wko.affected_start_index,
            )
        )

    if grammar.target is not None:
        mechanisms.append(
            TargetTerminationMechanism(
                component_id="target_mech",
                source_component_ids=tuple(leg.component_id for leg in legs),
                metric=grammar.target.metric,
                accumulation_side=grammar.target.accumulation_side,
                target_value=grammar.target.target_value,
                hit_action=grammar.target.hit_action,
                accumulation_currency=grammar.target.accumulation_currency,
            )
        )

    tags = {
        "grammar_kind": "FX_OPTION_PACKAGE_RATIO_FORWARD",
        "scheme": grammar.economic_terms.scheme.value,
        "same_economics_as": "COUPON_SWAP_RATIO_FORWARD",
        "payment_schedule_dates": ",".join(d.isoformat() for d in payment_dates[:period_count]),
    }

    return ContractForm(
        form_id=form_id,
        form_kind="FX_OPTION_PACKAGE_RATIO_FORWARD",
        parties=grammar.counterparties.both(),
        party_roles=(
            PartyRoleAssignment("client", client_id),
            PartyRoleAssignment("bank", bank_id),
        ),
        references=(UnderlierRef(grammar.economic_terms.pair.symbol(), "FX"),),
        transfers=tuple(transfers),
        legs=tuple(legs),
        formulas=(),
        mechanisms=tuple(mechanisms),
        tags=tags,
    )


# ---------------------------------------------------------------------------
# Representative examples
# ---------------------------------------------------------------------------

def build_example_coupon_swap_gap_wko() -> ContractForm:
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
            notional_base=Decimal("1000000"),
            call_level=Decimal("1.0"),
            put_level=Decimal("2.0"),
        ),
        call_strike=Decimal("148.00"),
        put_strike=Decimal("152.00"),
        sold_option_selector=SoldOptionSelector.PUT,
        sold_option_knock_in=EuropeanKnockInSpec(
            barrier=Decimal("158.00"),
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
            barrier=Decimal("160.00"),
            direction=BarrierDirection.UP,
            observation_schedule=schedule.fixing_schedule,
            monitoring_start_index=1,
            affected_start_index=2,
        ),
    )
    return build_coupon_swap_ratio_forward_grammar_contract(grammar, "EXAMPLE-COUPON-SWAP-GAP-WKO")


def build_example_fx_option_package_two_stage_target() -> ContractForm:
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
            notional_base=Decimal("1000000"),
            call_level=Decimal("1.0"),
            put_level=Decimal("2.0"),
        ),
        call_strike=Decimal("150.00"),
        put_strike=Decimal("150.00"),
        two_stage=TwoStageStrikeSpec(
            stage_switch_index=2,
            stage1_strike=Decimal("150.00"),
            stage2_strike=Decimal("153.00"),
        ),
    )
    grammar = FxOptionPackageRatioForwardGrammar(
        counterparties=cp,
        schedule=schedule,
        economic_terms=econ,
        settlement_style=SettlementStyle.CASH,
        settlement_currency=Currency.JPY,
        premium=Money(Decimal("2500000"), Currency.JPY),
        premium_payment_date=date(2025, 12, 30),
        target=TargetConfig(
            metric=TargetMetric.AMOUNT,
            target_value=Decimal("10000000"),
            accumulation_side=TargetAccumulationSide.CLIENT_GAIN,
            hit_action=TargetHitAction.FULL_HIT_CF_THEN_STOP,
            accumulation_currency=Currency.JPY,
        ),
    )
    return build_fx_option_package_ratio_forward_grammar_contract(
        grammar,
        "EXAMPLE-FX-OPTION-PACKAGE-TWO-STAGE-TARGET",
    )
