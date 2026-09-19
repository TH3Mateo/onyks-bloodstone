from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum, func
from database import Base
from datetime import datetime, timezone
import uuid
from enum import Enum as PyEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import DDL, event

event.listen(
    Base.metadata,
    "before_create",
    DDL("CREATE EXTENSION IF NOT EXISTS pgcrypto"),
)

class UserRank(PyEnum):
    viewer = "viewer"
    admin = "admin"
    editor = "editor"


class User(Base):
    __tablename__ = "users"
    __table_args__ = {'schema': 'private'}

    id: Mapped[int] = mapped_column(primary_key=True)
    login = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    expirationTime = Column(
        'expiration_time',
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    rank = Column(
        Enum(UserRank, name='user_rank', native_enum=True),
        nullable=False,
        default=UserRank.viewer,
    )
    # Which CAD tool this person uses; decides whether their database role is granted
    # altium_* or kicad_* membership, and therefore which schema they can read.
    tool = Column(String(16), nullable=False, default='altium', server_default='altium')

class Manufacturer(Base):
    __tablename__ = "manufacturers"
    __table_args__ = {'schema': 'private'}

    id:  Mapped[int] = mapped_column(primary_key=True)
    name = Column('name', String, unique=True, index=True, nullable=False)
    createdAt = Column('created_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = {'schema': 'private'}

    id: Mapped[int] = mapped_column(primary_key=True)
    name = Column('name', String, unique=True, index=True, nullable=False)
    createdAt = Column('created_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class Table(Base):
    __tablename__ = "tables"
    __table_args__ = {'schema': 'private'}

    id: Mapped[int] = mapped_column(primary_key=True)
    name = Column('name', String, unique=True, nullable=False)
    createdAt = Column('created_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    elements = relationship("Element", back_populates="tableCategory")


class Element(Base):
    __tablename__ = "elements"
    __table_args__ = {'schema': 'private'}

    uuid = Column('uuid', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partName = Column("part_name", String(1024), nullable=False)

    manufacturer = Column(
        String(1024), 
        ForeignKey("private.manufacturers.name", ondelete="SET NULL", onupdate="CASCADE"), 
        nullable=True
    )

    table = Column('table',
        String(1024), 
        ForeignKey("private.tables.name", ondelete="CASCADE", onupdate="CASCADE"), 
        nullable=False
    )

    description = Column('description', String(1024), nullable=True, default='')
    value = Column('value', String(1024), nullable=True, default='')
    availability = Column('availability', String(1024), nullable=True, default='')
    datasheet = Column(Boolean, nullable=False, default=False)

    # Number of ADDITIONAL documents stored as <uuid>_1.pdf .. <uuid>_N.pdf.
    # The main datasheet (<uuid>.pdf) is tracked by the `datasheet` flag above and is
    # the only one exposed to Altium/KiCad through the views' HelpURL/Datasheet column.
    docsCount = Column('docs_count', Integer, nullable=False, default=0, server_default='0')

    libraryReference = Column('library_ref', String(1024), nullable=True, default='')
    libraryPath = Column('library_path', String(1024), nullable=True, default='')
    
    footprintReferenceNo1 = Column('footprint_reference_1', String(1024), nullable=True, default='')
    footprintPathNo1 = Column('footprint_path_1', String(1024), nullable=True, default='')
    
    footprintReferenceNo2 = Column('footprint_reference_2', String(1024), nullable=True, default='')
    footprintPathNo2 = Column('footprint_path_2', String(1024), nullable=True, default='')
    
    footprintReferenceNo3 = Column('footprint_reference_3', String(1024), nullable=True, default='')
    footprintPathNo3 = Column('footprint_path_3', String(1024), nullable=True, default='')
    
    suppliers = Column('suppliers', JSONB, default={})

    createdAt = Column('created_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    tableCategory = relationship("Table", back_populates="elements")
    manufacturerRel = relationship("Manufacturer")