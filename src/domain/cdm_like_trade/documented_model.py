"""
cdm_contract_model.py

A contract-focused Python model inspired by the FINOS Common Domain Model (CDM).

This module is intentionally focused on **contract representation**:
it models who the parties are, what product was traded, what the economic
terms are, and what payout mechanics exist.

It intentionally does **not** model post-trade lifecycle management such as:
- exercises
- terminations
- partial unwinds
- novations
- settlement events already performed
- state transitions over time

Core design ideas
-----------------
1. A trade is represented as:

   Trade
   └─ TradableProduct
      ├─ counterparties
      └─ product
         └─ NonTransferableProduct
            └─ EconomicTerms
               └─ Payouts

2. Products are built from composable **Payout** components.
   This follows the CDM idea that a product is better understood as a bundle
   of economic obligations / payoff mechanics than as a single opaque label.

3. Party direction is normalized through Party1 / Party2.
   This keeps product definitions party-agnostic.

4. Prices and quantities are represented via Measure / Schedule / PriceQuantity
   building blocks, which makes it easy to express both single values and
   stepped schedules.

5. Contingent conditions such as knock-out / digital-style conditions can be
   attached to a payout as a payout-local feature, instead of forcing every
   such condition into an independent option object.

Important note
--------------
This module is **not** a verbatim transcription of the official CDM schema.
It is a Pythonic model that follows the same architectural direction for
contract representation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional, Tuple, Union
from abc import ABC


# ============================================================================
# Common helpers
# ============================================================================
#
# This section contains small utilities used throughout the model:
# - unified numeric coercion to Decimal
# - lightweight validation helpers
#
# They exist to preserve basic consistency rules in the same spirit as CDM
# cardinality / one-of constraints.
# ============================================================================

Number = Union[int, float, Decimal]


def _to_decimal(value: Number) -> Decimal:
    """Convert supported numeric input into Decimal.

    Financial contract models often benefit from using Decimal rather than
    float to reduce unintended binary floating-point artifacts.
    """
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _require(condition: bool, message: str) -> None:
    """Raise ValueError when a required condition is not met."""
    if not condition:
        raise ValueError(message)


def _require_exactly_one(*values: object, message: str) -> None:
    """Enforce a simple 'one-of' rule.

    Used for classes where exactly one of several fields must be populated,
    similar to one-of patterns in schema-driven models.
    """
    count = sum(v is not None for v in values)
    if count != 1:
        raise ValueError(message)


# ============================================================================
# Enumerations
# ============================================================================
#
# Enumerations are used to keep core categorical concepts explicit and avoid
# free-text drift in key structural fields.
# ============================================================================

class CounterpartyRole(Enum):
    """Normalized bilateral counterparty roles.

    CDM commonly normalizes bilateral counterparties into Party1 / Party2
    instead of using actual institution names in payoff direction rules.
    """
    PARTY_1 = "Party1"
    PARTY_2 = "Party2"


class PayerReceiverRole(Enum):
    """Reserved for contexts where a named payer/receiver role enum is useful."""
    PAYER = "PAYER"
    RECEIVER = "RECEIVER"


class PeriodUnit(Enum):
    """Time units used in schedule frequencies and relative offsets."""
    DAY = "D"
    WEEK = "W"
    MONTH = "M"
    YEAR = "Y"


class DayCountConvention(Enum):
    """Minimal set of day-count conventions for interest-like payouts."""
    ACT_360 = "ACT/360"
    ACT_365F = "ACT/365F"
    THIRTY_360 = "30/360"


class RollConvention(Enum):
    """Simple roll convention choices for generated schedules."""
    EOM = "EOM"
    NONE = "NONE"


class PriceType(Enum):
    """Semantic type of a price-like value."""
    ASSET_PRICE = "ASSET_PRICE"
    INTEREST_RATE = "INTEREST_RATE"
    FX_RATE = "FX_RATE"
    FORWARD_POINTS = "FORWARD_POINTS"
    PREMIUM = "PREMIUM"
    CASH_PRICE = "CASH_PRICE"
    SPREAD = "SPREAD"
    CUSTOM = "CUSTOM"


class PriceExpression(Enum):
    """Qualifier for how a price should be interpreted."""
    GROSS = "GROSS"
    NET = "NET"
    CLEAN = "CLEAN"
    DIRTY = "DIRTY"
    CUSTOM = "CUSTOM"


class FinancialUnit(Enum):
    """Illustrative financial unit vocabulary."""
    SHARE = "SHARE"
    CONTRACT = "CONTRACT"
    INDEX_UNIT = "INDEX_UNIT"
    NOTIONAL = "NOTIONAL"
    BASIS_POINT = "BASIS_POINT"
    UNIT = "UNIT"


class SettlementType(Enum):
    """High-level settlement method."""
    CASH = "CASH"
    PHYSICAL = "PHYSICAL"


class TransferSettlementType(Enum):
    """Settlement transfer style."""
    PAYMENT_VS_PAYMENT = "PVP"
    DELIVERY_VS_PAYMENT = "DVP"
    FREE = "FREE"


class OptionType(Enum):
    """Basic option direction."""
    CALL = "CALL"
    PUT = "PUT"


class ExerciseStyle(Enum):
    """Option exercise style."""
    EUROPEAN = "EUROPEAN"
    AMERICAN = "AMERICAN"
    BERMUDAN = "BERMUDAN"


class ObservationMode(Enum):
    """How an observable is monitored."""
    DISCRETE = "DISCRETE"
    CONTINUOUS = "CONTINUOUS"


class ObservationOperator(Enum):
    """Comparison operator used by trigger conditions."""
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    EQUAL = "=="


class FeatureEffectType(Enum):
    """Effect categories for payout-local contingent features."""
    TERMINATE_PAYOUT = "TERMINATE_PAYOUT"
    ZERO_OUT_MATCHED_PERIODS = "ZERO_OUT_MATCHED_PERIODS"
    REDUCE_RATE = "REDUCE_RATE"
    REDUCE_NOTIONAL = "REDUCE_NOTIONAL"
    FLAG_ONLY = "FLAG_ONLY"
    CUSTOM = "CUSTOM"


class TriggerType(Enum):
    """High-level trigger families for contingent features."""
    KNOCK_OUT = "KNOCK_OUT"
    KNOCK_IN = "KNOCK_IN"
    DIGITAL = "DIGITAL"
    TARGET = "TARGET"
    AUTOCALL = "AUTOCALL"
    CUSTOM = "CUSTOM"


class AssetClass(Enum):
    """Minimal asset-class classification used by observables."""
    INTEREST_RATE = "INTEREST_RATE"
    EQUITY = "EQUITY"
    FX = "FX"
    CREDIT = "CREDIT"
    COMMODITY = "COMMODITY"
    DIGITAL_ASSET = "DIGITAL_ASSET"
    OTHER = "OTHER"


# ============================================================================
# Reference / identifier layer
# ============================================================================
#
# These types represent identifiers and classifications attached to parties,
# assets, products, and trades.
# ============================================================================

@dataclass(frozen=True)
class Identifier:
    """A generic identifier.

    Examples:
    - LEI
    - ISIN
    - internal product ID
    - UTI
    """
    issuer: Optional[str]
    value: str
    identifier_type: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.value.strip()), "Identifier.value must be non-empty.")


@dataclass(frozen=True)
class Taxonomy:
    """A generic classification tag attached to an object."""
    scheme: str
    value: str

    def __post_init__(self) -> None:
        _require(bool(self.scheme.strip()), "Taxonomy.scheme must be non-empty.")
        _require(bool(self.value.strip()), "Taxonomy.value must be non-empty.")


# ============================================================================
# Party layer
# ============================================================================
#
# This is the bilateral counterparty layer.
# The important design choice is:
# - Party stores actual party identity
# - Counterparty adds a normalized bilateral role (Party1 / Party2)
# ============================================================================

@dataclass(frozen=True)
class ContactInformation:
    """Basic contact details for a party."""
    email: Optional[str] = None
    phone: Optional[str] = None


@dataclass(frozen=True)
class BusinessUnit:
    """A named business unit inside an institution."""
    name: str

    def __post_init__(self) -> None:
        _require(bool(self.name.strip()), "BusinessUnit.name must be non-empty.")


@dataclass(frozen=True)
class NaturalPerson:
    """A natural person reference attached to a party."""
    first_name: str
    last_name: str


@dataclass(frozen=True)
class Account:
    """A simple account representation."""
    account_id: str
    account_type: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.account_id.strip()), "Account.account_id must be non-empty.")


@dataclass(frozen=True)
class Party:
    """An actual legal or organizational party.

    A Party can have multiple identifiers and optional operational metadata.
    """
    party_ids: Tuple[Identifier, ...]
    name: Optional[str] = None
    business_units: Tuple[BusinessUnit, ...] = ()
    persons: Tuple[NaturalPerson, ...] = ()
    account: Optional[Account] = None
    contact_information: Optional[ContactInformation] = None

    def __post_init__(self) -> None:
        _require(len(self.party_ids) >= 1, "Party must have at least one identifier.")


@dataclass(frozen=True)
class Counterparty:
    """A Party plus its normalized bilateral role in a trade."""
    role: CounterpartyRole
    party: Party


@dataclass(frozen=True)
class AncillaryParty:
    """A party involved in a supporting rather than principal bilateral role."""
    role: str
    party: Party

    def __post_init__(self) -> None:
        _require(bool(self.role.strip()), "AncillaryParty.role must be non-empty.")


# ============================================================================
# Date / schedule layer
# ============================================================================
#
# These classes represent contractual date expressions:
# - absolute dates
# - relative offsets
# - frequencies
# - high-level schedule descriptors
#
# This module intentionally stops at *contract representation* and does not
# generate full cashflow schedules.
# ============================================================================

@dataclass(frozen=True)
class AdjustableDate:
    """An absolute date plus optional business-day adjustment metadata."""
    unadjusted_date: date
    business_day_convention: Optional[str] = None
    business_centers: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RelativeDateOffset:
    """A relative date expression such as '2 business days before' or '3M after'."""
    amount: int
    unit: PeriodUnit
    business_day_convention: Optional[str] = None
    business_centers: Tuple[str, ...] = ()


@dataclass(frozen=True)
class AdjustableOrRelativeDate:
    """A one-of wrapper for either an absolute or relative date definition."""
    adjustable_date: Optional[AdjustableDate] = None
    relative_date_offset: Optional[RelativeDateOffset] = None

    def __post_init__(self) -> None:
        _require_exactly_one(
            self.adjustable_date,
            self.relative_date_offset,
            message="AdjustableOrRelativeDate requires exactly one of adjustable_date or relative_date_offset.",
        )


@dataclass(frozen=True)
class Frequency:
    """A contractual recurrence frequency, such as 3M or 1Y."""
    period_multiplier: int
    period: PeriodUnit

    def __post_init__(self) -> None:
        _require(self.period_multiplier > 0, "Frequency.period_multiplier must be > 0.")


@dataclass(frozen=True)
class CalculationPeriodDates:
    """High-level accrual / calculation period definition for a payout."""
    effective_date: AdjustableOrRelativeDate
    termination_date: AdjustableOrRelativeDate
    frequency: Frequency
    roll_convention: RollConvention = RollConvention.NONE


@dataclass(frozen=True)
class PaymentDates:
    """High-level payment-date description."""
    payment_frequency: Frequency
    payment_delay_days: int = 0


@dataclass(frozen=True)
class ResetDates:
    """High-level reset/fixing schedule description."""
    reset_frequency: Frequency
    fixing_offset_days: int = 0


# ============================================================================
# Units / measures / schedules
# ============================================================================
#
# This layer is one of the most important conceptual parts of the model.
#
# Instead of treating price / quantity / rates as primitive scalars, the model
# treats them as:
# - a value
# - a unit
# - possibly a dated schedule
#
# This mirrors the CDM intuition that many contractual terms are naturally
# schedule-able.
# ============================================================================

@dataclass(frozen=True)
class UnitType:
    """A unit domain.

    Exactly one unit family must be specified.
    """
    capacity_unit: Optional[str] = None
    weather_unit: Optional[str] = None
    financial_unit: Optional[FinancialUnit] = None
    currency: Optional[str] = None

    def __post_init__(self) -> None:
        _require_exactly_one(
            self.capacity_unit,
            self.weather_unit,
            self.financial_unit,
            self.currency,
            message="UnitType must define exactly one unit domain.",
        )


@dataclass(frozen=True)
class MeasureBase:
    """A generic (value, unit) pair."""
    value: Optional[Decimal] = None
    unit: Optional[UnitType] = None

    def __post_init__(self) -> None:
        if self.value is not None:
            object.__setattr__(self, "value", _to_decimal(self.value))


@dataclass(frozen=True)
class Measure(MeasureBase):
    """A measure with mandatory value."""
    def __post_init__(self) -> None:
        super().__post_init__()
        _require(self.value is not None, "Measure requires value.")


@dataclass(frozen=True)
class DatedValue:
    """A single value effective from a specified date."""
    date: date
    value: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _to_decimal(self.value))


@dataclass(frozen=True)
class MeasureSchedule(MeasureBase):
    """A value that may either be flat or vary over time."""
    dated_values: Tuple[DatedValue, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        _require(
            self.value is not None or len(self.dated_values) > 0,
            "MeasureSchedule requires value or dated_values.",
        )


@dataclass(frozen=True)
class PriceSchedule(MeasureSchedule):
    """A schedule-able price-like quantity.

    Examples:
    - asset price
    - interest rate
    - spread
    - premium
    """
    per_unit_of: Optional[UnitType] = None
    price_type: PriceType = PriceType.CUSTOM
    price_expression: Optional[PriceExpression] = None
    metadata_location: Optional[str] = None


@dataclass(frozen=True)
class QuantitySchedule(MeasureSchedule):
    """A schedule-able quantity-like amount.

    A quantity must have a unit and is restricted to non-negative values.
    """
    multiplier: Optional[Measure] = None
    frequency: Optional[Frequency] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        _require(self.unit is not None, "QuantitySchedule requires unit.")
        if self.value is not None:
            _require(self.value >= 0, "QuantitySchedule.value must be non-negative.")
        for dv in self.dated_values:
            _require(dv.value >= 0, "QuantitySchedule.dated_values must be non-negative.")
        if self.multiplier is not None and self.multiplier.value is not None:
            _require(self.multiplier.value >= 0, "QuantitySchedule.multiplier must be non-negative.")


@dataclass(frozen=True)
class NonNegativeQuantitySchedule(QuantitySchedule):
    """Explicit subtype kept for semantic clarity."""
    pass


# ============================================================================
# Observable / index / asset reference
# ============================================================================
#
# Observables are market quantities referenced by payout formulas or triggers.
# ============================================================================

@dataclass(frozen=True)
class Observable:
    """A market observable such as USDJPY, SOFR, an equity price, etc."""
    name: str
    asset_class: AssetClass = AssetClass.OTHER
    identifier: Optional[Identifier] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.name.strip()), "Observable.name must be non-empty.")


# ============================================================================
# Settlement layer
# ============================================================================
#
# Used when a price/quantity pair is itself subject to settlement mechanics,
# such as premium payments, FX exchanges, or upfront payments.
# ============================================================================

@dataclass(frozen=True)
class SettlementDate:
    """Settlement date wrapper."""
    date: AdjustableOrRelativeDate


@dataclass(frozen=True)
class CashSettlementTerms:
    """Additional details for cash settlement."""
    valuation_observable: Optional[Observable] = None
    valuation_date: Optional[AdjustableOrRelativeDate] = None


@dataclass(frozen=True)
class PhysicalSettlementTerms:
    """Additional details for physical settlement."""
    deliverable_description: Optional[str] = None


@dataclass(frozen=True)
class SettlementBase:
    """Settlement characteristics common across methods."""
    settlement_type: SettlementType
    transfer_settlement_type: Optional[TransferSettlementType] = None
    settlement_currency: Optional[str] = None
    settlement_date: Optional[SettlementDate] = None
    settlement_center: Optional[str] = None
    standard_settlement_style: Optional[str] = None


@dataclass(frozen=True)
class SettlementTerms(SettlementBase):
    """Full settlement terms including cash/physical-specific extensions."""
    cash_settlement_terms: Tuple[CashSettlementTerms, ...] = ()
    physical_settlement_terms: Optional[PhysicalSettlementTerms] = None


@dataclass(frozen=True)
class BuyerSeller:
    """Settlement direction for a price/quantity pair."""
    buyer: CounterpartyRole
    seller: CounterpartyRole

    def __post_init__(self) -> None:
        _require(self.buyer != self.seller, "Buyer and seller must be different.")


# ============================================================================
# PriceQuantity layer
# ============================================================================
#
# PriceQuantity groups together:
# - price-like terms
# - quantity-like terms
# - the observable they refer to
# - optional settlement metadata
#
# This is useful when those terms are economically meaningful as a bundle.
# ============================================================================

@dataclass(frozen=True)
class PriceQuantity:
    """A grouped representation of price/quantity/observable terms."""
    prices: Tuple[PriceSchedule, ...] = ()
    quantities: Tuple[NonNegativeQuantitySchedule, ...] = ()
    observable: Optional[Observable] = None
    effective_date: Optional[AdjustableOrRelativeDate] = None
    settlement_terms: Optional[SettlementTerms] = None
    buyer_seller: Optional[BuyerSeller] = None

    def __post_init__(self) -> None:
        _require(
            len(self.prices) > 0 or len(self.quantities) > 0 or self.observable is not None,
            "PriceQuantity must contain at least one of price, quantity, or observable.",
        )
        if self.settlement_terms is not None:
            _require(self.buyer_seller is not None, "buyer_seller is required when settlement_terms are specified.")


# ============================================================================
# Asset / product base layer
# ============================================================================

@dataclass(frozen=True)
class AssetBase:
    """A minimal asset reference base class."""
    identifiers: Tuple[Identifier, ...]
    taxonomies: Tuple[Taxonomy, ...] = ()
    is_exchange_listed: Optional[bool] = None
    exchange: Optional[Party] = None
    related_exchanges: Tuple[Party, ...] = ()

    def __post_init__(self) -> None:
        _require(len(self.identifiers) >= 1, "AssetBase requires at least one identifier.")


@dataclass(frozen=True)
class CashAsset(AssetBase):
    """A cash asset identified by currency."""
    currency: str = "USD"


@dataclass(frozen=True)
class InstrumentAsset(AssetBase):
    """A generic instrument-like asset reference."""
    instrument_type: Optional[str] = None


Asset = Union[CashAsset, InstrumentAsset]


# ============================================================================
# Rate specification layer
# ============================================================================
#
# This layer describes how an interest-like payout determines its rate.
# ============================================================================

@dataclass(frozen=True)
class FixedRateSpecification:
    """A fixed-rate definition."""
    rate: PriceSchedule

    def __post_init__(self) -> None:
        _require(self.rate.price_type in (PriceType.INTEREST_RATE, PriceType.SPREAD, PriceType.CUSTOM),
                 "FixedRateSpecification.rate should be an interest-rate-like PriceSchedule.")


@dataclass(frozen=True)
class FloatingRateIndex:
    """A floating rate index reference such as SOFR, TONA, etc."""
    name: str
    tenor: Optional[str] = None
    source: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.name.strip()), "FloatingRateIndex.name must be non-empty.")


@dataclass(frozen=True)
class FloatingRateSpecification:
    """A floating-rate definition using an index plus optional spread."""
    rate_index: FloatingRateIndex
    spread: Optional[PriceSchedule] = None
    reset_dates: Optional[ResetDates] = None
    day_count_convention: Optional[DayCountConvention] = None


RateSpecification = Union[FixedRateSpecification, FloatingRateSpecification]


# ============================================================================
# Feature / trigger layer
# ============================================================================
#
# This is the main extension layer used to attach contingent behavior directly
# to a payout.
#
# It is especially useful for cases where a condition is *not* best modeled
# as an independent option object, but rather as a condition affecting a
# specific contractual payout stream.
# ============================================================================

@dataclass(frozen=True)
class ObservationTerms:
    """How an observable is monitored for a feature."""
    observable: Observable
    observation_mode: ObservationMode = ObservationMode.DISCRETE
    observation_dates: Tuple[AdjustableOrRelativeDate, ...] = ()
    description: Optional[str] = None


@dataclass(frozen=True)
class TriggerLevel:
    """Barrier / trigger level used in a condition."""
    value: Decimal
    unit: UnitType

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _to_decimal(self.value))


@dataclass(frozen=True)
class TriggerCondition:
    """A trigger condition tied to an observable and comparison rule."""
    observable: Observable
    operator: ObservationOperator
    level: TriggerLevel
    observation_terms: Optional[ObservationTerms] = None
    trigger_type: TriggerType = TriggerType.CUSTOM


@dataclass(frozen=True)
class FeatureEffect:
    """What happens when a trigger condition is met."""
    effect_type: FeatureEffectType
    applies_to: Optional[str] = None
    parameter_name: Optional[str] = None
    parameter_value: Optional[Decimal] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        if self.parameter_value is not None:
            object.__setattr__(self, "parameter_value", _to_decimal(self.parameter_value))


@dataclass(frozen=True)
class ContingentFeature:
    """A payout-local contingent feature.

    Conceptually:
        trigger + effect + name
    """
    name: str
    trigger: TriggerCondition
    effect: FeatureEffect

    def __post_init__(self) -> None:
        _require(bool(self.name.strip()), "ContingentFeature.name must be non-empty.")


# ============================================================================
# Payout layer
# ============================================================================
#
# This is the core product-building layer.
#
# Key design principle:
# - Products are assembled from one or more payouts
# - A payout represents a coherent payoff mechanics block
# - Contingent features may attach to that payout
#
# This helps express products such as:
# - plain vanilla swap legs
# - bonus coupon streams
# - premium/upfront settlement
# - options
# without forcing everything into a monolithic product class.
# ============================================================================

@dataclass(frozen=True)
class PayerReceiver:
    """Direction of contractual payment flow for a payout."""
    payer: CounterpartyRole
    receiver: CounterpartyRole

    def __post_init__(self) -> None:
        _require(self.payer != self.receiver, "payer and receiver must be different.")


@dataclass(frozen=True)
class PayoutBase(ABC):
    """Abstract base for all payout types.

    Shared fields:
    - payer_receiver: direction of the payout
    - price_quantities: grouped economic quantities referenced by the payout
    - features: conditional logic attached to the payout
    """
    payer_receiver: PayerReceiver
    price_quantities: Tuple[PriceQuantity, ...] = ()
    features: Tuple[ContingentFeature, ...] = ()
    payout_id: Optional[str] = None
    description: Optional[str] = None


@dataclass(frozen=True)
class InterestRatePayout(PayoutBase):
    """Interest-rate-like payout.

    Covers examples such as:
    - fixed coupon leg
    - floating coupon leg
    - bonus coupon stream
    """
    calculation_period_dates: Optional[CalculationPeriodDates] = None
    payment_dates: Optional[PaymentDates] = None
    notional_schedule: Optional[NonNegativeQuantitySchedule] = None
    rate_specification: Optional[RateSpecification] = None
    day_count_convention: Optional[DayCountConvention] = None
    compounding_method: Optional[str] = None

    def __post_init__(self) -> None:
        _require(self.notional_schedule is not None, "InterestRatePayout requires notional_schedule.")
        _require(self.rate_specification is not None, "InterestRatePayout requires rate_specification.")


@dataclass(frozen=True)
class SettlementPayout(PayoutBase):
    """Settlement/upfront/premium-like payout."""
    settlement_terms: SettlementTerms = field(default_factory=lambda: SettlementTerms(settlement_type=SettlementType.CASH))
    price_quantity: Optional[PriceQuantity] = None

    def __post_init__(self) -> None:
        _require(self.price_quantity is not None, "SettlementPayout requires price_quantity.")


@dataclass(frozen=True)
class OptionExerciseTerms:
    """Exercise terms for an option payout."""
    style: ExerciseStyle
    exercise_dates: Tuple[AdjustableOrRelativeDate, ...] = ()


@dataclass(frozen=True)
class OptionPayout(PayoutBase):
    """A standalone option-style payout."""
    option_type: OptionType = OptionType.CALL
    exercise_terms: Optional[OptionExerciseTerms] = None
    underlier: Optional[Asset] = None
    strike_price: Optional[PriceSchedule] = None
    premium: Optional[PriceQuantity] = None

    def __post_init__(self) -> None:
        _require(self.underlier is not None, "OptionPayout requires underlier.")
        _require(self.strike_price is not None, "OptionPayout requires strike_price.")


Payout = Union[InterestRatePayout, SettlementPayout, OptionPayout]


# ============================================================================
# Product / economic terms / trade layer
# ============================================================================
#
# This is the top-level contract representation hierarchy.
# ============================================================================

@dataclass(frozen=True)
class EconomicTerms:
    """The economic content of a product, primarily through its payouts."""
    payouts: Tuple[Payout, ...]
    effective_date: Optional[AdjustableOrRelativeDate] = None
    termination_date: Optional[AdjustableOrRelativeDate] = None
    non_standardised_terms: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(len(self.payouts) >= 1, "EconomicTerms must contain at least one payout.")


@dataclass(frozen=True)
class NonTransferableProduct:
    """A bilateral product represented through identifiers and economic terms."""
    identifiers: Tuple[Identifier, ...] = ()
    taxonomies: Tuple[Taxonomy, ...] = ()
    economic_terms: EconomicTerms = field(default_factory=lambda: EconomicTerms(payouts=()))


@dataclass(frozen=True)
class TradableProduct:
    """A product plus exactly two principal counterparties."""
    product: NonTransferableProduct
    counterparties: Tuple[Counterparty, Counterparty]
    ancillary_parties: Tuple[AncillaryParty, ...] = ()

    def __post_init__(self) -> None:
        _require(len(self.counterparties) == 2, "TradableProduct requires exactly two counterparties.")
        roles = {c.role for c in self.counterparties}
        _require(
            roles == {CounterpartyRole.PARTY_1, CounterpartyRole.PARTY_2},
            "TradableProduct counterparties must contain Party1 and Party2 exactly once.",
        )


@dataclass(frozen=True)
class TradeIdentifier:
    """A trade-level identifier."""
    identifier: Identifier
    assigned_by: Optional[Party] = None


@dataclass(frozen=True)
class Trade:
    """Top-level trade object."""
    trade_date: date
    tradable_product: TradableProduct
    trade_identifiers: Tuple[TradeIdentifier, ...] = ()
    execution_timestamp: Optional[str] = None

    def __post_init__(self) -> None:
        _require(self.trade_date is not None, "Trade.trade_date is required.")


# ============================================================================
# Convenience builders
# ============================================================================
#
# These are ergonomic helpers used to create commonly needed objects without
# too much boilerplate.
# ============================================================================

def currency_unit(ccy: str) -> UnitType:
    """Create a currency UnitType."""
    return UnitType(currency=ccy)


def financial_unit(unit: FinancialUnit) -> UnitType:
    """Create a financial-unit UnitType."""
    return UnitType(financial_unit=unit)


def decimal_measure(value: Number, unit: Optional[UnitType] = None) -> Measure:
    """Create a Measure from a numeric value and optional unit."""
    return Measure(value=_to_decimal(value), unit=unit)


def flat_price(
    value: Number,
    unit: UnitType,
    price_type: PriceType,
    per_unit_of: Optional[UnitType] = None,
    price_expression: Optional[PriceExpression] = None,
    metadata_location: Optional[str] = None,
) -> PriceSchedule:
    """Create a flat (non-stepped) PriceSchedule."""
    return PriceSchedule(
        value=_to_decimal(value),
        unit=unit,
        per_unit_of=per_unit_of,
        price_type=price_type,
        price_expression=price_expression,
        metadata_location=metadata_location,
    )


def flat_quantity(
    value: Number,
    unit: UnitType,
    multiplier: Optional[Measure] = None,
    frequency: Optional[Frequency] = None,
) -> NonNegativeQuantitySchedule:
    """Create a flat (non-stepped) non-negative quantity schedule."""
    return NonNegativeQuantitySchedule(
        value=_to_decimal(value),
        unit=unit,
        multiplier=multiplier,
        frequency=frequency,
    )


# ============================================================================
# Example assembly
# ============================================================================
#
# This example demonstrates the intended reading of the model:
# - a trade has two bilateral counterparties
# - a product is assembled from multiple payouts
# - one payout can have a payout-local contingent feature
#
# Importantly, the example remains at the contract-definition level.
# It does not evaluate triggers or generate lifecycle events.
# ============================================================================

def example_trade() -> Trade:
    """Build a compact sample trade for exploratory reading and testing.

    Structure:
    - Party1 and Party2
    - one product
    - two payouts:
      * base coupon payout
      * bonus coupon payout with a payout-local knock-out feature
    """
    party1 = Party(
        party_ids=(Identifier(issuer="LEI", value="PARTY1LEI"),),
        name="Bank A",
    )
    party2 = Party(
        party_ids=(Identifier(issuer="LEI", value="PARTY2LEI"),),
        name="Bank B",
    )

    cp1 = Counterparty(role=CounterpartyRole.PARTY_1, party=party1)
    cp2 = Counterparty(role=CounterpartyRole.PARTY_2, party=party2)

    # Shared economic inputs.
    notional = flat_quantity(10_000_000, currency_unit("USD"))
    fixed_rate = flat_price(
        value=0.025,
        unit=currency_unit("USD"),
        per_unit_of=currency_unit("USD"),
        price_type=PriceType.INTEREST_RATE,
    )

    # Observable and payout-local KO feature.
    fx_obs = Observable(
        name="USDJPY",
        asset_class=AssetClass.FX,
        identifier=Identifier(issuer="RIC", value="USDJPY="),
    )

    ko_feature = ContingentFeature(
        name="BonusCouponKnockOut",
        trigger=TriggerCondition(
            observable=fx_obs,
            operator=ObservationOperator.GREATER_THAN_OR_EQUAL,
            level=TriggerLevel(value=Decimal("150"), unit=currency_unit("JPY")),
            observation_terms=ObservationTerms(observable=fx_obs),
            trigger_type=TriggerType.KNOCK_OUT,
        ),
        effect=FeatureEffect(
            effect_type=FeatureEffectType.TERMINATE_PAYOUT,
            applies_to="this_payout",
            description="If USDJPY >= 150, terminate this payout's future contractual stream.",
        ),
    )

    # Base coupon payout.
    base_coupon = InterestRatePayout(
        payout_id="base_coupon",
        payer_receiver=PayerReceiver(
            payer=CounterpartyRole.PARTY_1,
            receiver=CounterpartyRole.PARTY_2,
        ),
        notional_schedule=notional,
        rate_specification=FixedRateSpecification(rate=fixed_rate),
        day_count_convention=DayCountConvention.ACT_360,
        calculation_period_dates=CalculationPeriodDates(
            effective_date=AdjustableOrRelativeDate(
                adjustable_date=AdjustableDate(date(2026, 1, 1))
            ),
            termination_date=AdjustableOrRelativeDate(
                adjustable_date=AdjustableDate(date(2031, 1, 1))
            ),
            frequency=Frequency(3, PeriodUnit.MONTH),
        ),
        payment_dates=PaymentDates(payment_frequency=Frequency(3, PeriodUnit.MONTH)),
        description="Base coupon payout without knock-out feature.",
    )

    # Bonus coupon payout, modeled as a separate payout because its payoff
    # mechanics / contingent behavior are distinct from the base coupon stream.
    bonus_coupon = InterestRatePayout(
        payout_id="bonus_coupon",
        payer_receiver=PayerReceiver(
            payer=CounterpartyRole.PARTY_1,
            receiver=CounterpartyRole.PARTY_2,
        ),
        notional_schedule=notional,
        rate_specification=FixedRateSpecification(
            rate=flat_price(
                value=0.01,
                unit=currency_unit("USD"),
                per_unit_of=currency_unit("USD"),
                price_type=PriceType.INTEREST_RATE,
            )
        ),
        day_count_convention=DayCountConvention.ACT_360,
        calculation_period_dates=CalculationPeriodDates(
            effective_date=AdjustableOrRelativeDate(
                adjustable_date=AdjustableDate(date(2027, 1, 1))
            ),
            termination_date=AdjustableOrRelativeDate(
                adjustable_date=AdjustableDate(date(2031, 1, 1))
            ),
            frequency=Frequency(3, PeriodUnit.MONTH),
        ),
        payment_dates=PaymentDates(payment_frequency=Frequency(3, PeriodUnit.MONTH)),
        features=(ko_feature,),
        description="Bonus coupon payout with payout-local knock-out feature.",
    )

    product = NonTransferableProduct(
        identifiers=(Identifier(issuer="INTERNAL", value="PROD-001"),),
        taxonomies=(Taxonomy(scheme="ASSET_CLASS", value="INTEREST_RATE"),),
        economic_terms=EconomicTerms(
            payouts=(base_coupon, bonus_coupon),
            effective_date=AdjustableOrRelativeDate(
                adjustable_date=AdjustableDate(date(2026, 1, 1))
            ),
            termination_date=AdjustableOrRelativeDate(
                adjustable_date=AdjustableDate(date(2031, 1, 1))
            ),
        ),
    )

    tradable_product = TradableProduct(
        product=product,
        counterparties=(cp1, cp2),
    )

    return Trade(
        trade_date=date(2026, 1, 1),
        tradable_product=tradable_product,
        trade_identifiers=(
            TradeIdentifier(identifier=Identifier(issuer="UTI", value="UTI-EXAMPLE-0001")),
        ),
    )


if __name__ == "__main__":
    t = example_trade()
    print("Trade date:", t.trade_date)
    print("Counterparties:", [cp.role.value for cp in t.tradable_product.counterparties])
    print("Payout count:", len(t.tradable_product.product.economic_terms.payouts))
    for payout in t.tradable_product.product.economic_terms.payouts:
        print("-", payout.payout_id, type(payout).__name__, "features=", len(payout.features))
