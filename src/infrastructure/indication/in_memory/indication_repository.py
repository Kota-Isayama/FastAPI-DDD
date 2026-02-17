import copy
from typing import Callable, Self
from domain.indication.indication import Indication
from domain.indication.repository import IIndicationRepository
from domain.indication.value_object import IndicationId


class InMemoryIndicationDB:
    def __init__(self):
        self.indications: dict[IndicationId, Indication] = {}

    def snapshot(self) -> Self:
        return copy.deepcopy(self)


class InMemoryIndicationRepository(IIndicationRepository):
    def __init__(self, db_provider: Callable[[], InMemoryIndicationDB]) -> None:
        self.__db_provider = db_provider

    def add(self, indication: Indication) -> None:
        self.__db_provider().indications[indication.indication_id] = indication

    def get_by_id(self, indication_id: IndicationId):
        return copy.deepcopy(self.__db_provider().indications.get(indication_id, None))
    