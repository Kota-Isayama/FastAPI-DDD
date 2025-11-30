import datetime
from typing import List
from infrastructure.indication.sqlalchemy.db_base import Base
from sqlalchemy import String, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

class IndicationOrm(Base):
    __tablename__ = "indication"

    indication_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    group_id: Mapped[int]
    indication_sequential_number: Mapped[int]
    indication_status: Mapped[str]
    created_by: Mapped[str]
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    
    history: Mapped[List["IndicationRevisionOrm"]] = relationship(back_populates="indication")
    

class IndicationRevisionOrm(Base):
    __tablename__ = "indication_revision"

    indication_history_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    indication_id: Mapped[str] = mapped_column(String(26), ForeignKey("indication.indication_id"))
    created_by: Mapped[str]
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    counterparty: Mapped[str]

    indication: Mapped["IndicationOrm"] = relationship(back_populates="history")


if __name__ == "__main__":
    from ulid import ULID
    from zoneinfo import ZoneInfo

    engine = create_engine("postgresql://user:postgres@localhost:5432/indication", echo=True)
    
    # created_at = datetime.datetime.now(tz=ZoneInfo(key="Asia/Tokyo"))

    # with Session(engine) as session:
    #     indication = IndicationOrm(
    #         indication_id = str(ULID()),
    #         created_by = "KotaIsayama",
    #         created_at=created_at,
    #     )

    #     indication_history = IndicationHistoryOrm(
    #         indication_history_id=str(ULID()),
    #         created_by="KotaIsayama",
    #         created_at=created_at,
    #         counterparty="YumiAkiyama",
    #         indication=indication,
    #     )

    #     session.add(indication)

    #     session.commit()

    with Session(engine) as session:
        indication = session.get(IndicationOrm, "01KB9PWZ7G58RAP3TF1BKMSBDT")
        print(indication.history[0].counterparty)
    