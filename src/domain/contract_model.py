from __future__ import annotations

"""
Form-first derivative contract model.

Layers
------
1. InputTemplate  : concise user-facing input
2. ContractForm   : source of truth / editable authoring form
3. RuntimeState   : path/lifecycle state during observation/event processing
4. NormalizedView : derived comparison-oriented projection

This module is intentionally pragmatic rather than exhaustive. It aims to be a
strong architectural baseline for broad derivative coverage, especially for:
- vanilla forwards/options
- coupon products / notes
- path-dependent structures (snowball / autocall / TARF)
- MtM notional cross-currency swaps
"""

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Iterable, Literal, Optional, Sequence, Union


# ---------------------------------------------------------------------------
# Enums and scalar value objects
# ---------------------------------------------------------------------------


class Currency(str, Enum):
    JPY = "JPY"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CHF = "CHF"
    AUD = "AUD"
    NZD = "NZD"
    CAD = "CAD"


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

    def opposite(self) -> "Side":
        return Side.SELL if self is Side.BUY else Side.BUY


class PayReceive(str, Enum):
    PAY = "PAY"
    RECEIVE = "RECEIVE"

    def opposite(self) -> "PayReceive":
        return PayReceive.RECEIVE if self is PayReceive.PAY else PayReceive.PAY


class OptionType(str, Enum):
    CALL = "CALL"
    PUT = "PUT"


class SettlementStyle(str, Enum):
    CASH = "CASH"
    PHYSICAL = "PHYSICAL"


class BarrierDirection(str, Enum):
    UP = "UP"
    DOWN = "DOWN"


class ComparisonOp(str, Enum):
    GE = ">="
    GT = ">"
    LE = "<="
    LT = "<"
    EQ = "=="


class ObservationKind(str, Enum):
    SPOT = "SPOT"
    CLOSE = "CLOSE"
    OPEN = "OPEN"
    AVERAGE = "AVERAGE"
    MAX = "MAX"
    MIN = "MIN"
    WORST_OF = "WORST_OF"
    BEST_OF = "BEST_OF"


class DayCount(str, Enum):
    ACT_360 = "ACT/360"
    ACT_365F = "ACT/365F"
    THIRTY_360 = "30/360"


class MechanismKind(str, Enum):
    KNOCK_OUT = "KNOCK_OUT"
    KNOCK_IN = "KNOCK_IN"
    COUPON_MEMORY = "COUPON_MEMORY"
    STEP_UP = "STEP_UP"
    ACCUMULATE_UNTIL_TARGET = "ACCUMULATE_UNTIL_TARGET"
    AUTOCALL = "AUTOCALL"
    AMORTIZATION = "AMORTIZATION"
    NOTIONAL_RESET = "NOTIONAL_RESET"
    EXERCISE = "EXERCISE"


class PrincipalExchangeMode(str, Enum):
    NONE = "NONE"
    INITIAL_ONLY = "INITIAL_ONLY"
    INITIAL_AND_FINAL = "INITIAL_AND_FINAL"


class FinalExchangeNotionalSource(str, Enum):
    ORIGINAL = "ORIGINAL"
    CURRENT = "CURRENT"


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: Currency


@dataclass(frozen=True)
class UnderlierRef:
    symbol: str
    kind: Literal["EQ", "FX", "IR", "CMDTY", "CREDIT", "OTHER"] = "OTHER"


@dataclass(frozen=True)
class BasketRef:
    underliers: tuple[UnderlierRef, ...]
    weighting: Literal["EQUAL", "CUSTOM"] = "EQUAL"


ReferenceRef = Union[UnderlierRef, BasketRef]


# ---------------------------------------------------------------------------
# Schedule / time / steps / overrides
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DateListSchedule:
    dates: tuple[date, ...]

    def sorted_dates(self) -> tuple[date, ...]:
        return tuple(sorted(self.dates))


@dataclass(frozen=True)
class PeriodicSchedule:
    start_date: date
    end_date: date
    frequency: Literal[
        "DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "SEMI_ANNUAL", "ANNUAL"
    ]


Schedule = Union[DateListSchedule, PeriodicSchedule]


@dataclass(frozen=True)
class ObservationWindow:
    start_date: date
    end_date: date
    kind: ObservationKind = ObservationKind.AVERAGE


@dataclass(frozen=True)
class StepPoint:
    effective_date: date
    value: Decimal


@dataclass(frozen=True)
class SteppedDecimal:
    initial: Decimal
    steps: tuple[StepPoint, ...] = ()

    def value_on(self, dt: date) -> Decimal:
        value = self.initial
        for step in sorted(self.steps, key=lambda s: s.effective_date):
            if dt >= step.effective_date:
                value = step.value
        return value


@dataclass(frozen=True)
class SchedulePatch:
    original_date: date
    new_date: date
    reason: str


@dataclass(frozen=True)
class CashflowOverride:
    component_id: str
    payment_date: date
    field_name: str
    value: Decimal
    reason: str


# ---------------------------------------------------------------------------
# Observation / formulas / predicates
# ---------------------------------------------------------------------------


class ObservationRule:
    pass


@dataclass(frozen=True)
class SingleAssetObservation(ObservationRule):
    underlier: UnderlierRef
    observation_kind: ObservationKind
    schedule: DateListSchedule


@dataclass(frozen=True)
class BasketObservation(ObservationRule):
    basket: BasketRef
    observation_kind: ObservationKind
    schedule: DateListSchedule


class Predicate:
    pass


@dataclass(frozen=True)
class ComparisonPredicate(Predicate):
    left_operand: str
    operator: ComparisonOp
    right_constant: Decimal


@dataclass(frozen=True)
class BarrierPredicate(Predicate):
    underlier: UnderlierRef
    direction: BarrierDirection
    level: Decimal
    observation_schedule: DateListSchedule
    observation_kind: ObservationKind = ObservationKind.CLOSE


@dataclass(frozen=True)
class TargetReachedPredicate(Predicate):
    state_key: str
    operator: ComparisonOp
    target_amount: Decimal


class Formula:
    pass


@dataclass(frozen=True)
class FixedRateFormula(Formula):
    rate: SteppedDecimal


@dataclass(frozen=True)
class FloatingRateFormula(Formula):
    index_name: str
    spread: SteppedDecimal
    floor: Optional[Decimal] = None
    cap: Optional[Decimal] = None


@dataclass(frozen=True)
class FxForwardPayoffFormula(Formula):
    strike: SteppedDecimal
    leverage_above_strike: Optional[Decimal] = None
    leverage_below_strike: Optional[Decimal] = None


