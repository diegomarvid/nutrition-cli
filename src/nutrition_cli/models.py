from __future__ import annotations

from datetime import date as Date
from typing import Any

from pydantic import BaseModel, Field, field_validator


SEX_ALIASES = {
    "m": "male",
    "male": "male",
    "man": "male",
    "hombre": "male",
    "masculino": "male",
    "f": "female",
    "female": "female",
    "woman": "female",
    "mujer": "female",
    "femenino": "female",
    "other": "other",
    "otro": "other",
    "otra": "other",
    "nonbinary": "other",
    "non-binary": "other",
    "no binario": "other",
    "no-binario": "other",
}

ACTIVITY_LEVELS = {
    "sedentary",
    "light",
    "moderate",
    "active",
    "very-active",
}

ACTIVITY_ALIASES = {
    "sedentario": "sedentary",
    "sedentaria": "sedentary",
    "sedentary": "sedentary",
    "light": "light",
    "liviano": "light",
    "liviana": "light",
    "ligero": "light",
    "ligera": "light",
    "moderate": "moderate",
    "moderado": "moderate",
    "moderada": "moderate",
    "active": "active",
    "activo": "active",
    "activa": "active",
    "very active": "very-active",
    "very-active": "very-active",
    "muy activo": "very-active",
    "muy activa": "very-active",
}


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
    target: float | None = None
    category: str = "other"
    nutrient_id: int | None = None
    note: str | None = None


class UserProfile(BaseModel):
    birth_date: Date | None = None
    sex: str | None = Field(default=None, description="male, female, or other; used only for nutrition target estimates")
    height_cm: float | None = Field(default=None, gt=0)
    weight_kg: float | None = Field(default=None, gt=0)
    activity_level: str | None = Field(
        default=None,
        description="sedentary, light, moderate, active, or very-active",
    )

    @field_validator("birth_date")
    @classmethod
    def reject_future_birth_date(cls, value: Date | None) -> Date | None:
        if value is not None and value > Date.today():
            raise ValueError("birth_date cannot be in the future")
        return value

    @field_validator("sex")
    @classmethod
    def normalize_sex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().lower().split())
        if not normalized:
            return None
        if normalized not in SEX_ALIASES:
            raise ValueError("sex must be male, female, or other")
        return SEX_ALIASES[normalized]

    @field_validator("activity_level")
    @classmethod
    def normalize_activity_level(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().lower().split())
        if not normalized:
            return None
        normalized = ACTIVITY_ALIASES.get(normalized, normalized)
        if normalized not in ACTIVITY_LEVELS:
            raise ValueError("activity_level must be sedentary, light, moderate, active, or very-active")
        return normalized

    def age_on(self, day: Date) -> int | None:
        if self.birth_date is None:
            return None
        years = day.year - self.birth_date.year
        if (day.month, day.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return years
