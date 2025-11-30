import dataclasses
import datetime


@dataclasses.dataclass(frozen=True)
class AwareDateTime:
    value: datetime.datetime

    def __post_init__(self) -> None:
        if not isinstance(self.value, datetime.datetime):
            raise ValueError
        if self.value.tzinfo is None:
            raise ValueError
    
    def to_datetime(self) -> datetime.datetime:
        return self.value
    
