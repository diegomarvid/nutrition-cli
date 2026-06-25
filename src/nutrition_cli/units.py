from __future__ import annotations

import re
import unicodedata

from .database import find_portion_grams
from .models import ParsedItem


MASS_UNITS = {
    "g": 1.0,
    "gr": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "gramo": 1.0,
    "gramos": 1.0,
    "kg": 1000.0,
    "kilo": 1000.0,
    "kilos": 1000.0,
    "kilogram": 1000.0,
    "kilograms": 1000.0,
    "mg": 0.001,
    "oz": 28.3495,
    "ounce": 28.3495,
    "ounces": 28.3495,
    "lb": 453.592,
    "lbs": 453.592,
    "pound": 453.592,
    "pounds": 453.592,
}

FALLBACK_GRAMS = {
    "cup": 240.0,
    "cups": 240.0,
    "taza": 240.0,
    "tazas": 240.0,
    "tbsp": 15.0,
    "tablespoon": 15.0,
    "tablespoons": 15.0,
    "cda": 15.0,
    "cdas": 15.0,
    "cucharada": 15.0,
    "cucharadas": 15.0,
    "tsp": 5.0,
    "teaspoon": 5.0,
    "teaspoons": 5.0,
    "cdita": 5.0,
    "cditas": 5.0,
    "cucharadita": 5.0,
    "cucharaditas": 5.0,
    "unit": 100.0,
    "units": 100.0,
    "unidad": 100.0,
    "unidades": 100.0,
    "piece": 100.0,
    "pieces": 100.0,
    "pieza": 100.0,
    "piezas": 100.0,
    "serving": 100.0,
    "porcion": 100.0,
    "porción": 100.0,
}

ALIAS_UNIT_GRAMS = [
    (re.compile(r"\b(manzana|apple|apples)\b"), 182.0),
    (re.compile(r"\b(huevo|huevos|egg|eggs)\b"), 50.0),
    (re.compile(r"\b(banana|bananas|platano|plátano)\b"), 118.0),
    (re.compile(r"\b(muslo|muslos|thigh|thighs|drumstick|drumsticks)\b"), 125.0),
]

ALIAS_UNIT_SPECIFIC_GRAMS = [
    (re.compile(r"\b(arroz|rice)\b"), {"cup", "taza"}, 158.0),
    (re.compile(r"\b(avena|oats|oatmeal)\b"), {"cup", "taza"}, 80.0),
]


def estimate_grams(conn, item: ParsedItem, fdc_id: int | None) -> tuple[float | None, str | None]:
    if item.quantity_g is not None:
        return float(item.quantity_g), None

    quantity = item.quantity if item.quantity is not None else 1.0
    unit = normalize_unit(item.unit)
    if unit is None:
        unit = "unit"

    if unit in MASS_UNITS:
        return quantity * MASS_UNITS[unit], None

    if fdc_id is not None:
        portion_grams = find_portion_grams(conn, fdc_id, unit)
        if portion_grams is not None:
            return quantity * portion_grams, None

    alias = strip_accents(item.food_alias.lower())
    for pattern, units, grams in ALIAS_UNIT_SPECIFIC_GRAMS:
        if unit in units and pattern.search(alias):
            return quantity * grams, f"estimated with local fallback: 1 {unit} ~= {grams:g}g"

    for pattern, grams in ALIAS_UNIT_GRAMS:
        if pattern.search(alias):
            return quantity * grams, f"estimated with local fallback: 1 {unit} ~= {grams:g}g"

    fallback = FALLBACK_GRAMS.get(unit)
    if fallback is not None:
        return quantity * fallback, f"estimated with local fallback: 1 {unit} ~= {fallback:g}g"

    return None, f"could not convert {quantity:g} {unit} to grams"


def normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    normalized = strip_accents(unit.strip().lower())
    aliases = {
        "grs": "g",
        "gramos": "g",
        "gramo": "g",
        "kilogramo": "kg",
        "kilogramos": "kg",
        "kilos": "kg",
        "libra": "lb",
        "libras": "lb",
        "onza": "oz",
        "onzas": "oz",
        "cups": "cup",
        "tazas": "taza",
        "un": "unit",
        "una": "unit",
        "uno": "unit",
        "pieza": "piece",
        "piezas": "piece",
        "porciones": "serving",
        "porcion": "serving",
    }
    return aliases.get(normalized, normalized)


def strip_accents(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char)
    )
