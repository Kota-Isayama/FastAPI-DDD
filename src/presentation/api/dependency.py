from fastapi import Depends
from application_service.indication.indication_service import IIndicationGroupIdProvider, IIndicationSequentialNumberProvider, IndicationApplicationService
from application_service.indication.indication_unit_of_work import IIndicationUnitOfWork
from infrastructure.indication.in_memory.group_id_provider import InMemoryIndicationGroupIdProvider
from infrastructure.indication.in_memory.sequential_number_provider import InMemoryIndicationSequentialNumberProvider
from infrastructure.indication.sqlalchemy.indication_unit_of_work import SqlAlchemyIndicationUnitOfWork


def get_indication_uow() -> IIndicationUnitOfWork:
    return SqlAlchemyIndicationUnitOfWork()


def get_indication_sequential_number_provider() -> IIndicationSequentialNumberProvider:
    return InMemoryIndicationSequentialNumberProvider()


def get_indication_group_id_provider() -> IIndicationGroupIdProvider:
    return InMemoryIndicationGroupIdProvider()


def get_indication_application_service(
    unit_of_work: IIndicationUnitOfWork = Depends(get_indication_uow),
    sequential_number_provider: IIndicationSequentialNumberProvider = Depends(get_indication_sequential_number_provider),
    group_id_provider: IIndicationGroupIdProvider = Depends(get_indication_group_id_provider),
) -> IndicationApplicationService:
    return IndicationApplicationService(
        unit_of_work=unit_of_work,
        sequential_number_provider=sequential_number_provider,
        group_id_provider=group_id_provider,
    )
