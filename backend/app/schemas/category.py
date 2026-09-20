from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

CategoryName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]


class CategoryCreate(BaseModel):
    name: CategoryName
    description: Optional[str] = Field(default=None, max_length=255)


class CategoryUpdate(BaseModel):
    name: Optional[CategoryName] = None
    description: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    is_active: bool
