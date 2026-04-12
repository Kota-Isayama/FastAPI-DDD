import dataclasses
import datetime

from domain.indication.value_object import Frequency


@dataclasses.dataclass(frozen=True)
class FxOptionBundleScheduleTerms:
    trade_date: datetime.date
    start_date: datetime.date
    end_date: datetime.date
    payment_frequency: Frequency
    total_periods: int
    std_or_eom: str
    