from __future__ import annotations

from datetime import datetime

from ..workflow.trade import ExternalComponentRef, ExternalTradeRef, TradeDraft


class UserSpecifiedPrefixAllocator:
    def __init__(self) -> None:
        self._trade_counters: dict[str, int] = {}
        self._component_counters: dict[tuple[str, str], int] = {}

    def allocate_trade_ref(self, *, draft: TradeDraft, system_name: str, user_prefix: str, issued_at: datetime) -> ExternalTradeRef:
        key = f"{system_name}:{user_prefix}"
        self._trade_counters[key] = self._trade_counters.get(key, 0) + 1
        external_trade_id = f"{user_prefix}-{self._trade_counters[key]:06d}"
        ref = ExternalTradeRef(
            system_name=system_name,
            external_trade_id=external_trade_id,
            target_revision_no=draft.revision_no,
            issued_at=issued_at,
        )
        draft.register_external_trade_ref(ref)
        return ref

    def allocate_component_refs_for_current_snapshot(self, *, draft: TradeDraft, system_name: str, parent_external_trade_id: str, user_prefix: str, issued_at: datetime) -> list[ExternalComponentRef]:
        refs: list[ExternalComponentRef] = []
        for cf in draft.current_snapshot.cashflows:
            component_kind = cf.metadata.get("component_kind")
            component_key = cf.metadata.get("component_key")
            if component_kind != "option_leg" or not component_key:
                continue
            counter_key = (f"{system_name}:{user_prefix}", component_key)
            self._component_counters[counter_key] = self._component_counters.get(counter_key, 0) + 1
            external_component_id = f"{user_prefix}-{component_key}-{self._component_counters[counter_key]:04d}"
            ref = ExternalComponentRef(
                system_name=system_name,
                component_kind="option_leg",
                component_key=component_key,
                external_component_id=external_component_id,
                parent_external_trade_id=parent_external_trade_id,
                target_revision_no=draft.revision_no,
                issued_at=issued_at,
            )
            draft.register_external_component_ref(ref)
            refs.append(ref)
        return refs
