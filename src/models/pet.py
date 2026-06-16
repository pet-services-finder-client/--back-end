from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.models.enums import PetGender

if TYPE_CHECKING:
    from src.models.animal_type import AnimalType
    from src.models.user import User


class Pet(Base):
    __tablename__ = "pets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    animal_type_id: Mapped[int] = mapped_column(
        ForeignKey("animal_types.id", ondelete="RESTRICT"), index=True, nullable=False
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    breed: Mapped[str | None] = mapped_column(String(100), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[PetGender] = mapped_column(
        Enum(
            PetGender,
            name="pet_gender",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=PetGender.UNKNOWN,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    owner: Mapped["User"] = relationship(back_populates="pets")
    animal_type: Mapped["AnimalType"] = relationship(lazy="joined")
