from pydantic import BaseModel, Field
from typing import Optional


class EnrichRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: Optional[str] = Field(default=None, max_length=4000)
    price_gbp: float