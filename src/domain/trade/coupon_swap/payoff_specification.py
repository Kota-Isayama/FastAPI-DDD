import dataclasses
from decimal import Decimal
import enum


class FixingAnchor(enum.Enum):
    ACCRUAL_START = "accrual_start"
    ACCRUAL_END = "accrual_end"
    PAYMENT_DATE = "payment_date"


@dataclasses.dataclass(frozen=True)
class FixingRule:
    fixing_anchor: FixingAnchor  # どの日付からずらすのかを表現
    fixing_lag_days: int
    fixing_calendar: frozenset[str]


@dataclasses.dataclass(frozen=True)
class NormalPayoffSpecification:
    @dataclasses.dataclass(frozen=True)
    class LegSpecification:
        notional: Decimal
        coupon_rate_above_strike: Decimal
        coupon_rate_below_strike: Decimal

    base_currency: str
    quote_currency: str
    fixing_rule: FixingRule

    strike: Decimal
    base_currency_leg: LegSpecification
    quote_currency: LegSpecification

    def __post_init__(self) -> None:
        """If the payoff is not continuous, this is not normal payoff."""


@dataclasses.dataclass(frozen=True)
class NormalGapPayoffSpecification:
    @dataclasses.dataclass(frozen=True)
    class LegSpecification:
        notional: Decimal
        coupon_rate_above_strike: Decimal
        coupon_rate_below_strike: Decimal

    base_currency: str
    quote_currency: str
    fixing_rule: FixingRule

    strike: Decimal
    base_currency_leg: LegSpecification
    quote_currency: LegSpecification

    def __post_init__(self) -> None:
        """If the payoff is continuous, this is not normal gap payoff."""


@dataclasses.dataclass(frozen=True)
class RangeGapPayoffSpecification:
    @dataclasses.dataclass(frozen=True)
    class LegSpecification:
        notional: Decimal
        coupon_rate_above_high_strike: Decimal
        coupon_rate_above_between_strikes: Decimal
        coupon_rate_below_low_strike: Decimal

    base_currency: str
    quote_currency: str
    fixing_rule: FixingRule

    high_strike: Decimal
    low_strike: Decimal
    base_currency_leg: LegSpecification
    quote_currency: LegSpecification

    def __post_init__(self) -> None:
        assert self.low_strike < self.high_strike


@dataclasses.dataclass(frozen=True)
class CollarPayoffSpecification:
    @dataclasses.dataclass(frozen=True)
    class LegSpecification:
        notional: Decimal
        coupon_rate_above_high_strike: Decimal
        coupon_rate_above_between_strikes: Decimal
        coupon_rate_below_low_strike: Decimal

    base_currency: str
    quote_currency: str
    fixing_rule: FixingRule

    high_strike: Decimal
    low_strike: Decimal
    base_currency_leg: LegSpecification
    quote_currency: LegSpecification

    def __post_init__(self) -> None:
        assert self.low_strike < self.high_strike


@dataclasses.dataclass(frozen=True)
class TwoStagePayoffSpecification:
    @dataclasses.dataclass(frozen=True)
    class LegSpecification:
        notional: Decimal
        coupon_rate_above_strike: Decimal
        coupon_rate_below_strike: Decimal

    base_currency: str
    quote_currency: str
    fixing_rule: FixingRule

    first_high_strike: Decimal
    first_low_strike: Decimal
    first_base_currency_leg: LegSpecification
    first_quote_currency_leg: LegSpecification

    second_high_strike: Decimal
    second_low_strike: Decimal
    second_base_currency_leg: LegSpecification
    second_quote_currency_leg: LegSpecification


CouponSwapPayoffSpecification = NormalPayoffSpecification | NormalGapPayoffSpecification | RangeGapPayoffSpecification | CollarPayoffSpecification | TwoStagePayoffSpecification