from pydantic import BaseModel, ConfigDict, Field, constr, field_validator, model_validator
from datetime import datetime
from typing import List, Optional, Generic, TypeVar
from fastapi import Query
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, BeforeValidator, StringConstraints

# Names of manufacturers, suppliers and categories: surrounding whitespace is dropped
# before validation, so "onsemi " and "onsemi" can no longer become two entries and a
# name made of spaces only is rejected as empty. Applies to every client of the API
# (web GUI and the Chalcedon desktop app alike).
DictionaryName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]

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

    # Library paths are relative to the repository root, which Altium/KiCad already search
    # from, so they must start with the top-level folder (never with the repository name)
    # and point at a library file. A reference and its path only make sense together.
    @model_validator(mode='after')
    def checkLibraryPaths(self):
        pairs = [
            ("Symbol", self.libraryReference, self.libraryPath, "symbols/", ".schlib"),
            ("Footprint 1", self.footprintReferenceNo1, self.footprintPathNo1, "footprints/", ".pcblib"),
            ("Footprint 2", self.footprintReferenceNo2, self.footprintPathNo2, "footprints/", ".pcblib"),
            ("Footprint 3", self.footprintReferenceNo3, self.footprintPathNo3, "footprints/", ".pcblib"),
        ]
        for label, reference, path, prefix, extension in pairs:
            if (reference is None) != (path is None):
                raise ValueError(f"{label}: reference and path must be set together.")
            if path is not None and not (path.startswith(prefix) and path.lower().endswith(extension)):
                raise ValueError(f"{label}: path must start with '{prefix}' and point at a {extension} file.")
        return self


class ElementFull(ElementBase):
    uuid: UUID
    createdAt: datetime

class ElementList(BaseModel):
    total: int
    items: List[ElementFull]

class ManufacturerBase(BaseModel):
    name: DictionaryName

class ManufacturerFull(ManufacturerBase):
    id: int
    createdAt: datetime

class ManufacturerList(BaseModel):
    total: int
    items: List[ManufacturerFull]

class SupplierBase(BaseModel):
    name: DictionaryName

class SupplierFull(SupplierBase):
    id: int
    createdAt: datetime
    # Name of this supplier's code column in the Altium/KiCad views (e.g. "supplier_lcsc").
    columnName: str | None = None

class SupplierList(BaseModel):
    total: int
    items: List[SupplierFull]

class TableBase(BaseModel):
    name: DictionaryName

class TableFull(TableBase):
    id: int
    createdAt: datetime

class TableList(BaseModel):
    total: int
    items: List[TableFull]

