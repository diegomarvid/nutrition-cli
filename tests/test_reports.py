from datetime import date

from nutrition_cli.database import commit_meal, connect, init_db, upsert_food_detail
from nutrition_cli.models import ParsedItem, ParsedMeal
from nutrition_cli.reports import load_report


def test_report_aggregates_per_100g(tmp_path):
    conn = connect(tmp_path / "nutrition.db")
    init_db(conn)
    upsert_food_detail(
        conn,
        {
            "fdcId": 1,
            "description": "Test chicken",
            "foodNutrients": [
                {"nutrient": {"number": "203", "id": 1003, "name": "Protein", "unitName": "g"}, "amount": 20},
                {"nutrient": {"number": "208", "id": 1008, "name": "Energy", "unitName": "kcal"}, "amount": 200},
            ],
        },
    )
    meal = ParsedMeal(
        raw_text="200g chicken",
        date=date(2026, 6, 24),
        items=[ParsedItem(food_alias="chicken", quantity=200, unit="g", quantity_g=200)],
    )
    commit_meal(conn, meal, "2026-06-24", [(meal.items[0], 1, 200)])

    report = load_report(conn, date(2026, 6, 24), date(2026, 6, 24))

    assert report.totals["203"] == 40
    assert report.totals["208"] == 400
