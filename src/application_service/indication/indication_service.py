from abc import ABC, abstractmethod
import datetime
import zoneinfo

import ulid
from application_service.indication.data_transfer_object import IndicationDetailDto, IndicationGetCommand, IndicationGetResult, IndicationRegisterCommand, IndicationRegisterResult
from application_service.indication.indication_unit_of_work import IIndicationUnitOfWork
from domain.common.aware_datetime import AwareDateTime
from domain.indication.indication import Indication, IndicationDetail
from domain.indication.value_object import IndicationDetailId, IndicationId


class IIndicationSequentialNumberProvider(ABC):
    @abstractmethod
    def sequential_numbers(self, count: int) -> list[int]:
        pass


class IIndicationGroupIdProvider(ABC):
    @abstractmethod
    def group_id() -> int:
        pass

class IndicationApplicationService:
    def __init__(
            self,
            unit_of_work: IIndicationUnitOfWork,
            sequential_number_provider: IIndicationSequentialNumberProvider,
            group_id_provider: IIndicationGroupIdProvider,
            ) -> None:
        self.__indication_unit_of_work = unit_of_work
        self.__sequential_number_provider = sequential_number_provider
        self.__group_id_provider = group_id_provider
        
    def register_indication(self, command: IndicationRegisterCommand) -> IndicationRegisterResult:
        with self.__indication_unit_of_work as uow:
            # Generate common data.
            group_id = self.__group_id_provider.group_id()
            sequential_numbers = self.__sequential_number_provider.sequential_numbers(count=len(command.details))
            created_at = AwareDateTime(datetime.datetime.now(zoneinfo.ZoneInfo(key="Asia/Tokyo")))

            indications: list[Indication] = []
            for detail, sequential_number in zip(command.details, sequential_numbers):
                indication_id = IndicationId(ulid.ULID())
                indication_detail_id = IndicationDetailId(ulid.ULID())

                detail = IndicationDetail(
                    indication_detail_id=indication_detail_id,
                    created_by=command.created_by,
                    created_at=created_at,
                    counterparty=detail.counterparty,
                    indication_id=indication_id,
                )
                
                indication = Indication(
                    indication_id=indication_id,
                    created_by=command.created_by,
                    created_at=created_at,
                    history=[detail],    
                )

                indications.append(indication)

                uow.indication_repository().save(indication)

            uow.commit()
        
        return IndicationRegisterResult(indication_ids=[indication.indication_id.to_str() for indication in indications])
            
    def get_by_id(self, indication_id_str: str) -> IndicationGetResult:
        with self.__indication_unit_of_work as uow:
            indication_id = IndicationId.from_str(indication_id_str)
            indication = uow.indication_repository().get_by_id(indication_id=indication_id)

        return IndicationGetResult(
            indication_id=indication_id.to_str(),
            created_by=indication._created_by,
            created_at=indication._created_at.to_datetime(),
            history=[IndicationDetailDto(counterparty=indication_detail._counterparty) for indication_detail in indication._history]
        )
    