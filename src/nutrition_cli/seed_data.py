from __future__ import annotations

from copy import deepcopy

from .database import get_alias, upsert_alias, upsert_food_detail


def nutrient(number: str, nutrient_id: int, name: str, unit: str, amount: float) -> dict:
    return {
        "nutrient": {"number": number, "id": nutrient_id, "name": name, "unitName": unit},
        "amount": amount,
    }


COMMON_FOODS = {
    171688: {
        "fdcId": 171688,
        "description": "Apples, raw, with skin",
        "dataType": "SR Legacy",
        "foodNutrients": [
            nutrient("208", 1008, "Energy", "kcal", 52.0),
            nutrient("203", 1003, "Protein", "g", 0.26),
            nutrient("204", 1004, "Total lipid (fat)", "g", 0.17),
            nutrient("205", 1005, "Carbohydrate, by difference", "g", 13.81),
            nutrient("291", 1079, "Fiber, total dietary", "g", 2.4),
            nutrient("301", 1087, "Calcium, Ca", "mg", 6.0),
            nutrient("307", 1093, "Sodium, Na", "mg", 1.0),
            nutrient("303", 1089, "Iron, Fe", "mg", 0.12),
            nutrient("304", 1090, "Magnesium, Mg", "mg", 5.0),
            nutrient("306", 1092, "Potassium, K", "mg", 107.0),
            nutrient("309", 1095, "Zinc, Zn", "mg", 0.04),
            nutrient("320", 1106, "Vitamin A, RAE", "ug", 3.0),
            nutrient("401", 1162, "Vitamin C, total ascorbic acid", "mg", 4.6),
            nutrient("417", 1177, "Folate, total", "ug", 3.0),
            nutrient("418", 1178, "Vitamin B-12", "ug", 0.0),
            nutrient("430", 1185, "Vitamin K (phylloquinone)", "ug", 2.2),
        ],
        "foodPortions": [
            {"amount": 1.0, "gramWeight": 182.0, "measureUnit": {"name": "unit"}, "modifier": "medium"},
        ],
    },
    173625: {
        "fdcId": 173625,
        "description": "Chicken, broilers or fryers, thigh, meat and skin, cooked, roasted",
        "dataType": "SR Legacy",
        "foodNutrients": [
            nutrient("208", 1008, "Energy", "kcal", 232.0),
            nutrient("203", 1003, "Protein", "g", 23.26),
            nutrient("204", 1004, "Total lipid (fat)", "g", 14.71),
            nutrient("205", 1005, "Carbohydrate, by difference", "g", 0.0),
            nutrient("291", 1079, "Fiber, total dietary", "g", 0.0),
            nutrient("301", 1087, "Calcium, Ca", "mg", 9.0),
            nutrient("307", 1093, "Sodium, Na", "mg", 95.0),
            nutrient("303", 1089, "Iron, Fe", "mg", 1.08),
            nutrient("304", 1090, "Magnesium, Mg", "mg", 22.0),
            nutrient("306", 1092, "Potassium, K", "mg", 253.0),
            nutrient("309", 1095, "Zinc, Zn", "mg", 1.73),
            nutrient("320", 1106, "Vitamin A, RAE", "ug", 19.0),
            nutrient("401", 1162, "Vitamin C, total ascorbic acid", "mg", 0.0),
            nutrient("417", 1177, "Folate, total", "ug", 4.0),
            nutrient("418", 1178, "Vitamin B-12", "ug", 0.44),
            nutrient("430", 1185, "Vitamin K (phylloquinone)", "ug", 3.3),
        ],
        "foodPortions": [
            {"amount": 1.0, "gramWeight": 137.0, "measureUnit": {"name": "unit"}, "modifier": "thigh with skin"},
            {"amount": 3.0, "gramWeight": 85.0, "measureUnit": {"name": "oz"}, "modifier": None},
        ],
    },
    2708408: {
        "fdcId": 2708408,
        "description": "Rice, white, cooked, no added fat",
        "dataType": "Survey (FNDDS)",
        "foodNutrients": [
            nutrient("208", 1008, "Energy", "kcal", 129.0),
            nutrient("203", 1003, "Protein", "g", 2.67),
            nutrient("204", 1004, "Total lipid (fat)", "g", 0.28),
            nutrient("205", 1005, "Carbohydrate, by difference", "g", 28.0),
            nutrient("291", 1079, "Fiber, total dietary", "g", 0.4),
            nutrient("301", 1087, "Calcium, Ca", "mg", 10.0),
            nutrient("307", 1093, "Sodium, Na", "mg", 0.0),
            nutrient("303", 1089, "Iron, Fe", "mg", 1.19),
            nutrient("304", 1090, "Magnesium, Mg", "mg", 12.0),
            nutrient("306", 1092, "Potassium, K", "mg", 35.0),
            nutrient("309", 1095, "Zinc, Zn", "mg", 0.49),
            nutrient("320", 1106, "Vitamin A, RAE", "ug", 0.0),
            nutrient("401", 1162, "Vitamin C, total ascorbic acid", "mg", 0.0),
            nutrient("417", 1177, "Folate, total", "ug", 58.0),
            nutrient("418", 1178, "Vitamin B-12", "ug", 0.0),
            nutrient("430", 1185, "Vitamin K (phylloquinone)", "ug", 0.0),
        ],
        "foodPortions": [
            {"amount": 1.0, "gramWeight": 158.0, "measureUnit": {"name": "cup"}, "modifier": None},
        ],
    },
    9000001: {
        "fdcId": 9000001,
        "description": "Local estimate: hot dog / frankfurter",
        "dataType": "Local Estimate",
        "foodNutrients": [
            nutrient("208", 1008, "Energy", "kcal", 290.0),
            nutrient("203", 1003, "Protein", "g", 10.3),
            nutrient("204", 1004, "Total lipid (fat)", "g", 26.0),
            nutrient("205", 1005, "Carbohydrate, by difference", "g", 4.2),
            nutrient("291", 1079, "Fiber, total dietary", "g", 0.0),
            nutrient("301", 1087, "Calcium, Ca", "mg", 110.0),
            nutrient("307", 1093, "Sodium, Na", "mg", 1090.0),
            nutrient("303", 1089, "Iron, Fe", "mg", 1.6),
            nutrient("304", 1090, "Magnesium, Mg", "mg", 12.0),
            nutrient("306", 1092, "Potassium, K", "mg", 180.0),
            nutrient("309", 1095, "Zinc, Zn", "mg", 1.5),
            nutrient("320", 1106, "Vitamin A, RAE", "ug", 8.0),
            nutrient("401", 1162, "Vitamin C, total ascorbic acid", "mg", 0.0),
            nutrient("417", 1177, "Folate, total", "ug", 5.0),
            nutrient("418", 1178, "Vitamin B-12", "ug", 1.2),
            nutrient("430", 1185, "Vitamin K (phylloquinone)", "ug", 1.8),
        ],
        "foodPortions": [
            {"amount": 1.0, "gramWeight": 45.0, "measureUnit": {"name": "unit"}, "modifier": "hot dog"},
        ],
    },
    9000002: {
        "fdcId": 9000002,
        "description": "Local estimate: potato, cooked",
        "dataType": "Local Estimate",
        "foodNutrients": [
            nutrient("208", 1008, "Energy", "kcal", 87.0),
            nutrient("203", 1003, "Protein", "g", 1.9),
            nutrient("204", 1004, "Total lipid (fat)", "g", 0.1),
            nutrient("205", 1005, "Carbohydrate, by difference", "g", 20.1),
            nutrient("291", 1079, "Fiber, total dietary", "g", 1.8),
            nutrient("301", 1087, "Calcium, Ca", "mg", 5.0),
            nutrient("307", 1093, "Sodium, Na", "mg", 4.0),
            nutrient("303", 1089, "Iron, Fe", "mg", 0.3),
            nutrient("304", 1090, "Magnesium, Mg", "mg", 22.0),
            nutrient("306", 1092, "Potassium, K", "mg", 379.0),
            nutrient("309", 1095, "Zinc, Zn", "mg", 0.3),
            nutrient("320", 1106, "Vitamin A, RAE", "ug", 0.0),
            nutrient("401", 1162, "Vitamin C, total ascorbic acid", "mg", 13.0),
            nutrient("417", 1177, "Folate, total", "ug", 10.0),
            nutrient("418", 1178, "Vitamin B-12", "ug", 0.0),
            nutrient("430", 1185, "Vitamin K (phylloquinone)", "ug", 2.0),
        ],
        "foodPortions": [],
    },
    9000003: {
        "fdcId": 9000003,
        "description": "Local estimate: sweet potato / boniato, cooked",
        "dataType": "Local Estimate",
        "foodNutrients": [
            nutrient("208", 1008, "Energy", "kcal", 90.0),
            nutrient("203", 1003, "Protein", "g", 2.0),
            nutrient("204", 1004, "Total lipid (fat)", "g", 0.2),
            nutrient("205", 1005, "Carbohydrate, by difference", "g", 20.7),
            nutrient("291", 1079, "Fiber, total dietary", "g", 3.3),
            nutrient("301", 1087, "Calcium, Ca", "mg", 38.0),
            nutrient("307", 1093, "Sodium, Na", "mg", 36.0),
            nutrient("303", 1089, "Iron, Fe", "mg", 0.7),
            nutrient("304", 1090, "Magnesium, Mg", "mg", 27.0),
            nutrient("306", 1092, "Potassium, K", "mg", 475.0),
            nutrient("309", 1095, "Zinc, Zn", "mg", 0.3),
            nutrient("320", 1106, "Vitamin A, RAE", "ug", 961.0),
            nutrient("401", 1162, "Vitamin C, total ascorbic acid", "mg", 19.6),
            nutrient("417", 1177, "Folate, total", "ug", 6.0),
            nutrient("418", 1178, "Vitamin B-12", "ug", 0.0),
            nutrient("430", 1185, "Vitamin K (phylloquinone)", "ug", 2.3),
        ],
        "foodPortions": [],
    },
    9000004: {
        "fdcId": 9000004,
        "description": "Local estimate: pumpkin / calabaza, cooked",
        "dataType": "Local Estimate",
        "foodNutrients": [
            nutrient("208", 1008, "Energy", "kcal", 40.0),
            nutrient("203", 1003, "Protein", "g", 0.9),
            nutrient("204", 1004, "Total lipid (fat)", "g", 0.1),
            nutrient("205", 1005, "Carbohydrate, by difference", "g", 10.5),
            nutrient("291", 1079, "Fiber, total dietary", "g", 2.8),
            nutrient("301", 1087, "Calcium, Ca", "mg", 15.0),
            nutrient("307", 1093, "Sodium, Na", "mg", 4.0),
            nutrient("303", 1089, "Iron, Fe", "mg", 0.6),
            nutrient("304", 1090, "Magnesium, Mg", "mg", 17.0),
            nutrient("306", 1092, "Potassium, K", "mg", 230.0),
            nutrient("309", 1095, "Zinc, Zn", "mg", 0.3),
            nutrient("320", 1106, "Vitamin A, RAE", "ug", 558.0),
            nutrient("401", 1162, "Vitamin C, total ascorbic acid", "mg", 12.3),
            nutrient("417", 1177, "Folate, total", "ug", 19.0),
            nutrient("418", 1178, "Vitamin B-12", "ug", 0.0),
            nutrient("430", 1185, "Vitamin K (phylloquinone)", "ug", 1.1),
        ],
        "foodPortions": [],
    },
    9000005: {
        "fdcId": 9000005,
        "description": "Local estimate: orange carrot ginger juice",
        "dataType": "Local Estimate",
        "foodNutrients": [
            nutrient("208", 1008, "Energy", "kcal", 45.0),
            nutrient("203", 1003, "Protein", "g", 0.7),
            nutrient("204", 1004, "Total lipid (fat)", "g", 0.1),
            nutrient("205", 1005, "Carbohydrate, by difference", "g", 10.5),
            nutrient("291", 1079, "Fiber, total dietary", "g", 0.3),
            nutrient("301", 1087, "Calcium, Ca", "mg", 13.0),
            nutrient("307", 1093, "Sodium, Na", "mg", 5.0),
            nutrient("303", 1089, "Iron, Fe", "mg", 0.2),
            nutrient("304", 1090, "Magnesium, Mg", "mg", 10.0),
            nutrient("306", 1092, "Potassium, K", "mg", 190.0),
            nutrient("309", 1095, "Zinc, Zn", "mg", 0.1),
            nutrient("320", 1106, "Vitamin A, RAE", "ug", 280.0),
            nutrient("401", 1162, "Vitamin C, total ascorbic acid", "mg", 35.0),
            nutrient("417", 1177, "Folate, total", "ug", 20.0),
            nutrient("418", 1178, "Vitamin B-12", "ug", 0.0),
            nutrient("430", 1185, "Vitamin K (phylloquinone)", "ug", 2.0),
        ],
        "foodPortions": [],
    },
}

