import dataclasses
from decimal import Decimal
import enum

from domain.common.aware_datetime import AwareDateTime
from domain.trade.coupon_swap.payoff_specification import CouponSwapPayoffSpecification
from domain.trade.final_ver.common.counterparty import Counterparty
from domain.trade.final_ver.common.fee import UpfrontFee
from domain.trade.final_ver.common.knock_out import KnockOut
from domain.trade.final_ver.common.schedules import RuleBasedSchedule
from domain.trade.final_ver.coupon_swap.coupon import Coupon


@dataclasses.dataclass(frozen=True)
class CouponScheduleRule:
    accrual_schedule: RuleBasedSchedule
    payment_lag: int


@dataclasses.dataclass(frozen=True)
class CouponSwapTradeRevision:
    coupon_swap_trade_revision_id: str  # unique_id
    coupon_swap_trade_revision_version: int  # version
    coupon_schedule: CouponScheduleRule
    leg_dates_diverged_from_coupon_schedule: bool

    payoff_specification: CouponSwapPayoffSpecification | None
    coupons_diverged_from_payoff_specification: bool
    base_currency_leg: tuple[Coupon, ...]
    quote_currency_leg: tuple[Coupon, ...]

    knock_out: KnockOut
    upfront_fee: UpfrontFee
    counterparty: Counterparty
    referenced_market: Market

    created_by: str
    created_at: AwareDateTime
    

@dataclasses.dataclass(frozen=True)
class CouponSwapBookingSystemReference:
    booking_system: str
    trade_id_in_booking_system: str


class CouponSwapTrade:
    coupon_swap_trade_id: str

    coupon_swap_trade_revisions: list[CouponSwapTradeRevision]
    
    trade_status: str
    booking_system_reference: CouponSwapBookingSystemReference | None
