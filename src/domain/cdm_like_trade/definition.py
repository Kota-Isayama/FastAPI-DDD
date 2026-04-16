
"""
typical_product_definitions.py

A typical-product definition layer that sits *above* the CDM-like contract model.

Purpose
-------
This module is not the normalized contract model itself.
Instead, it defines "typical product" classes whose job is to:

1. expose the minimum-sufficient fields a client needs to define/edit a product,
2. preserve the user's *intent*,
3. support both:
   - rule-based schedule / step generation, and
   - explicit irregular per-period definitions,
4. serve as input to a later generator that maps these definitions into a
   CDM-like Trade / Product / EconomicTerms / Payout model.

Why this layer exists
---------------------
A normalized CDM-like contract model is powerful but flexible enough that many
clients would find it difficult to assemble correctly.

This layer provides domain-specific product definitions such as:
- FX TARF
- Coupon Swap
- Digital Coupon Swap

Each definition:
- captures product-specific required fields,
- hides unnecessary contract-model internals,
- allows both regular and irregular schedule shapes,
- preserves whether something was intended as rule-based or explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional, Tuple, Union
from abc import ABC


# ============================================================================
# Helpers
# ============================================================================

def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _non_empty(value: str, field_name: str) -> None:
    _require(bool(value.strip()), f"{field_name} must be non-empty.")


# ============================================================================
# Generic base metadata
# ============================================================================

@dataclass(frozen=True)
class ProductDefinition(ABC):
    """Base class for all typical product definitions.

    This is the client-facing product layer. It is product-specific, editable,
    and intentionally more constrained than a general contract model.
    """
    product_type: str
    template_name: str
    display_name: Optional[str] = None
    tags: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _non_empty(self.product_type, "product_type")
        _non_empty(self.template_name, "template_name")


# ============================================================================
# Common enums
# ============================================================================

class ScheduleDefinitionKind(Enum):
    RULE_BASED = "RULE_BASED"
    EXPLICIT = "EXPLICIT"
    MIXED = "MIXED"


class StepDefinitionKind(Enum):
    RULE_BASED = "RULE_BASED"
    EXPLICIT = "EXPLICIT"
    MIXED = "MIXED"


class StubConvention(Enum):
    SHORT_INITIAL = "SHORT_INITIAL"
    LONG_INITIAL = "LONG_INITIAL"
    SHORT_FINAL = "SHORT_FINAL"
    LONG_FINAL = "LONG_FINAL"
    NONE = "NONE"


class ObservationMode(Enum):
    DISCRETE = "DISCRETE"
    CONTINUOUS = "CONTINUOUS"


class ComparisonOperator(Enum):
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "=="


class CouponDirection(Enum):
    PAY = "PAY"
    RECEIVE = "RECEIVE"


class TargetAccrualMethod(Enum):
    SUM_POSITIVE_PAYOFF = "SUM_POSITIVE_PAYOFF"
    SUM_ABSOLUTE_PAYOFF = "SUM_ABSOLUTE_PAYOFF"
    SUM_COUPON_AMOUNT = "SUM_COUPON_AMOUNT"
    CUSTOM = "CUSTOM"


class KnockOutScope(Enum):
    THIS_COMPONENT = "THIS_COMPONENT"
    REMAINING_COMPONENT = "REMAINING_COMPONENT"
    REMAINING_PRODUCT = "REMAINING_PRODUCT"
    NAMED_COMPONENTS = "NAMED_COMPONENTS"
    CUSTOM = "CUSTOM"


class DigitalDirection(Enum):
    UP = "UP"
    DOWN = "DOWN"


class BusinessDayConvention(Enum):
    FOLLOWING = "FOLLOWING"
    MODIFIED_FOLLOWING = "MODIFIED_FOLLOWING"
    PRECEDING = "PRECEDING"
    NONE = "NONE"


class PeriodUnit(Enum):
    DAY = "D"
    WEEK = "W"
    MONTH = "M"
    YEAR = "Y"


# ============================================================================
# General reusable pieces
# ============================================================================

@dataclass(frozen=True)
class CurrencyPairDefinition:
    """Simple currency-pair descriptor.

    The pair is represented explicitly as base and quote currencies to avoid
    relying only on a free-text concatenation.
    """
    base_currency: str
    quote_currency: str

    def __post_init__(self) -> None:
        _non_empty(self.base_currency, "base_currency")
        _non_empty(self.quote_currency, "quote_currency")


@dataclass(frozen=True)
class PeriodFrequency:
    """Frequency such as 1M, 3M, 1Y."""
    multiplier: int
    unit: PeriodUnit

    def __post_init__(self) -> None:
        _require(self.multiplier > 0, "PeriodFrequency.multiplier must be > 0.")


@dataclass(frozen=True)
class CounterpartyRolePairDefinition:
    """Client-facing payment direction.

    We keep this simple here and do not force Party1/Party2 directly into the
    client-facing layer unless desired by the application.
    """
    payer_label: str
    receiver_label: str

    def __post_init__(self) -> None:
        _non_empty(self.payer_label, "payer_label")
        _non_empty(self.receiver_label, "receiver_label")
        _require(self.payer_label != self.receiver_label, "payer_label and receiver_label must differ.")


# ============================================================================
# Schedule definitions
# ============================================================================
#
# Key idea:
# A schedule can be represented in multiple ways:
# - rule-based: user intended a regular recurrence rule
# - explicit: user intended a hand-specified irregular set of periods
# - mixed: started from a rule but has explicit modifications
#
# This preserves not only the resulting dates, but also the original intent.
# ============================================================================

@dataclass(frozen=True)
class RuleBasedScheduleDefinition:
    """A regular schedule specification.

    This captures the intent that the schedule was generated by rule.
    """
    start_date: date
    end_date: date
    frequency: PeriodFrequency
    business_day_convention: BusinessDayConvention = BusinessDayConvention.NONE
    payment_lag_days: int = 0
    stub_convention: StubConvention = StubConvention.NONE
    roll_day: Optional[int] = None
    calendars: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(self.end_date > self.start_date, "end_date must be after start_date.")
        if self.roll_day is not None:
            _require(1 <= self.roll_day <= 31, "roll_day must be between 1 and 31.")


@dataclass(frozen=True)
class ExplicitSchedulePeriod:
    """One explicitly specified period in an irregular schedule.

    Not every field must always be populated. A product may care about fixing
    and payment dates but not accrual dates, or vice versa.
    """
    period_id: str
    fixing_date: Optional[date] = None
    payment_date: Optional[date] = None
    accrual_start: Optional[date] = None
    accrual_end: Optional[date] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        _non_empty(self.period_id, "period_id")


@dataclass(frozen=True)
class ExplicitScheduleDefinition:
    """An irregular schedule specified period-by-period."""
    periods: Tuple[ExplicitSchedulePeriod, ...]

    def __post_init__(self) -> None:
        _require(len(self.periods) >= 1, "ExplicitScheduleDefinition requires at least one period.")


@dataclass(frozen=True)
class MixedScheduleDefinition:
    """A mostly rule-based schedule with explicit exceptions or overrides.

    This is useful when:
    - the user *intended* a regular schedule,
    - but some periods were manually adjusted later.

    We keep both:
    - the originating rule,
    - the explicit overrides,
    to preserve intent.
    """
    base_rule: RuleBasedScheduleDefinition
    explicit_overrides: Tuple[ExplicitSchedulePeriod, ...] = ()
    description: Optional[str] = None


ScheduleDefinition = Union[
    RuleBasedScheduleDefinition,
    ExplicitScheduleDefinition,
    MixedScheduleDefinition,
]


def schedule_definition_kind(schedule: ScheduleDefinition) -> ScheduleDefinitionKind:
    """Return the schedule kind in a structured way."""
    if isinstance(schedule, RuleBasedScheduleDefinition):
        return ScheduleDefinitionKind.RULE_BASED
    if isinstance(schedule, ExplicitScheduleDefinition):
        return ScheduleDefinitionKind.EXPLICIT
    if isinstance(schedule, MixedScheduleDefinition):
        return ScheduleDefinitionKind.MIXED
    raise TypeError(f"Unsupported schedule definition type: {type(schedule)!r}")


# ============================================================================
# Step definitions
# ============================================================================
#
# The same philosophy is used for step-up / step-down / stepped parameters:
# keep both the ability to express an irregular explicit sequence and the
# ability to preserve that the sequence was intended to be rule-driven.
# ============================================================================

@dataclass(frozen=True)
class RuleBasedStepDefinition:
    """A step definition driven by a rule or ordered values.

    Typical use cases:
    - strike steps monthly according to a planned list
    - notional steps quarterly
    - rate changes on known step dates
    """
    initial_value: Decimal
    step_values: Tuple[Decimal, ...] = ()
    step_dates: Tuple[date, ...] = ()
    step_frequency: Optional[PeriodFrequency] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "initial_value", _to_decimal(self.initial_value))
        step_values = tuple(_to_decimal(v) for v in self.step_values)
        object.__setattr__(self, "step_values", step_values)

        if self.step_frequency is None and len(self.step_dates) == 0 and len(self.step_values) > 0:
            # This is still acceptable: it means an ordered step series but
            # the application will interpret sequencing externally.
            pass

        if len(self.step_dates) > 0:
            _require(
                len(self.step_values) == len(self.step_dates),
                "When step_dates are provided, step_values and step_dates must have the same length.",
            )


@dataclass(frozen=True)
class ExplicitStepPoint:
    """An explicitly specified value at a period/date."""
    value: Decimal
    period_id: Optional[str] = None
    effective_date: Optional[date] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _to_decimal(self.value))
        _require(
            self.period_id is not None or self.effective_date is not None,
            "ExplicitStepPoint requires period_id or effective_date.",
        )


@dataclass(frozen=True)
class ExplicitStepDefinition:
    """An irregular step definition specified point-by-point."""
    points: Tuple[ExplicitStepPoint, ...]

    def __post_init__(self) -> None:
        _require(len(self.points) >= 1, "ExplicitStepDefinition requires at least one point.")


@dataclass(frozen=True)
class MixedStepDefinition:
    """A step definition that started from a rule but includes explicit edits."""
    base_rule: RuleBasedStepDefinition
    explicit_points: Tuple[ExplicitStepPoint, ...] = ()
    description: Optional[str] = None


StepDefinition = Union[
    RuleBasedStepDefinition,
    ExplicitStepDefinition,
    MixedStepDefinition,
]


def step_definition_kind(step: StepDefinition) -> StepDefinitionKind:
    """Return the step definition kind."""
    if isinstance(step, RuleBasedStepDefinition):
        return StepDefinitionKind.RULE_BASED
    if isinstance(step, ExplicitStepDefinition):
        return StepDefinitionKind.EXPLICIT
    if isinstance(step, MixedStepDefinition):
        return StepDefinitionKind.MIXED
    raise TypeError(f"Unsupported step definition type: {type(step)!r}")


# ============================================================================
# Feature / condition definitions
# ============================================================================

@dataclass(frozen=True)
class BarrierConditionDefinition:
    """Generic barrier / trigger condition used by typical products."""
    observable_name: str
    operator: ComparisonOperator
    level: Decimal
    observation_schedule: ScheduleDefinition
    observation_mode: ObservationMode = ObservationMode.DISCRETE
    observable_description: Optional[str] = None

    def __post_init__(self) -> None:
        _non_empty(self.observable_name, "observable_name")
        object.__setattr__(self, "level", _to_decimal(self.level))


@dataclass(frozen=True)
class KnockOutRuleDefinition:
    """Client-facing knockout rule.

    This is intentionally simpler than the normalized contract-model feature
    representation. The generator can later map it into one or more
    contract-model features.
    """
    condition: BarrierConditionDefinition
    scope: KnockOutScope
    target_component_names: Tuple[str, ...] = ()
    description: Optional[str] = None

    def __post_init__(self) -> None:
        if self.scope == KnockOutScope.NAMED_COMPONENTS:
            _require(
                len(self.target_component_names) >= 1,
                "NAMED_COMPONENTS scope requires target_component_names.",
            )


@dataclass(frozen=True)
class TargetRedemptionDefinition:
    """Client-facing target redemption definition for TARF-like products."""
    target_amount: Decimal
    accrual_currency: str
    accrual_method: TargetAccrualMethod
    include_negative_amounts: bool = False
    description: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_amount", _to_decimal(self.target_amount))
        _require(self.target_amount >= 0, "target_amount must be non-negative.")
        _non_empty(self.accrual_currency, "accrual_currency")


# ============================================================================
# Coupon formula definitions
# ============================================================================

@dataclass(frozen=True)
class CouponFormulaDefinition(ABC):
    """Base class for coupon formula definitions."""
    formula_type: str

    def __post_init__(self) -> None:
        _non_empty(self.formula_type, "formula_type")


@dataclass(frozen=True)
class FixedCouponFormulaDefinition(CouponFormulaDefinition):
    """A fixed coupon formula with possibly stepped rate."""
    rate: StepDefinition

    def __init__(self, rate: StepDefinition):
        object.__setattr__(self, "formula_type", "FIXED_COUPON")
        object.__setattr__(self, "rate", rate)


@dataclass(frozen=True)
class FloatingCouponFormulaDefinition(CouponFormulaDefinition):
    """A floating coupon formula with index + spread."""
    index_name: str
    spread: Optional[StepDefinition] = None
    reset_schedule: Optional[ScheduleDefinition] = None
    day_count: Optional[str] = None

    def __init__(
        self,
        index_name: str,
        spread: Optional[StepDefinition] = None,
        reset_schedule: Optional[ScheduleDefinition] = None,
        day_count: Optional[str] = None,
    ):
        object.__setattr__(self, "formula_type", "FLOATING_COUPON")
        object.__setattr__(self, "index_name", index_name)
        object.__setattr__(self, "spread", spread)
        object.__setattr__(self, "reset_schedule", reset_schedule)
        object.__setattr__(self, "day_count", day_count)
        _non_empty(index_name, "index_name")


@dataclass(frozen=True)
class DigitalCouponFormulaDefinition(CouponFormulaDefinition):
    """A digital coupon formula.

    Example:
    - if USDJPY >= strike then payoff_amount else 0
    """
    underlying_observable: str
    strike: StepDefinition
    payoff_amount: StepDefinition
    direction: DigitalDirection
    observation_schedule: ScheduleDefinition

    def __init__(
        self,
        underlying_observable: str,
        strike: StepDefinition,
        payoff_amount: StepDefinition,
        direction: DigitalDirection,
        observation_schedule: ScheduleDefinition,
    ):
        object.__setattr__(self, "formula_type", "DIGITAL_COUPON")
        object.__setattr__(self, "underlying_observable", underlying_observable)
        object.__setattr__(self, "strike", strike)
        object.__setattr__(self, "payoff_amount", payoff_amount)
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "observation_schedule", observation_schedule)
        _non_empty(underlying_observable, "underlying_observable")


# ============================================================================
# Coupon components / swaps
# ============================================================================

@dataclass(frozen=True)
class CouponComponentDefinition:
    """One coupon stream or component inside a coupon swap.

    This component-centric view is useful because:
    - base coupon can be one component,
    - digital bonus can be another,
    - AKO may apply only to one component.
    """
    component_name: str
    direction: CouponDirection
    coupon_schedule: ScheduleDefinition
    notional: StepDefinition
    formula: CouponFormulaDefinition
    knock_out_rule: Optional[KnockOutRuleDefinition] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        _non_empty(self.component_name, "component_name")


@dataclass(frozen=True)
class CouponSwapDefinition(ProductDefinition):
    """Typical coupon swap definition.

    The product is represented as one or more coupon components rather than a
    free-form collection of arbitrary payouts.
    """
    currency: str
    components: Tuple[CouponComponentDefinition, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        _non_empty(self.currency, "currency")
        _require(len(self.components) >= 1, "CouponSwapDefinition requires at least one component.")


@dataclass(frozen=True)
class DigitalCouponSwapDefinition(ProductDefinition):
    """A convenience-typed product for digital coupon swaps.

    It still supports multiple components, but this class exists so the client
    can choose a more specific product type with stronger semantic intent.
    """
    currency: str
    components: Tuple[CouponComponentDefinition, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        _non_empty(self.currency, "currency")
        _require(len(self.components) >= 1, "DigitalCouponSwapDefinition requires at least one component.")


# ============================================================================
# TARF definitions
# ============================================================================

@dataclass(frozen=True)
class RatioForwardTermsDefinition:
    """Definition of the ratio-forward payoff mechanics used in an FX TARF.

    The key design choice is that strike and notional are StepDefinitions,
    meaning they can be:
    - rule-based,
    - explicit,
    - mixed.
    """
    bought_currency: str
    sold_currency: str
    ratio: Decimal
    strike: StepDefinition
    bought_notional: StepDefinition
    sold_notional: Optional[StepDefinition] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        _non_empty(self.bought_currency, "bought_currency")
        _non_empty(self.sold_currency, "sold_currency")
        object.__setattr__(self, "ratio", _to_decimal(self.ratio))
        _require(self.ratio > 0, "ratio must be > 0.")


@dataclass(frozen=True)
class FxTarfDefinition(ProductDefinition):
    """Typical FX TARF definition.

    Important design point:
    A TARF is not modeled here as 'must be regular monthly schedule'.

    Instead, its essential identity is:
    - a payoff stream whose payoffs are ratio-forwards,
    - plus target redemption logic.

    The payoff schedule itself may be:
    - rule-based,
    - explicit/irregular,
    - mixed.

    This allows:
    - regular scheduled TARFs,
    - irregular TARFs,
    - edited TARFs that started regular but were later customized.
    """
    currency_pair: CurrencyPairDefinition
    payoff_schedule: ScheduleDefinition
    ratio_forward_terms: RatioForwardTermsDefinition
    target_redemption: TargetRedemptionDefinition
    knock_out_rule: Optional[KnockOutRuleDefinition] = None

    def __post_init__(self) -> None:
        super().__post_init__()


# ============================================================================
# Generation metadata / wrapper
# ============================================================================

@dataclass(frozen=True)
class GenerationMetadata:
    """Metadata about how a definition was turned into a contract model.

    This does not belong to the normalized contract model itself, but is very
    helpful in applications for auditability and editability.
    """
    generator_name: str
    generator_version: str
    notes: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _non_empty(self.generator_name, "generator_name")
        _non_empty(self.generator_version, "generator_version")


@dataclass(frozen=True)
class GeneratedProductBundle:
    """A wrapper tying together:
    - the client-facing typical product definition,
    - the generated normalized trade/contract object,
    - generation metadata.

    The generated_trade is intentionally typed as object here because this
    module should remain independent from the contract-model module.
    """
    definition: ProductDefinition
    generated_trade: object
    metadata: GenerationMetadata


# ============================================================================
# Example objects
# ============================================================================

def example_irregular_tarf_definition() -> FxTarfDefinition:
    """Irregular TARF example.

    This example demonstrates the intended semantics:
    - payoff schedule is explicit / irregular,
    - strike and notional are explicit by period,
    - product identity is still FX TARF because each payoff is a ratio-forward
      and the product has a target redemption definition.
    """
    periods = (
        ExplicitSchedulePeriod(
            period_id="p01",
            fixing_date=date(2026, 1, 28),
            payment_date=date(2026, 1, 30),
        ),
        ExplicitSchedulePeriod(
            period_id="p02",
            fixing_date=date(2026, 2, 26),
            payment_date=date(2026, 2, 28),
        ),
        ExplicitSchedulePeriod(
            period_id="p03",
            fixing_date=date(2026, 4, 3),   # intentionally irregular
            payment_date=date(2026, 4, 7),
        ),
        ExplicitSchedulePeriod(
            period_id="p04",
            fixing_date=date(2026, 5, 19),  # intentionally irregular
            payment_date=date(2026, 5, 21),
        ),
    )

    strike = ExplicitStepDefinition(
        points=(
            ExplicitStepPoint(period_id="p01", value=Decimal("150.00")),
            ExplicitStepPoint(period_id="p02", value=Decimal("151.00")),
            ExplicitStepPoint(period_id="p03", value=Decimal("152.50")),
            ExplicitStepPoint(period_id="p04", value=Decimal("154.00")),
        )
    )

    notional = ExplicitStepDefinition(
        points=(
            ExplicitStepPoint(period_id="p01", value=Decimal("1000000")),
            ExplicitStepPoint(period_id="p02", value=Decimal("1200000")),
            ExplicitStepPoint(period_id="p03", value=Decimal("1400000")),
            ExplicitStepPoint(period_id="p04", value=Decimal("1600000")),
        )
    )

    return FxTarfDefinition(
        product_type="FX_TARF",
        template_name="FX_TARF_RATIO_FORWARD",
        display_name="Irregular USDJPY TARF",
        currency_pair=CurrencyPairDefinition(base_currency="USD", quote_currency="JPY"),
        payoff_schedule=ExplicitScheduleDefinition(periods=periods),
        ratio_forward_terms=RatioForwardTermsDefinition(
            bought_currency="USD",
            sold_currency="JPY",
            ratio=Decimal("2.0"),
            strike=strike,
            bought_notional=notional,
            description="Each payoff is a ratio-forward; schedule is intentionally irregular.",
        ),
        target_redemption=TargetRedemptionDefinition(
            target_amount=Decimal("500000"),
            accrual_currency="JPY",
            accrual_method=TargetAccrualMethod.SUM_POSITIVE_PAYOFF,
        ),
        tags=("irregular", "tarf", "ratio-forward"),
    )


def example_rule_based_tarf_definition() -> FxTarfDefinition:
    """Rule-based TARF example.

    This demonstrates the opposite intent:
    - the product was intentionally defined from a regular schedule rule,
    - strike and notional step according to rule-based definitions.
    """
    schedule = RuleBasedScheduleDefinition(
        start_date=date(2026, 1, 28),
        end_date=date(2026, 6, 28),
        frequency=PeriodFrequency(multiplier=1, unit=PeriodUnit.MONTH),
        business_day_convention=BusinessDayConvention.MODIFIED_FOLLOWING,
        payment_lag_days=2,
    )

    strike = RuleBasedStepDefinition(
        initial_value=Decimal("150.00"),
        step_values=(
            Decimal("151.00"),
            Decimal("152.50"),
            Decimal("154.00"),
            Decimal("155.50"),
        ),
        step_frequency=PeriodFrequency(multiplier=1, unit=PeriodUnit.MONTH),
        description="Monthly strike step-up rule.",
    )

    notional = RuleBasedStepDefinition(
        initial_value=Decimal("1000000"),
        step_values=(
            Decimal("1200000"),
            Decimal("1400000"),
            Decimal("1600000"),
            Decimal("1800000"),
        ),
        step_frequency=PeriodFrequency(multiplier=1, unit=PeriodUnit.MONTH),
        description="Monthly bought notional step-up rule.",
    )

    return FxTarfDefinition(
        product_type="FX_TARF",
        template_name="FX_TARF_RATIO_FORWARD",
        display_name="Rule-based USDJPY TARF",
        currency_pair=CurrencyPairDefinition(base_currency="USD", quote_currency="JPY"),
        payoff_schedule=schedule,
        ratio_forward_terms=RatioForwardTermsDefinition(
            bought_currency="USD",
            sold_currency="JPY",
            ratio=Decimal("2.0"),
            strike=strike,
            bought_notional=notional,
        ),
        target_redemption=TargetRedemptionDefinition(
            target_amount=Decimal("500000"),
            accrual_currency="JPY",
            accrual_method=TargetAccrualMethod.SUM_POSITIVE_PAYOFF,
        ),
        tags=("rule-based", "tarf", "ratio-forward"),
    )


def example_ako_coupon_swap_definition() -> CouponSwapDefinition:
    """Coupon swap example with a bonus component carrying AKO logic."""
    quarterly = RuleBasedScheduleDefinition(
        start_date=date(2026, 1, 1),
        end_date=date(2028, 1, 1),
        frequency=PeriodFrequency(multiplier=3, unit=PeriodUnit.MONTH),
        business_day_convention=BusinessDayConvention.MODIFIED_FOLLOWING,
    )

    quarterly_obs = RuleBasedScheduleDefinition(
        start_date=date(2026, 1, 1),
        end_date=date(2028, 1, 1),
        frequency=PeriodFrequency(multiplier=3, unit=PeriodUnit.MONTH),
        business_day_convention=BusinessDayConvention.MODIFIED_FOLLOWING,
    )

    base_component = CouponComponentDefinition(
        component_name="base_coupon",
        direction=CouponDirection.RECEIVE,
        coupon_schedule=quarterly,
        notional=RuleBasedStepDefinition(initial_value=Decimal("10000000")),
        formula=FixedCouponFormulaDefinition(
            rate=RuleBasedStepDefinition(initial_value=Decimal("0.02"))
        ),
        description="Base coupon stream with no knockout.",
    )

    ako_condition = BarrierConditionDefinition(
        observable_name="USDJPY",
        operator=ComparisonOperator.GTE,
        level=Decimal("150"),
        observation_schedule=quarterly_obs,
        observation_mode=ObservationMode.DISCRETE,
    )

    bonus_component = CouponComponentDefinition(
        component_name="bonus_coupon",
        direction=CouponDirection.RECEIVE,
        coupon_schedule=quarterly,
        notional=RuleBasedStepDefinition(initial_value=Decimal("10000000")),
        formula=FixedCouponFormulaDefinition(
            rate=RuleBasedStepDefinition(initial_value=Decimal("0.01"))
        ),
        knock_out_rule=KnockOutRuleDefinition(
            condition=ako_condition,
            scope=KnockOutScope.REMAINING_COMPONENT,
            description="AKO on bonus coupon component only.",
        ),
        description="Bonus coupon stream with AKO.",
    )

    return CouponSwapDefinition(
        product_type="COUPON_SWAP",
        template_name="AKO_COUPON_SWAP",
        display_name="AKO bonus coupon swap",
        currency="USD",
        components=(base_component, bonus_component),
        tags=("coupon-swap", "ako"),
    )


if __name__ == "__main__":
    a = example_irregular_tarf_definition()
    b = example_rule_based_tarf_definition()
    c = example_ako_coupon_swap_definition()

    print("Irregular TARF schedule kind:", schedule_definition_kind(a.payoff_schedule).value)
    print("Irregular TARF strike kind:", step_definition_kind(a.ratio_forward_terms.strike).value)

    print("Rule-based TARF schedule kind:", schedule_definition_kind(b.payoff_schedule).value)
    print("Rule-based TARF strike kind:", step_definition_kind(b.ratio_forward_terms.strike).value)

    print("Coupon swap components:", [x.component_name for x in c.components])
