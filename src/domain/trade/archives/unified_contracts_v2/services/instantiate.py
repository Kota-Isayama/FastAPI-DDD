from __future__ import annotations

from datetime import date, datetime

from ..common.cashflows import CashflowRecord, ScheduleArchive
from ..common.payoffs import ForwardPayoffLeg, OptionPayoffLeg, classify_trade_payoff
from ..common.representations import TradeRepresentation
from ..common.schedules import Event, EventSchedule, PeriodicScheduleSpec, ScheduleLike
from ..common.terms import ConstantTerm, StepByIndexTerm, Term
from ..products import AKOCouponSwapSpec, Contract, CouponSwapSpec, TARFSpec
from ..workflow.trade import IndicationSnapshot, TradeDraft, TradeSnapshot

FREQ_MONTHS = {"monthly": 1, "quarterly": 3, "semiannual": 6, "annual": 12}


def _add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def expand_schedule(schedule: ScheduleLike) -> EventSchedule:
    if isinstance(schedule, EventSchedule):
        return schedule
    if not isinstance(schedule, PeriodicScheduleSpec):
        raise TypeError(f"unsupported schedule type: {type(schedule)!r}")
    step_months = FREQ_MONTHS.get(schedule.frequency)
    if step_months is None:
        raise ValueError(f"unsupported frequency: {schedule.frequency}")
    events = []
    current = schedule.start_date
    idx = 0
    while current <= schedule.end_date:
        settlement_date = date.fromordinal(current.toordinal() + schedule.settlement_lag_days)
        events.append(Event(index=idx, fixing_date=current, settlement_date=settlement_date))
        current = _add_months(current, step_months)
        idx += 1
    return EventSchedule(events=tuple(events), role=schedule.role)


def _term_value(term: Term[float] | None, event_index: int) -> str:
    if term is None:
        return "<none>"
    if isinstance(term, ConstantTerm):
        return str(term.value)
    if isinstance(term, StepByIndexTerm):
        return str(term.value_at(event_index))
    return "<term>"


def _cashflows_for_program(schedule: EventSchedule, schedule_id: str, currency: str, view_kind: str, program, notional_desc: str) -> list[CashflowRecord]:
    out: list[CashflowRecord] = []
    for event in schedule.events:
        payoff = program.event_payoff_at(event.index)
        if view_kind == "coupon_swap":
            amount_desc = f"{payoff.scheme_name} coupon: {notional_desc} x payoff(event={event.index})"
            out.append(CashflowRecord(
                cashflow_id=f"cf-{schedule_id}-{event.index}-coupon",
                source_schedule_id=schedule_id,
                source_event_index=event.index,
                view_kind=view_kind,
                leg_label="coupon_leg",
                currency=currency,
                amount_description=amount_desc,
                payment_date=event.settlement_date.isoformat(),
                metadata={"trade_payoff_scheme": payoff.scheme_name},
            ))
        else:
            for leg_no, leg in enumerate(payoff.legs):
                if isinstance(leg, ForwardPayoffLeg):
                    out.append(CashflowRecord(
                        cashflow_id=f"cf-{schedule_id}-{event.index}-call-syn-{leg_no}",
                        source_schedule_id=schedule_id,
                        source_event_index=event.index,
                        view_kind=view_kind,
                        leg_label=f"call_option_leg_{leg_no}",
                        currency=currency,
                        amount_description=f"synthetic call from forward, K={_term_value(leg.strike, event.index)}, qty={_term_value(leg.ratio, event.index)}",
                        payment_date=event.settlement_date.isoformat(),
                        metadata={"component_kind": "option_leg", "component_key": f"event_{event.index}_call_{leg_no}", "trade_payoff_scheme": payoff.scheme_name},
                    ))
                    out.append(CashflowRecord(
                        cashflow_id=f"cf-{schedule_id}-{event.index}-put-syn-{leg_no}",
                        source_schedule_id=schedule_id,
                        source_event_index=event.index,
                        view_kind=view_kind,
                        leg_label=f"put_option_leg_{leg_no}",
                        currency=currency,
                        amount_description=f"synthetic put from forward, K={_term_value(leg.strike, event.index)}, qty={_term_value(leg.ratio, event.index)}",
                        payment_date=event.settlement_date.isoformat(),
                        metadata={"component_kind": "option_leg", "component_key": f"event_{event.index}_put_{leg_no}", "trade_payoff_scheme": payoff.scheme_name},
                    ))
                elif isinstance(leg, OptionPayoffLeg):
                    barrier_txt = " with KI" if leg.barrier is not None else ""
                    out.append(CashflowRecord(
                        cashflow_id=f"cf-{schedule_id}-{event.index}-{leg.option_type}-{leg_no}",
                        source_schedule_id=schedule_id,
                        source_event_index=event.index,
                        view_kind=view_kind,
                        leg_label=f"{leg.option_type}_option_leg_{leg_no}",
                        currency=currency,
                        amount_description=f"{leg.position} {leg.option_type} K={_term_value(leg.strike, event.index)} qty={_term_value(leg.ratio, event.index)}{barrier_txt}",
                        payment_date=event.settlement_date.isoformat(),
                        metadata={"component_kind": "option_leg", "component_key": f"event_{event.index}_{leg.option_type}_{leg_no}", "trade_payoff_scheme": payoff.scheme_name},
                    ))
    return out


def instantiate_trade_draft(*, draft_id: str, contract: Contract, representation: TradeRepresentation, indication_payload: dict,
                            captured_at: datetime, created_by: str = "system", reason: str = "initial instantiation from indication") -> TradeDraft:
    if isinstance(contract, TARFSpec):
        schedule_id = "payoff_schedule"
        archives = (ScheduleArchive(schedule_id=schedule_id, original_schedule=contract.payoff_schedule),)
        schedule = expand_schedule(contract.payoff_schedule)
        ccy = contract.settlement_currency
        cashflows = tuple(_cashflows_for_program(schedule, schedule_id, ccy, representation.kind, contract.payoff_program, "base_notional x ratio"))
        trade_scheme = contract.trade_payoff_scheme
    elif isinstance(contract, (CouponSwapSpec, AKOCouponSwapSpec)):
        schedule_id = "coupon_schedule"
        archives = (ScheduleArchive(schedule_id=schedule_id, original_schedule=contract.coupon_schedule),)
        schedule = expand_schedule(contract.coupon_schedule)
        ccy = contract.coupon_currency
        cashflows = tuple(_cashflows_for_program(schedule, schedule_id, ccy, representation.kind, contract.payoff_program, "notional"))
        trade_scheme = contract.trade_payoff_scheme
    else:
        raise TypeError(f"unsupported contract type: {type(contract)!r}")

    initial_snapshot = TradeSnapshot(
        revision_no=1,
        created_at=captured_at,
        created_by=created_by,
        reason=reason,
        contract=contract,
        representation=representation,
        trade_payoff_scheme=trade_scheme,
        schedule_archives=archives,
        cashflows=cashflows,
    )
    return TradeDraft(
        draft_id=draft_id,
        indication_snapshot=IndicationSnapshot(source_payload=indication_payload, captured_at=captured_at),
        snapshots=[initial_snapshot],
    )
