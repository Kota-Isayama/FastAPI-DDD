from __future__ import annotations

from datetime import date

from ..common.cashflows import CashflowRecord, ScheduleArchive
from ..common.representations import TradeRepresentation
from ..common.schedules import Event, EventSchedule, PeriodicScheduleSpec, ScheduleLike
from ..common.terms import ConstantTerm, StepByIndexTerm, Term
from ..products import AKOCouponSwapSpec, Contract, CouponSwapSpec, TARFSpec
from ..workflow.trade import IndicationSnapshot, TradeDraft, TradeSnapshot


FREQ_MONTHS = {
    "monthly": 1,
    "quarterly": 3,
    "semiannual": 6,
    "annual": 12,
}


def _add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                      31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def expand_schedule(schedule: ScheduleLike) -> EventSchedule:
    if isinstance(schedule, EventSchedule):
        return schedule
    if not isinstance(schedule, PeriodicScheduleSpec):
        raise TypeError(f"unsupported schedule type: {type(schedule)!r}")
    step_months = FREQ_MONTHS.get(schedule.frequency)
    if step_months is None:
        raise ValueError(f"unsupported frequency for demo expander: {schedule.frequency}")
    events: list[Event] = []
    current = schedule.start_date
    idx = 0
    while current <= schedule.end_date:
        settlement_date = current
        if schedule.settlement_lag_days:
            settlement_date = date.fromordinal(settlement_date.toordinal() + schedule.settlement_lag_days)
        events.append(Event(index=idx, fixing_date=current, settlement_date=settlement_date))
        idx += 1
        current = _add_months(current, step_months)
    return EventSchedule(events=tuple(events), role=schedule.role)



def _describe_term(term: Term[float], event_index: int) -> str:
    if isinstance(term, ConstantTerm):
        return str(term.value)
    if isinstance(term, StepByIndexTerm):
        current_value = term.steps[0][1]
        for idx, value in term.steps:
            if idx <= event_index:
                current_value = value
            else:
                break
        return str(current_value)
    return "<term>"



def _cashflows_for_tarf(contract: TARFSpec, view_kind: str, schedule_id: str) -> list[CashflowRecord]:
    schedule = expand_schedule(contract.payoff_schedule)
    out: list[CashflowRecord] = []
    for event in schedule.events:
        strike = _describe_term(contract.main_leg.strike, event.index)
        ratio = _describe_term(contract.main_leg.ratio, event.index)
        if view_kind == "coupon_swap":
            amount_desc = f"coupon from TARF {contract.payoff_style}: notional x payoff(spot, K={strike}) x ratio={ratio}"
            out.append(CashflowRecord(
                cashflow_id=f"cf-{schedule_id}-{event.index}-coupon",
                source_schedule_id=schedule_id,
                source_event_index=event.index,
                view_kind=view_kind,
                leg_label="coupon_leg",
                currency=contract.settlement_currency,
                amount_description=amount_desc,
                payment_date=event.settlement_date.isoformat(),
                metadata={"underlying": contract.underlying},
            ))
        else:
            call_desc = f"call option slice derived from TARF event, K={strike}, qty ratio={ratio}"
            put_desc = f"put option slice derived from TARF event, K={strike}, qty ratio={ratio}"
            out.append(CashflowRecord(
                cashflow_id=f"cf-{schedule_id}-{event.index}-call",
                source_schedule_id=schedule_id,
                source_event_index=event.index,
                view_kind=view_kind,
                leg_label="call_option_leg",
                currency=contract.settlement_currency,
                amount_description=call_desc,
                payment_date=event.settlement_date.isoformat(),
            ))
            out.append(CashflowRecord(
                cashflow_id=f"cf-{schedule_id}-{event.index}-put",
                source_schedule_id=schedule_id,
                source_event_index=event.index,
                view_kind=view_kind,
                leg_label="put_option_leg",
                currency=contract.settlement_currency,
                amount_description=put_desc,
                payment_date=event.settlement_date.isoformat(),
            ))
    return out



def _cashflows_for_coupon_swap(contract: CouponSwapSpec | AKOCouponSwapSpec, view_kind: str, schedule_id: str) -> list[CashflowRecord]:
    schedule = expand_schedule(contract.coupon_schedule)
    out: list[CashflowRecord] = []
    for event in schedule.events:
        strike = _describe_term(contract.coupon_formula.strike, event.index)
        ratio = _describe_term(contract.coupon_formula.ratio, event.index)
        if view_kind == "coupon_swap":
            amount_desc = f"coupon {contract.coupon_formula.payoff_style}: notional x formula(K={strike}, ratio={ratio})"
            out.append(CashflowRecord(
                cashflow_id=f"cf-{schedule_id}-{event.index}-coupon",
                source_schedule_id=schedule_id,
                source_event_index=event.index,
                view_kind=view_kind,
                leg_label="coupon_leg",
                currency=contract.coupon_currency,
                amount_description=amount_desc,
                payment_date=event.settlement_date.isoformat(),
            ))
        else:
            call_desc = f"call option basket slice from {contract.coupon_formula.payoff_style}, K={strike}, qty={ratio}"
            put_desc = f"put option basket slice from {contract.coupon_formula.payoff_style}, K={strike}, qty={ratio}"
            out.append(CashflowRecord(
                cashflow_id=f"cf-{schedule_id}-{event.index}-call",
                source_schedule_id=schedule_id,
                source_event_index=event.index,
                view_kind=view_kind,
                leg_label="call_option_leg",
                currency=contract.coupon_currency,
                amount_description=call_desc,
                payment_date=event.settlement_date.isoformat(),
            ))
            out.append(CashflowRecord(
                cashflow_id=f"cf-{schedule_id}-{event.index}-put",
                source_schedule_id=schedule_id,
                source_event_index=event.index,
                view_kind=view_kind,
                leg_label="put_option_leg",
                currency=contract.coupon_currency,
                amount_description=put_desc,
                payment_date=event.settlement_date.isoformat(),
            ))
    return out



def instantiate_trade_draft(
    *,
    draft_id: str,
    contract: Contract,
    representation: TradeRepresentation,
    indication_payload: dict,
    captured_at,
    created_by: str = "system",
    reason: str = "initial instantiation from indication",
) -> TradeDraft:
    if isinstance(contract, TARFSpec):
        schedule_id = "payoff_schedule"
        archives = [ScheduleArchive(schedule_id=schedule_id, original_schedule=contract.payoff_schedule)]
        cashflows = _cashflows_for_tarf(contract, representation.kind, schedule_id)
    elif isinstance(contract, (CouponSwapSpec, AKOCouponSwapSpec)):
        schedule_id = "coupon_schedule"
        archives = [ScheduleArchive(schedule_id=schedule_id, original_schedule=contract.coupon_schedule)]
        cashflows = _cashflows_for_coupon_swap(contract, representation.kind, schedule_id)
    else:
        raise TypeError(f"unsupported contract type: {type(contract)!r}")

    initial_snapshot = TradeSnapshot(
        revision_no=1,
        created_at=captured_at,
        created_by=created_by,
        reason=reason,
        contract=contract,
        representation=representation,
        schedule_archives=tuple(archives),
        cashflows=tuple(cashflows),
    )
    return TradeDraft(
        draft_id=draft_id,
        indication_snapshot=IndicationSnapshot(source_payload=indication_payload, captured_at=captured_at),
        snapshots=[initial_snapshot],
    )
