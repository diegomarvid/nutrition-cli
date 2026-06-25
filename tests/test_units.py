from nutrition_cli.models import ParsedItem
from nutrition_cli.units import estimate_grams


def test_estimate_direct_grams():
    grams, note = estimate_grams(None, ParsedItem(food_alias="pollo", quantity=500, unit="g", quantity_g=500), None)

    assert grams == 500
    assert note is None


def test_estimate_alias_unit_fallback():
    grams, note = estimate_grams(None, ParsedItem(food_alias="manzana", quantity=1, unit="serving"), None)

    assert grams == 182
    assert note is not None


def test_estimate_rice_cup_fallback():
    grams, note = estimate_grams(None, ParsedItem(food_alias="arroz blanco cocido", quantity=1, unit="cup"), None)

    assert grams == 158
    assert note is not None
