from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.models.enums import BusinessStatus

if TYPE_CHECKING:
    from src.models.business_category import BusinessCategory
    from src.models.user import User


class Business(Base):
    __tablename__ = "businesses"
    __table_args__ = (
        UniqueConstraint("name", "address", name="uq_business_name_address"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(220), unique=True, index=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships (FK)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("business_categories.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Moderation
    status: Mapped[BusinessStatus] = mapped_column(
        Enum(
            BusinessStatus,
            name="business_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=BusinessStatus.PENDING,
        index=True,
        nullable=False,
    )

    # Location
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(100), default="Київ", nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    # Contacts
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Emergency flags
    accepts_emergencies: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    emergency_24_7: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Image
    cover_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships (ORM)
    category: Mapped["BusinessCategory"] = relationship(lazy="joined")
    owner: Mapped["User"] = relationship(back_populates="businesses")
