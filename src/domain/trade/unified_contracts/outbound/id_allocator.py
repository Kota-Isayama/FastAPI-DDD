from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from ..common.external_refs import ExternalComponentRef, ExternalTradeRef
from ..common.representations import OptionBundleRepresentation
from ..workflow.trade import TradeDraft


class ExternalIdAllocator:
    """In-memory demo allocator.

    In production this should be backed by a durable repository keyed by
    (system_name, trade_id, revision_no, component_key).
    """

    def __init__(self) -> None:
        self._trade_counters: dict[str, int] = defaultdict(int)
        self._component_counters: dict[str, int] = defaultdict(int)

    def allocate_trade_ref(self, *, system_name: str, trade: TradeDraft, issued_at: datetime | None = None) -> ExternalTradeRef:
        self._trade_counters[system_name] += 1
        external_trade_id = f"{system_name}-{self._trade_counters[system_name]:06d}"
        ref = ExternalTradeRef(
            system_name=system_name,
            external_trade_id=external_trade_id,
            target_revision_no=trade.revision_no,
            mode="create",
            issued_at=issued_at or datetime.utcnow(),
            status="issued",
        )
        trade.attach_external_trade_ref(ref)
        return ref

    def allocate_component_refs_for_option_bundle(
        self,
        *,
        system_name: str,
        trade: TradeDraft,
        parent_external_trade_id: str,
        issued_at: datetime | None = None,
    ) -> list[ExternalComponentRef]:
        if not isinstance(trade.representation, OptionBundleRepresentation):
            return []
        refs: list[ExternalComponentRef] = []
        ts = issued_at or datetime.utcnow()
        for cf in trade.cashflows:
            component_key = str(cf.metadata.get("component_key", cf.cashflow_id))
            self._component_counters[system_name] += 1
            external_component_id = f"{system_name}-OPT-{self._component_counters[system_name]:06d}"
            ref = ExternalComponentRef(
                system_name=system_name,
                component_kind="option_leg",
                component_key=component_key,
                external_component_id=external_component_id,
                parent_external_trade_id=parent_external_trade_id,
                target_revision_no=trade.revision_no,
                mode="create",
                issued_at=ts,
                status="issued",
            )
            trade.attach_external_component_ref(ref)
            refs.append(ref)
        return refs
