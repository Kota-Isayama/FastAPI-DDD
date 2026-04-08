from calendar import Calendar
import dataclasses
import datetime

from domain.indication.value_object import BusinessDayConvention, Frequency, RollConvention


@dataclasses.dataclass(frozen=True):
class CouponSwapScheduleTerms:
    effective_date: datetime.date
    termination_date: datetime.date
    first_foll_date: datetime.date
    roll_convention: RollConvention
    roll_frequency: Frequency
    
    fixing_mode: str
    fixing_lag: int  # TODO 何からのラグなのかを明示したい
    fixing_calendar: set[Calendar]
    fixing_bussiness_day_convention: BusinessDayConvention

    payment_lag: int
    payment_calendar: set[Calendar]
    payment_business_day_convention: BusinessDayConvention
    