from datetime import date

from nutrition_cli.parser import parse_with_rules


def test_parse_common_spanish_log():
    meal = parse_with_rules(
        "comí 500g de muslo de pollo cocido con piel, 1 taza de arroz blanco cocido y una manzana",
        forced_date=date(2026, 6, 24),
    )

    assert meal.date == date(2026, 6, 24)
    assert [item.food_alias for item in meal.items] == [
        "muslo de pollo cocido con piel",
        "arroz blanco cocido",
        "manzana",
    ]
    assert meal.items[0].quantity_g == 500
    assert meal.items[1].quantity == 1
    assert meal.items[1].unit == "taza"
    assert meal.items[2].quantity == 1
    assert meal.items[2].unit == "unit"


def test_parse_count_items():
    meal = parse_with_rules("hoy comí 4 huevos y 2 bananas")

    assert meal.items[0].food_alias == "huevos"
    assert meal.items[0].quantity == 4
    assert meal.items[0].unit == "unit"
    assert meal.items[1].food_alias == "bananas"
    assert meal.items[1].quantity == 2
