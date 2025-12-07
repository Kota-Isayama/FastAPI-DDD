import dataclasses
import enum

from ulid import ULID


@dataclasses.dataclass(frozen=True)
class SolverTaskId:
    value: ULID

    def __post_init__(self):
        if not isinstance(self.value, ULID):
            raise ValueError
        

@dataclasses.dataclass(frozen=True)
class SolverResultId:
    value: ULID

    def __post_init__(self):
        if not isinstance(self.value, ULID):
            raise ValueError
        

class SolverTaskStatus(enum.Enum):
    REQUESTED = "requested"
    QUEUED = "queued"
    SOLVING = "solving"
    SOLVED = "solved"
    CALCULATING_GREEKS = "calculating_greeks"
    CALCULATED_GREEKS = "calculated_greeks"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"


class SolveOutcome(enum.Enum):
    OPTIMAL = "optimal"
    NO_CONVERGENCE = "no_convergence"
    ERROE = "error"


class GreeksOutcome(enum.Enum):
    OK = "ok"
    SKIPPED_NO_SOLUTION = "skipped_no_solution"
    ERROR = "error"


@dataclasses.dataclass(frozen=True)
class TradeId:
    value: ULID

    def __post_init__(self):
        if not isinstance(self.value, ULID):
            raise ValueError
        

@dataclasses.dataclass(frozen=True)
class MarketId:
    value: ULID

    def __post_init__(self):
        if not isinstance(self.value, ULID):
            raise ValueError
        
