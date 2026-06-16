from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from src.models.enums import BusinessStatus
from src.schemas.animal_type import AnimalTypeRead
from src.schemas.business_category import BusinessCategoryRead
from src.schemas.business_hours import BusinessHoursRead
from src.schemas.service import ServiceRead
from src.schemas.user import UserPublic


class BusinessRead(BaseModel):
    """Full business details with all related entities."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None
    status: BusinessStatus

    # Location
    address: str
    city: str
    latitude: float
    longitude: float

    # Contacts
    phone: str | None
    website: str | None
    email: EmailStr | None

    # Emergency flags
    accepts_emergencies: bool
    emergency_24_7: bool

    # Image
    cover_image_url: str | None

    # Relationships
    category: BusinessCategoryRead
    owner: UserPublic
    animal_types: list[AnimalTypeRead]
    services: list[ServiceRead]
    hours: list[BusinessHoursRead]

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Ratings (aggregated from non-hidden reviews)
    avg_rating: float | None = None
    reviews_count: int = 0
