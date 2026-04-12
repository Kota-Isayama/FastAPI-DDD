import dataclasses
import datetime
from decimal import Decimal
import enum
from multiprocessing import Value
from types import NoneType
from typing import Protocol

from ulid import T

from domain.trade.ver2.value_object import FixingMode, Frequency


class TradeStatus(enum.Enum):
    LIVE = "live"
    AMENDED = "amended"
    CANCELLED = "cancelled"


@dataclasses.dataclass(frozen=True)
class TradeHeader:
    trade_id: str
    trade_date: str
    counterparty: str
    book: str
    sales: str
    upfront_fee: float


@dataclasses.dataclass(frozen=True)
class TradeRevisionMeta:
    version: int
    created_by: str
    created_at: datetime.date
    reason: str | None


@dataclasses.dataclass(frozen=True)
class ProjectedCashflow:
    cashflow_id: str
    component_id: str | None
    period_index: int | None
    fixing_date: datetime.date
    payment_date: datetime.date
    currency: str
    amount: Decimal
    label: str
    notes: ...


class CashflowProjectable(Protocol):
    def project_cashflows(self) -> list[ProjectedCashflow]:
        pass


# ===========================
# オプション束約定
# ===========================

class SettlementType(enum.Enum):
    CASH = "cash"
    PHYSICAL = "physical"


class OptionSide(enum.Enum):
    CALL = "call"
    PUT = "put"


@dataclasses.dataclass(frozen=True)
class KnockInTerms:
    strike: Decimal
    style: str  # Europeanなど


@dataclasses.dataclass(frozen=True)
class KnockOutTerms:
    lower_strike: Decimal | None
    upper_strike: Decimal | None


@dataclasses.dataclass(frozen=True)
class OptionBundleCompressedTerms:
    structure_label: str  # ??
    currency_pair: str  # ??
    
    effective_date: datetime.date
    termination_date: datetime.date
    first_roll_date: datetime.date
    frequency: Frequency

    fixing_mode: FixingMode
    fixing_lag: int
    payment_lag: int

    amount: Decimal
    marukan: Decimal

    call_level: Decimal
    call_strike: Decimal
    call_knock_in_strike: Decimal

    put_level: Decimal
    put_strike: Decimal|None
    put_knock_out_strike: Decimal|None


@dataclasses.dataclass(frozen=True)
class OptionComponentTerms:
    component_id: str
    currency_pair: str
    option_side: OptionSide

    amount_currency: str
    amount: Decimal
    level: Decimal  # ??

    strike: Decimal
    expiry_date: datetime.date
    delivery_date: datetime.date
    settlement_type: SettlementType

    knock_in: KnockInTerms | None
    knock_out: KnockOutTerms | None

    premium_currency: str
    premium_amount: Decimal

    def effective_amount(self) -> Decimal:
        return self.amount
    

@dataclasses.dataclass(frozen=True)
class OptionComponentScheduleLine:
    component_id: str
    period_index: int
    fixing_date: datetime.date
    payment_date: datetime.date
    expiry_date: datetime.date
    delivery_date: datetime.date
    

@dataclasses.dataclass(frozen=True)
class OptionComponentSnapshot:
    terms: OptionComponentTerms  # このTermsとは？
    schedule_lines: list[OptionComponentScheduleLine]  # このスケジュールはどういうのを考えている？Pay側の列？

    def project_cashflows(self) -> list[ProjectedCashflow]:
        cashflows: list[ProjectedCashflow] = []

        if self.terms.premium_amount is not None and self.terms.premium_currency is not None:
            cashflows.append(  
                ProjectedCashflow(
                    cashflow_id=f"{self.terms.component_id}-premium",
                    component_id=self.terms.component_id,
                    period_index=None,
                    fixing_date=None,
                    payment_date=self.schedule_lines[0].payment_date if self.schedule_lines else None,
                    currency=self.terms.premium_currency,
                    amount=self.terms.premium_amount,
                    label="component premium",
                ),
            )

        for line in self.schedule_lines:
            cashflows.append(
                ProjectedCashflow(
                    cashflow_id=f"{self.terms.component_id}-{line.period_index}",
                    component_id=self.terms.component_id,
                    period_index=line.period_index,
                    fixing_date=line.fixing_date,
                    payment_date=line.payment_date,
                    currency=self.terms.amount_currency,
                    amount=None,
                    label=f"{self.terms.option_side.value} option payoff",
                ),
            )

        return cashflows


