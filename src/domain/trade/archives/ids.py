import dataclasses

import ulid


@dataclasses.dataclass(frozen=True)
class TradeId:
    value: ulid.ULID


@dataclasses.dataclass(frozen=True)
class CashflowId:
    value: ulid.ULID


@dataclasses.dataclass(frozen=True)
class ObservationEventId:
    value: ulid.ULID
