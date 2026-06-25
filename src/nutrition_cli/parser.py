from __future__ import annotations

import re
from datetime import date

from .models import ParsedItem, ParsedMeal
from .units import MASS_UNITS, strip_accents


NUMBER_WORDS = {
    "un": 1,
    "una": 1,
    "uno": 1,
    "one": 1,
    "dos": 2,
    "two": 2,
    "tres": 3,
    "three": 3,
    "cuatro": 4,
    "four": 4,
    "cinco": 5,
    "five": 5,
    "seis": 6,
    "six": 6,
    "siete": 7,
    "seven": 7,
    "ocho": 8,
    "eight": 8,
    "nueve": 9,
    "nine": 9,
    "diez": 10,
    "ten": 10,
    "medio": 0.5,
    "media": 0.5,
    "half": 0.5,
}

UNIT_WORDS = {
    "taza",
    "tazas",
    "cup",
    "cups",
    "cucharada",
    "cucharadas",
    "tbsp",
    "cda",
    "cdas",
    "cucharadita",
    "cucharaditas",
    "tsp",
    "unidad",
    "unidades",
    "pieza",
    "piezas",
    "porcion",
    "porción",
    "serving",
    "servings",
}

PREPARATION_WORDS = {
    "cocido": "cooked",
    "cocida": "cooked",
    "cocidos": "cooked",
    "cocidas": "cooked",
    "crudo": "raw",
    "cruda": "raw",
    "asado": "roasted",
    "asada": "roasted",
    "roasted": "roasted",
    "cooked": "cooked",
    "raw": "raw",
    "frito": "fried",
    "frita": "fried",
    "fried": "fried",
    "hervido": "boiled",
    "hervida": "boiled",
    "boiled": "boiled",
}

LEADING_NOISE = re.compile(
    r"^\s*(hoy\s+)?(com[ií]|comi|almorc[eé]|cene|cen[eé]|desayune|desayun[eé]|merend[eé]|i ate|ate|had)\s+",
    re.IGNORECASE,
)


def parse_meal(text: str, forced_date: date | None = None) -> ParsedMeal:
    return parse_with_rules(text, forced_date)


def parse_with_rules(text: str, forced_date: date | None = None) -> ParsedMeal:
    meal_type = detect_meal_type(text)
    cleaned = LEADING_NOISE.sub("", text.strip())
    parts = split_items(cleaned)
    items = [parse_item(part) for part in parts if part.strip()]
    needs = []
    if not items:
        needs.append("No pude detectar alimentos en el texto.")
    return ParsedMeal(
        raw_text=text,
        date=forced_date,
        meal_type=meal_type,
        items=items,
        confidence=0.55 if items else 0.1,
        needs_clarification=needs,
    )


def detect_meal_type(text: str) -> str | None:
    normalized = strip_accents(text.lower())
    if re.search(r"\b(desayune|desayuno|breakfast)\b", normalized):
        return "breakfast"
    if re.search(r"\b(almorce|almuerzo|lunch)\b", normalized):
        return "lunch"
    if re.search(r"\b(merende|merienda|snack)\b", normalized):
        return "snack"
    if re.search(r"\b(cene|cena|dinner)\b", normalized):
        return "dinner"
    return None


def split_items(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text)
    return [
        part.strip(" .")
        for part in re.split(r"\s*,\s*|\s*;\s*|\s+\+\s+|\s+y\s+|\s+and\s+", normalized)
        if part.strip(" .")
    ]


def parse_item(text: str) -> ParsedItem:
    original = text.strip()
    normalized = strip_accents(original.lower())

    mass_match = re.search(
        r"(?P<qty>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|kilos?|kilogramos?|g|gr|grs|gramos?|mg|oz|onzas?|lb|lbs|libras?)\b(?:\s+de)?\s*(?P<food>.*)",
        normalized,
    )
    if mass_match:
        quantity = parse_number(mass_match.group("qty"))
        unit = mass_match.group("unit")
        food = clean_food_alias(mass_match.group("food") or original)
        preparation = extract_preparation(original)
        quantity_g = quantity * MASS_UNITS.get(normalize_mass_unit(unit), 1.0)
        return ParsedItem(
            food_alias=food,
            quantity=quantity,
            unit=normalize_mass_unit(unit),
            quantity_g=quantity_g,
            preparation=preparation,
            confidence=0.75,
        )

    unit_match = re.search(
        r"(?:(?P<qty>\d+(?:[.,]\d+)?|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|medio|media|one|two|three|four|five|half)\s+)?(?P<unit>"
        + "|".join(sorted(UNIT_WORDS, key=len, reverse=True))
        + r")\s+(?:de\s+)?(?P<food>.*)",
        normalized,
    )
    if unit_match:
        quantity = parse_number(unit_match.group("qty") or "1")
        unit = unit_match.group("unit")
        food = clean_food_alias(unit_match.group("food") or original)
        return ParsedItem(
            food_alias=food,
            quantity=quantity,
            unit=unit,
            preparation=extract_preparation(original),
            confidence=0.65,
        )

    count_match = re.search(
        r"(?P<qty>\d+(?:[.,]\d+)?|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|one|two|three|four|five)\s+(?P<food>.+)",
        normalized,
    )
    if count_match:
        return ParsedItem(
            food_alias=clean_food_alias(count_match.group("food")),
            quantity=parse_number(count_match.group("qty")),
            unit="unit",
            preparation=extract_preparation(original),
            confidence=0.55,
        )

    return ParsedItem(
        food_alias=clean_food_alias(original),
        quantity=1,
        unit="serving",
        preparation=extract_preparation(original),
        confidence=0.35,
        notes="rule parser assumed one serving",
    )


def parse_number(value: str) -> float:
    normalized = strip_accents(value.strip().lower()).replace(",", ".")
    if normalized in NUMBER_WORDS:
        return float(NUMBER_WORDS[normalized])
    return float(normalized)


def normalize_mass_unit(unit: str) -> str:
    normalized = strip_accents(unit.lower())
    aliases = {
        "gramo": "g",
        "gramos": "g",
        "gr": "g",
        "grs": "g",
        "kilo": "kg",
        "kilos": "kg",
        "kilogramo": "kg",
        "kilogramos": "kg",
        "onza": "oz",
        "onzas": "oz",
        "libra": "lb",
        "libras": "lb",
    }
    return aliases.get(normalized, normalized)


def clean_food_alias(value: str) -> str:
    food = strip_accents(value.lower())
    food = re.sub(r"^(de|of)\s+", "", food)
    food = re.sub(r"\b(aprox|aproximadamente|ponele|about|around)\b", "", food)
    food = re.sub(r"\s+", " ", food).strip(" .")
    return food


def extract_preparation(value: str) -> str | None:
    normalized = strip_accents(value.lower())
    found = []
    for word, label in PREPARATION_WORDS.items():
        if re.search(rf"\b{re.escape(strip_accents(word))}\b", normalized):
            found.append(label)
    if "con piel" in normalized or "with skin" in normalized:
        found.append("with skin")
    if "sin piel" in normalized or "skinless" in normalized:
        found.append("skinless")
    if not found:
        return None
    return ", ".join(dict.fromkeys(found))
