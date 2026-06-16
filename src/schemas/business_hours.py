from datetime import time

from pydantic import BaseModel, ConfigDict


class BusinessHoursRead(BaseModel):
    """One day of operating hours for a business."""
    model_config = ConfigDict(from_attributes=True)

    day_of_week: int
    is_closed: bool
    is_24h: bool
    open_time: time | None
    close_time: time | None
