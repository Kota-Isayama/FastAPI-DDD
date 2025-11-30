from typing import Self
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from application_service.indication.indication_unit_of_work import IIndicationUnitOfWork
from infrastructure.indication.sqlalchemy.repository import SqlAlchemyIndicationRepository


DEFAULT_SESSION_FACTORY = sessionmaker(
    bind=create_engine("postgresql://user:postgres@localhost:5432/indication")
)

class SqlAlchemyIndicationUnitOfWork(IIndicationUnitOfWork):
    def __init__(self, session_factory: sessionmaker = DEFAULT_SESSION_FACTORY) -> None:
        self.__session_factory = session_factory
        self.__session = None
        self.__indication_repository = None

    def __enter__(self) -> Self:
        self.__session = self.__session_factory()
        self.__indication_repository = SqlAlchemyIndicationRepository(self.__session)
        
        return self
    
    def __exit__(self, *args) -> None:
        self.__session.rollback()
        self.__session.close()

    def commit(self) -> None:
        self.__session.commit()

    def rollback(self) -> None:
        self.__session.rollback()

    def indication_repository(self):
        return self.__indication_repository