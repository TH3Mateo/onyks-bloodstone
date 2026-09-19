from pydantic import BaseModel, ConfigDict, Field, constr, field_validator
from datetime import datetime
from typing import List, Optional, Generic, TypeVar
from fastapi import Query
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, BeforeValidator

def emptyToNone(v: str | None) -> str | None:
    if isinstance(v, str) and not v.strip():
        return None
    return v

NotEmptyString = Annotated[str | None, BeforeValidator(emptyToNone)]

class ElementBase(BaseModel):
    partName: NotEmptyString = Field(min_length=3, max_length=256)
    description: NotEmptyString = Field(max_length=256)
    availability: NotEmptyString = Field(max_length=256)
    value: NotEmptyString = Field(max_length=256)
    manufacturer: NotEmptyString = Field(max_length=256)
    suppliers: dict = Field(default_factory=dict)
    datasheet: bool = False
    isDatasheetSupposedToChange: int = Field(0)
    libraryReference: NotEmptyString = Field(max_length=1024)
    libraryPath: NotEmptyString = Field(max_length=1024)
    footprintReferenceNo1: NotEmptyString = Field(max_length=1024)
    footprintPathNo1: NotEmptyString = Field(max_length=1024)
    footprintReferenceNo2: NotEmptyString = Field(max_length=1024)
    footprintPathNo2: NotEmptyString = Field(max_length=1024)
    footprintReferenceNo3: NotEmptyString = Field(max_length=1024)
    footprintPathNo3: NotEmptyString = Field(max_length=1024)
    manufacturer: NotEmptyString = Field(max_length=256)
    table: NotEmptyString = Field(max_length=256)


class ElementFull(ElementBase):
    uuid: UUID
    createdAt: datetime

class ElementList(BaseModel):
    total: int
    items: List[ElementFull]

class ManufacturerBase(BaseModel):
    name: str = Field(min_length=1, max_length=256)

class ManufacturerFull(ManufacturerBase):
    id: int
    createdAt: datetime

class ManufacturerList(BaseModel):
    total: int
    items: List[ManufacturerFull]

class SupplierBase(BaseModel):
    name: str = Field(min_length=1, max_length=256)

class SupplierFull(SupplierBase):
    id: int
    createdAt: datetime

class SupplierList(BaseModel):
    total: int
    items: List[SupplierFull]

class TableBase(BaseModel):
    name: str = Field(min_length=1, max_length=256)

class TableFull(TableBase):
    id: int
    createdAt: datetime

class TableList(BaseModel):
    total: int
    items: List[TableFull]

