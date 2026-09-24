from pydantic import BaseModel, Field
from typing import List
from enum import Enum


class Category(str, Enum):
    FICTION = "fiction"
    NON_FICTION = "non-fiction"
    POETRY = "poetry"
    CHILDRENS = "childrens"
    OTHER = "other"


class QualityFlag(str, Enum):
    MISSING_DESCRIPTION = "missing_description"
    DESCRIPTION_DUPLICATED = "description_duplicated"
    GENERIC_TITLE = "generic_title"
    PRICE_OUTLIER = "price_outlier"


class EnrichmentResult(BaseModel):
    category: Category
    summary: str = Field(max_length=200)
    quality_flags: List[QualityFlag] = []
    confidence: float = Field(ge=0.0, le=1.0)