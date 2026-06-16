from datetime import time

from pydantic import BaseModel, EmailStr, Field, model_validator
from typing_extensions import Self


class BusinessHoursCreate(BaseModel):
    """One day of operating hours when creating a business."""
    day_of_week: int = Field(ge=0, le=6, description="0=Monday, 6=Sunday")
    is_closed: bool = False
    is_24h: bool = False
    open_time: time | None = None
    close_time: time | None = None

    @model_validator(mode="after")
    def validate_hours_consistency(self) -> Self:
        """Ensure hours fields are coherent."""
        if self.is_closed:
            # Closed days should have no times
            if self.open_time is not None or self.close_time is not None:
                raise ValueError("Closed days should not have open/close times")
        elif self.is_24h:
            # 24h days should have no times either
            if self.open_time is not None or self.close_time is not None:
                raise ValueError("24/7 days should not have open/close times")
        else:
            # Regular days need both times
            if self.open_time is None or self.close_time is None:
                raise ValueError("Regular days require both open_time and close_time")
        return self


class BusinessCreate(BaseModel):
    """Schema for user-submitted business proposals."""
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    category_id: int

    # Location
    address: str = Field(min_length=5, max_length=500)
    city: str = Field(default="Київ", max_length=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    # Contacts
    phone: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=500)
    email: EmailStr | None = None

    # Emergency flags
    accepts_emergencies: bool = False
    emergency_24_7: bool = False

    # Image
    cover_image_url: str | None = Field(default=None, max_length=500)

    # Many-to-many (lists of IDs)
    animal_type_ids: list[int] = Field(min_length=1, description="At least one animal type")
    service_ids: list[int] = Field(default_factory=list)

    # Operating hours — must be exactly 7 days (one per weekday)
    hours: list[BusinessHoursCreate] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def validate_hours_cover_all_days(self) -> Self:
        """Ensure each weekday is represented exactly once."""
        days_of_week = {h.day_of_week for h in self.hours}
        if days_of_week != {0, 1, 2, 3, 4, 5, 6}:
            raise ValueError(
                "Hours must include exactly one entry for each day_of_week 0-6"
            )
        return self
