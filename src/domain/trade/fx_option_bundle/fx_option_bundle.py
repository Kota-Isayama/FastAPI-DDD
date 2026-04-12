import dataclasses
import datetime
from decimal import Decimal
import enum

from domain.trade.final_ver.common.counterparty import Counterparty
from domain.trade.final_ver.common.fee import Fee, Marukan, UpfrontFee
from domain.trade.final_ver.common.knock_out import WindowKnockOut
from domain.trade.final_ver.common.schedules import ObservationWindow, RuleBasedSchedule


@dataclasses.dataclass(frozen=True)
class FxOptionBundleScheduleRule:
    maturity_schedule: RuleBasedSchedule
    settlement_lag: int


class RelativePosition(enum.Enum):
    BELLOW = "bellow"
    BELLOW_OR_EQUAL = "bellow_or_equal"
    ABOVE = "above"
    ABOVE_OR_EQUAL = "above_or_equal"


@dataclasses.dataclass(frozen=True)
class EuropeanKnockIn:
    reference_rate: str  # fx_spot or ...
    barrier: Decimal
    
    observation_date: datetime.date
    trigger_condition: RelativePosition


class FxOption:
    fx_option_id: str  # unique_id
    position: str  # or direction.  (buy, sell)

    maturity_date: datetime.date
    settlement_date: datetime.date

    bought_currency: str
    sold_currency: str  # e.g. USD

    bought_amount: Decimal  # the amount of bought currency.
    strike: Decimal 
    
    knock_in: EuropeanKnockIn


class FixingAnchor(enum.Enum):
    MATURITY_DATE = "maturity_date"
    SETTLEMENT_DATE = "settlement_date"


@dataclasses.dataclass(frozen=True)
class FixingRule:
    fixing_anchor: FixingAnchor  # どの日付からずらすのかを表現
    fixing_lag_days: int
    fixing_calendar: frozenset[str]


@dataclasses.dataclass(frozen=True)
class NormalPayoffSpecification:
    strike: Decimal
    



@dataclasses.dataclass(frozen=True)
class FxOptionBundle:
    # Schedule related
    option_schedule: FxOptionBundleScheduleRule  # summary
    economic_rule: FxOptionEconomicRule


    explicit_fx_options: list[FxOption] | None


class FxOptionBundleTradeRevision:
    fx_option_bundle_trade_content_id: str
    fx_option_bundle: FxOptionBundle
    knock_out: WindowKnockOut
    upfront_fee: UpfrontFee
    marukan: Marukan
    counterparty: Counterparty
    referenced_market: Market

    
class FxOptionBundleTrade:
    fx_option_bundle_trade_id: str

    fx_option_bundle_trade_revisions: list[FxOptionBundleTradeRevision]

    trade_status: str
    booking_system_reference: FxOptionBundleBookingSystemRefrence

