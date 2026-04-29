"""
contract_model_v2_2_full.py

Form-first derivative contract model v2.2.

Main change from v2.1:
- Target accumulation is represented by AccumulationValueRule, not TargetMetric/ClientGain enums.
- ContractPeriod / PeriodDateBinding / PeriodComponentGroup are first-class.
- Deactivation effects use ComponentSelector for period/group/range-based KO.

Carried over from v2.1:
- CouponStreamLeg no longer has an ambiguous `coupon_rule_id`.
- Coupon calculation is explicitly either rate-based or amount-based.
- RateRule returns only a rate. It never includes notional or accrual factor.
- AmountRule returns an amount directly. It is used when a cashflow cannot naturally
  be decomposed as notional * rate * accrual_factor.
- MtM reset is a QuantityRule used by a NotionalResetLifecycleRule; the observation
  belongs to the lifecycle event, not to the quantity rule itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Literal, Optional, Sequence, Union

ZERO = Decimal("0")
ONE = Decimal("1")


def D(x: str | int | Decimal) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def q(x: Decimal, digits: str = "0.00000001") -> Decimal:
    return x.quantize(Decimal(digits), rounding=ROUND_HALF_UP)


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


class SpreadDirection(str, Enum):
    LEFT_MINUS_RIGHT = "LEFT_MINUS_RIGHT"
    RIGHT_MINUS_LEFT = "RIGHT_MINUS_LEFT"


class DayCount(str, Enum):
    ACT_360 = "ACT/360"
    ACT_365F = "ACT/365F"
    THIRTY_360 = "30/360"


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: Currency


# ---------------------------------------------------------------------------
# Reference / Observable
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UnderlierRef:
    symbol: str
    kind: Literal["EQ", "FX", "IR", "CMDTY", "CREDIT", "OTHER"] = "OTHER"


@dataclass(frozen=True)
class FxPair:
    base_currency: Currency
    quote_currency: Currency

    @property
    def symbol(self) -> str:
        return f"{self.base_currency.value}{self.quote_currency.value}"


@dataclass(frozen=True)
class BasketRef:
    underliers: tuple[UnderlierRef, ...]
    weighting: Literal["EQUAL", "CUSTOM"] = "EQUAL"


ReferenceRef = Union[UnderlierRef, BasketRef]


class ObservationKind(str, Enum):
    SPOT = "SPOT"
    CLOSE = "CLOSE"
    OPEN = "OPEN"
    AVERAGE = "AVERAGE"
    MAX = "MAX"
    MIN = "MIN"
    WORST_OF = "WORST_OF"
    BEST_OF = "BEST_OF"


class ObservationStyle(str, Enum):
    EUROPEAN = "EUROPEAN"
    AMERICAN = "AMERICAN"
    BERMUDAN = "BERMUDAN"
    CONTINUOUS = "CONTINUOUS"


@dataclass(frozen=True)
class ObservableRef:
    observable_id: str
    reference: ReferenceRef
    kind: ObservationKind = ObservationKind.CLOSE
    description: str = ""


@dataclass(frozen=True)
class ObservationRuleRef:
    rule_id: str


@dataclass(frozen=True)
class FxObservable:
    pair: FxPair
    quotation: Literal["QUOTE_PER_BASE", "BASE_PER_QUOTE"] = "QUOTE_PER_BASE"
    source: str | None = None


@dataclass(frozen=True)
class FxObservationRule:
    observable: FxObservable
    schedule: "ScheduleRefLike"
    style: ObservationStyle = ObservationStyle.EUROPEAN
    kind: ObservationKind = ObservationKind.SPOT
    description: str = ""


# ---------------------------------------------------------------------------
# Schedule / Event
# ---------------------------------------------------------------------------

class BusinessDayConvention(str, Enum):
    NONE = "NONE"
    FOLLOWING = "FOLLOWING"
    PRECEDING = "PRECEDING"
    MODIFIED_FOLLOWING = "MODIFIED_FOLLOWING"


class OffsetUnit(str, Enum):
    CALENDAR_DAYS = "CALENDAR_DAYS"
    BUSINESS_DAYS = "BUSINESS_DAYS"


class DateRole(str, Enum):
    PAYMENT = "PAYMENT"
    FIXING = "FIXING"
    OBSERVATION = "OBSERVATION"
    EXERCISE = "EXERCISE"
    SETTLEMENT = "SETTLEMENT"
    RESET = "RESET"
    PRINCIPAL_EXCHANGE = "PRINCIPAL_EXCHANGE"
    ACCRUAL_START = "ACCRUAL_START"
    ACCRUAL_END = "ACCRUAL_END"
    DETERMINATION = "DETERMINATION"
    PREMIUM_PAYMENT = "PREMIUM_PAYMENT"
    FEE_PAYMENT = "FEE_PAYMENT"
    CUSTOM = "CUSTOM"


class ScheduleOwnerType(str, Enum):
    FORM = "FORM"
    LEG = "LEG"
    MECHANISM = "MECHANISM"
    TRANSFER = "TRANSFER"
    RULE = "RULE"


class BoundaryAlignment(str, Enum):
    CURRENT = "CURRENT"
    PREVIOUS = "PREVIOUS"
    NEXT = "NEXT"


@dataclass(frozen=True)
class DateListSchedule:
    dates: tuple[date, ...]

    def sorted_dates(self) -> tuple[date, ...]:
        return tuple(sorted(self.dates))


@dataclass(frozen=True)
class ScheduleNodeId:
    value: str


@dataclass(frozen=True)
class ScheduleRef:
    node_id: ScheduleNodeId


ScheduleRefLike = Union[DateListSchedule, ScheduleRef]


@dataclass(frozen=True)
class ScheduleOwner:
    owner_type: ScheduleOwnerType
    owner_id: str


@dataclass(frozen=True)
class ScheduleMeaning:
    roles: frozenset[DateRole]
    owner: ScheduleOwner
    custom_labels: tuple[str, ...] = ()

    def has_role(self, role: DateRole) -> bool:
        return role in self.roles


@dataclass(frozen=True)
class SchedulePattern:
    start_date: date
    end_date: date
    frequency: Literal["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "SEMI_ANNUAL", "ANNUAL"]
    business_day_convention: BusinessDayConvention = BusinessDayConvention.MODIFIED_FOLLOWING


@dataclass(frozen=True)
class PatternScheduleSource:
    pattern: SchedulePattern


@dataclass(frozen=True)
class ExplicitDateScheduleSource:
    dates: DateListSchedule


@dataclass(frozen=True)
class RelativeDateScheduleSource:
    base_ref: ScheduleRef
    offset: int
    unit: OffsetUnit = OffsetUnit.BUSINESS_DAYS
    business_day_convention: BusinessDayConvention = BusinessDayConvention.MODIFIED_FOLLOWING


@dataclass(frozen=True)
class BoundaryAlignedScheduleSource:
    base_ref: ScheduleRef
    alignment: BoundaryAlignment
    first_date: date | None = None
    last_date: date | None = None


ScheduleSource = Union[PatternScheduleSource, ExplicitDateScheduleSource, RelativeDateScheduleSource, BoundaryAlignedScheduleSource]


@dataclass(frozen=True)
class ScheduleNode:
    node_id: ScheduleNodeId
    meaning: ScheduleMeaning
    source: ScheduleSource
    description: str = ""


@dataclass(frozen=True)
class ObservationRule:
    rule_id: str
    observable_id: str
    schedule: ScheduleRefLike
    style: ObservationStyle = ObservationStyle.EUROPEAN
    kind_override: ObservationKind | None = None
    description: str = ""


# ---------------------------------------------------------------------------
# Decimal-like values / stepped parameters
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConstantDecimal:
    value: Decimal


@dataclass(frozen=True)
class DateStepPoint:
    effective_date: date
    value: Decimal


@dataclass(frozen=True)
class DateSteppedDecimal:
    initial: Decimal
    steps: tuple[DateStepPoint, ...] = ()


@dataclass(frozen=True)
class IndexStepPoint:
    effective_index: int
    value: Decimal


@dataclass(frozen=True)
class IndexSteppedDecimal:
    initial: Decimal
    steps: tuple[IndexStepPoint, ...] = ()


DecimalLike = Union[ConstantDecimal, DateSteppedDecimal, IndexSteppedDecimal, Decimal]


def decimal_value_on(value: DecimalLike, *, when: date | None = None, index: int | None = None) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, ConstantDecimal):
        return value.value
    if isinstance(value, DateSteppedDecimal):
        if when is None:
            return value.initial
        out = value.initial
        for step in sorted(value.steps, key=lambda x: x.effective_date):
            if step.effective_date <= when:
                out = step.value
        return out
    if isinstance(value, IndexSteppedDecimal):
        if index is None:
            return value.initial
        out = value.initial
        for step in sorted(value.steps, key=lambda x: x.effective_index):
            if step.effective_index <= index:
                out = step.value
        return out
    raise TypeError(f"Unsupported DecimalLike: {type(value)}")


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------

class Condition:
    condition_id: str


@dataclass(frozen=True)
class BarrierCondition(Condition):
    condition_id: str
    observation_rule_id: str
    direction: BarrierDirection
    level: Decimal


@dataclass(frozen=True)
class ComparisonCondition(Condition):
    condition_id: str
    left_state_key: str
    operator: ComparisonOp
    right_value: Decimal


@dataclass(frozen=True)
class TargetReachedCondition(Condition):
    condition_id: str
    accumulator_id: str
    operator: ComparisonOp
    target_value: Decimal


ConditionType = Union[BarrierCondition, ComparisonCondition, TargetReachedCondition]


# ---------------------------------------------------------------------------
# Determination rules
# ---------------------------------------------------------------------------

class DeterminationRule:
    rule_id: str


class QuantityRule(DeterminationRule):
    """Returns a quantity/notional, never a rate or amount."""


@dataclass(frozen=True)
class FixedQuantityRule(QuantityRule):
    rule_id: str
    quantity: DecimalLike


@dataclass(frozen=True)
class MtMResetQuantityRule(QuantityRule):
    """
    Pure conversion from observed reference value to new quantity.

    Observation timing/source is owned by NotionalResetLifecycleRule, not this rule.
    """
    rule_id: str
    base_quantity: Decimal
    base_reference_value: Decimal
    scale_direction: Literal["DIRECT", "INVERSE"] = "DIRECT"
    floor: Decimal | None = None
    cap: Decimal | None = None
    rounding_digits: int | None = None


class RateRule(DeterminationRule):
    """Returns a rate only. It must not include notional or accrual factor."""


@dataclass(frozen=True)
class FixedRateRule(RateRule):
    rule_id: str
    rate: DecimalLike


@dataclass(frozen=True)
class FloatingRateRule(RateRule):
    rule_id: str
    index_name: str
    fixing_observation_rule_id: str
    spread: DecimalLike = Decimal("0")
    floor: Decimal | None = None
    cap: Decimal | None = None


@dataclass(frozen=True)
class FxLinkedRateRule(RateRule):
    rule_id: str
    fx_observation_rule_id: str
    strike: DecimalLike
    leverage: DecimalLike = Decimal("1")
    floor: Decimal | None = None
    cap: Decimal | None = None


@dataclass(frozen=True)
class RangeAccrualRateRule(RateRule):
    rule_id: str
    base_rate_rule_id: str
    observation_rule_id: str
    lower_bound: Decimal | None = None
    upper_bound: Decimal | None = None


@dataclass(frozen=True)
class PRDCRateRule(RateRule):
    rule_id: str
    domestic_rate_rule_id: str
    foreign_rate_rule_id: str
    fx_observation_rule_id: str
    leverage: DecimalLike = Decimal("1")
    floor: Decimal | None = None
    cap: Decimal | None = None


class PayoffRule(DeterminationRule):
    """Generic payoff rule, mainly for option/right style components."""


@dataclass(frozen=True)
class VanillaOptionPayoffRule(PayoffRule):
    rule_id: str
    option_type: OptionType
    strike: DecimalLike
    quantity_rule_id: str


@dataclass(frozen=True)
class FxForwardPayoffRule(PayoffRule):
    rule_id: str
    pair: FxPair
    strike: DecimalLike
    base_quantity_rule_id: str
    leverage_above_strike: Decimal | None = None
    leverage_below_strike: Decimal | None = None


@dataclass(frozen=True)
class ConditionalPayoffRule(PayoffRule):
    rule_id: str
    condition_id: str
    if_true_amount: Money
    if_false_amount: Money


class AmountRule(DeterminationRule):
    """Returns a money amount directly. Use only when rate decomposition is unnatural."""


@dataclass(frozen=True)
class FixedAmountRule(AmountRule):
    rule_id: str
    amount: Money


@dataclass(frozen=True)
class FxForwardAmountRule(AmountRule):
    rule_id: str
    pair: FxPair
    fixing_observation_rule_id: str
    strike: DecimalLike
    base_quantity_rule_id: str
    settlement_currency: Currency
    leverage_above_strike: Decimal | None = None
    leverage_below_strike: Decimal | None = None


@dataclass(frozen=True)
class ConditionalAmountRule(AmountRule):
    rule_id: str
    condition_id: str
    if_true_amount_rule_id: str
    if_false_amount_rule_id: str | None = None


@dataclass(frozen=True)
class RatioForwardCouponAmountRule(AmountRule):
    """
    Amount-based coupon rule for coupon-swap form of ratio-forward-like economics.

    This rule is deliberately amount-based, not rate-based. It may refer to
    condition ids for sold-side KI, but it is not an option KnockIn mechanism.
    """
    rule_id: str
    pair: FxPair
    scheme: str
    side_role: Literal["BASE_DELIVERY", "QUOTE_DELIVERY"]
    bought_side_quantity_rule_id: str
    sold_side_quantity_rule_id: str
    sold_option_selector: str
    sold_side_condition_id: str | None = None


DeterminationRuleType = Union[
    FixedQuantityRule,
    MtMResetQuantityRule,
    FixedRateRule,
    FloatingRateRule,
    FxLinkedRateRule,
    RangeAccrualRateRule,
    PRDCRateRule,
    VanillaOptionPayoffRule,
    FxForwardPayoffRule,
    ConditionalPayoffRule,
    FixedAmountRule,
    FxForwardAmountRule,
    ConditionalAmountRule,
    RatioForwardCouponAmountRule,
]


# ---------------------------------------------------------------------------
# Coupon calculation specs
# ---------------------------------------------------------------------------

class CouponCalculationSpec:
    """Defines how a coupon amount is assembled for a CouponStreamLeg."""


@dataclass(frozen=True)
class RateBasedCouponCalculation(CouponCalculationSpec):
    """coupon_amount = notional * rate * accrual_factor."""
    notional_rule_id: str
    rate_rule_id: str
    accrual_start_schedule: ScheduleRefLike
    accrual_end_schedule: ScheduleRefLike
    day_count: DayCount = DayCount.ACT_365F


@dataclass(frozen=True)
class AmountBasedCouponCalculation(CouponCalculationSpec):
    """coupon_amount = amount_rule."""
    amount_rule_id: str


CouponCalculationType = Union[RateBasedCouponCalculation, AmountBasedCouponCalculation]


# ---------------------------------------------------------------------------
# Overlays / Modifiers
# ---------------------------------------------------------------------------

class OverlayRule:
    overlay_id: str


@dataclass(frozen=True)
class CapFloorOverlay(OverlayRule):
    overlay_id: str
    target_rule_id: str
    floor: Decimal | None = None
    cap: Decimal | None = None


@dataclass(frozen=True)
class LeverageOverlay(OverlayRule):
    overlay_id: str
    target_rule_id: str
    multiplier: Decimal


@dataclass(frozen=True)
class MemoryOverlay(OverlayRule):
    overlay_id: str
    target_rule_id: str
    state_key: str


@dataclass(frozen=True)
class StepOverlay(OverlayRule):
    overlay_id: str
    target_rule_id: str
    stepped_value: DecimalLike


OverlayRuleType = Union[CapFloorOverlay, LeverageOverlay, MemoryOverlay, StepOverlay]


# ---------------------------------------------------------------------------
# Economic actions / components
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PartyRef:
    party_id: str
    display_name: str


@dataclass(frozen=True)
class PartyRoleAssignment:
    role: str
    party_id: str


@dataclass(frozen=True)
class CounterpartySpec:
    book_party: PartyRef = field(default_factory=lambda: PartyRef("BOOK", "Book"))
    counterparty: PartyRef = field(default_factory=lambda: PartyRef("COUNTERPARTY", "Counterparty"))

    def both(self) -> tuple[PartyRef, PartyRef]:
        return (self.book_party, self.counterparty)


class Component:
    component_id: str


@dataclass(frozen=True)
class PremiumTransfer(Component):
    component_id: str
    payer_party_id: str
    receiver_party_id: str
    amount: Money
    payment_date: date


@dataclass(frozen=True)
class RedemptionTransfer(Component):
    component_id: str
    payer_party_id: str
    receiver_party_id: str
    amount: Money
    payment_date: date


@dataclass(frozen=True)
class FeeTransfer(Component):
    component_id: str
    payer_party_id: str
    receiver_party_id: str
    amount: Money
    payment_date: date
    description: str = ""


@dataclass(frozen=True)
class CouponStreamLeg(Component):
    component_id: str
    payer_party_id: str
    receiver_party_id: str
    reference: ReferenceRef
    payment_schedule: ScheduleRefLike
    calculation: CouponCalculationType
    currency: Currency


@dataclass(frozen=True)
class FundingLeg(Component):
    component_id: str
    payer_party_id: str
    receiver_party_id: str
    pay_receive: PayReceive
    notional_rule_id: str
    rate_rule_id: str
    payment_schedule: ScheduleRefLike
    currency: Currency
    day_count: DayCount = DayCount.ACT_360


@dataclass(frozen=True)
class FxOptionExerciseLeg(Component):
    component_id: str
    buyer_party_id: str
    seller_party_id: str
    pair: FxPair
    side: Side
    option_type: OptionType
    base_quantity_rule_id: str
    strike: DecimalLike
    expiry_date: date
    settlement_style: SettlementStyle
    settlement_currency: Currency | None = None
    premium_currency: Currency | None = None


@dataclass(frozen=True)
class FxWindowLeg(Component):
    component_id: str
    payer_party_id: str
    receiver_party_id: str
    pair: FxPair
    base_quantity_rule_id: str
    payoff_rule_id: str
    fixing_observation_rule_id: str
    payment_schedule: ScheduleRefLike
    settlement_currency: Currency


@dataclass(frozen=True)
class PrincipalExchangeLeg(Component):
    component_id: str
    payer_party_id: str
    receiver_party_id: str
    quantity_rule_id: str
    currency: Currency
    payment_schedule: ScheduleRefLike


ComponentType = Union[
    PremiumTransfer,
    RedemptionTransfer,
    FeeTransfer,
    CouponStreamLeg,
    FundingLeg,
    FxOptionExerciseLeg,
    FxWindowLeg,
    PrincipalExchangeLeg,
]


# ---------------------------------------------------------------------------
# Lifecycle / State / Accumulation / Effects
# ---------------------------------------------------------------------------

class TargetHitAction(str, Enum):
    KNOCK_OUT_INCLUDING_HIT_CF = "KNOCK_OUT_INCLUDING_HIT_CF"
    PARTIAL_HIT_CF_TO_TARGET_THEN_STOP = "PARTIAL_HIT_CF_TO_TARGET_THEN_STOP"
    FULL_HIT_CF_THEN_STOP = "FULL_HIT_CF_THEN_STOP"


class MetricSelection(str, Enum):
    POSITIVE_PART = "POSITIVE_PART"
    NEGATIVE_PART = "NEGATIVE_PART"
    SIGNED = "SIGNED"
    ABSOLUTE = "ABSOLUTE"


class AccumulationUnitKind(str, Enum):
    CURRENCY = "CURRENCY"
    FX_PIP = "FX_PIP"
    POINT = "POINT"
    COUNT = "COUNT"
    RATE_BPS = "RATE_BPS"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True)
class AccumulationUnit:
    kind: AccumulationUnitKind
    currency: Currency | None = None
    pair: FxPair | None = None
    point_unit: Decimal | None = None
    label: str | None = None

    @staticmethod
    def currency_unit(currency: Currency) -> "AccumulationUnit":
        return AccumulationUnit(kind=AccumulationUnitKind.CURRENCY, currency=currency)

    @staticmethod
    def fx_pip(pair: FxPair, pip_size: Decimal, label: str | None = None) -> "AccumulationUnit":
        return AccumulationUnit(kind=AccumulationUnitKind.FX_PIP, pair=pair, point_unit=pip_size, label=label or f"{pair.symbol} pips")

    @staticmethod
    def count(label: str = "count") -> "AccumulationUnit":
        return AccumulationUnit(kind=AccumulationUnitKind.COUNT, label=label)


class AmountSignConvention:
    pass


@dataclass(frozen=True)
class SignedByParty(AmountSignConvention):
    positive_for_party_id: str


@dataclass(frozen=True)
class SignedByComponentReceiver(AmountSignConvention):
    component_id: str


@dataclass(frozen=True)
class SignedByComponentPayer(AmountSignConvention):
    component_id: str


@dataclass(frozen=True)
class RawAmountSignConvention(AmountSignConvention):
    positive_means: str


AmountSignConventionType = Union[SignedByParty, SignedByComponentReceiver, SignedByComponentPayer, RawAmountSignConvention]


class AccumulationValueRule:
    pass


@dataclass(frozen=True)
class AmountAccumulationValueRule(AccumulationValueRule):
    amount_rule: AmountRule
    sign_convention: AmountSignConventionType


@dataclass(frozen=True)
class FxPipSpreadAccumulationValueRule(AccumulationValueRule):
    observed_fx: FxObservationRule
    reference: DecimalLike
    direction: SpreadDirection
    pip_size: Decimal | None = None


@dataclass(frozen=True)
class CountAccumulationValueRule(AccumulationValueRule):
    condition: ConditionType
    count_value: Decimal = Decimal("1")


@dataclass(frozen=True)
class PackageNetAmountAccumulationValueRule(AccumulationValueRule):
    group_selector: "ComponentSelector"
    sign_convention: AmountSignConventionType
    currency: Currency


AccumulationValueRuleType = Union[
    AmountAccumulationValueRule,
    FxPipSpreadAccumulationValueRule,
    CountAccumulationValueRule,
    PackageNetAmountAccumulationValueRule,
]


@dataclass(frozen=True)
class AccumulationTiming:
    accumulation_schedule: ScheduleRefLike | None = None
    value_period_mapping: Literal["BY_PERIOD_INDEX", "BY_DATE", "CUSTOM"] = "BY_PERIOD_INDEX"
    include_hit_period_increment: bool = True


@dataclass(frozen=True)
class AccumulatorSpec:
    accumulator_id: str
    value_rule: AccumulationValueRuleType
    selection: MetricSelection
    unit: AccumulationUnit
    timing: AccumulationTiming = field(default_factory=AccumulationTiming)
    state_key: str = "target_accumulation"


class ComponentSelector:
    pass


@dataclass(frozen=True)
class ExplicitComponentSelector(ComponentSelector):
    component_ids: tuple[str, ...]


@dataclass(frozen=True)
class PeriodTagComponentSelector(ComponentSelector):
    roles: tuple[str, ...] | None = None
    start_period_index: int | None = None
    end_period_index: int | None = None
    group_kind: str | None = None


@dataclass(frozen=True)
class TriggerRelativePeriodSelector(ComponentSelector):
    roles: tuple[str, ...] | None = None
    start_offset_from_hit_period: int = 0
    end_offset_from_hit_period: int | None = None
    group_kind: str | None = None


@dataclass(frozen=True)
class GroupComponentSelector(ComponentSelector):
    group_kind: str | None = None
    start_period_index: int | None = None
    end_period_index: int | None = None


@dataclass(frozen=True)
class TriggerRelativeGroupComponentSelector(ComponentSelector):
    group_kind: str
    start_offset_from_hit_period: int = 1
    end_offset_from_hit_period: int | None = None


ComponentSelectorType = Union[
    ExplicitComponentSelector,
    PeriodTagComponentSelector,
    TriggerRelativePeriodSelector,
    GroupComponentSelector,
    TriggerRelativeGroupComponentSelector,
]


@dataclass(frozen=True)
class ContractPeriod:
    period_id: str
    period_index: int
    period_kind: str
    label: str | None = None
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PeriodDateBinding:
    period_id: str
    owner_id: str
    owner_type: Literal["COMPONENT", "RULE", "OBSERVATION", "GROUP", "ACCUMULATOR"]
    date_role: DateRole
    purpose: str
    date_value: date


@dataclass(frozen=True)
class PeriodComponentGroup:
    group_id: str
    period_id: str
    group_kind: str
    component_ids: tuple[str, ...]
    role_by_component_id: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Trigger:
    trigger_id: str
    condition_id: str
    effective_schedule: ScheduleRefLike | None = None
    description: str = ""


class Effect:
    pass


@dataclass(frozen=True)
class ActivateComponentsEffect(Effect):
    selector: ComponentSelectorType


@dataclass(frozen=True)
class DeactivateComponentsEffect(Effect):
    selector: ComponentSelectorType


@dataclass(frozen=True)
class SetStateEffect(Effect):
    state_key: str
    value: bool | Decimal | str


@dataclass(frozen=True)
class AddCashflowEffect(Effect):
    transfer_component_id: str


@dataclass(frozen=True)
class UpdateQuantityStateEffect(Effect):
    state_key: str
    quantity_rule_id: str


EffectType = Union[
    ActivateComponentsEffect,
    DeactivateComponentsEffect,
    SetStateEffect,
    AddCashflowEffect,
    UpdateQuantityStateEffect,
]


class LifecycleRule:
    lifecycle_rule_id: str


@dataclass(frozen=True)
class EventLifecycleRule(LifecycleRule):
    lifecycle_rule_id: str
    trigger: Trigger
    effects: tuple[EffectType, ...]


@dataclass(frozen=True)
class NotionalResetLifecycleRule(LifecycleRule):
    lifecycle_rule_id: str
    target_component_ids: tuple[str, ...]
    state_keys: tuple[str, ...]
    reset_observation_rule_id: str
    reset_schedule: ScheduleRefLike
    quantity_rule_id: str


@dataclass(frozen=True)
class TargetLifecycleRule(LifecycleRule):
    lifecycle_rule_id: str
    accumulator_id: str
    target_condition_id: str
    hit_cashflow_action: TargetHitAction
    effects: tuple[EffectType, ...]
    priority: int = 0


LifecycleRuleType = Union[EventLifecycleRule, NotionalResetLifecycleRule, TargetLifecycleRule]


# ---------------------------------------------------------------------------
# Contract form v2.1
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContractFormV2:
    form_id: str
    form_kind: str
    parties: tuple[PartyRef, ...]
    party_roles: tuple[PartyRoleAssignment, ...]
    references: tuple[ReferenceRef, ...]

    schedule_nodes: tuple[ScheduleNode, ...] = ()

    periods: tuple[ContractPeriod, ...] = ()
    period_date_bindings: tuple[PeriodDateBinding, ...] = ()
    period_component_groups: tuple[PeriodComponentGroup, ...] = ()

    observables: tuple[ObservableRef, ...] = ()
    observation_rules: tuple[ObservationRule, ...] = ()
    conditions: tuple[ConditionType, ...] = ()

    components: tuple[ComponentType, ...] = ()
    determination_rules: tuple[DeterminationRuleType, ...] = ()
    overlay_rules: tuple[OverlayRuleType, ...] = ()
    accumulators: tuple[AccumulatorSpec, ...] = ()
    lifecycle_rules: tuple[LifecycleRuleType, ...] = ()

    tags: dict[str, str] = field(default_factory=dict)

    def component_by_id(self, component_id: str) -> ComponentType:
        for component in self.components:
            if component.component_id == component_id:
                return component
        raise KeyError(f"Unknown component_id: {component_id}")

    def determination_rule_by_id(self, rule_id: str) -> DeterminationRuleType:
        for rule in self.determination_rules:
            if rule.rule_id == rule_id:
                return rule
        raise KeyError(f"Unknown determination rule: {rule_id}")

    def observation_rule_by_id(self, rule_id: str) -> ObservationRule:
        for rule in self.observation_rules:
            if rule.rule_id == rule_id:
                return rule
        raise KeyError(f"Unknown observation rule: {rule_id}")

    def condition_by_id(self, condition_id: str) -> ConditionType:
        for condition in self.conditions:
            if condition.condition_id == condition_id:
                return condition
        raise KeyError(f"Unknown condition: {condition_id}")

    def accumulator_by_id(self, accumulator_id: str) -> AccumulatorSpec:
        for accumulator in self.accumulators:
            if accumulator.accumulator_id == accumulator_id:
                return accumulator
        raise KeyError(f"Unknown accumulator: {accumulator_id}")

    def resolve_schedule_ref(self, ref: ScheduleRefLike) -> DateListSchedule:
        if isinstance(ref, DateListSchedule):
            return DateListSchedule(ref.sorted_dates())
        if isinstance(ref, ScheduleRef):
            return self._resolve_schedule_node(ref.node_id, {}, set())
        raise TypeError(f"Unsupported schedule ref: {type(ref)}")

    def _resolve_schedule_node(self, node_id: ScheduleNodeId, cache: dict[str, DateListSchedule], visiting: set[str]) -> DateListSchedule:
        key = node_id.value
        if key in cache:
            return cache[key]
        if key in visiting:
            raise ValueError(f"Cyclic schedule dependency at {key}")
        visiting.add(key)
        node = next((n for n in self.schedule_nodes if n.node_id == node_id), None)
        if node is None:
            raise KeyError(f"Unknown schedule node: {key}")
        source = node.source
        if isinstance(source, ExplicitDateScheduleSource):
            out = DateListSchedule(source.dates.sorted_dates())
        elif isinstance(source, PatternScheduleSource):
            out = _generate_from_pattern(source.pattern)
        elif isinstance(source, RelativeDateScheduleSource):
            base = self._resolve_schedule_node(source.base_ref.node_id, cache, visiting)
            out = DateListSchedule(tuple(_apply_offset(d, source.offset, source.unit, source.business_day_convention) for d in base.sorted_dates()))
        elif isinstance(source, BoundaryAlignedScheduleSource):
            base = self._resolve_schedule_node(source.base_ref.node_id, cache, visiting).sorted_dates()
            if source.alignment is BoundaryAlignment.CURRENT:
                dates = base
            elif source.alignment is BoundaryAlignment.PREVIOUS:
                dates = tuple([source.first_date] + list(base[:-1])) if source.first_date else base[:-1]
            elif source.alignment is BoundaryAlignment.NEXT:
                dates = tuple(list(base[1:]) + [source.last_date]) if source.last_date else base[1:]
            else:
                raise ValueError(source.alignment)
            out = DateListSchedule(tuple(d for d in dates if d is not None))
        else:
            raise TypeError(type(source))
        visiting.remove(key)
        cache[key] = out
        return out

    def validate(self) -> None:
        component_ids = [c.component_id for c in self.components]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("Duplicate component_id")
        component_id_set = set(component_ids)

        rule_ids = [r.rule_id for r in self.determination_rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Duplicate determination rule_id")
        rule_id_set = set(rule_ids)

        obs_rule_ids = [r.rule_id for r in self.observation_rules]
        if len(obs_rule_ids) != len(set(obs_rule_ids)):
            raise ValueError("Duplicate observation rule_id")
        obs_rule_id_set = set(obs_rule_ids)

        cond_ids = [c.condition_id for c in self.conditions]
        if len(cond_ids) != len(set(cond_ids)):
            raise ValueError("Duplicate condition_id")
        cond_id_set = set(cond_ids)

        acc_ids = [a.accumulator_id for a in self.accumulators]
        if len(acc_ids) != len(set(acc_ids)):
            raise ValueError("Duplicate accumulator_id")
        accumulator_id_set = set(acc_ids)

        period_ids = [p.period_id for p in self.periods]
        if len(period_ids) != len(set(period_ids)):
            raise ValueError("Duplicate period_id")
        period_id_set = set(period_ids)

        group_ids = [g.group_id for g in self.period_component_groups]
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("Duplicate period component group_id")

        observable_ids = {o.observable_id for o in self.observables}
        for obs_rule in self.observation_rules:
            if obs_rule.observable_id not in observable_ids:
                raise ValueError(f"Observation rule {obs_rule.rule_id} refers to unknown observable {obs_rule.observable_id}")
            if obs_rule.style is ObservationStyle.EUROPEAN and isinstance(obs_rule.schedule, DateListSchedule) and len(obs_rule.schedule.dates) > 1:
                raise ValueError(f"European observation rule {obs_rule.rule_id} should have a single observation date")

        for binding in self.period_date_bindings:
            _require(binding.period_id, period_id_set, "period date binding period")

        for group in self.period_component_groups:
            _require(group.period_id, period_id_set, "period group period")
            for cid in group.component_ids:
                _require(cid, component_id_set, "period group component")

        for condition in self.conditions:
            if isinstance(condition, BarrierCondition):
                _require(condition.observation_rule_id, obs_rule_id_set, "barrier observation rule")
            elif isinstance(condition, TargetReachedCondition):
                _require(condition.accumulator_id, accumulator_id_set, "target accumulator")

        for component in self.components:
            if isinstance(component, CouponStreamLeg):
                _validate_coupon_calculation(component.calculation, rule_id_set)
            elif isinstance(component, FundingLeg):
                _require(component.notional_rule_id, rule_id_set, "notional rule")
                _require(component.rate_rule_id, rule_id_set, "rate rule")
            elif isinstance(component, FxOptionExerciseLeg):
                _require(component.base_quantity_rule_id, rule_id_set, "base quantity rule")
            elif isinstance(component, FxWindowLeg):
                _require(component.base_quantity_rule_id, rule_id_set, "base quantity rule")
                _require(component.payoff_rule_id, rule_id_set, "payoff rule")
                _require(component.fixing_observation_rule_id, obs_rule_id_set, "fixing observation rule")
            elif isinstance(component, PrincipalExchangeLeg):
                _require(component.quantity_rule_id, rule_id_set, "quantity rule")

        for rule in self.determination_rules:
            if isinstance(rule, FloatingRateRule):
                _require(rule.fixing_observation_rule_id, obs_rule_id_set, "fixing observation rule")
            elif isinstance(rule, FxLinkedRateRule):
                _require(rule.fx_observation_rule_id, obs_rule_id_set, "FX observation rule")
            elif isinstance(rule, RangeAccrualRateRule):
                _require(rule.base_rate_rule_id, rule_id_set, "base rate rule")
                _require(rule.observation_rule_id, obs_rule_id_set, "range observation rule")
            elif isinstance(rule, PRDCRateRule):
                _require(rule.domestic_rate_rule_id, rule_id_set, "domestic rate rule")
                _require(rule.foreign_rate_rule_id, rule_id_set, "foreign rate rule")
                _require(rule.fx_observation_rule_id, obs_rule_id_set, "FX observation rule")
            elif isinstance(rule, VanillaOptionPayoffRule):
                _require(rule.quantity_rule_id, rule_id_set, "quantity rule")
            elif isinstance(rule, FxForwardPayoffRule):
                _require(rule.base_quantity_rule_id, rule_id_set, "base quantity rule")
            elif isinstance(rule, ConditionalPayoffRule):
                _require(rule.condition_id, cond_id_set, "condition")
            elif isinstance(rule, FxForwardAmountRule):
                _require(rule.fixing_observation_rule_id, obs_rule_id_set, "fixing observation rule")
                _require(rule.base_quantity_rule_id, rule_id_set, "base quantity rule")
            elif isinstance(rule, ConditionalAmountRule):
                _require(rule.condition_id, cond_id_set, "condition")
                _require(rule.if_true_amount_rule_id, rule_id_set, "true amount rule")
                if rule.if_false_amount_rule_id is not None:
                    _require(rule.if_false_amount_rule_id, rule_id_set, "false amount rule")
            elif isinstance(rule, RatioForwardCouponAmountRule):
                _require(rule.bought_side_quantity_rule_id, rule_id_set, "bought side quantity rule")
                _require(rule.sold_side_quantity_rule_id, rule_id_set, "sold side quantity rule")
                if rule.sold_side_condition_id is not None:
                    _require(rule.sold_side_condition_id, cond_id_set, "sold-side condition")

        for accumulator in self.accumulators:
            _validate_accumulation_value_rule(accumulator.value_rule, component_id_set, rule_id_set)

        for lifecycle_rule in self.lifecycle_rules:
            if isinstance(lifecycle_rule, EventLifecycleRule):
                _require(lifecycle_rule.trigger.condition_id, cond_id_set, "trigger condition")
                for effect in lifecycle_rule.effects:
                    _validate_effect(effect, component_id_set, rule_id_set)
            elif isinstance(lifecycle_rule, NotionalResetLifecycleRule):
                _require(lifecycle_rule.quantity_rule_id, rule_id_set, "reset quantity rule")
                _require(lifecycle_rule.reset_observation_rule_id, obs_rule_id_set, "reset observation rule")
                if len(lifecycle_rule.target_component_ids) != len(lifecycle_rule.state_keys):
                    raise ValueError("target_component_ids/state_keys length mismatch")
                for cid in lifecycle_rule.target_component_ids:
                    _require(cid, component_id_set, "reset target component")
            elif isinstance(lifecycle_rule, TargetLifecycleRule):
                _require(lifecycle_rule.accumulator_id, accumulator_id_set, "target accumulator")
                _require(lifecycle_rule.target_condition_id, cond_id_set, "target condition")
                for effect in lifecycle_rule.effects:
                    _validate_effect(effect, component_id_set, rule_id_set)


# ---------------------------------------------------------------------------
# Runtime support
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ObservationRecord:
    observation_date: date
    observable_id: str
    value: Decimal


@dataclass(frozen=True)
class RealizedCashflow:
    payment_date: date
    component_id: str
    amount: Money
    description: str


@dataclass
class RuntimeStateV2:
    active_component_ids: set[str] = field(default_factory=set)
    flags: dict[str, bool] = field(default_factory=dict)
    numeric_state: dict[str, Decimal] = field(default_factory=dict)
    observations: list[ObservationRecord] = field(default_factory=list)
    realized_cashflows: list[RealizedCashflow] = field(default_factory=list)

    @classmethod
    def initial_from_form(cls, form: ContractFormV2) -> "RuntimeStateV2":
        active = {c.component_id for c in form.components}
        state = cls(active_component_ids=active)
        for component in form.components:
            if isinstance(component, FundingLeg):
                _initialize_quantity_state(form, state, component.component_id, component.notional_rule_id)
            elif isinstance(component, CouponStreamLeg) and isinstance(component.calculation, RateBasedCouponCalculation):
                _initialize_quantity_state(form, state, component.component_id, component.calculation.notional_rule_id)
        for accumulator in form.accumulators:
            state.numeric_state[accumulator.state_key] = ZERO
        return state

    def is_active(self, component_id: str) -> bool:
        return component_id in self.active_component_ids

    def activate(self, component_id: str) -> None:
        self.active_component_ids.add(component_id)

    def deactivate(self, component_id: str) -> None:
        self.active_component_ids.discard(component_id)


def _initialize_quantity_state(form: ContractFormV2, state: RuntimeStateV2, component_id: str, rule_id: str) -> None:
    try:
        rule = form.determination_rule_by_id(rule_id)
        if isinstance(rule, FixedQuantityRule):
            state.numeric_state[f"current_notional_{component_id}"] = decimal_value_on(rule.quantity)
    except KeyError:
        pass


def barrier_hit(direction: BarrierDirection, observed: Decimal, level: Decimal) -> bool:
    return observed >= level if direction is BarrierDirection.UP else observed <= level


def comparison_hit(op: ComparisonOp, left: Decimal, right: Decimal) -> bool:
    if op is ComparisonOp.GE:
        return left >= right
    if op is ComparisonOp.GT:
        return left > right
    if op is ComparisonOp.LE:
        return left <= right
    if op is ComparisonOp.LT:
        return left < right
    if op is ComparisonOp.EQ:
        return left == right
    raise ValueError(op)


def evaluate_condition(form: ContractFormV2, state: RuntimeStateV2, condition_id: str, observation: ObservationRecord | None = None) -> bool:
    condition = form.condition_by_id(condition_id)
    if isinstance(condition, BarrierCondition):
        if observation is None:
            return False
        obs_rule = form.observation_rule_by_id(condition.observation_rule_id)
        if observation.observable_id != obs_rule.observable_id:
            return False
        if observation.observation_date not in form.resolve_schedule_ref(obs_rule.schedule).dates:
            return False
        return barrier_hit(condition.direction, observation.value, condition.level)
    if isinstance(condition, ComparisonCondition):
        left = state.numeric_state.get(condition.left_state_key, ZERO)
        return comparison_hit(condition.operator, left, condition.right_value)
    if isinstance(condition, TargetReachedCondition):
        accumulator = form.accumulator_by_id(condition.accumulator_id)
        left = state.numeric_state.get(accumulator.state_key, ZERO)
        return comparison_hit(condition.operator, left, condition.target_value)
    raise TypeError(type(condition))


def evaluate_quantity_rule(
    form: ContractFormV2,
    state: RuntimeStateV2,
    rule_id: str,
    *,
    when: date | None = None,
    index: int | None = None,
    observation_value: Decimal | None = None,
) -> Decimal:
    rule = form.determination_rule_by_id(rule_id)
    if isinstance(rule, FixedQuantityRule):
        return decimal_value_on(rule.quantity, when=when, index=index)
    if isinstance(rule, MtMResetQuantityRule):
        if observation_value is None:
            raise ValueError("MtMResetQuantityRule requires observation_value")
        if rule.base_reference_value == ZERO:
            raise ZeroDivisionError("base_reference_value must not be zero")
        if rule.scale_direction == "DIRECT":
            out = rule.base_quantity * observation_value / rule.base_reference_value
        else:
            if observation_value == ZERO:
                raise ZeroDivisionError("observation_value must not be zero for inverse scaling")
            out = rule.base_quantity * rule.base_reference_value / observation_value
        if rule.floor is not None:
            out = max(out, rule.floor)
        if rule.cap is not None:
            out = min(out, rule.cap)
        if rule.rounding_digits is not None:
            quantum = Decimal("1").scaleb(-rule.rounding_digits)
            out = out.quantize(quantum, rounding=ROUND_HALF_UP)
        return out
    raise TypeError(f"Rule {rule_id} is not a QuantityRule: {type(rule)}")


def apply_observation(form: ContractFormV2, state: RuntimeStateV2, observation: ObservationRecord) -> None:
    state.observations.append(observation)
    for lifecycle_rule in form.lifecycle_rules:
        if isinstance(lifecycle_rule, EventLifecycleRule):
            if evaluate_condition(form, state, lifecycle_rule.trigger.condition_id, observation):
                _apply_effects(form, state, lifecycle_rule.effects, observation)
        elif isinstance(lifecycle_rule, NotionalResetLifecycleRule):
            obs_rule = form.observation_rule_by_id(lifecycle_rule.reset_observation_rule_id)
            if observation.observable_id != obs_rule.observable_id:
                continue
            if observation.observation_date not in form.resolve_schedule_ref(lifecycle_rule.reset_schedule).dates:
                continue
            new_quantity = evaluate_quantity_rule(form, state, lifecycle_rule.quantity_rule_id, observation_value=observation.value)
            for component_id, state_key in zip(lifecycle_rule.target_component_ids, lifecycle_rule.state_keys):
                state.numeric_state[state_key] = new_quantity
                state.numeric_state[f"current_notional_{component_id}"] = new_quantity


def _apply_effects(form: ContractFormV2, state: RuntimeStateV2, effects: tuple[EffectType, ...], observation: ObservationRecord | None = None) -> None:
    for effect in effects:
        if isinstance(effect, ActivateComponentsEffect):
            for cid in resolve_component_selector(form, effect.selector):
                state.activate(cid)
        elif isinstance(effect, DeactivateComponentsEffect):
            for cid in resolve_component_selector(form, effect.selector):
                state.deactivate(cid)
        elif isinstance(effect, SetStateEffect):
            if isinstance(effect.value, bool):
                state.flags[effect.state_key] = effect.value
            elif isinstance(effect.value, Decimal):
                state.numeric_state[effect.state_key] = effect.value
            else:
                state.flags[effect.state_key] = bool(effect.value)
        elif isinstance(effect, AddCashflowEffect):
            component = form.component_by_id(effect.transfer_component_id)
            if isinstance(component, (PremiumTransfer, RedemptionTransfer, FeeTransfer)):
                state.realized_cashflows.append(
                    RealizedCashflow(component.payment_date, component.component_id, component.amount, f"Triggered transfer {component.component_id}")
                )
        elif isinstance(effect, UpdateQuantityStateEffect):
            if observation is None:
                continue
            new_q = evaluate_quantity_rule(form, state, effect.quantity_rule_id, observation_value=observation.value)
            state.numeric_state[effect.state_key] = new_q


def resolve_component_selector(
    form: ContractFormV2,
    selector: ComponentSelectorType,
    *,
    hit_period_index: int | None = None,
) -> tuple[str, ...]:
    if isinstance(selector, ExplicitComponentSelector):
        return selector.component_ids

    def period_ok(idx: int, start: int | None, end: int | None) -> bool:
        if start is not None and idx < start:
            return False
        if end is not None and idx > end:
            return False
        return True

    selected: list[str] = []
    if isinstance(selector, (GroupComponentSelector, PeriodTagComponentSelector)):
        for group in form.period_component_groups:
            if selector.group_kind is not None and group.group_kind != selector.group_kind:
                continue
            period = next((p for p in form.periods if p.period_id == group.period_id), None)
            if period is None or not period_ok(period.period_index, selector.start_period_index, selector.end_period_index):
                continue
            roles = getattr(selector, "roles", None)
            if roles is None:
                selected.extend(group.component_ids)
            else:
                selected.extend(cid for cid in group.component_ids if group.role_by_component_id.get(cid) in roles)
        return tuple(dict.fromkeys(selected))

    if isinstance(selector, (TriggerRelativePeriodSelector, TriggerRelativeGroupComponentSelector)):
        if hit_period_index is None:
            start = None
            end = None
        else:
            start = hit_period_index + selector.start_offset_from_hit_period
            end = None if selector.end_offset_from_hit_period is None else hit_period_index + selector.end_offset_from_hit_period
        group_kind = getattr(selector, "group_kind", None)
        roles = getattr(selector, "roles", None)
        for group in form.period_component_groups:
            if group_kind is not None and group.group_kind != group_kind:
                continue
            period = next((p for p in form.periods if p.period_id == group.period_id), None)
            if period is None or not period_ok(period.period_index, start, end):
                continue
            if roles is None:
                selected.extend(group.component_ids)
            else:
                selected.extend(cid for cid in group.component_ids if group.role_by_component_id.get(cid) in roles)
        return tuple(dict.fromkeys(selected))

    raise TypeError(f"Unsupported component selector: {type(selector)}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require(value: str, allowed: set[str], label: str) -> None:
    if value not in allowed:
        raise ValueError(f"Unknown {label}: {value}")


def _validate_coupon_calculation(calculation: CouponCalculationType, rule_id_set: set[str]) -> None:
    if isinstance(calculation, RateBasedCouponCalculation):
        _require(calculation.notional_rule_id, rule_id_set, "coupon notional rule")
        _require(calculation.rate_rule_id, rule_id_set, "coupon rate rule")
    elif isinstance(calculation, AmountBasedCouponCalculation):
        _require(calculation.amount_rule_id, rule_id_set, "coupon amount rule")
    else:
        raise TypeError(f"Unsupported coupon calculation: {type(calculation)}")

def _validate_effect(effect: EffectType, component_id_set: set[str], rule_id_set: set[str]) -> None:
    if isinstance(effect, (ActivateComponentsEffect, DeactivateComponentsEffect)):
        if isinstance(effect.selector, ExplicitComponentSelector):
            for cid in effect.selector.component_ids:
                _require(cid, component_id_set, "effect component")
    elif isinstance(effect, AddCashflowEffect):
        _require(effect.transfer_component_id, component_id_set, "effect transfer")
    elif isinstance(effect, UpdateQuantityStateEffect):
        _require(effect.quantity_rule_id, rule_id_set, "effect quantity rule")


def _validate_accumulation_value_rule(value_rule: AccumulationValueRuleType, component_id_set: set[str], rule_id_set: set[str]) -> None:
    if isinstance(value_rule, AmountAccumulationValueRule):
        if isinstance(value_rule.sign_convention, (SignedByComponentReceiver, SignedByComponentPayer)):
            _require(value_rule.sign_convention.component_id, component_id_set, "amount sign component")
    elif isinstance(value_rule, (FxPipSpreadAccumulationValueRule, CountAccumulationValueRule, PackageNetAmountAccumulationValueRule)):
        pass
    else:
        raise TypeError(type(value_rule))



def schedule_node_id(value: str) -> ScheduleNodeId:
    return ScheduleNodeId(value)


def schedule_ref(value: str) -> ScheduleRef:
    return ScheduleRef(ScheduleNodeId(value))


def schedule_meaning(*roles: DateRole, owner_type: ScheduleOwnerType, owner_id: str, custom_labels: Sequence[str] = ()) -> ScheduleMeaning:
    return ScheduleMeaning(frozenset(roles), ScheduleOwner(owner_type, owner_id), tuple(custom_labels))


def _generate_from_pattern(pattern: SchedulePattern) -> DateListSchedule:
    step_days = {
        "DAILY": 1,
        "WEEKLY": 7,
        "MONTHLY": 30,
        "QUARTERLY": 91,
        "SEMI_ANNUAL": 182,
        "ANNUAL": 365,
    }[pattern.frequency]
    out: list[date] = []
    d = pattern.start_date
    while d <= pattern.end_date:
        out.append(_apply_bdc(d, pattern.business_day_convention))
        d += timedelta(days=step_days)
    if out and out[-1] != _apply_bdc(pattern.end_date, pattern.business_day_convention):
        out.append(_apply_bdc(pattern.end_date, pattern.business_day_convention))
    return DateListSchedule(tuple(sorted(set(out))))


def _apply_offset(d: date, offset: int, unit: OffsetUnit, bdc: BusinessDayConvention) -> date:
    if unit is OffsetUnit.CALENDAR_DAYS:
        return _apply_bdc(d + timedelta(days=offset), bdc)
    step = 1 if offset >= 0 else -1
    cur = d
    remaining = abs(offset)
    while remaining:
        cur += timedelta(days=step)
        if _is_business_day(cur):
            remaining -= 1
    return _apply_bdc(cur, bdc)


def _apply_bdc(d: date, bdc: BusinessDayConvention) -> date:
    if bdc is BusinessDayConvention.NONE or _is_business_day(d):
        return d
    if bdc is BusinessDayConvention.FOLLOWING:
        cur = d
        while not _is_business_day(cur):
            cur += timedelta(days=1)
        return cur
    if bdc is BusinessDayConvention.PRECEDING:
        cur = d
        while not _is_business_day(cur):
            cur -= timedelta(days=1)
        return cur
    if bdc is BusinessDayConvention.MODIFIED_FOLLOWING:
        cur = d
        while not _is_business_day(cur):
            cur += timedelta(days=1)
        if cur.month != d.month:
            cur = d
            while not _is_business_day(cur):
                cur -= timedelta(days=1)
        return cur
    return d


def _is_business_day(d: date) -> bool:
    return d.weekday() < 5


__all__ = [name for name in globals() if not name.startswith("_")]
