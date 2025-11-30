from domain.common.aware_datetime import AwareDateTime
from domain.indication.value_object import IndicationDetailId, IndicationId


class IndicationDetail:
    def __init__(
            self,
            indication_detail_id: IndicationDetailId,
            indication_id: IndicationId,
            created_by: str,
            created_at: AwareDateTime,
            counterparty: str,
            ) -> None:
        self._indication_detail_id = indication_detail_id
        self._indication_id = indication_id
        self._created_by = created_by
        self._created_at = created_at
        self._counterparty = counterparty 
        

class Indication:
    def __init__(
            self,
            indication_id: IndicationId,
            history: list[IndicationDetail],
            created_by: str,
            created_at: AwareDateTime,
            ) -> None:
        self._indication_id = indication_id
        self._created_by = created_by
        self._created_at = created_at
        self._history = history
        self._events = []
    
    @property
    def indication_id(self) -> IndicationId:
        return self._indication_id
    