import dataclasses
import datetime
from decimal import Decimal


@dataclasses.dataclass(frozen=True)
class FixedCoupon:
    payment_date: datetime.date
    accrual_start: datetime.date
    accrual_end: datetime.date
    daycount: str  # almolstly, 1/1

    currency: str
    notional: Decimal

    coupon_rate: Decimal


@dataclasses.dataclass(frozen=True)
class DigitalCoupon:
    payment_date: datetime.date
    accrual_start_date: datetime.date
    accrual_end_date: datetime.date
    daycount: str  # almostly, 1/1
    
    currency: str
    notional: Decimal

    reference_index: str  # FX_SPOT
    fixing_date: datetime.date
    strike: Decimal
    coupon_rate_above_strike: Decimal
    coupon_rate_below_strike: Decimal


@dataclasses.dataclass(frozen=True)
class RangeDigitalCoupon:
    payment_date: datetime.date
    accrual_start_date: datetime.date
    accrual_end_date: datetime.date
    daycount: str  # almostly, 1/1
    
    currency: str
    notional: Decimal

    reference_index: str
    fixing_date: datetime.date
    low_strike: Decimal
    high_strike: Decimal
    coupon_rate_above_high_strike: Decimal
    coupon_rate_between_strikes: Decimal
    coupon_rate_below_low_strike: Decimal


Coupon = FixedCoupon | DigitalCoupon | RangeDigitalCoupon
