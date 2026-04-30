"""Junction tables for many-to-many relationships."""

from sqlalchemy import Column, ForeignKey, Integer, PrimaryKeyConstraint, Table

from src.core.database import Base


business_animal_types = Table(
    "business_animal_types",
    Base.metadata,
    Column(
        "business_id",
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "animal_type_id",
        Integer,
        ForeignKey("animal_types.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    PrimaryKeyConstraint("business_id", "animal_type_id"),
)


business_services = Table(
    "business_services",
    Base.metadata,
    Column(
        "business_id",
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "service_id",
        Integer,
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    PrimaryKeyConstraint("business_id", "service_id"),
)