@dataclass(frozen=True)
class MtMNotionalResetFormula(Formula):
    """
    Canonical simple form:
        new_notional = base_notional * observed_reference / base_reference_value
    or inverse if the quotation direction is opposite to the target leg semantics.
    """

    base_notional: Decimal
    base_reference_value: Decimal
    rounding_digits: Optional[int] = None
    scale_direction: Literal["DIRECT", "INVERSE"] = "DIRECT"
    floor: Optional[Decimal] = None
    cap: Optional[Decimal] = None


@dataclass(frozen=True)
class DigitalFormula(Formula):
    predicate_name: str
    if_true_amount: Decimal
    if_false_amount: Decimal = Decimal("0")


@dataclass(frozen=True)
class CouponMemoryFormula(Formula):
    base_formula: Formula
    memory_state_key: str = "memory_coupon_balance"


@dataclass(frozen=True)
class FormulaBinding:
    name: str
    formula: Formula


# ---------------------------------------------------------------------------
# Components: transfers and legs
# ---------------------------------------------------------------------------


class Component:
    component_id: str


class Transfer(Component):
    pass


@dataclass(frozen=True)
class PremiumTransfer(Transfer):
    component_id: str
    payer_side: Side
    amount: Money
    payment_date: date


@dataclass(frozen=True)
class RedemptionTransfer(Transfer):
    component_id: str
    amount: Money
    payment_date: date


@dataclass(frozen=True)
class FeeTransfer(Transfer):
    component_id: str
    amount: Money
    payment_date: date
    description: str


class Leg(Component):
    pass


@dataclass(frozen=True)
class SettlementLeg(Leg):
    component_id: str
    underlier: UnderlierRef
    side: Side
    quantity: Decimal
    settlement_date: date
    settlement_style: SettlementStyle
    price: Decimal
    currency: Currency


@dataclass(frozen=True)
class OptionExerciseLeg(Leg):
    component_id: str
    underlier: UnderlierRef
    side: Side
    option_type: OptionType
    quantity: Decimal
    strike: Decimal
    expiry_date: date
    settlement_style: SettlementStyle
    currency: Currency


@dataclass(frozen=True)
class CouponLeg(Leg):
    component_id: str
    reference: ReferenceRef
    notional: SteppedDecimal
    payment_schedule: DateListSchedule
    rate_formula_name: str
    currency: Currency
    day_count: DayCount = DayCount.ACT_365F


@dataclass(frozen=True)
class FundingLeg(Leg):
    component_id: str
    pay_receive: PayReceive
    notional: SteppedDecimal
    rate_formula_name: str
    payment_schedule: DateListSchedule
    currency: Currency
    day_count: DayCount = DayCount.ACT_360


@dataclass(frozen=True)
class FxWindowLeg(Leg):
    component_id: str
    currency_pair: UnderlierRef
    buy_amount: Decimal
    payoff_formula_name: str
    fixing_schedule: DateListSchedule
    payment_schedule: DateListSchedule
    settlement_currency: Currency


# ---------------------------------------------------------------------------
# Mechanisms
# ---------------------------------------------------------------------------


class Mechanism(Component):
    kind: MechanismKind


@dataclass(frozen=True)
class KnockOutMechanism(Mechanism):
    component_id: str
    kind: MechanismKind = MechanismKind.KNOCK_OUT
    predicate: Predicate = field(
        default_factory=lambda: BarrierPredicate(
            underlier=UnderlierRef("UNKNOWN"),
            direction=BarrierDirection.UP,
            level=Decimal("0"),
            observation_schedule=DateListSchedule(()),
        )
    )
    deactivate_components: tuple[str, ...] = ()
    redemption_on_trigger: Optional[RedemptionTransfer] = None
    state_flag_name: str = "knocked_out"


@dataclass(frozen=True)
class KnockInMechanism(Mechanism):
    component_id: str
    kind: MechanismKind = MechanismKind.KNOCK_IN
    predicate: Predicate = field(
        default_factory=lambda: BarrierPredicate(
            underlier=UnderlierRef("UNKNOWN"),
            direction=BarrierDirection.DOWN,
            level=Decimal("0"),
            observation_schedule=DateListSchedule(()),
        )
    )
    activate_components: tuple[str, ...] = ()
    state_flag_name: str = "knocked_in"


@dataclass(frozen=True)
class CouponMemoryMechanism(Mechanism):
    component_id: str
    target_leg_id: str
    state_key: str = "memory_coupon_balance"
    kind: MechanismKind = MechanismKind.COUPON_MEMORY


@dataclass(frozen=True)
class StepUpMechanism(Mechanism):
    component_id: str
    target_formula_name: str
    stepped_values: SteppedDecimal
    kind: MechanismKind = MechanismKind.STEP_UP


@dataclass(frozen=True)
class AccumulateUntilTargetMechanism(Mechanism):
    component_id: str
    source_leg_id: str
    state_key: str
    target_amount: Decimal
    accumulation_currency: Currency
    terminate_on_reach: bool = True
    kind: MechanismKind = MechanismKind.ACCUMULATE_UNTIL_TARGET


@dataclass(frozen=True)
class ExerciseMechanism(Mechanism):
    component_id: str
    exercise_schedule: DateListSchedule
    exercisable_component_ids: tuple[str, ...]
    kind: MechanismKind = MechanismKind.EXERCISE


@dataclass(frozen=True)
class AutoCallMechanism(Mechanism):
    component_id: str
    predicate: Predicate
    observation_schedule: DateListSchedule
    terminate_on_trigger: bool = True
    redemption_on_trigger: Optional[RedemptionTransfer] = None
    state_flag_name: str = "autocalled"
    kind: MechanismKind = MechanismKind.AUTOCALL


@dataclass(frozen=True)
class AmortizationMechanism(Mechanism):
    component_id: str
    target_leg_id: str
    amortization_schedule: DateListSchedule
    remaining_notional: SteppedDecimal
    kind: MechanismKind = MechanismKind.AMORTIZATION


@dataclass(frozen=True)
class NotionalResetMechanism(Mechanism):
    """
    Observation-driven reset of outstanding notional.

    target_leg_ids and state_keys are aligned positionally. For most use cases they are
    the same logical pair, e.g.
      target_leg_ids=("pay_leg",)
      state_keys=("current_notional_pay_leg",)
    """

    component_id: str
    target_leg_ids: tuple[str, ...]
    reference: UnderlierRef
    reset_schedule: DateListSchedule
    formula_name: str
    state_keys: tuple[str, ...]
    kind: MechanismKind = MechanismKind.NOTIONAL_RESET


MechanismType = Union[
    KnockOutMechanism,
    KnockInMechanism,
    CouponMemoryMechanism,
    StepUpMechanism,
    AccumulateUntilTargetMechanism,
    ExerciseMechanism,
    AutoCallMechanism,
    AmortizationMechanism,
    NotionalResetMechanism,
]


