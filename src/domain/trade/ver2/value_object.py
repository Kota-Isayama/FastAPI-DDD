# ========================
# 共通 enum / value object
# ========================

import dataclasses
import datetime
from decimal import Decimal
import enum
from locale import currency
from types import NoneType

from click import pass_context
from sqlalchemy import true

from domain.common import aware_datetime
from domain.common.aware_datetime import AwareDateTime
from domain.indication.value_object import IndicationId, IndicationStatus


class BusinessDayConvention(enum.Enum):
    FOLLOWING = "following"
    MODIFIED_FOLLOWING = "modified_following"
    PRECEDING = "preceding"


class RollConvention(enum.Enum):
    EOM = "eom"
    STD = "std"


class Frequency(enum.Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"


class FixingMode(enum.Enum):
    PERIOD_START = "period_start"
    PERIOD_END = "period_end"


class SchemeKind(enum.Enum):
    NORMAL = "normal"
    NORMAL_GAP = "normal_gap"
    COLLAR = "collar"
    TWO_STAGE = "two_stage"
    GENERIC = "generic"


class SteppableParameter(enum.Enum):
    CALL_NOTIONAL = "call_notional"
    CALL_STRIKE = "call_strike"
    CALL_KNOCK_IN_STRIKE = "call_knock_in_strike"
    PUT_NOTIONAL = "put_notional"
    PUT_STRIKE = "put_strike"
    PUT_KNOCK_IN_STRIKE = "put_knock_in_strike"
    LOWER_KNOCK_OUT_STRIKE = "lower_knock_out_strike"
    UPPER_KNOCK_OUT_STRIKE = "upper_knock_out_strike"


# =========================
# スケジュールまわり
# =========================

@dataclasses.dataclass(frozen=True)
class AccrualSchedule:
    effective_date: datetime.date
    termination_date: datetime.date
    first_roll_date: datetime.date
    roll_convention: RollConvention
    roll_frequency: Frequency


@dataclasses.dataclass(frozen=True)
class FixingTerms:
    fixing_mode: FixingMode
    fixing_lag: int
    fixing_calendar: set[str]
    fixing_business_day_convention: BusinessDayConvention


@dataclasses.dataclass(frozen=True)
class PaymentSchedule:
    payment_lag: int
    payment_calendar: set[str]
    payment_business_day_convention: BusinessDayConvention


# =========================
# 生の構造入力
# =========================

@dataclasses.dataclass(frozen=True)
class RawPayoffInput:
    """
    IndicationContentのPayoff共通項目を寄せたもの。
    ここではまだschemeを信用しすぎない。
    """
    base_amount: Decimal
    marukan: Decimal
    upfront_fee: Decimal

    call_level: Decimal
    call_strike: Decimal
    call_knock_in_strike: Decimal | None

    put_level: Decimal
    put_strike: Decimal
    put_knock_in_strike: Decimal | None
    
    declared_scheme: SchemeKind | None


@dataclasses.dataclass(frozen=True)
class WindowKnockOutInput:
    knock_out_start_date: datetime.date
    lower_knock_out_strike: Decimal
    upper_knock_out_strike: Decimal


@dataclasses.dataclass(frozen=True)
class TargetRedemptionInput:
    has_call_target: bool
    call_target: Decimal
    has_put_target: bool
    put_target: Decimal
    target_month: Decimal


@dataclasses.dataclass(frozen=True)
class ParameterStepRule:
    parameter: str
    delta: Decimal
    start_period_index: int
    frequency: int
    max_applications: int | None

    def cumulative_delta_at(self, period_index: int) -> Decimal:
        if period_index < self.start_period_index:
            return Decimal("0")
        
        distance = period_index - self.start_period_index
        if distance % self.frequency != 0:


@dataclasses.dataclass(frozen=True)
class RawIndicationStructure:
    payoff: RawPayoffInput
    knock_out: WindowKnockOutInput | None
    target_redemption: TargetRedemptionInput | None
    step_rules: tuple[ParameterStepRule, ...]


# =========================
# 期ごとの解決済み terms
# =========================

@dataclasses.dataclass(frozen=True)
class PeriodPayoffTerms:
    period_index: int

    base_amount: Decimal
    base_currency: str

    call_level: Decimal
    call_strike: Decimal
    call_knock_in_strike: Decimal | None

    put_level: Decimal
    put_strike: Decimal
    put_knock_in_strike: Decimal | None

    lower_knock_out_strike: Decimal | None
    upper_knock_out_strike: Decimal | None

    @property
    def effective_call_amount(self) -> Decimal:
        return self.base_amount * self.call_level
    
    @property
    def effective_put_amount(self) -> Decimal:
        return self.base_amount * self.put_level


# =========================
# 分類結果
# =========================
@dataclasses.dataclass(frozen=True)
class ClassifiedScheme:
    scheme_type: SchemeKind
    reason: str | None  # ??


# =========================
# resolver / classifier
# =========================

@dataclasses.dataclass(frozen=True)
class PeriodTermsResolver:
    def resolve(
        self,
        *,
        raw: RawIndicationStructure,
        period_count: int,
    ) -> list[PeriodPayoffTerms]:
        terms: list[PeriodPayoffTerms] = []

        for period_index in range(period_count):
            base_amount = raw.payoff.base_amount
            
            call_level = raw.payoff.call_level
            call_strike = raw.payoff.call_strike
            call_knock_in_strike = raw.payoff.call_knock_in_strike

            put_level = raw.payoff.put_level
            put_strike = raw.payoff.put_strike
            put_knock_in_strike = raw.payoff.put_knock_in_strike

            lower_knock_out_strike = raw.knock_out.lower_knock_out_strike
            upper_knock_out_strike = raw.knock_out.upper_knock_out_strike

            for rule in raw.step_rules:
                delta = rule.cumulative_delta_at(period_index)
                if delta == 0:
                    continue
                
                if rule.parameter == SteppableParameter.CALL_STRIKE:
                    call_strike += delta
                elif rule.parameter == SteppableParameter.CALL_KNOCK_IN_STRIKE:
                    call_knock_in_strike += delta
                elif rule.parameter == SteppableParameter.PUT_STRIKE:
                    put_strike += delta
                elif rule.parameter == SteppableParameter.PUT_KNOCK_IN_STRIKE:
                    put_knock_in_strike += delta
                elif rule.parameter == SteppableParameter.LOWER_KNOCK_OUT_STRIKE:
                    lower_knock_out_strike += delta
                elif rule.parameter == SteppableParameter.UPPER_KNOCK_OUT_STRIKE:
                    upper_knock_out_strike += delta
                
            terms.append(
                PeriodPayoffTerms(
                    period_index=period_index,
                    base_amount=base_amount,
                    call_level=call_level,
                    call_strike=call_strike,
                    call_knock_in_strike=call_knock_in_strike,
                    put_level=put_level,
                    put_strike=put_strike,
                    put_knock_in_strike=put_knock_in_strike,
                    lower_knock_out_strike=lower_knock_out_strike,
                    upper_knock_out_strike=upper_knock_out_strike,
                )
            )

        return terms
    

class SchemeClassfier:
    def classfy(self, periods: list[PeriodPayoffTerms]) -> ClassifiedScheme:
        if not periods:
            return ClassifiedScheme(SchemeKind.GENERIC)
        
        if self._is_two_stage(periods):
            return ClassifiedScheme(SchemeKind.TWO_STAGE)
        elif self._is_all_normal(periods):
            return ClassifiedScheme(SchemeKind.NORMAL)
        elif self._is_all_normal_gap(periods):
            return ClassifiedScheme(SchemeKind.NORMAL_GAP)
        elif self._is_all_range_gap(periods):
            return ClassifiedScheme(SchemeKind.RANGE_GAP)
        elif self._is_all_collar(periods):
            return ClassifiedScheme(SchemeKind.COLLAR)
        
        return ClassifiedScheme(
            SchemeKind.GENERIC,
            "mixed or non-standard period payoff shapes."
        )
    
    def _is_all_normal(self, periods: list[PeriodPayoffTerms]) -> bool:
        pass


# =========================
# キャッシュフロースナップショット
# =========================

@dataclasses.dataclass(frozen=True)
class CashflowSnapshotLine:
    period_index: int
    fixing_date: datetime.date | None  # いらない
    payment_date: datetime.date | None  # いらない
    label: str  # ?
    base_currency: str
    quote_currency: str
    amount: Decimal
    formula_text: str | None  # ?


# =========================
# revision content
# =========================

class RevisionContentType(enum.Enum):
    STRUCTURE = "structure"
    CASHFLOW_SNAPSHOT = "cashflow_snapshot"


@dataclasses.dataclass(frozen=True)
class StructureBasedContent:  # なんでこちらにはSchemeがないのか？
    accrual_schedule: AccrualSchedule
    fixing_terms: FixingTerms
    payment_schedule: PaymentSchedule
    label: str # ?
    base_currency: str
    quote_currency: str
    amount: Decimal
    formula_text: str # ?


@dataclasses.dataclass(frozen=True)
class CashflowBasedContent:
    summary_scheme: SchemeKind
    lines: list[CashflowSnapshotLine]
    notes: tuple[str, ...]  # ?


IndicationRevisionContent = StructureBasedContent | CashflowBasedContent


# =========================
# revision / aggregate
# =========================

@dataclasses.dataclass(frozen=True)
class IndicationRevision:
    indication_revision_id: str
    indication_revision_version: int
    created_by: str
    created_at: AwareDateTime
    content: IndicationRevisionContent


@dataclasses.dataclass(frozen=True)
class Indication:
    indication_id: IndicationId
    indication_sequential_number: int
    indication_status: IndicationStatus
    
    indication_revisions: list[IndicationRevision]
    created_by: str
    created_at: AwareDateTime

    def revise_with_cashflow_snapshot(self, *, created_by, content: CashflowBasedContent) -> None:
        pass

    def revise_with_structure(self, created_by, content: StructureBasedContent)