@dataclasses.dataclass(frozen=True)
class OptionBundleTradeSnapshot(CashflowProjectable):
    header: TradeHeader
    structure_label: str  # ?
    components: tuple[OptionComponentSnapshot, ...]
    total_premium_currency: str
    total_premium_amount: Decimal | None

    def __post_init__(self) -> None:
        if not self.components:
            raise ValueError("option bundle must have at least one component.")
        
    def project_cashflows(self) -> list[ProjectedCashflow]:
        cashflows: list[ProjectedCashflow] = []
        for component in self.components:
            cashflows.extend(component.project_cashflows())
        return cashflows
    

@dataclasses.dataclass(frozen=True)
class OptionBundleTradeRevision:
    mata: TradeRevisionMeta
    snapshot: OptionBundleTradeSnapshot


@dataclasses.dataclass(frozen=True)
class OptionBundleTrade:
    trade_id: str
    status: TradeStatus
    history: list[OptionBundleTradeRevision]

    def current(self) -> OptionBundleTradeSnapshot:
        if not self.history:
            raise RuntimeError("no revisions")
        return max(self.history, key=lambda r: r.meta.version).snapshot
    
    def revise(self, meta: TradeRevisionMeta, snapshot: OptionBundleTradeSnapshot) -> None:
        self.history.append(OptionBundleTradeRevision(meta=meta, snapshot=snapshot))


# ==========================
# クーポンスワップ
# ==========================

class PayReceive(enum.Enum):
    PAY = "pay"
    RECEIVE = "receive"


@dataclasses.dataclass(frozen=True)
class CouponLegPeriodTerms:
    period_index: int
    notional: Decimal
    level: Decimal  # ???
    strike: Decimal  # ???
    knock_in_strike: Decimal | None
    notes: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class CouponLegScheduleLine:
    period_index: int
    accrual_start: datetime.date
    accrual_end: datetime.date
    fixing_date: datetime.date
    payment_date: datetime.date


@dataclasses.dataclass(frozen=True)
class CouponLegSnapshot:
    leg_id: str  # ??
    direction: PayReceive
    periods: tuple[CouponLegPeriodTerms, ...]
    scheudle_lines: tuple[CouponLegScheduleLine, ...]

    def project_cashflows(self) -> list[ProjectedCashflow]:
        by_index = {line.period_index : line for line in self.scheudle_lines}
        cashflows: list[ProjectedCashflow] = []

        for p in self.periods:
            line = by_index[p.period_index]
            
            cashflows.append(
                ProjectedCashflow(
                    cashflow_id=f"{self.leg_id}-{p.period_index}",
                    component_id=self.leg_id,
                    period_index=p.period_index,
                    fixing_date=line.fixing_date,
                    payment_date=line.payment_date,
                    currency=self.currency,
                    amount=None,
                    label=f"{self.direction.value} coupon payoff",  # ??
                )
            )
    
        return cashflows


@dataclasses.dataclass(frozen=True)
class CouponSwapTradeSnapshot(CashflowProjectable):
    header: TradeHeader
    structure_label: str
    pay_leg: CouponLegSnapshot
    receive_lag: CouponLegSnapshot

    def __post_init__(self) -> None:
        if self.pay_leg.direction != PayReceive.PAY:
            raise ValueError("pay_lag must be PAY.")
        if self.receive_leg.direction != PayReceive.RECEIVE:
            raise ValueError("receive_leg must be RECEIVE")
        
    def project_cashflows(self) -> list[ProjectedCashflow]:
        return [
            *self.pay_leg.project_cashflows(),
            *self.receive_leg.project_cashflows(),
        ]
    

@dataclasses.dataclass(frozen=True)
class CouponSwapTradeRevision:
    meta: TradeRevisionMeta
    snapshot: CouponSwapTradeSnapshot


@dataclasses.dataclass(frozen=True)
class CouponSwapTrade:
    trade_id: str
    status: TradeStatus
    history: list[CouponSwapTradeRevision]

    def current(self) -> CouponSwapTradeSnapshot:
        if not self.history:
            raise RuntimeError("no revisions")
        return max(self.history, key=lambda r: r.meta.version).snapshot

    def revise(self, meta: TradeRevisionMeta, snapshot: CouponSwapTradeSnapshot) -> None:
        self.history.append(CouponSwapTradeRevision(meta=meta, snapshot=snapshot))