# ---------------------------------------------------------------------------
# Product form and templates
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContractForm:
    form_id: str
    form_kind: str
    parties: dict[str, str]
    references: tuple[ReferenceRef, ...]
    transfers: tuple[Transfer, ...]
    legs: tuple[Leg, ...]
    formulas: tuple[FormulaBinding, ...]
    mechanisms: tuple[MechanismType, ...]
    overrides: tuple[CashflowOverride, ...] = ()
    schedule_patches: tuple[SchedulePatch, ...] = ()
    tags: dict[str, str] = field(default_factory=dict)

    def formula_by_name(self, name: str) -> Formula:
        for binding in self.formulas:
            if binding.name == name:
                return binding.formula
        raise KeyError(f"Unknown formula name: {name}")

    def leg_by_id(self, component_id: str) -> Leg:
        for leg in self.legs:
            if leg.component_id == component_id:
                return leg
        raise KeyError(f"Unknown leg id: {component_id}")

    def transfer_by_id(self, component_id: str) -> Transfer:
        for transfer in self.transfers:
            if transfer.component_id == component_id:
                return transfer
        raise KeyError(f"Unknown transfer id: {component_id}")

    def validate(self) -> None:
        component_ids: set[str] = set()
        for component in (*self.transfers, *self.legs, *self.mechanisms):
            if component.component_id in component_ids:
                raise ValueError(f"Duplicate component_id: {component.component_id}")
            component_ids.add(component.component_id)

        formula_names: set[str] = set()
        for binding in self.formulas:
            if binding.name in formula_names:
                raise ValueError(f"Duplicate formula name: {binding.name}")
            formula_names.add(binding.name)

        for leg in self.legs:
            if isinstance(leg, (CouponLeg, FundingLeg)) and leg.rate_formula_name not in formula_names:
                raise ValueError(f"Leg {leg.component_id} refers to unknown formula {leg.rate_formula_name}")
            if isinstance(leg, FxWindowLeg) and leg.payoff_formula_name not in formula_names:
                raise ValueError(f"Leg {leg.component_id} refers to unknown formula {leg.payoff_formula_name}")

        for mech in self.mechanisms:
            if isinstance(mech, StepUpMechanism) and mech.target_formula_name not in formula_names:
                raise ValueError(f"Step-up mechanism targets unknown formula {mech.target_formula_name}")
            if isinstance(mech, NotionalResetMechanism):
                if mech.formula_name not in formula_names:
                    raise ValueError(f"Notional reset mechanism refers to unknown formula {mech.formula_name}")
                if len(mech.target_leg_ids) != len(mech.state_keys):
                    raise ValueError("Notional reset mechanism target_leg_ids/state_keys length mismatch")
                for leg_id in mech.target_leg_ids:
                    leg = self.leg_by_id(leg_id)
                    if not isinstance(leg, (FundingLeg, CouponLeg)):
                        raise ValueError(f"Notional reset target leg must be FundingLeg/CouponLeg: {leg_id}")

        for override in self.overrides:
            if override.component_id not in component_ids:
                raise ValueError(f"Override references unknown component {override.component_id}")


class InputTemplate:
    template_kind: str


@dataclass(frozen=True)
class ForwardInputTemplate(InputTemplate):
    template_kind: Literal["FORWARD"] = "FORWARD"
    realization: Literal["OUTRIGHT", "PREPAID"] = "OUTRIGHT"
    underlier: UnderlierRef = field(default_factory=lambda: UnderlierRef("UNKNOWN"))
    side: Side = Side.BUY
    quantity: Decimal = Decimal("0")
    strike: Decimal = Decimal("0")
    expiry_date: date = field(default_factory=date.today)
    settlement_date: date = field(default_factory=date.today)
    settlement_style: SettlementStyle = SettlementStyle.PHYSICAL
    currency: Currency = Currency.JPY


@dataclass(frozen=True)
class SyntheticForwardInputTemplate(InputTemplate):
    template_kind: Literal["FORWARD"] = "FORWARD"
    realization: Literal["SYNTHETIC"] = "SYNTHETIC"
    underlier: UnderlierRef = field(default_factory=lambda: UnderlierRef("UNKNOWN"))
    side: Side = Side.BUY
    quantity: Decimal = Decimal("0")
    strike: Decimal = Decimal("0")
    expiry_date: date = field(default_factory=date.today)
    premium_currency: Currency = Currency.JPY
    settlement_style: SettlementStyle = SettlementStyle.CASH


@dataclass(frozen=True)
class VanillaOptionInputTemplate(InputTemplate):
    template_kind: Literal["VANILLA_OPTION"] = "VANILLA_OPTION"
    underlier: UnderlierRef = field(default_factory=lambda: UnderlierRef("UNKNOWN"))
    side: Side = Side.BUY
    option_type: OptionType = OptionType.CALL
    quantity: Decimal = Decimal("0")
    strike: Decimal = Decimal("0")
    expiry_date: date = field(default_factory=date.today)
    premium: Money = field(default_factory=lambda: Money(Decimal("0"), Currency.JPY))
    premium_payment_date: date = field(default_factory=date.today)
    settlement_style: SettlementStyle = SettlementStyle.CASH


@dataclass(frozen=True)
class SnowballInputTemplate(InputTemplate):
    template_kind: Literal["SNOWBALL"] = "SNOWBALL"
    underlier: UnderlierRef = field(default_factory=lambda: UnderlierRef("UNKNOWN", "EQ"))
    notional: Decimal = Decimal("0")
    currency: Currency = Currency.JPY
    coupon_schedule: DateListSchedule = field(default_factory=lambda: DateListSchedule(()))
    observation_schedule: DateListSchedule = field(default_factory=lambda: DateListSchedule(()))
    base_coupon_rate: Decimal = Decimal("0")
    knock_out_barrier: Optional[Decimal] = None
    coupon_memory: bool = True
    step_up_coupon_rate: Optional[Decimal] = None
    knock_out_redemption_amount: Optional[Decimal] = None


@dataclass(frozen=True)
class TarfInputTemplate(InputTemplate):
    template_kind: Literal["TARF"] = "TARF"
    currency_pair: UnderlierRef = field(default_factory=lambda: UnderlierRef("USDJPY", "FX"))
    buy_amount: Decimal = Decimal("0")
    strike: Decimal = Decimal("0")
    fixing_schedule: DateListSchedule = field(default_factory=lambda: DateListSchedule(()))
    payment_schedule: DateListSchedule = field(default_factory=lambda: DateListSchedule(()))
    settlement_currency: Currency = Currency.JPY
    target_amount: Decimal = Decimal("0")
    accumulation_currency: Currency = Currency.JPY
    leverage_above_strike: Optional[Decimal] = None
    leverage_below_strike: Optional[Decimal] = None
    terminate_on_target: bool = True


