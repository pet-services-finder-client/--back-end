from pydantic import BaseModel, ConfigDict


class BusinessCategoryRead(BaseModel):
    """Business category as returned to clients (e.g., for dropdowns)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    icon_url: str | None
    sort_order: int
