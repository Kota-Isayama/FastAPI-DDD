from domain.indication.repository import IIndicationRepository
from sqlalchemy.orm import Session

from domain.indication.indication import Indication
from domain.indication.value_object import IndicationId
from infrastructure.indication.sqlalchemy.indication_mapper import indication_to_orm, orm_to_indication
from infrastructure.indication.sqlalchemy.indication_orm import IndicationOrm

class SqlAlchemyIndicationRepository(IIndicationRepository):
    def __init__(self, session: Session):
        self.__session = session

    def save(self, indication: Indication):
        indication_orm = indication_to_orm(indication=indication)
        self.__session.add(indication_orm)

    def get_by_id(self, indication_id: IndicationId):
        indication_orm = self.__session.get(IndicationOrm, indication_id.to_str())
        return orm_to_indication(indication_orm=indication_orm)

    