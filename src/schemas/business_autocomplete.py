from typing import Literal

from pydantic import BaseModel, ConfigDict


class AutocompleteItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    type: Literal["business", "service"]
    id: int
    name: str
    slug: str
    category_slug: str
