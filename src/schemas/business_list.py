from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.schemas.business_category import BusinessCategoryRead


class BusinessListItem(BaseModel):
    """Compact business representation for list views."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    address: str
    city: str
    latitude: float
    longitude: float
    accepts_emergencies: bool
    emergency_24_7: bool
    cover_image_url: str | None

    category: BusinessCategoryRead

    created_at: datetime
    distance_km: float | None = None

    avg_rating: float | None = None
    reviews_count: int = 0


class BusinessListResponse(BaseModel):
    """Paginated list of businesses with metadata."""
    items: list[BusinessListItem]
    total: int
    limit: int
    offset: int
