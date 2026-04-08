import enum


class TradeStatus(enum.Enum):
    EDITING = "editing"


class ArtifactState(enum.Enum):
    GENERATED = "generated"
    MIXED = "mixed"
    