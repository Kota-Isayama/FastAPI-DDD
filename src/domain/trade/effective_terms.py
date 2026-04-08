import dataclasses
import enum


class ProductType(enum.Enum):
    COUPON_SWAP = "CPSW"
    FX_OPTION_BUNDLE = "FXOP"


class KnockOutType(enum.Enum):
    BLT = "BLT"
    AKO = "AKO"
    TRF = "TRF"
    

@dataclasses.dataclass(frozen=True)
class EconomicTerms:
    product_type: ProductType
