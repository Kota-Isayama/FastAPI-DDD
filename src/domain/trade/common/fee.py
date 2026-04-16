import dataclasses
import datetime
from decimal import Decimal
import enum


class PremiumPayer(enum.Enum):
    COUNTERPARTY = "counterparty"
    NIKKO = "nikko"


@dataclasses.dataclass(frozen=True)
class UpfrontFee:
    payer: PremiumPayer

    settlement_date: datetime.date

    value: Decimal
    

@dataclasses.dataclass(frozen=True)
class Marukan:
    value: Decimal
