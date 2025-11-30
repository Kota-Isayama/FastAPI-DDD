from domain.common.aware_datetime import AwareDateTime
from domain.indication.indication import Indication, IndicationRevision
from domain.indication.value_object import IndicationRevisionId, IndicationId
from infrastructure.indication.sqlalchemy.indication_orm import IndicationRevisionOrm, IndicationOrm


def indication_to_orm(indication: Indication) -> IndicationOrm:
    indication_orm = IndicationOrm(
        indication_id=indication._indication_id.to_str(),
        created_by=indication._created_by,
        created_at=indication._created_at.to_datetime(),
    )

    indication_orm.history = [
        _detail_to_history_orm(indication._indication_id, detail)
        for detail in indication._history
    ]

    return indication_orm


def _detail_to_history_orm(indication_id: IndicationId, detail: IndicationRevision) -> IndicationRevisionOrm:
    return IndicationRevisionOrm(
        indication_history_id=detail._indication_detail_id.to_str(),
        indication_id=indication_id,
        created_by=detail._created_by,
        created_at=detail._created_at.to_datetime(),
        counterparty=detail._counterparty,
    )


def orm_to_indication(indication_orm: IndicationOrm) -> Indication:
    history = [
        IndicationRevision(
            indication_detail_id=IndicationRevisionId.from_str(history.indication_history_id),
            indication_id=IndicationId.from_str(history.indication_id),
            counterparty=history.counterparty,
            created_by=history.created_by,
            created_at=AwareDateTime(history.created_at),
        )
        for history in indication_orm.history
    ]

    return Indication(
        indication_id=IndicationId.from_str(indication_orm.indication_id),
        history=history,
        created_by=indication_orm.created_by,
        created_at=AwareDateTime(indication_orm.created_at),
    )
