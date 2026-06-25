from __future__ import annotations

from datetime import date as Date
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ParsedItem(BaseModel):
    food_alias: str = Field(description="User-facing food name, preferably in the user's language.")
    fdc_id: int | None = Field(default=None, description="Optional USDA FoodData Central id when already known.")
    quantity: float | None = Field(default=None, description="Numeric quantity as spoken by the user.")
    unit: str | None = Field(default=None, description="Unit for quantity, for example g, cup, unit.")
    quantity_g: float | None = Field(default=None, description="Quantity in grams when directly stated or confidently inferred.")
    preparation: str | None = Field(default=None, description="Preparation details such as cooked, raw, with skin.")
    confidence: float = Field(default=0.6, ge=0, le=1)
    notes: str | None = None

    @field_validator("food_alias")
    @classmethod
    def normalize_alias(cls, value: str) -> str:
        return " ".join(value.strip().lower().split())

    @field_validator("unit")
    @classmethod
    def normalize_unit(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.strip().lower().split())


class ParsedMeal(BaseModel):
    raw_text: str
    date: Date | None = None
    items: list[ParsedItem]
    confidence: float = Field(default=0.6, ge=0, le=1)
    needs_clarification: list[str] = Field(default_factory=list)

    def as_db_json(self) -> str:
        return self.model_dump_json()


class FoodCandidate(BaseModel):
    fdc_id: int
    description: str
    data_type: str | None = None
    brand_owner: str | None = None
    score: float | None = None

    @classmethod
    def from_fdc(cls, payload: dict[str, Any]) -> "FoodCandidate":
        return cls(
            fdc_id=int(payload["fdcId"]),
            description=payload.get("description") or "",
            data_type=payload.get("dataType"),
            brand_owner=payload.get("brandOwner"),
            score=payload.get("score"),
        )


class NutrientTarget(BaseModel):
    number: str
    label: str
    unit: str
    target: float
