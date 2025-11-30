from abc import ABC, abstractmethod
from ast import Pass
from typing import Self

from domain.indication.repository import IIndicationRepository


class IIndicationUnitOfWork(ABC):
    @abstractmethod
    def __enter__(self) -> Self:
        pass

    @abstractmethod
    def __exit__(self, *args) -> None:
        pass

    @abstractmethod
    def commit(self) -> None:
        pass

    @abstractmethod
    def rollback(self) -> None:
        pass

    @abstractmethod
    def indication_repository(self) -> IIndicationRepository:
        pass
