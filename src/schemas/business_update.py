from datetime import time

from pydantic import BaseModel, EmailStr, Field, model_validator
from typing_extensions import Self


class BusinessHoursUpdate(BaseModel):
    """One day of operating hours when updating a business."""
    day_of_week: int = Field(ge=0, le=6)
    is_closed: bool = False
    is_24h: bool = False
    open_time: time | None = None
    close_time: time | None = None

    @model_validator(mode="after")
    def validate_hours_consistency(self) -> Self:
        if self.is_closed:
            if self.open_time is not None or self.close_time is not None:
                raise ValueError("Closed days should not have open/close times")
        elif self.is_24h:
            if self.open_time is not None or self.close_time is not None:
                raise ValueError("24/7 days should not have open/close times")
        else:
            if self.open_time is None or self.close_time is None:
                raise ValueError("Regular days require both open_time and close_time")
        return self


class BusinessUpdate(BaseModel):
    """Schema for partial updates of a business by its owner.

    All fields are optional — only provided fields will be updated.
    To change hours or m:n relationships, the full new list must be provided.
    """
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    category_id: int | None = None

    address: str | None = Field(default=None, min_length=5, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    phone: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=500)
    email: EmailStr | None = None

    accepts_emergencies: bool | None = None
    emergency_24_7: bool | None = None

    cover_image_url: str | None = Field(default=None, max_length=500)

    animal_type_ids: list[int] | None = Field(default=None, min_length=1)
    service_ids: list[int] | None = None

    hours: list[BusinessHoursUpdate] | None = Field(default=None, min_length=7, max_length=7)

    @model_validator(mode="after")
    def validate_hours_cover_all_days(self) -> Self:
        """If hours are provided, ensure all 7 weekdays are covered exactly once."""
        if self.hours is not None:
            days_of_week = {h.day_of_week for h in self.hours}
            if days_of_week != {0, 1, 2, 3, 4, 5, 6}:
                raise ValueError(
                    "Hours must include exactly one entry for each day_of_week 0-6"
                )
        return self
