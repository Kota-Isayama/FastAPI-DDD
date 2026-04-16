import dataclasses

from domain.trade.common.schedules.schedules import RuleBasedSchedule
from domain.trade.coupon_swap.coupon import Coupon
from domain.trade.coupon_swap.payoff_specification import CouponSwapPayoffSpecification


@dataclasses.dataclass(frozen=True)
class CouponSwapLegs:
    base_currency_leg: list[Coupon]
    quote_currency_leg: list[Coupon]


class LegFactory:
    def create_legs(schedule_rule: RuleBasedSchedule, payoff_spec: CouponSwapPayoffSpecification) -> CouponSwapLegs:
        explicit_schedule = 