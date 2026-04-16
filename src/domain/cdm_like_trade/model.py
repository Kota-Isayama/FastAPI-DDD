
"""
cdm_contract_model.py

A contract-focused Python model inspired by the FINOS Common Domain Model (CDM).

Design goals
------------
- Focus on *contract representation* only.
- Omit post-trade lifecycle / event management entirely.
- Preserve CDM-like top-level structure:
    Trade -> TradableProduct -> Product -> EconomicTerms -> Payouts
- Preserve Party / Counterparty / Party1 / Party2 normalization.
- Preserve PriceQuantity / Measure / schedules concepts.
- Allow generic contingent features (e.g. knock conditions) to be attached to payouts.
- Stay broad enough to represent more than a single coupon swap toy example.

This is not a verbatim reproduction of the CDM schema.
It is a Pythonic contract model that follows the same architectural direction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional, Sequence, Tuple, Union
from abc import ABC


# ============================================================================
# Common helpers
# ============================================================================

Number = Union[int, float, Decimal]


def _to_decimal(value: Number) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _require_exactly_one(*values: object, message: str) -> None:
    count = sum(v is not None for v in values)
    if count != 1:
        raise ValueError(message)


# ============================================================================
# Enumerations
# ============================================================================

class CounterpartyRole(Enum):
    PARTY_1 = "Party1"
    PARTY_2 = "Party2"


class PayerReceiverRole(Enum):
    PAYER = "PAYER"
    RECEIVER = "RECEIVER"


class PeriodUnit(Enum):
    DAY = "D"
    WEEK = "W"
    MONTH = "M"
    YEAR = "Y"


class DayCountConvention(Enum):
    ACT_360 = "ACT/360"
    ACT_365F = "ACT/365F"
    THIRTY_360 = "30/360"


class RollConvention(Enum):
    EOM = "EOM"
    NONE = "NONE"


class PriceType(Enum):
    ASSET_PRICE = "ASSET_PRICE"
    INTEREST_RATE = "INTEREST_RATE"
    FX_RATE = "FX_RATE"
    FORWARD_POINTS = "FORWARD_POINTS"
    PREMIUM = "PREMIUM"
    CASH_PRICE = "CASH_PRICE"
    SPREAD = "SPREAD"
    CUSTOM = "CUSTOM"


class PriceExpression(Enum):
    GROSS = "GROSS"
    NET = "NET"
    CLEAN = "CLEAN"
    DIRTY = "DIRTY"
    CUSTOM = "CUSTOM"


class FinancialUnit(Enum):
    SHARE = "SHARE"
    CONTRACT = "CONTRACT"
    INDEX_UNIT = "INDEX_UNIT"
    NOTIONAL = "NOTIONAL"
    BASIS_POINT = "BASIS_POINT"
    UNIT = "UNIT"


class SettlementType(Enum):
    CASH = "CASH"
    PHYSICAL = "PHYSICAL"


class TransferSettlementType(Enum):
    PAYMENT_VS_PAYMENT = "PVP"
    DELIVERY_VS_PAYMENT = "DVP"
    FREE = "FREE"


class OptionType(Enum):
    CALL = "CALL"
    PUT = "PUT"


class ExerciseStyle(Enum):
    EUROPEAN = "EUROPEAN"
    AMERICAN = "AMERICAN"
    BERMUDAN = "BERMUDAN"


class ObservationMode(Enum):
    DISCRETE = "DISCRETE"
    CONTINUOUS = "CONTINUOUS"


class ObservationOperator(Enum):
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    EQUAL = "=="


class FeatureEffectType(Enum):
    TERMINATE_PAYOUT = "TERMINATE_PAYOUT"
    ZERO_OUT_MATCHED_PERIODS = "ZERO_OUT_MATCHED_PERIODS"
    REDUCE_RATE = "REDUCE_RATE"
    REDUCE_NOTIONAL = "REDUCE_NOTIONAL"
    FLAG_ONLY = "FLAG_ONLY"
    CUSTOM = "CUSTOM"


class TriggerType(Enum):
    KNOCK_OUT = "KNOCK_OUT"
    KNOCK_IN = "KNOCK_IN"
    DIGITAL = "DIGITAL"
    TARGET = "TARGET"
    AUTOCALL = "AUTOCALL"
    CUSTOM = "CUSTOM"


class AssetClass(Enum):
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

@dataclass(frozen=True)
class Identifier:
    issuer: Optional[str]
    value: str
    identifier_type: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.value.strip()), "Identifier.value must be non-empty.")


@dataclass(frozen=True)
class Taxonomy:
    scheme: str
    value: str

    def __post_init__(self) -> None:
        _require(bool(self.scheme.strip()), "Taxonomy.scheme must be non-empty.")
        _require(bool(self.value.strip()), "Taxonomy.value must be non-empty.")


# ============================================================================
# Party layer
# ============================================================================

@dataclass(frozen=True)
class ContactInformation:
    email: Optional[str] = None
    phone: Optional[str] = None


@dataclass(frozen=True)
class BusinessUnit:
    name: str

    def __post_init__(self) -> None:
        _require(bool(self.name.strip()), "BusinessUnit.name must be non-empty.")


@dataclass(frozen=True)
class NaturalPerson:
    first_name: str
    last_name: str


@dataclass(frozen=True)
class Account:
    account_id: str
    account_type: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.account_id.strip()), "Account.account_id must be non-empty.")


@dataclass(frozen=True)
class Party:
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
    role: CounterpartyRole
    party: Party


@dataclass(frozen=True)
class AncillaryParty:
    role: str
    party: Party

    def __post_init__(self) -> None:
        _require(bool(self.role.strip()), "AncillaryParty.role must be non-empty.")


# ============================================================================
# Date / schedule layer
# ============================================================================

@dataclass(frozen=True)
class AdjustableDate:
    unadjusted_date: date
    business_day_convention: Optional[str] = None
    business_centers: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RelativeDateOffset:
    amount: int
    unit: PeriodUnit
    business_day_convention: Optional[str] = None
    business_centers: Tuple[str, ...] = ()


@dataclass(frozen=True)
class AdjustableOrRelativeDate:
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
    period_multiplier: int
    period: PeriodUnit

    def __post_init__(self) -> None:
        _require(self.period_multiplier > 0, "Frequency.period_multiplier must be > 0.")


@dataclass(frozen=True)
class CalculationPeriodDates:
    effective_date: AdjustableOrRelativeDate
    termination_date: AdjustableOrRelativeDate
    frequency: Frequency
    roll_convention: RollConvention = RollConvention.NONE


@dataclass(frozen=True)
class PaymentDates:
    payment_frequency: Frequency
    payment_delay_days: int = 0


@dataclass(frozen=True)
class ResetDates:
    reset_frequency: Frequency
    fixing_offset_days: int = 0


# ============================================================================
# Units / measures / schedules
# ============================================================================

@dataclass(frozen=True)
class UnitType:
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
    value: Optional[Decimal] = None
    unit: Optional[UnitType] = None

    def __post_init__(self) -> None:
        if self.value is not None:
            object.__setattr__(self, "value", _to_decimal(self.value))


@dataclass(frozen=True)
class Measure(MeasureBase):
    def __post_init__(self) -> None:
        super().__post_init__()
        _require(self.value is not None, "Measure requires value.")


@dataclass(frozen=True)
class DatedValue:
    date: date
    value: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _to_decimal(self.value))


@dataclass(frozen=True)
class MeasureSchedule(MeasureBase):
    dated_values: Tuple[DatedValue, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        _require(
            self.value is not None or len(self.dated_values) > 0,
            "MeasureSchedule requires value or dated_values.",
        )


@dataclass(frozen=True)
class PriceSchedule(MeasureSchedule):
    per_unit_of: Optional[UnitType] = None
    price_type: PriceType = PriceType.CUSTOM
    price_expression: Optional[PriceExpression] = None
    metadata_location: Optional[str] = None


@dataclass(frozen=True)
class QuantitySchedule(MeasureSchedule):
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
    pass


# ============================================================================
# Observable / index / asset reference
# ============================================================================

@dataclass(frozen=True)
class Observable:
    name: str
    asset_class: AssetClass = AssetClass.OTHER
    identifier: Optional[Identifier] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.name.strip()), "Observable.name must be non-empty.")


# ============================================================================
# Settlement layer
# ============================================================================

@dataclass(frozen=True)
class SettlementDate:
    date: AdjustableOrRelativeDate


@dataclass(frozen=True)
class CashSettlementTerms:
    valuation_observable: Optional[Observable] = None
    valuation_date: Optional[AdjustableOrRelativeDate] = None


@dataclass(frozen=True)
class PhysicalSettlementTerms:
    deliverable_description: Optional[str] = None


@dataclass(frozen=True)
class SettlementBase:
    settlement_type: SettlementType
    transfer_settlement_type: Optional[TransferSettlementType] = None
    settlement_currency: Optional[str] = None
    settlement_date: Optional[SettlementDate] = None
    settlement_center: Optional[str] = None
    standard_settlement_style: Optional[str] = None


@dataclass(frozen=True)
class SettlementTerms(SettlementBase):
    cash_settlement_terms: Tuple[CashSettlementTerms, ...] = ()
    physical_settlement_terms: Optional[PhysicalSettlementTerms] = None


@dataclass(frozen=True)
class BuyerSeller:
    buyer: CounterpartyRole
    seller: CounterpartyRole

    def __post_init__(self) -> None:
        _require(self.buyer != self.seller, "Buyer and seller must be different.")


# ============================================================================
# PriceQuantity layer
# ============================================================================

@dataclass(frozen=True)
class PriceQuantity:
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
    identifiers: Tuple[Identifier, ...]
    taxonomies: Tuple[Taxonomy, ...] = ()
    is_exchange_listed: Optional[bool] = None
    exchange: Optional[Party] = None
    related_exchanges: Tuple[Party, ...] = ()

    def __post_init__(self) -> None:
        _require(len(self.identifiers) >= 1, "AssetBase requires at least one identifier.")


@dataclass(frozen=True)
class CashAsset(AssetBase):
    currency: str = "USD"


@dataclass(frozen=True)
class InstrumentAsset(AssetBase):
    instrument_type: Optional[str] = None


Asset = Union[CashAsset, InstrumentAsset]


# ============================================================================
# Rate specification layer
# ============================================================================

@dataclass(frozen=True)
class FixedRateSpecification:
    rate: PriceSchedule

    def __post_init__(self) -> None:
        _require(self.rate.price_type in (PriceType.INTEREST_RATE, PriceType.SPREAD, PriceType.CUSTOM),
                 "FixedRateSpecification.rate should be an interest-rate-like PriceSchedule.")


@dataclass(frozen=True)
class FloatingRateIndex:
    name: str
    tenor: Optional[str] = None
    source: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.name.strip()), "FloatingRateIndex.name must be non-empty.")


@dataclass(frozen=True)
class FloatingRateSpecification:
    rate_index: FloatingRateIndex
    spread: Optional[PriceSchedule] = None
    reset_dates: Optional[ResetDates] = None
    day_count_convention: Optional[DayCountConvention] = None


RateSpecification = Union[FixedRateSpecification, FloatingRateSpecification]


# ============================================================================
# Feature / trigger layer
# ============================================================================

@dataclass(frozen=True)
class ObservationTerms:
    observable: Observable
    observation_mode: ObservationMode = ObservationMode.DISCRETE
    observation_dates: Tuple[AdjustableOrRelativeDate, ...] = ()
    description: Optional[str] = None


@dataclass(frozen=True)
class TriggerLevel:
    value: Decimal
    unit: UnitType

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _to_decimal(self.value))


@dataclass(frozen=True)
class TriggerCondition:
    observable: Observable
    operator: ObservationOperator
    level: TriggerLevel
    observation_terms: Optional[ObservationTerms] = None
    trigger_type: TriggerType = TriggerType.CUSTOM


@dataclass(frozen=True)
class FeatureEffect:
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
    name: str
    trigger: TriggerCondition
    effect: FeatureEffect

    def __post_init__(self) -> None:
        _require(bool(self.name.strip()), "ContingentFeature.name must be non-empty.")


# ============================================================================
# Payout layer
# ============================================================================

@dataclass(frozen=True)
class PayerReceiver:
    payer: CounterpartyRole
    receiver: CounterpartyRole

    def __post_init__(self) -> None:
        _require(self.payer != self.receiver, "payer and receiver must be different.")


@dataclass(frozen=True)
class PayoutBase(ABC):
    payer_receiver: PayerReceiver
    price_quantities: Tuple[PriceQuantity, ...] = ()
    features: Tuple[ContingentFeature, ...] = ()
    payout_id: Optional[str] = None
    description: Optional[str] = None


@dataclass(frozen=True)
class InterestRatePayout(PayoutBase):
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
    settlement_terms: SettlementTerms = field(default_factory=lambda: SettlementTerms(settlement_type=SettlementType.CASH))
    price_quantity: Optional[PriceQuantity] = None

    def __post_init__(self) -> None:
        _require(self.price_quantity is not None, "SettlementPayout requires price_quantity.")


@dataclass(frozen=True)
class OptionExerciseTerms:
    style: ExerciseStyle
    exercise_dates: Tuple[AdjustableOrRelativeDate, ...] = ()


@dataclass(frozen=True)
class OptionPayout(PayoutBase):
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

@dataclass(frozen=True)
class EconomicTerms:
    payouts: Tuple[Payout, ...]
    effective_date: Optional[AdjustableOrRelativeDate] = None
    termination_date: Optional[AdjustableOrRelativeDate] = None
    non_standardised_terms: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(len(self.payouts) >= 1, "EconomicTerms must contain at least one payout.")


@dataclass(frozen=True)
class NonTransferableProduct:
    identifiers: Tuple[Identifier, ...] = ()
    taxonomies: Tuple[Taxonomy, ...] = ()
    economic_terms: EconomicTerms = field(default_factory=lambda: EconomicTerms(payouts=()))


@dataclass(frozen=True)
class TradableProduct:
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
    identifier: Identifier
    assigned_by: Optional[Party] = None


@dataclass(frozen=True)
class Trade:
    trade_date: date
    tradable_product: TradableProduct
    trade_identifiers: Tuple[TradeIdentifier, ...] = ()
    execution_timestamp: Optional[str] = None

    def __post_init__(self) -> None:
        _require(self.trade_date is not None, "Trade.trade_date is required.")


# ============================================================================
# Convenience builders
# ============================================================================

def currency_unit(ccy: str) -> UnitType:
    return UnitType(currency=ccy)


def financial_unit(unit: FinancialUnit) -> UnitType:
    return UnitType(financial_unit=unit)


def decimal_measure(value: Number, unit: Optional[UnitType] = None) -> Measure:
    return Measure(value=_to_decimal(value), unit=unit)


def flat_price(
    value: Number,
    unit: UnitType,
    price_type: PriceType,
    per_unit_of: Optional[UnitType] = None,
    price_expression: Optional[PriceExpression] = None,
    metadata_location: Optional[str] = None,
) -> PriceSchedule:
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
    return NonNegativeQuantitySchedule(
        value=_to_decimal(value),
        unit=unit,
        multiplier=multiplier,
        frequency=frequency,
    )


# ============================================================================
# Example assembly (contract only, no event model)
# ============================================================================

def example_trade() -> Trade:
    """
    A tiny example showing how the contract model fits together.
    The example is intentionally compact; it is not meant to be a production
    market-convention implementation.
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

    notional = flat_quantity(10_000_000, currency_unit("USD"))
    fixed_rate = flat_price(
        value=0.025,
        unit=currency_unit("USD"),
        per_unit_of=currency_unit("USD"),
        price_type=PriceType.INTEREST_RATE,
    )

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
