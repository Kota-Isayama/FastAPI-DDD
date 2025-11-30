import datetime
import zoneinfo
import ulid
from domain.common.aware_datetime import AwareDateTime
from domain.indication.value_object import IndicationRevisionId, IndicationId, IndicationStatus


class IndicationContent:
    def __init__(
            self,
            counterparty: str,
            ) -> None:
        self._counterparty = counterparty


class IndicationRevision:
    def __init__(
            self,
            indication_revision_id: IndicationRevisionId,
            indication_revision_version: int,
            created_by: str,
            created_at: AwareDateTime,
            indication_content: IndicationContent
            ) -> None:
        self._indication_revision_id = indication_revision_id
        self._indication_revision_version = indication_revision_version
        self._created_by = created_by
        self._created_at = created_at
        self._indication_content = indication_content

        @property
        def indication_revision_id(self) -> IndicationRevisionId:
            return self._indication_revision_id

        @property
        def indication_revision_version(self) -> int:
            return self._indication_revision_version
        

class Indication:
    def __init__(
            self,
            indication_id: IndicationId,
            group_id: int,
            indication_sequential_number: int,
            indication_status: IndicationStatus,
            history: list[IndicationRevision],
            created_by: str,
            created_at: AwareDateTime,
            ) -> None:
        self._indication_id = indication_id
        self._group_id = group_id
        self._indication_sequential_number = indication_sequential_number
        self._indication_status = indication_status
        self._created_by = created_by
        self._created_at = created_at
        self._history = history
        self._events = []
    
    @property
    def indication_id(self) -> IndicationId:
        return self._indication_id
    
    def current_revision_version(self) -> int:
        return max([revision.indication_revision_version for revision in self._history])
    
    def can_revise(self) -> bool:
        """When the indication is requesting or responded, the indication can be revised."""
        return self._indication_status in [IndicationStatus.REQUESTING, IndicationStatus.RESPONDED]
    
    def revice(self, created_by: str, indication_content: IndicationContent) -> None:
        if not self.can_revise():
            raise RuntimeError
        
        next_revision_version = self.current_revision_version() + 1
        indication_revision_id = IndicationRevisionId(ulid.ULID())
        created_at = AwareDateTime(datetime.datetime.now(zoneinfo.ZoneInfo(key="Asia/Tokyo")))

        next_revision = IndicationRevision(
            indication_revision_id=indication_revision_id,
            indication_revision_version=next_revision_version,
            indication_id=self._indication_id,
            created_by=created_by,
            created_at=created_at,
            indication_content=indication_content,
        )

        self._history.append(next_revision)
        
    