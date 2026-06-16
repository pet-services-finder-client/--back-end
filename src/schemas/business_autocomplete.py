from pydantic import BaseModel, ConfigDict

class BusinessAutocompleteItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    category_slug: str
