import dataclasses
from decimal import Decimal
import enum

from domain.trade.contracts_ext.terms import Term
from domain.trade.final_ver.common.schedules import ObservationWindow
from domain.trade.final_ver.fx_option_bundle.fx_option_bundle import RelativePosition


@dataclasses.dataclass(frozen=True)
class WindowKnockOut:
    reference_rate: str
    barrier: Term[float]  # This is steppable...

    observation_window: ObservationWindow
    trigger_condition: RelativePosition


class TargetMeasure(enum.Enum):
    COUNTERPARTY_NET_SETTLEMENT = "counterparty_net_settlement"
    NIKKO_NET_SETTLEMENT = "nikko_net_settlement"


class AccumulationStyle(enum.Enum):
    SIGNED = "signed"
    POSITIVE_PART = "positive_part"
    NEGATIVE_PART = "negative_part"


class TargetHitCouponTreatment(enum.Enum):
    CAPPED_TO_TARGET = "capped_to_target"
    FULL = "full"
    OMIT = "omit"


@dataclasses.dataclass(frozen=True)
class TargetRedemption:
    # この2つはもう一度考えたほうがいい
    target_measure: TargetMeasure
    accumulation_style: AccumulationStyle

    target_amount: Decimal
    target_type: str  # Amount, Percentage or etc...

    target_hit_coupon_treatment: TargetHitCouponTreatment


KnockOut = WindowKnockOut | TargetRedemption