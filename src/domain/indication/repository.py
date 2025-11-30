from abc import ABC, abstractmethod

from domain.indication.indication import Indication
from domain.indication.value_object import IndicationId


class IIndicationRepository(ABC):
    @abstractmethod
    def save(self, indication: Indication) -> None:
        pass

    @abstractmethod
    def get_by_id(self, indication_id: IndicationId) -> Indication:
        pass
