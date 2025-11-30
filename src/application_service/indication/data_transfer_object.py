import datetime
from typing import List, Self
from pydantic import BaseModel, Field

from domain.indication.indication import Indication, IndicationContent, IndicationRevision


class IndicationContentDto(BaseModel):
    counterparty: str = Field(examples=["AkiyamaYumi"])

    @classmethod
    def from_indication_content(cls, indication_content: IndicationContent) -> Self:
        return cls(counterparty=indication_content._counterparty)

class IndicationRegisterCommand(BaseModel):
    created_by: str = Field(examples=["KotaIsayama"])
    contents: List[IndicationContentDto] = Field(examples=[[IndicationContentDto(counterparty="YumiAkiyama"), IndicationContentDto(counterparty="YuriKatsuki")]])


class IndicationRegisterResult(BaseModel):
    indication_ids: List[str] = Field(examples=[["01KBA6DBS6QHG0B4FVJ54QKBM1", "01KBA6E878MVJGRNXW38MNZK1M"]])
    

class IndicationGetCommand(BaseModel):
    indication_id: str


class IndicationRevisionDto(BaseModel):
    indication_revision_id: str = Field(examples=["01KBA6E878MVJGRNXW38MNZK1M"])
    indication_revision_version: int = Field(examples=[1])
    created_by: str = Field(examples=["TanjiroKamado"])
    created_at: datetime.datetime = Field(examples=[datetime.datetime(2025, 11, 30)])
    indication_content: IndicationContentDto

    @classmethod
    def from_indication_revision(cls, indication_revision: IndicationRevision) -> Self:
        cls(
            indication_revision_id=indication_revision._indication_revision_id.to_str(),
            indication_revision_version=indication_revision._indication_revision_version,
            created_by=indication_revision._created_by,
            created_at=indication_revision._created_at.to_datetime(),
            indication_content=IndicationContentDto.from_indication_content(indication_revision._indication_content),
        )


class IndicationGetResult(BaseModel):
    indication_id: str = Field(examples=["01KBA6DBS6QHG0B4FVJ54QKBM1"])
    indication_status: str = Field(examples=["requesting", "responded"])
    created_by: str = Field(examples=["KotaIsayama"])
    created_at: datetime.datetime = Field(examples=[datetime.datetime(2025, 11, 30)])
    history: List[IndicationRevisionDto]

    @classmethod
    def from_indication(cls, indication: Indication) -> Self:
        history = [
            IndicationRevisionDto.from_indication_revision(indication_revision)
            for indication_revision in indication._history
        ]

        return cls(
            indication_id=indication.indication_id.to_str(),
            indication_status=indication._indication_status.value,
            created_by=indication._created_by,
            created_at=indication._created_at.to_datetime(),
            history=history,
        )

class IndicationReviseCommand(BaseModel):
    indication_id: str
    created_by: str
    indication_content: IndicationContentDto


IndicationReviseResult = IndicationGetResult
