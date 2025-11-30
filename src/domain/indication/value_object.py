import dataclasses
import enum
import ulid

@dataclasses.dataclass(frozen=True)
class IndicationId:
    value: ulid.ULID

    def __post_init__(self) -> None:
        if not isinstance(self.value, ulid.ULID):
            raise ValueError
        
    def to_str(self) -> str:
        return str(self.value)
    
    @classmethod
    def from_str(cls, raw: str) -> "IndicationId":
        return cls(ulid.ULID.from_str(raw))


@dataclasses.dataclass(frozen=True)
class IndicationRevisionId:
    value: ulid.ULID

    def __post_init__(self) -> None:
        if not isinstance(self.value, ulid.ULID):
            raise ValueError
        
    def to_str(self) -> str:
        return str(self.value)
    
    @classmethod
    def from_str(cls, raw: str) -> "IndicationRevisionId":
        return cls(ulid.ULID.from_str(raw))
    

class IndicationStatus(enum.Enum):
    REQUESTING = "requesting"
    RESPONDED = "responded"
    DONE = "done"
    DISPOSAL = "disposal"