@dataclass(frozen=True)
class MtMNotionalSwapInputTemplate(InputTemplate):
    template_kind: Literal["MTM_NOTIONAL_SWAP"] = "MTM_NOTIONAL_SWAP"
    form_kind: Literal["MTM_XCCY_SWAP"] = "MTM_XCCY_SWAP"
    fx_reference: UnderlierRef = field(default_factory=lambda: UnderlierRef("USDJPY", "FX"))
    pay_currency: Currency = Currency.JPY
    receive_currency: Currency = Currency.USD
    pay_initial_notional: Decimal = Decimal("0")
    receive_initial_notional: Decimal = Decimal("0")
    base_fx: Decimal = Decimal("0")
    effective_date: date = field(default_factory=date.today)
    maturity_date: date = field(default_factory=date.today)
    coupon_schedule: DateListSchedule = field(default_factory=lambda: DateListSchedule(()))
    reset_schedule: DateListSchedule = field(default_factory=lambda: DateListSchedule(()))
    principal_exchange_mode: PrincipalExchangeMode = PrincipalExchangeMode.INITIAL_AND_FINAL
    principal_exchange_schedule: DateListSchedule = field(default_factory=lambda: DateListSchedule(()))
    final_exchange_notional_source: FinalExchangeNotionalSource = FinalExchangeNotionalSource.CURRENT
    pay_rate_formula: FloatingRateFormula = field(
        default_factory=lambda: FloatingRateFormula(index_name="TONA", spread=SteppedDecimal(Decimal("0")))
    )
    receive_rate_formula: FloatingRateFormula = field(
        default_factory=lambda: FloatingRateFormula(index_name="SOFR", spread=SteppedDecimal(Decimal("0")))
    )
    reset_target_leg_ids: tuple[str, ...] = ("pay_leg",)
    reset_target_state_keys: tuple[str, ...] = ("current_notional_pay_leg",)
    scale_direction: Literal["DIRECT", "INVERSE"] = "DIRECT"
    rounding_digits: Optional[int] = None
    reset_floor: Optional[Decimal] = None
    reset_cap: Optional[Decimal] = None


AnyInputTemplate = Union[
    ForwardInputTemplate,
    SyntheticForwardInputTemplate,
    VanillaOptionInputTemplate,
    SnowballInputTemplate,
    TarfInputTemplate,
    MtMNotionalSwapInputTemplate,
]


# ---------------------------------------------------------------------------
# Builder: InputTemplate -> ContractForm
# ---------------------------------------------------------------------------


def build_contract_form(template: AnyInputTemplate) -> ContractForm:
    if isinstance(template, ForwardInputTemplate):
        form = _build_forward_form(template)
    elif isinstance(template, SyntheticForwardInputTemplate):
        form = _build_synthetic_forward_form(template)
    elif isinstance(template, VanillaOptionInputTemplate):
        form = _build_vanilla_option_form(template)
    elif isinstance(template, SnowballInputTemplate):
        form = _build_snowball_form(template)
    elif isinstance(template, TarfInputTemplate):
        form = _build_tarf_form(template)
    elif isinstance(template, MtMNotionalSwapInputTemplate):
        form = _build_mtm_notional_swap_form(template)
    else:
        raise TypeError(f"Unsupported template type: {type(template)}")
    form.validate()
    return form


def _build_forward_form(tpl: ForwardInputTemplate) -> ContractForm:
    settlement = SettlementLeg(
        component_id="settlement_leg",
        underlier=tpl.underlier,
        side=tpl.side,
        quantity=tpl.quantity,
        settlement_date=tpl.settlement_date,
        settlement_style=tpl.settlement_style,
        price=tpl.strike,
        currency=tpl.currency,
    )
    transfers: tuple[Transfer, ...] = ()
    form_kind = "FORWARD_OUTRIGHT"
    if tpl.realization == "PREPAID":
        transfers = (
            PremiumTransfer(
                component_id="prepaid_transfer",
                payer_side=tpl.side,
                amount=Money(tpl.quantity * tpl.strike, tpl.currency),
                payment_date=tpl.expiry_date,
            ),
        )
        settlement = replace(settlement, price=Decimal("0"))
        form_kind = "FORWARD_PREPAID"

    return ContractForm(
        form_id=f"FORM-{form_kind}",
        form_kind=form_kind,
        parties={"buyer": tpl.side.value},
        references=(tpl.underlier,),
        transfers=transfers,
        legs=(settlement,),
        formulas=(),
        mechanisms=(),
        tags={"template_kind": tpl.template_kind},
    )


def _build_synthetic_forward_form(tpl: SyntheticForwardInputTemplate) -> ContractForm:
    long_call = OptionExerciseLeg(
        component_id="long_call_leg",
        underlier=tpl.underlier,
        side=tpl.side,
        option_type=OptionType.CALL,
        quantity=tpl.quantity,
        strike=tpl.strike,
        expiry_date=tpl.expiry_date,
        settlement_style=tpl.settlement_style,
        currency=tpl.premium_currency,
    )
    short_put = OptionExerciseLeg(
        component_id="short_put_leg",
        underlier=tpl.underlier,
        side=tpl.side.opposite(),
        option_type=OptionType.PUT,
        quantity=tpl.quantity,
        strike=tpl.strike,
        expiry_date=tpl.expiry_date,
        settlement_style=tpl.settlement_style,
        currency=tpl.premium_currency,
    )
    return ContractForm(
        form_id="FORM-FORWARD-SYNTHETIC",
        form_kind="FORWARD_SYNTHETIC",
        parties={"buyer": tpl.side.value},
        references=(tpl.underlier,),
        transfers=(),
        legs=(long_call, short_put),
        formulas=(),
        mechanisms=(),
        tags={"template_kind": tpl.template_kind},
    )


def _build_vanilla_option_form(tpl: VanillaOptionInputTemplate) -> ContractForm:
    premium = PremiumTransfer(
        component_id="premium_transfer",
        payer_side=Side.BUY if tpl.side is Side.BUY else Side.SELL,
        amount=tpl.premium,
        payment_date=tpl.premium_payment_date,
    )
    option_leg = OptionExerciseLeg(
        component_id="option_leg",
        underlier=tpl.underlier,
        side=tpl.side,
        option_type=tpl.option_type,
        quantity=tpl.quantity,
        strike=tpl.strike,
        expiry_date=tpl.expiry_date,
        settlement_style=tpl.settlement_style,
        currency=tpl.premium.currency,
    )
    exercise = ExerciseMechanism(
        component_id="exercise_mechanism",
        exercise_schedule=DateListSchedule((tpl.expiry_date,)),
        exercisable_component_ids=("option_leg",),
    )
    return ContractForm(
        form_id=f"FORM-VANILLA-{tpl.option_type.value}-{tpl.side.value}",
        form_kind=f"VANILLA_{tpl.option_type.value}_{tpl.side.value}",
        parties={"holder": tpl.side.value},
        references=(tpl.underlier,),
        transfers=(premium,),
        legs=(option_leg,),
        formulas=(),
        mechanisms=(exercise,),
        tags={"template_kind": tpl.template_kind},
    )


