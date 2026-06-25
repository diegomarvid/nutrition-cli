from datetime import date

from nutrition_cli.database import (
    commit_meal,
    connect,
    get_user_profile,
    init_db,
    upsert_food_detail,
    upsert_user_profile,
)
from nutrition_cli.models import ParsedItem, ParsedMeal, UserProfile
from nutrition_cli.reports import build_targets, load_report


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


def test_profile_roundtrip(tmp_path):
    conn = connect(tmp_path / "nutrition.db")
    init_db(conn)
    profile = UserProfile(
        birth_date=date(1990, 1, 15),
        sex="hombre",
        height_cm=180,
        weight_kg=80,
        activity_level="liviano",
    )

    upsert_user_profile(conn, profile)
    loaded = get_user_profile(conn)

    assert loaded is not None
    assert loaded.birth_date == date(1990, 1, 15)
    assert loaded.sex == "male"
    assert loaded.height_cm == 180
    assert loaded.weight_kg == 80
    assert loaded.activity_level == "light"


def test_profile_targets_use_age_sex_and_body_size():
    profile = UserProfile(
        birth_date=date(1995, 1, 1),
        sex="female",
        height_cm=165,
        weight_kg=60,
        activity_level="sedentary",
    )

    targets = build_targets(profile, date(2026, 1, 1))

    assert 1500 <= targets["208"].target <= 1700
    assert targets["203"].target == 48
    assert targets["291"].target == 25
    assert targets["303"].target == 18
    assert targets["304"].target == 320
