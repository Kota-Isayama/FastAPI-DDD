from ast import main
import datetime
from types import NoneType, TracebackType
from typing import Self
from unittest.mock import Base

import ulid
from domain.common.aware_datetime import AwareDateTime
from domain.indication.indication import Indication
from domain.indication.value_object import IndicationId, IndicationStatus
from infrastructure.indication.in_memory.indication_repository import InMemoryIndicationDB, InMemoryIndicationRepository
from usecase.indication.indication_unit_of_work import IIndicationUnitOfWork


class InMemoryIndicationUnitOfWork(IIndicationUnitOfWork):
    def __init__(self, persistent_db: InMemoryIndicationDB) -> None:
        self.__commieted_db = persistent_db
        self.__staging_db: InMemoryIndicationDB | None = None
        self.__is_active = False

        self.__indication_repository : InMemoryIndicationRepository | None = None

    def _current_db(self) -> InMemoryIndicationDB:
        if not self.__is_active or self.__staging_db is None:
            msg = "outside transaction."
            raise RuntimeError(msg)
        
        return self.__staging_db

    def __enter__(self) -> Self:
        if self.__staging_db is not None:
            msg = "UoW is not re-entrant in this simple implementation."
            raise RuntimeError(msg)
        
        self.__is_active = True
        self.__staging_db = self.__commieted_db.snapshot()
        self.__indication_repository = InMemoryIndicationRepository(db_provider=self._current_db)
        return self
    
    def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, trace_back: TracebackType | None) -> bool | None:
        self.__staging_db = None
        self.__indication_repository = None
        self.__is_active = False

    def commit(self):
        self.__commieted_db.indications = self.__staging_db.snapshot().indications

    def rollback(self):
        self.__staging_db = self.__commieted_db.snapshot()

    def indication_repository(self):
        return self.__indication_repository
    

if __name__ == "__main__":
    global_db = InMemoryIndicationDB()
    unit_of_work = InMemoryIndicationUnitOfWork(global_db)

    with unit_of_work as uow:
        indication_repository = uow.indication_repository()
        indication_id1 = IndicationId(ulid.ULID())
        indication1 = Indication(
            indication_id=indication_id1,
            group_id=1,
            indication_sequential_number=1,
            indication_status=IndicationStatus.REQUESTING,
            history=[],
            created_by="KotaIsayama",
            created_at=AwareDateTime(datetime.datetime(2026, 2, 17, tzinfo=datetime.timezone.utc)),
        )
        indication_repository.add(indication1)

        uow.commit()

        indication_id2 = IndicationId(ulid.ULID())
        indication2 = Indication(
            indication_id=indication_id2,
            group_id=2,
            indication_sequential_number=2,
            indication_status=IndicationStatus.REQUESTING,
            history=[],
            created_by="KotaIsayama",
            created_at=AwareDateTime(datetime.datetime(2026, 2, 17, tzinfo=datetime.timezone.utc)),
        )

        indication_repository.add(indication2)

        print("indication1: ", indication1 := indication_repository.get_by_id(indication_id1))
        print("indication2: ", indication2 := indication_repository.get_by_id(indication_id2))

        uow.rollback()

        print("indication1: ", indication1 := indication_repository.get_by_id(indication_id1))
        print("indication2: ", indication2 := indication_repository.get_by_id(indication_id2))
        print(indication1._indication_status)

        indication1._indication_status = IndicationStatus.RESPONDED
        indication_repository.add(indication1)

        uow.commit()

    with unit_of_work as uow:
        indication1_ = uow.indication_repository().get_by_id(indication_id1)
        print(indication1_._indication_status)

        indication1_._indication_status = IndicationStatus.DONE
        uow.indication_repository().add(indication1_)

        uow.rollback()

        indication1_ = uow.indication_repository().get_by_id(indication_id1)
        print(indication1_._indication_status)
        

        