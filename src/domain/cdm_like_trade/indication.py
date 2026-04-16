
"""
indication_layer.py

Indication layer that sits above the typical product definition layer.

Design goal
-----------
Support *both* of the following use cases:

1. Typed indication lane
   For high-volume, product-typed RFQ / indication workflows.

2. Flexible / bespoke indication lane
   For cases where the client wants more flexible indication-time input, while
   still expressing economically meaningful terms in a structured way.

This module does NOT contain pricing logic.
It models indication requests and their relationship to:
- typical product definitions
- later contract normalization
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional, Tuple, Union
from abc import ABC

from typical_product_definitions import (
    ProductDefinition,
    FxTarfDefinition,
    CouponSwapDefinition,
    DigitalCouponSwapDefinition,
    CurrencyPairDefinition,
    PeriodFrequency,
    PeriodUnit,
    RuleBasedScheduleDefinition,
    ExplicitScheduleDefinition,
    ExplicitSchedulePeriod,
    MixedScheduleDefinition,
    RuleBasedStepDefinition,
    ExplicitStepDefinition,
    ExplicitStepPoint,
    MixedStepDefinition,
    ScheduleDefinition,
    StepDefinition,
    TargetRedemptionDefinition,
    TargetAccrualMethod,
    BarrierConditionDefinition,
    KnockOutRuleDefinition,
    KnockOutScope,
    ComparisonOperator,
    ObservationMode,
    RatioForwardTermsDefinition,
    CouponComponentDefinition,
    CouponDirection,
    FixedCouponFormulaDefinition,
    FloatingCouponFormulaDefinition,
    DigitalCouponFormulaDefinition,
    DigitalDirection,
    BusinessDayConvention,
)


# ============================================================================
# Helpers
# ============================================================================

def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _non_empty(value: str, field_name: str) -> None:
    _require(bool(value.strip()), f"{field_name} must be non-empty.")


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


# ============================================================================
# Base enums
# ============================================================================

class IndicationLane(Enum):
    TYPED = "TYPED"
    FLEXIBLE = "FLEXIBLE"


class ProductHint(Enum):
    FX_TARF = "FX_TARF"
    COUPON_SWAP = "COUPON_SWAP"
    DIGITAL_COUPON_SWAP = "DIGITAL_COUPON_SWAP"
    UNKNOWN = "UNKNOWN"


class UpliftPreference(Enum):
    STRICT_TYPED_ONLY = "STRICT_TYPED_ONLY"
    PREFER_TYPED_IF_POSSIBLE = "PREFER_TYPED_IF_POSSIBLE"
    KEEP_FLEXIBLE_UNLESS_CONFIDENT = "KEEP_FLEXIBLE_UNLESS_CONFIDENT"


# ============================================================================
# Shared indication building blocks
# ============================================================================

@dataclass(frozen=True)
class IndicationContext:
    client_reference: Optional[str] = None
    sales_region: Optional[str] = None
    book_hint: Optional[str] = None
    trader_notes: Tuple[str, ...] = ()
    requested_response_deadline: Optional[date] = None


@dataclass(frozen=True)
class ScheduleIntent:
    """Wrapper to keep indication layer conceptually separate from definitions."""
    schedule: ScheduleDefinition
    comment: Optional[str] = None


@dataclass(frozen=True)
class StepIntent:
    step: StepDefinition
    comment: Optional[str] = None


# ============================================================================
# Base indication classes
# ============================================================================

@dataclass(frozen=True)
class IndicationRequest(ABC):
    lane: IndicationLane
    display_name: Optional[str] = None
    context: Optional[IndicationContext] = None


@dataclass(frozen=True)
class TypedIndicationRequest(IndicationRequest, ABC):
    product_hint: ProductHint = ProductHint.UNKNOWN

    def __post_init__(self) -> None:
        _require(self.lane == IndicationLane.TYPED, "TypedIndicationRequest requires lane=TYPED.")


@dataclass(frozen=True)
class FlexibleIndicationRequest(IndicationRequest):
    product_hint: ProductHint = ProductHint.UNKNOWN
    uplift_preference: UpliftPreference = UpliftPreference.PREFER_TYPED_IF_POSSIBLE
    freeform_description: Optional[str] = None
    economic_clauses: Tuple["EconomicClause", ...] = ()

    def __post_init__(self) -> None:
        _require(self.lane == IndicationLane.FLEXIBLE, "FlexibleIndicationRequest requires lane=FLEXIBLE.")
        _require(
            self.freeform_description is not None or len(self.economic_clauses) > 0,
            "FlexibleIndicationRequest requires freeform_description or at least one economic clause.",
        )


# ============================================================================
# Typed indication definitions
# ============================================================================

@dataclass(frozen=True)
class FxTarfIndication(TypedIndicationRequest):
    currency_pair: CurrencyPairDefinition = field(default_factory=lambda: CurrencyPairDefinition("USD", "JPY"))
    payoff_schedule: ScheduleIntent = field(default_factory=lambda: ScheduleIntent(
        schedule=RuleBasedScheduleDefinition(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 1),
            frequency=PeriodFrequency(1, PeriodUnit.MONTH),
        )
    ))
    bought_currency: str = "USD"
    sold_currency: str = "JPY"
    ratio: Decimal = Decimal("1")
    strike: StepIntent = field(default_factory=lambda: StepIntent(step=RuleBasedStepDefinition(initial_value=Decimal("0"))))
    bought_notional: StepIntent = field(default_factory=lambda: StepIntent(step=RuleBasedStepDefinition(initial_value=Decimal("0"))))
    target_redemption: TargetRedemptionDefinition = field(default_factory=lambda: TargetRedemptionDefinition(
        target_amount=Decimal("0"),
        accrual_currency="JPY",
        accrual_method=TargetAccrualMethod.SUM_POSITIVE_PAYOFF,
    ))
    knock_out_rule: Optional[KnockOutRuleDefinition] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        _require(self.product_hint == ProductHint.FX_TARF, "FxTarfIndication requires product_hint=FX_TARF.")
        _non_empty(self.bought_currency, "bought_currency")
        _non_empty(self.sold_currency, "sold_currency")
        object.__setattr__(self, "ratio", _to_decimal(self.ratio))
        _require(self.ratio > 0, "ratio must be > 0.")

    def to_definition(self) -> FxTarfDefinition:
        return FxTarfDefinition(
            product_type="FX_TARF",
            template_name="FX_TARF_RATIO_FORWARD",
            display_name=self.display_name,
            currency_pair=self.currency_pair,
            payoff_schedule=self.payoff_schedule.schedule,
            ratio_forward_terms=RatioForwardTermsDefinition(
                bought_currency=self.bought_currency,
                sold_currency=self.sold_currency,
                ratio=self.ratio,
                strike=self.strike.step,
                bought_notional=self.bought_notional.step,
            ),
            target_redemption=self.target_redemption,
            knock_out_rule=self.knock_out_rule,
            tags=("typed-indication", "fx-tarf"),
        )


@dataclass(frozen=True)
class CouponSwapIndication(TypedIndicationRequest):
    currency: str = "USD"
    components: Tuple[CouponComponentDefinition, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        _require(self.product_hint == ProductHint.COUPON_SWAP, "CouponSwapIndication requires product_hint=COUPON_SWAP.")
        _non_empty(self.currency, "currency")
        _require(len(self.components) >= 1, "CouponSwapIndication requires at least one component.")

    def to_definition(self) -> CouponSwapDefinition:
        return CouponSwapDefinition(
            product_type="COUPON_SWAP",
            template_name="COUPON_SWAP",
            display_name=self.display_name,
            currency=self.currency,
            components=self.components,
            tags=("typed-indication", "coupon-swap"),
        )


@dataclass(frozen=True)
class DigitalCouponSwapIndication(TypedIndicationRequest):
    currency: str = "USD"
    components: Tuple[CouponComponentDefinition, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        _require(
            self.product_hint == ProductHint.DIGITAL_COUPON_SWAP,
            "DigitalCouponSwapIndication requires product_hint=DIGITAL_COUPON_SWAP.",
        )
        _non_empty(self.currency, "currency")
        _require(len(self.components) >= 1, "DigitalCouponSwapIndication requires at least one component.")

    def to_definition(self) -> DigitalCouponSwapDefinition:
        return DigitalCouponSwapDefinition(
            product_type="DIGITAL_COUPON_SWAP",
            template_name="DIGITAL_COUPON_SWAP",
            display_name=self.display_name,
            currency=self.currency,
            components=self.components,
            tags=("typed-indication", "digital-coupon-swap"),
        )


TypedIndication = Union[
    FxTarfIndication,
    CouponSwapIndication,
    DigitalCouponSwapIndication,
]


# ============================================================================
# Flexible / bespoke indication building blocks
# ============================================================================

@dataclass(frozen=True)
class EconomicClause(ABC):
    clause_type: str

    def __post_init__(self) -> None:
        _non_empty(self.clause_type, "clause_type")


@dataclass(frozen=True)
class ScheduleClause(EconomicClause):
    schedule: ScheduleDefinition

    def __init__(self, schedule: ScheduleDefinition):
        object.__setattr__(self, "clause_type", "SCHEDULE")
        object.__setattr__(self, "schedule", schedule)


@dataclass(frozen=True)
class RatioForwardClause(EconomicClause):
    currency_pair: CurrencyPairDefinition
    bought_currency: str
    sold_currency: str
    ratio: Decimal
    strike: StepDefinition
    bought_notional: StepDefinition
    sold_notional: Optional[StepDefinition] = None
    description: Optional[str] = None

    def __init__(
        self,
        currency_pair: CurrencyPairDefinition,
        bought_currency: str,
        sold_currency: str,
        ratio: Decimal,
        strike: StepDefinition,
        bought_notional: StepDefinition,
        sold_notional: Optional[StepDefinition] = None,
        description: Optional[str] = None,
    ):
        object.__setattr__(self, "clause_type", "RATIO_FORWARD")
        object.__setattr__(self, "currency_pair", currency_pair)
        object.__setattr__(self, "bought_currency", bought_currency)
        object.__setattr__(self, "sold_currency", sold_currency)
        object.__setattr__(self, "ratio", _to_decimal(ratio))
        object.__setattr__(self, "strike", strike)
        object.__setattr__(self, "bought_notional", bought_notional)
        object.__setattr__(self, "sold_notional", sold_notional)
        object.__setattr__(self, "description", description)
        _non_empty(bought_currency, "bought_currency")
        _non_empty(sold_currency, "sold_currency")
        _require(_to_decimal(ratio) > 0, "ratio must be > 0.")


@dataclass(frozen=True)
class TargetRedemptionClause(EconomicClause):
    target: TargetRedemptionDefinition

    def __init__(self, target: TargetRedemptionDefinition):
        object.__setattr__(self, "clause_type", "TARGET_REDEMPTION")
        object.__setattr__(self, "target", target)


@dataclass(frozen=True)
class KnockOutClause(EconomicClause):
    knock_out_rule: KnockOutRuleDefinition

    def __init__(self, knock_out_rule: KnockOutRuleDefinition):
        object.__setattr__(self, "clause_type", "KNOCK_OUT")
        object.__setattr__(self, "knock_out_rule", knock_out_rule)


@dataclass(frozen=True)
class CouponComponentClause(EconomicClause):
    component: CouponComponentDefinition

    def __init__(self, component: CouponComponentDefinition):
        object.__setattr__(self, "clause_type", "COUPON_COMPONENT")
        object.__setattr__(self, "component", component)


FlexibleClause = Union[
    ScheduleClause,
    RatioForwardClause,
    TargetRedemptionClause,
    KnockOutClause,
    CouponComponentClause,
]


# ============================================================================
# Uplift support
# ============================================================================

@dataclass(frozen=True)
class IndicationUpliftResult:
    definition: Optional[ProductDefinition]
    inferred_product_hint: ProductHint
    confidence: float
    notes: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(0.0 <= self.confidence <= 1.0, "confidence must be between 0 and 1.")


class IndicationUplifter:
    """Best-effort uplift from indication requests into typed product definitions."""

    def uplift(self, indication: IndicationRequest) -> IndicationUpliftResult:
        if isinstance(indication, FxTarfIndication):
            return IndicationUpliftResult(
                definition=indication.to_definition(),
                inferred_product_hint=ProductHint.FX_TARF,
                confidence=1.0,
                notes=("typed indication uplifted directly",),
            )

        if isinstance(indication, CouponSwapIndication):
            return IndicationUpliftResult(
                definition=indication.to_definition(),
                inferred_product_hint=ProductHint.COUPON_SWAP,
                confidence=1.0,
                notes=("typed indication uplifted directly",),
            )

        if isinstance(indication, DigitalCouponSwapIndication):
            return IndicationUpliftResult(
                definition=indication.to_definition(),
                inferred_product_hint=ProductHint.DIGITAL_COUPON_SWAP,
                confidence=1.0,
                notes=("typed indication uplifted directly",),
            )

        if isinstance(indication, FlexibleIndicationRequest):
            return self._uplift_flexible(indication)

        raise TypeError(f"Unsupported indication type: {type(indication)!r}")

    def _uplift_flexible(self, indication: FlexibleIndicationRequest) -> IndicationUpliftResult:
        clauses = indication.economic_clauses

        ratio_clause = next((c for c in clauses if isinstance(c, RatioForwardClause)), None)
        target_clause = next((c for c in clauses if isinstance(c, TargetRedemptionClause)), None)
        ko_clause = next((c for c in clauses if isinstance(c, KnockOutClause)), None)
        schedule_clause = next((c for c in clauses if isinstance(c, ScheduleClause)), None)

        coupon_component_clauses = tuple(c for c in clauses if isinstance(c, CouponComponentClause))

        if ratio_clause is not None and target_clause is not None:
            schedule = (
                schedule_clause.schedule
                if schedule_clause is not None
                else ExplicitScheduleDefinition(
                    periods=(ExplicitSchedulePeriod(period_id="placeholder", fixing_date=date.today()),)
                )
            )

            definition = FxTarfDefinition(
                product_type="FX_TARF",
                template_name="FX_TARF_RATIO_FORWARD",
                display_name=indication.display_name,
                currency_pair=ratio_clause.currency_pair,
                payoff_schedule=schedule,
                ratio_forward_terms=RatioForwardTermsDefinition(
                    bought_currency=ratio_clause.bought_currency,
                    sold_currency=ratio_clause.sold_currency,
                    ratio=ratio_clause.ratio,
                    strike=ratio_clause.strike,
                    bought_notional=ratio_clause.bought_notional,
                    sold_notional=ratio_clause.sold_notional,
                    description=ratio_clause.description,
                ),
                target_redemption=target_clause.target,
                knock_out_rule=ko_clause.knock_out_rule if ko_clause is not None else None,
                tags=("uplifted-from-flexible", "fx-tarf"),
            )

            notes = [
                "recognized ratio-forward clause + target-redemption clause",
                "uplifted flexible indication into FxTarfDefinition",
            ]
            if schedule_clause is None:
                notes.append("no schedule clause provided; placeholder explicit schedule inserted")
            return IndicationUpliftResult(
                definition=definition,
                inferred_product_hint=ProductHint.FX_TARF,
                confidence=0.78 if schedule_clause is not None else 0.62,
                notes=tuple(notes),
            )

        if len(coupon_component_clauses) >= 1:
            components = tuple(c.component for c in coupon_component_clauses)
            has_digital = any(
                isinstance(c.component.formula, DigitalCouponFormulaDefinition)
                for c in coupon_component_clauses
            )

            if has_digital:
                definition = DigitalCouponSwapDefinition(
                    product_type="DIGITAL_COUPON_SWAP",
                    template_name="DIGITAL_COUPON_SWAP",
                    display_name=indication.display_name,
                    currency="USD",
                    components=components,
                    tags=("uplifted-from-flexible", "digital-coupon-swap"),
                )
                return IndicationUpliftResult(
                    definition=definition,
                    inferred_product_hint=ProductHint.DIGITAL_COUPON_SWAP,
                    confidence=0.74,
                    notes=("recognized coupon component clauses with at least one digital formula",),
                )

            definition = CouponSwapDefinition(
                product_type="COUPON_SWAP",
                template_name="COUPON_SWAP",
                display_name=indication.display_name,
                currency="USD",
                components=components,
                tags=("uplifted-from-flexible", "coupon-swap"),
            )
            return IndicationUpliftResult(
                definition=definition,
                inferred_product_hint=ProductHint.COUPON_SWAP,
                confidence=0.70,
                notes=("recognized coupon component clauses",),
            )

        return IndicationUpliftResult(
            definition=None,
            inferred_product_hint=indication.product_hint,
            confidence=0.0,
            notes=("could not confidently uplift flexible indication into a typed product definition",),
        )


# ============================================================================
# Example builders
# ============================================================================

def example_typed_tarf_indication() -> FxTarfIndication:
    return FxTarfIndication(
        lane=IndicationLane.TYPED,
        product_hint=ProductHint.FX_TARF,
        display_name="Typed USDJPY TARF indication",
        currency_pair=CurrencyPairDefinition(base_currency="USD", quote_currency="JPY"),
        payoff_schedule=ScheduleIntent(
            schedule=RuleBasedScheduleDefinition(
                start_date=date(2026, 1, 28),
                end_date=date(2026, 6, 28),
                frequency=PeriodFrequency(1, PeriodUnit.MONTH),
                business_day_convention=BusinessDayConvention.MODIFIED_FOLLOWING,
                payment_lag_days=2,
            ),
            comment="Monthly regular fixing schedule intended.",
        ),
        bought_currency="USD",
        sold_currency="JPY",
        ratio=Decimal("2.0"),
        strike=StepIntent(
            step=RuleBasedStepDefinition(
                initial_value=Decimal("150.00"),
                step_values=(Decimal("151.00"), Decimal("152.50"), Decimal("154.00")),
                step_frequency=PeriodFrequency(1, PeriodUnit.MONTH),
            ),
            comment="Monthly strike step-up intended.",
        ),
        bought_notional=StepIntent(
            step=RuleBasedStepDefinition(
                initial_value=Decimal("1000000"),
                step_values=(Decimal("1200000"), Decimal("1400000"), Decimal("1600000")),
                step_frequency=PeriodFrequency(1, PeriodUnit.MONTH),
            ),
            comment="Monthly bought-notional step-up intended.",
        ),
        target_redemption=TargetRedemptionDefinition(
            target_amount=Decimal("500000"),
            accrual_currency="JPY",
            accrual_method=TargetAccrualMethod.SUM_POSITIVE_PAYOFF,
        ),
    )


def example_flexible_tarf_like_indication() -> FlexibleIndicationRequest:
    periods = (
        ExplicitSchedulePeriod("p01", fixing_date=date(2026, 1, 28), payment_date=date(2026, 1, 30)),
        ExplicitSchedulePeriod("p02", fixing_date=date(2026, 2, 26), payment_date=date(2026, 2, 28)),
        ExplicitSchedulePeriod("p03", fixing_date=date(2026, 4, 3), payment_date=date(2026, 4, 7)),
    )

    strike = ExplicitStepDefinition(
        points=(
            ExplicitStepPoint(period_id="p01", value=Decimal("150.00")),
            ExplicitStepPoint(period_id="p02", value=Decimal("151.25")),
            ExplicitStepPoint(period_id="p03", value=Decimal("153.00")),
        )
    )

    notionals = ExplicitStepDefinition(
        points=(
            ExplicitStepPoint(period_id="p01", value=Decimal("1000000")),
            ExplicitStepPoint(period_id="p02", value=Decimal("1250000")),
            ExplicitStepPoint(period_id="p03", value=Decimal("1400000")),
        )
    )

    schedule_clause = ScheduleClause(
        schedule=ExplicitScheduleDefinition(periods=periods)
    )

    ratio_clause = RatioForwardClause(
        currency_pair=CurrencyPairDefinition("USD", "JPY"),
        bought_currency="USD",
        sold_currency="JPY",
        ratio=Decimal("2.0"),
        strike=strike,
        bought_notional=notionals,
        description="Each payoff should be ratio-forward-like; schedule is intentionally irregular.",
    )

    target_clause = TargetRedemptionClause(
        target=TargetRedemptionDefinition(
            target_amount=Decimal("500000"),
            accrual_currency="JPY",
            accrual_method=TargetAccrualMethod.SUM_POSITIVE_PAYOFF,
        )
    )

    return FlexibleIndicationRequest(
        lane=IndicationLane.FLEXIBLE,
        product_hint=ProductHint.FX_TARF,
        display_name="Flexible TARF-like indication",
        uplift_preference=UpliftPreference.PREFER_TYPED_IF_POSSIBLE,
        freeform_description="Client wants an irregular TARF-like structure with target redemption.",
        economic_clauses=(schedule_clause, ratio_clause, target_clause),
    )


def example_flexible_bespoke_indication() -> FlexibleIndicationRequest:
    quarterly = RuleBasedScheduleDefinition(
        start_date=date(2026, 1, 1),
        end_date=date(2027, 1, 1),
        frequency=PeriodFrequency(3, PeriodUnit.MONTH),
        business_day_convention=BusinessDayConvention.MODIFIED_FOLLOWING,
    )

    bonus_component = CouponComponentDefinition(
        component_name="bonus_coupon",
        direction=CouponDirection.RECEIVE,
        coupon_schedule=quarterly,
        notional=RuleBasedStepDefinition(initial_value=Decimal("10000000")),
        formula=DigitalCouponFormulaDefinition(
            underlying_observable="USDJPY",
            strike=RuleBasedStepDefinition(initial_value=Decimal("150")),
            payoff_amount=RuleBasedStepDefinition(initial_value=Decimal("0.01")),
            direction=DigitalDirection.UP,
            observation_schedule=quarterly,
        ),
    )

    barrier = BarrierConditionDefinition(
        observable_name="USDJPY",
        operator=ComparisonOperator.GTE,
        level=Decimal("155"),
        observation_schedule=quarterly,
        observation_mode=ObservationMode.DISCRETE,
    )

    return FlexibleIndicationRequest(
        lane=IndicationLane.FLEXIBLE,
        product_hint=ProductHint.UNKNOWN,
        display_name="Flexible bespoke indication",
        uplift_preference=UpliftPreference.KEEP_FLEXIBLE_UNLESS_CONFIDENT,
        freeform_description="Client is exploring a digital coupon idea with KO but not committing to a standard product yet.",
        economic_clauses=(
            CouponComponentClause(component=bonus_component),
            KnockOutClause(
                knock_out_rule=KnockOutRuleDefinition(
                    condition=barrier,
                    scope=KnockOutScope.THIS_COMPONENT,
                    description="KO only on the bonus component.",
                )
            ),
        ),
    )


if __name__ == "__main__":
    uplifter = IndicationUplifter()

    typed = example_typed_tarf_indication()
    flexible_tarf = example_flexible_tarf_like_indication()
    bespoke = example_flexible_bespoke_indication()

    for x in (typed, flexible_tarf, bespoke):
        result = uplifter.uplift(x)
        print(type(x).__name__, "=>", result.inferred_product_hint.value, result.confidence, result.definition is not None)