COMMON_ALIASES = {
    "manzana": 171688,
    "apple": 171688,
    "muslo de pollo": 173625,
    "muslo de pollo cocido con piel": 173625,
    "chicken thigh cooked with skin": 173625,
    "arroz blanco cocido": 2708408,
    "white rice cooked": 2708408,
    "pancho": 9000001,
    "panchos": 9000001,
    "hot dog": 9000001,
    "frankfurter": 9000001,
    "papa cocida": 9000002,
    "papas cocidas": 9000002,
    "potato cooked": 9000002,
    "boniato cocido": 9000003,
    "boñato cocido": 9000003,
    "sweet potato cooked": 9000003,
    "calabaza cocida": 9000004,
    "pumpkin cooked": 9000004,
    "jugo naranja zanahoria jengibre": 9000005,
    "orange carrot ginger juice": 9000005,
}

COMMON_ALIAS_DEFAULT_QUANTITY_G = {
    "manzana": 182.0,
    "apple": 182.0,
    "pancho": 45.0,
    "hot dog": 45.0,
    "frankfurter": 45.0,
}


def seed_food(conn, fdc_id: int) -> bool:
    payload = COMMON_FOODS.get(fdc_id)
    if payload is None:
        return False
    upsert_food_detail(conn, deepcopy(payload))
    return True


def seed_common_foods(conn) -> int:
    for fdc_id in COMMON_FOODS:
        seed_food(conn, fdc_id)
    for alias, fdc_id in COMMON_ALIASES.items():
        if get_alias(conn, alias) is not None:
            continue
        upsert_alias(
            conn,
            alias,
            fdc_id,
            default_quantity_g=COMMON_ALIAS_DEFAULT_QUANTITY_G.get(alias),
            notes=COMMON_FOODS[fdc_id]["description"],
        )
    return len(COMMON_FOODS)
