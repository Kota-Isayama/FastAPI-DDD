import datetime
from typing import List
from pydantic import BaseModel, Field


class IndicationDetailDto(BaseModel):
    counterparty: str = Field(examples=["AkiyamaYumi"])


class IndicationRegisterCommand(BaseModel):
    created_by: str = Field(examples=["KotaIsayama"])
    details: List[IndicationDetailDto] = Field(examples=[[IndicationDetailDto(counterparty="YumiAkiyama"), IndicationDetailDto(counterparty="YuriKatsuki")]])


class IndicationRegisterResult(BaseModel):
    indication_ids: List[str] = Field(examples=[["01KBA6DBS6QHG0B4FVJ54QKBM1", "01KBA6E878MVJGRNXW38MNZK1M"]])
    

class IndicationGetCommand(BaseModel):
    indication_id: str


class IndicationGetResult(BaseModel):
    indication_id: str = Field(examples=["01KBA6DBS6QHG0B4FVJ54QKBM1"])
    created_by: str = Field(examples=["KotaIsayama"])
    created_at: datetime.datetime = Field(examples=[datetime.datetime(2025, 11, 30)])
    history: List[IndicationDetailDto]