def _build_snowball_form(tpl: SnowballInputTemplate) -> ContractForm:
    coupon_formula_name = "base_coupon_formula"
    formulas: list[FormulaBinding] = [
        FormulaBinding(coupon_formula_name, FixedRateFormula(SteppedDecimal(tpl.base_coupon_rate)))
    ]
    coupon_leg = CouponLeg(
        component_id="coupon_leg",
        reference=tpl.underlier,
        notional=SteppedDecimal(tpl.notional),
        payment_schedule=tpl.coupon_schedule,
        rate_formula_name=coupon_formula_name,
        currency=tpl.currency,
    )
    mechanisms: list[MechanismType] = []
    if tpl.coupon_memory:
        memory_formula_name = "memory_coupon_formula"
        formulas = [
            FormulaBinding(memory_formula_name, CouponMemoryFormula(FixedRateFormula(SteppedDecimal(tpl.base_coupon_rate))))
        ]
        coupon_leg = replace(coupon_leg, rate_formula_name=memory_formula_name)
        mechanisms.append(CouponMemoryMechanism(component_id="coupon_memory", target_leg_id="coupon_leg"))
    if tpl.step_up_coupon_rate is not None:
        mechanisms.append(
            StepUpMechanism(
                component_id="coupon_step_up",
                target_formula_name=coupon_leg.rate_formula_name,
                stepped_values=SteppedDecimal(tpl.step_up_coupon_rate),
            )
        )

    transfers: list[Transfer] = []
    if tpl.knock_out_barrier is not None:
        ko_redemption = None
        if tpl.knock_out_redemption_amount is not None and tpl.coupon_schedule.dates:
            ko_redemption = RedemptionTransfer(
                component_id="ko_redemption",
                amount=Money(tpl.knock_out_redemption_amount, tpl.currency),
                payment_date=tpl.coupon_schedule.sorted_dates()[-1],
            )
            transfers.append(ko_redemption)
        mechanisms.append(
            KnockOutMechanism(
                component_id="knock_out",
                predicate=BarrierPredicate(
                    underlier=tpl.underlier,
                    direction=BarrierDirection.UP,
                    level=tpl.knock_out_barrier,
                    observation_schedule=tpl.observation_schedule,
                    observation_kind=ObservationKind.CLOSE,
                ),
                deactivate_components=("coupon_leg",),
                redemption_on_trigger=ko_redemption,
            )
        )

    return ContractForm(
        form_id="FORM-SNOWBALL",
        form_kind="SNOWBALL",
        parties={},
        references=(tpl.underlier,),
        transfers=tuple(transfers),
        legs=(coupon_leg,),
        formulas=tuple(formulas),
        mechanisms=tuple(mechanisms),
        tags={"template_kind": tpl.template_kind},
    )


def _build_tarf_form(tpl: TarfInputTemplate) -> ContractForm:
    payoff_formula_name = "fx_forward_like_formula"
    formulas = (
        FormulaBinding(
            payoff_formula_name,
            FxForwardPayoffFormula(
                strike=SteppedDecimal(tpl.strike),
                leverage_above_strike=tpl.leverage_above_strike,
                leverage_below_strike=tpl.leverage_below_strike,
            ),
        ),
    )
    fx_leg = FxWindowLeg(
        component_id="fx_window_leg",
        currency_pair=tpl.currency_pair,
        buy_amount=tpl.buy_amount,
        payoff_formula_name=payoff_formula_name,
        fixing_schedule=tpl.fixing_schedule,
        payment_schedule=tpl.payment_schedule,
        settlement_currency=tpl.settlement_currency,
    )
    accumulation = AccumulateUntilTargetMechanism(
        component_id="target_accumulation",
        source_leg_id="fx_window_leg",
        state_key="accumulated_target_amount",
        target_amount=tpl.target_amount,
        accumulation_currency=tpl.accumulation_currency,
        terminate_on_reach=tpl.terminate_on_target,
    )
    return ContractForm(
        form_id="FORM-TARF",
        form_kind="TARF",
        parties={},
        references=(tpl.currency_pair,),
        transfers=(),
        legs=(fx_leg,),
        formulas=formulas,
        mechanisms=(accumulation,),
        tags={"template_kind": tpl.template_kind},
    )


def _build_mtm_notional_swap_form(tpl: MtMNotionalSwapInputTemplate) -> ContractForm:
    pay_formula_name = "pay_rate_formula"
    receive_formula_name = "receive_rate_formula"
    reset_formula_name = "mtm_reset_formula"

    formulas = (
        FormulaBinding(pay_formula_name, tpl.pay_rate_formula),
        FormulaBinding(receive_formula_name, tpl.receive_rate_formula),
        FormulaBinding(
            reset_formula_name,
            MtMNotionalResetFormula(
                base_notional=tpl.pay_initial_notional,
                base_reference_value=tpl.base_fx,
                rounding_digits=tpl.rounding_digits,
                scale_direction=tpl.scale_direction,
                floor=tpl.reset_floor,
                cap=tpl.reset_cap,
            ),
        ),
    )

    pay_leg = FundingLeg(
        component_id="pay_leg",
        pay_receive=PayReceive.PAY,
        notional=SteppedDecimal(tpl.pay_initial_notional),
        rate_formula_name=pay_formula_name,
        payment_schedule=tpl.coupon_schedule,
        currency=tpl.pay_currency,
        day_count=DayCount.ACT_360,
    )
    receive_leg = FundingLeg(
        component_id="receive_leg",
        pay_receive=PayReceive.RECEIVE,
        notional=SteppedDecimal(tpl.receive_initial_notional),
        rate_formula_name=receive_formula_name,
        payment_schedule=tpl.coupon_schedule,
        currency=tpl.receive_currency,
        day_count=DayCount.ACT_360,
    )

    transfers: list[Transfer] = []
    px_dates = tpl.principal_exchange_schedule.sorted_dates()
    if tpl.principal_exchange_mode in {PrincipalExchangeMode.INITIAL_ONLY, PrincipalExchangeMode.INITIAL_AND_FINAL} and px_dates:
        transfers.extend(
            [
                RedemptionTransfer(
                    component_id="initial_exchange_pay",
                    amount=Money(tpl.pay_initial_notional, tpl.pay_currency),
                    payment_date=px_dates[0],
                ),
                RedemptionTransfer(
                    component_id="initial_exchange_receive",
                    amount=Money(tpl.receive_initial_notional, tpl.receive_currency),
                    payment_date=px_dates[0],
                ),
            ]
        )
    if tpl.principal_exchange_mode is PrincipalExchangeMode.INITIAL_AND_FINAL and px_dates:
        transfers.extend(
            [
                RedemptionTransfer(
                    component_id="final_exchange_pay",
                    amount=Money(
                        tpl.pay_initial_notional if tpl.final_exchange_notional_source is FinalExchangeNotionalSource.ORIGINAL else Decimal("0"),
                        tpl.pay_currency,
                    ),
                    payment_date=px_dates[-1],
                ),
                RedemptionTransfer(
                    component_id="final_exchange_receive",
                    amount=Money(
                        tpl.receive_initial_notional if tpl.final_exchange_notional_source is FinalExchangeNotionalSource.ORIGINAL else Decimal("0"),
                        tpl.receive_currency,
                    ),
                    payment_date=px_dates[-1],
                ),
            ]
        )

    reset_mechanism = NotionalResetMechanism(
        component_id="mtm_notional_reset",
        target_leg_ids=tpl.reset_target_leg_ids,
        reference=tpl.fx_reference,
        reset_schedule=tpl.reset_schedule,
        formula_name=reset_formula_name,
        state_keys=tpl.reset_target_state_keys,
    )

    return ContractForm(
        form_id="FORM-MTM-XCCY-SWAP",
        form_kind=tpl.form_kind,
        parties={"pay_leg_party": "PAY_LEG", "receive_leg_party": "RECEIVE_LEG"},
        references=(tpl.fx_reference,),
        transfers=tuple(transfers),
        legs=(pay_leg, receive_leg),
        formulas=formulas,
        mechanisms=(reset_mechanism,),
        tags={
            "template_kind": tpl.template_kind,
            "principal_exchange_mode": tpl.principal_exchange_mode.value,
            "final_exchange_notional_source": tpl.final_exchange_notional_source.value,
        },
    )


