import dataclasses
import enum
from locale import currency
from types import NoneType


class FxOptionDirection(enum.Enum):
    BUY = "suy"
    SELL = "sell"


class FxOptionType(enum.Enum):
    CALL = "call"
    PUT = "put"


@dataclasses.dataclass(frozen=True)
class FxOptionLegTerms:
    leg_no: int
    direction: FxOptionDirection
    option_type: FxOptionType

    amount: float
    amount_currency: Currency

    strike: float
    knock_in_strike: float | None

    