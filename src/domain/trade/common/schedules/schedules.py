import dataclasses
import datetime
from multiprocessing import Value


@dataclasses.dataclass(frozen=True)
class RuleBasedSchedule:
    start_date: datetime.date
    end_date: datetime.date
    frequency: str
    business_day_adjustment: str  # following, modified followind, etc.
    holiday_calendar: set[str]  # for example, (TKB, LNB, NYB)

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            msg = f"start_date must be <= end_date."
            raise ValueError(msg)
        
    def date_at(index: int) -> datetime.date:
        pass


@dataclasses.dataclass(frozen=True)
class ExplicitSchedule:
    dates: list[datetime.date]

    def __post_init__(self) -> None:
        if sorted(self.dates) != self.dates:
            msg = "dates must be sorted."
            raise ValueError(msg)
        
    def date_at(self, index: int) -> datetime.date:
        if index < 0:
            msg = "index must be 0 or positive integer."
            raise ValueError(msg)
        if index > len(self.dates):
            msg = f"index must be less then len(dates), but {index=}."
            raise ValueError(msg)
        
        return self.dates[index]


ScheduleLike = RuleBasedSchedule | ExplicitSchedule


@dataclasses.dataclass(frozen=True)
class ObservationWindow:
    start_date: datetime.date
    end_date: datetime.date
