from pydantic import BaseModel, ConfigDict


class ServiceRead(BaseModel):
    """Service as returned to clients (e.g., for dropdowns)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    category_id: int
    sort_order: int