# ---------------------------------------------------------------------------
# Runtime state and realized events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObservationRecord:
    observation_date: date
    source: str
    value: Decimal


@dataclass(frozen=True)
class RealizedCashflow:
    payment_date: date
    component_id: str
    amount: Money
    description: str


@dataclass
class RuntimeState:
    active_component_ids: set[str] = field(default_factory=set)
    flags: dict[str, bool] = field(default_factory=dict)
    numeric_state: dict[str, Decimal] = field(default_factory=dict)
    observations: list[ObservationRecord] = field(default_factory=list)
    realized_cashflows: list[RealizedCashflow] = field(default_factory=list)

    @classmethod
    def initial_from_form(cls, form: ContractForm) -> "RuntimeState":
        active = {leg.component_id for leg in form.legs} | {t.component_id for t in form.transfers}
        state = cls(active_component_ids=active)
        for leg in form.legs:
            if isinstance(leg, (CouponLeg, FundingLeg)):
                state.numeric_state[f"current_notional_{leg.component_id}"] = leg.notional.initial
        return state

    def is_active(self, component_id: str) -> bool:
        return component_id in self.active_component_ids

    def deactivate(self, component_id: str) -> None:
        self.active_component_ids.discard(component_id)

    def activate(self, component_id: str) -> None:
        self.active_component_ids.add(component_id)


# ---------------------------------------------------------------------------
# Formula evaluation helpers
# ---------------------------------------------------------------------------


def evaluate_mtm_notional_reset_formula(
    formula: MtMNotionalResetFormula, observed_reference: Decimal
) -> Decimal:
    if formula.base_reference_value == Decimal("0"):
        raise ZeroDivisionError("base_reference_value must not be zero")
    if formula.scale_direction == "DIRECT":
        value = formula.base_notional * observed_reference / formula.base_reference_value
    else:
        if observed_reference == Decimal("0"):
            raise ZeroDivisionError("observed_reference must not be zero for inverse scaling")
        value = formula.base_notional * formula.base_reference_value / observed_reference
    if formula.floor is not None:
        value = max(value, formula.floor)
    if formula.cap is not None:
        value = min(value, formula.cap)
    if formula.rounding_digits is not None:
        quantum = Decimal("1").scaleb(-formula.rounding_digits)
        value = value.quantize(quantum, rounding=ROUND_HALF_UP)
    return value


# ---------------------------------------------------------------------------
# State queries and event processing
# ---------------------------------------------------------------------------


def current_notional_for_leg(form: ContractForm, state: RuntimeState, leg_id: str) -> Decimal:
    key = f"current_notional_{leg_id}"
    if key in state.numeric_state:
        return state.numeric_state[key]
    leg = form.leg_by_id(leg_id)
    if isinstance(leg, (CouponLeg, FundingLeg)):
        return leg.notional.initial
    raise KeyError(f"No current notional available for leg: {leg_id}")


def apply_observation(form: ContractForm, state: RuntimeState, observation: ObservationRecord) -> None:
    state.observations.append(observation)
    for mech in form.mechanisms:
        if isinstance(mech, KnockOutMechanism):
            _apply_knock_out(form, state, mech, observation)
        elif isinstance(mech, AccumulateUntilTargetMechanism):
            current = state.numeric_state.get(mech.state_key, Decimal("0"))
            if current >= mech.target_amount and mech.terminate_on_reach:
                state.flags["terminated"] = True
                state.deactivate(mech.source_leg_id)
        elif isinstance(mech, NotionalResetMechanism):
            _apply_notional_reset(form, state, mech, observation)


def _apply_knock_out(
    form: ContractForm, state: RuntimeState, mech: KnockOutMechanism, observation: ObservationRecord
) -> None:
    pred = mech.predicate
    if not isinstance(pred, BarrierPredicate):
        return
    if pred.underlier.symbol != observation.source:
        return
    if observation.observation_date not in pred.observation_schedule.dates:
        return
    if _barrier_hit(pred.direction, observation.value, pred.level):
        state.flags[mech.state_flag_name] = True
        for component_id in mech.deactivate_components:
            state.deactivate(component_id)
        if mech.redemption_on_trigger is not None:
            state.realized_cashflows.append(
                RealizedCashflow(
                    payment_date=mech.redemption_on_trigger.payment_date,
                    component_id=mech.redemption_on_trigger.component_id,
                    amount=mech.redemption_on_trigger.amount,
                    description=f"Triggered redemption by {mech.component_id}",
                )
            )


def _apply_notional_reset(
    form: ContractForm, state: RuntimeState, mech: NotionalResetMechanism, observation: ObservationRecord
) -> None:
    if mech.reference.symbol != observation.source:
        return
    if observation.observation_date not in mech.reset_schedule.dates:
        return
    formula = form.formula_by_name(mech.formula_name)
    if not isinstance(formula, MtMNotionalResetFormula):
        raise TypeError(f"Formula {mech.formula_name} is not an MtMNotionalResetFormula")
    new_notional = evaluate_mtm_notional_reset_formula(formula, observation.value)
    for leg_id, state_key in zip(mech.target_leg_ids, mech.state_keys):
        # Keep both explicit state_key and conventional current_notional_<leg>
        state.numeric_state[state_key] = new_notional
        state.numeric_state[f"current_notional_{leg_id}"] = new_notional


