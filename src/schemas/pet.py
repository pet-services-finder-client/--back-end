from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import PetGender
from src.schemas.animal_type import AnimalTypeRead


class PetBase(BaseModel):
    """Shared fields used across pet schemas."""
    name: str = Field(min_length=1, max_length=100)
    breed: str | None = Field(default=None, max_length=100)
    birth_date: date | None = None
    gender: PetGender = PetGender.UNKNOWN
    notes: str | None = None


class PetCreate(PetBase):
    """Payload for creating a new pet. Client sends animal_type_id."""
    animal_type_id: int


class PetUpdate(BaseModel):
    """Payload for partial updates — all fields optional."""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    animal_type_id: int | None = None
    breed: str | None = Field(default=None, max_length=100)
    birth_date: date | None = None
    gender: PetGender | None = None
    notes: str | None = None


class PetRead(PetBase):
    """Pet returned to clients with embedded animal_type object."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    animal_type: AnimalTypeRead
    created_at: datetime
    updated_at: datetime
