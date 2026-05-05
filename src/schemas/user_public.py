from pydantic import BaseModel, ConfigDict


class UserPublic(BaseModel):
    """Minimal user info safe to expose publicly (e.g., as business owner)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str | None