def apply_realized_amount(
    form: ContractForm,
    state: RuntimeState,
    source_leg_id: str,
    amount: Money,
    payment_date: date,
    description: str,
) -> None:
    state.realized_cashflows.append(
        RealizedCashflow(
            payment_date=payment_date,
            component_id=source_leg_id,
            amount=amount,
            description=description,
        )
    )
    for mech in form.mechanisms:
        if isinstance(mech, AccumulateUntilTargetMechanism) and mech.source_leg_id == source_leg_id:
            if amount.currency != mech.accumulation_currency:
                continue
            current = state.numeric_state.get(mech.state_key, Decimal("0"))
            current += amount.amount
            state.numeric_state[mech.state_key] = current
            if current >= mech.target_amount and mech.terminate_on_reach:
                state.flags["terminated"] = True
                state.deactivate(mech.source_leg_id)


def realize_coupon_cashflow(
    form: ContractForm,
    state: RuntimeState,
    leg_id: str,
    payment_date: date,
    accrual_factor: Decimal,
    observed_rate: Optional[Decimal] = None,
) -> RealizedCashflow:
    leg = form.leg_by_id(leg_id)
    if not isinstance(leg, (CouponLeg, FundingLeg)):
        raise TypeError("Coupon realization is only supported for CouponLeg/FundingLeg")
    if not state.is_active(leg_id):
        raise ValueError(f"Leg {leg_id} is inactive")

    notional = current_notional_for_leg(form, state, leg_id)
    formula = form.formula_by_name(leg.rate_formula_name)
    effective_rate = _resolve_rate_formula(formula, payment_date, observed_rate)
    amount_abs = notional * effective_rate * accrual_factor
    signed_amount = amount_abs
    description = f"Coupon realization for {leg_id}"

    if isinstance(leg, FundingLeg) and leg.pay_receive is PayReceive.PAY:
        signed_amount = -amount_abs
        description = f"Pay coupon realization for {leg_id}"
    elif isinstance(leg, FundingLeg):
        description = f"Receive coupon realization for {leg_id}"

    cf = RealizedCashflow(
        payment_date=payment_date,
        component_id=leg_id,
        amount=Money(signed_amount, leg.currency),
        description=description,
    )
    state.realized_cashflows.append(cf)
    return cf


def realize_fx_window_cashflow(
    form: ContractForm,
    state: RuntimeState,
    leg_id: str,
    fixing_date: date,
    payment_date: date,
    observed_fx: Decimal,
) -> RealizedCashflow:
    leg = form.leg_by_id(leg_id)
    if not isinstance(leg, FxWindowLeg):
        raise TypeError("FX window realization is only supported for FxWindowLeg")
    if not state.is_active(leg_id):
        raise ValueError(f"Leg {leg_id} is inactive")
    if fixing_date not in leg.fixing_schedule.dates:
        raise ValueError(f"Fixing date {fixing_date} is not in leg fixing schedule")

    formula = form.formula_by_name(leg.payoff_formula_name)
    if not isinstance(formula, FxForwardPayoffFormula):
        raise TypeError("FX window leg requires FxForwardPayoffFormula")

    strike = formula.strike.value_on(fixing_date)
    payoff_ratio = observed_fx - strike
    if payoff_ratio >= 0 and formula.leverage_above_strike is not None:
        payoff_ratio *= formula.leverage_above_strike
    if payoff_ratio < 0 and formula.leverage_below_strike is not None:
        payoff_ratio *= formula.leverage_below_strike

    amount = leg.buy_amount * payoff_ratio
    cf = RealizedCashflow(
        payment_date=payment_date,
        component_id=leg_id,
        amount=Money(amount, leg.settlement_currency),
        description=f"FX window realization for {leg_id}",
    )
    state.realized_cashflows.append(cf)
    return cf


def realize_principal_exchange(
    form: ContractForm,
    state: RuntimeState,
    component_id: str,
) -> RealizedCashflow:
    transfer = form.transfer_by_id(component_id)
    if not isinstance(transfer, RedemptionTransfer):
        raise TypeError("Principal exchange realization expects RedemptionTransfer")

    amount = transfer.amount
    # Dynamic final exchange support for MtM XCCY swap.
    if form.form_kind == "MTM_XCCY_SWAP" and component_id in {"final_exchange_pay", "final_exchange_receive"}:
        source = form.tags.get("final_exchange_notional_source", FinalExchangeNotionalSource.CURRENT.value)
        if source == FinalExchangeNotionalSource.CURRENT.value:
            if component_id == "final_exchange_pay":
                amount = Money(current_notional_for_leg(form, state, "pay_leg"), amount.currency)
            elif component_id == "final_exchange_receive":
                amount = Money(current_notional_for_leg(form, state, "receive_leg"), amount.currency)

    cf = RealizedCashflow(
        payment_date=transfer.payment_date,
        component_id=component_id,
        amount=amount,
        description=f"Principal exchange for {component_id}",
    )
    state.realized_cashflows.append(cf)
    return cf


def build_event_timeline(form: ContractForm) -> tuple[date, ...]:
    out: set[date] = set()
    for leg in form.legs:
        if isinstance(leg, (CouponLeg, FundingLeg)):
            out.update(leg.payment_schedule.dates)
        elif isinstance(leg, FxWindowLeg):
            out.update(leg.fixing_schedule.dates)
            out.update(leg.payment_schedule.dates)
        elif isinstance(leg, SettlementLeg):
            out.add(leg.settlement_date)
        elif isinstance(leg, OptionExerciseLeg):
            out.add(leg.expiry_date)
    for t in form.transfers:
        if isinstance(t, (PremiumTransfer, RedemptionTransfer, FeeTransfer)):
            out.add(t.payment_date)
    for mech in form.mechanisms:
        if isinstance(mech, (ExerciseMechanism, AutoCallMechanism, NotionalResetMechanism, AmortizationMechanism)):
            if hasattr(mech, "exercise_schedule"):
                out.update(mech.exercise_schedule.dates)
            if hasattr(mech, "observation_schedule"):
                out.update(mech.observation_schedule.dates)
            if hasattr(mech, "reset_schedule"):
                out.update(mech.reset_schedule.dates)
            if hasattr(mech, "amortization_schedule"):
                out.update(mech.amortization_schedule.dates)
        elif isinstance(mech, (KnockOutMechanism, KnockInMechanism)):
            pred = mech.predicate
            if isinstance(pred, BarrierPredicate):
                out.update(pred.observation_schedule.dates)
    return tuple(sorted(out))


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _resolve_rate_formula(formula: Formula, when: date, observed_rate: Optional[Decimal]) -> Decimal:
    if isinstance(formula, FixedRateFormula):
        return formula.rate.value_on(when)
    if isinstance(formula, FloatingRateFormula):
        rate = (observed_rate or Decimal("0")) + formula.spread.value_on(when)
        if formula.floor is not None:
            rate = max(rate, formula.floor)
        if formula.cap is not None:
            rate = min(rate, formula.cap)
        return rate
    if isinstance(formula, CouponMemoryFormula):
        return _resolve_rate_formula(formula.base_formula, when, observed_rate)
    raise TypeError(f"Unsupported rate formula type: {type(formula)}")


