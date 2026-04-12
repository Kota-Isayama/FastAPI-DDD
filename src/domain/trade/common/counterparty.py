import dataclasses


@dataclasses.dataclass(frozen=True)
class Counterparty:
    official_name: str
    abbreviation: str
    english_name: str
    