def _barrier_hit(direction: BarrierDirection, observed: Decimal, level: Decimal) -> bool:
    if direction is BarrierDirection.UP:
        return observed >= level
    return observed <= level


def _ref_symbol(ref: ReferenceRef) -> str:
    if isinstance(ref, UnderlierRef):
        return ref.symbol
    return "+".join(u.symbol for u in ref.underliers)


# ---------------------------------------------------------------------------
# Normalized view
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedExposure:
    reference_symbol: str
    exposure_kind: str
    side: Optional[Union[Side, PayReceive]]
    quantity: Optional[Decimal]
    strike: Optional[Decimal]
    maturity_date: Optional[date]
    settlement_currency: Optional[Currency]


@dataclass(frozen=True)
class NormalizedView:
    normalized_kind: str
    exposures: tuple[NormalizedExposure, ...]
    source_form_kind: str



def normalize_contract_form(form: ContractForm) -> NormalizedView:
    exposures: list[NormalizedExposure] = []
    for leg in form.legs:
        if isinstance(leg, SettlementLeg):
            exposures.append(
                NormalizedExposure(
                    reference_symbol=leg.underlier.symbol,
                    exposure_kind="FORWARD_LIKE",
                    side=leg.side,
                    quantity=leg.quantity,
                    strike=leg.price,
                    maturity_date=leg.settlement_date,
                    settlement_currency=leg.currency,
                )
            )
        elif isinstance(leg, OptionExerciseLeg):
            exposures.append(
                NormalizedExposure(
                    reference_symbol=leg.underlier.symbol,
                    exposure_kind=f"OPTION_{leg.option_type.value}",
                    side=leg.side,
                    quantity=leg.quantity,
                    strike=leg.strike,
                    maturity_date=leg.expiry_date,
                    settlement_currency=leg.currency,
                )
            )
        elif isinstance(leg, CouponLeg):
            exposures.append(
                NormalizedExposure(
                    reference_symbol=_ref_symbol(leg.reference),
                    exposure_kind="COUPON_STREAM",
                    side=None,
                    quantity=leg.notional.initial,
                    strike=None,
                    maturity_date=leg.payment_schedule.sorted_dates()[-1] if leg.payment_schedule.dates else None,
                    settlement_currency=leg.currency,
                )
            )
        elif isinstance(leg, FundingLeg):
            exposures.append(
                NormalizedExposure(
                    reference_symbol=leg.currency.value,
                    exposure_kind="FUNDING_STREAM",
                    side=leg.pay_receive,
                    quantity=leg.notional.initial,
                    strike=None,
                    maturity_date=leg.payment_schedule.sorted_dates()[-1] if leg.payment_schedule.dates else None,
                    settlement_currency=leg.currency,
                )
            )
        elif isinstance(leg, FxWindowLeg):
            exposures.append(
                NormalizedExposure(
                    reference_symbol=leg.currency_pair.symbol,
                    exposure_kind="FX_FORWARD_WINDOW",
                    side=None,
                    quantity=leg.buy_amount,
                    strike=_extract_fx_strike(form, leg.payoff_formula_name),
                    maturity_date=leg.payment_schedule.sorted_dates()[-1] if leg.payment_schedule.dates else None,
                    settlement_currency=leg.settlement_currency,
                )
            )
    return NormalizedView(
        normalized_kind=_normalized_kind_for_form(form.form_kind),
        exposures=tuple(exposures),
        source_form_kind=form.form_kind,
    )



def _normalized_kind_for_form(form_kind: str) -> str:
    if form_kind.startswith("FORWARD"):
        return "FORWARD_LIKE"
    if form_kind.startswith("VANILLA"):
        return "OPTION"
    if form_kind == "SNOWBALL":
        return "PATH_DEPENDENT_COUPON"
    if form_kind == "TARF":
        return "TARGET_ACCUMULATING_FX"
    if form_kind == "MTM_XCCY_SWAP":
        return "MTM_CROSS_CURRENCY_SWAP"
    return "GENERIC_DERIVATIVE"



def _extract_fx_strike(form: ContractForm, formula_name: str) -> Optional[Decimal]:
    formula = form.formula_by_name(formula_name)
    if isinstance(formula, FxForwardPayoffFormula):
        return formula.strike.initial
    return None


# ---------------------------------------------------------------------------
# Smoke demo
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    usd_jpy = UnderlierRef("USDJPY", "FX")
    mtm_swap = build_contract_form(
        MtMNotionalSwapInputTemplate(
            fx_reference=usd_jpy,
            pay_currency=Currency.JPY,
            receive_currency=Currency.USD,
            pay_initial_notional=Decimal("150000000"),
            receive_initial_notional=Decimal("1000000"),
            base_fx=Decimal("150.00"),
            coupon_schedule=DateListSchedule((date(2026, 6, 30), date(2026, 12, 31))),
            reset_schedule=DateListSchedule((date(2026, 6, 28), date(2026, 12, 28))),
            principal_exchange_mode=PrincipalExchangeMode.INITIAL_AND_FINAL,
            principal_exchange_schedule=DateListSchedule((date(2026, 1, 5), date(2026, 12, 31))),
            final_exchange_notional_source=FinalExchangeNotionalSource.CURRENT,
        )
    )
    state = RuntimeState.initial_from_form(mtm_swap)
    apply_observation(mtm_swap, state, ObservationRecord(date(2026, 6, 28), "USDJPY", Decimal("155")))
    realize_coupon_cashflow(mtm_swap, state, "pay_leg", date(2026, 6, 30), Decimal("0.5"), Decimal("0.005"))
    realize_coupon_cashflow(mtm_swap, state, "receive_leg", date(2026, 6, 30), Decimal("0.5"), Decimal("0.004"))
    realize_principal_exchange(mtm_swap, state, "final_exchange_pay")
    print("timeline", build_event_timeline(mtm_swap))
    print("current pay notional", current_notional_for_leg(mtm_swap, state, "pay_leg"))
    for cf in state.realized_cashflows:
        print(cf)
