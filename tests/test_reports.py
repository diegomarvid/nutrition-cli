from datetime import date

from nutrition_cli.database import (
    add_food_source,
    commit_meal,
    connect,
    delete_food_preference,
    get_user_profile,
    init_db,
    list_alias_history,
    list_food_preferences,
    list_food_sources,
    list_meal_items_for_audit,
    list_resolution_events,
    upsert_food_preference,
    upsert_food_detail,
    upsert_alias,
    upsert_user_profile,
)
from nutrition_cli.cli import label_food_payload
from nutrition_cli.models import ParsedItem, ParsedMeal, UserProfile
from nutrition_cli.reports import assistant_handoff_lines, build_targets, has_missing_or_partial_coverage, load_report


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
    assert report.coverage["203"].known_items == 1
    assert report.coverage["301"].known_items == 0


def test_meal_type_is_stored_for_audit(tmp_path):
    conn = connect(tmp_path / "nutrition.db")
    init_db(conn)
    upsert_food_detail(
        conn,
        {
            "fdcId": 1,
            "description": "Test rice",
            "foodNutrients": [
                {"nutrient": {"number": "208", "id": 1008, "name": "Energy", "unitName": "kcal"}, "amount": 100},
            ],
        },
    )
    meal = ParsedMeal(
        raw_text="lunch rice",
        date=date(2026, 6, 24),
        meal_type="lunch",
        items=[ParsedItem(food_alias="rice", quantity_g=100)],
    )

    commit_meal(conn, meal, "2026-06-24", [(meal.items[0], 1, 100)])
    rows = list_meal_items_for_audit(conn, "2026-06-24", "2026-06-24")
    events = list_resolution_events(conn)

    assert rows[0]["meal_type"] == "lunch"
    assert rows[0]["food_alias"] == "rice"
    assert events[0]["source"] == "meal-log"
    assert events[0]["meal_log_id"] is not None
    assert events[0]["meal_item_id"] == rows[0]["meal_item_id"]


def test_report_tracks_partial_nutrient_coverage(tmp_path):
    conn = connect(tmp_path / "nutrition.db")
    init_db(conn)
    upsert_food_detail(
        conn,
        {
            "fdcId": 1,
            "description": "Food with calcium",
            "foodNutrients": [
                {"nutrient": {"number": "208", "id": 1008, "name": "Energy", "unitName": "kcal"}, "amount": 100},
                {"nutrient": {"number": "301", "id": 1087, "name": "Calcium", "unitName": "mg"}, "amount": 50},
            ],
        },
    )
    upsert_food_detail(
        conn,
        {
            "fdcId": 2,
            "description": "Label-only food",
            "foodNutrients": [
                {"nutrient": {"number": "208", "id": 1008, "name": "Energy", "unitName": "kcal"}, "amount": 200},
            ],
        },
    )
    meal = ParsedMeal(
        raw_text="mixed foods",
        date=date(2026, 6, 24),
        items=[
            ParsedItem(food_alias="food with calcium", quantity_g=100),
            ParsedItem(food_alias="label food", quantity_g=300),
        ],
    )
    commit_meal(conn, meal, "2026-06-24", [(meal.items[0], 1, 100), (meal.items[1], 2, 300)])

    report = load_report(conn, date(2026, 6, 24), date(2026, 6, 24))

    assert report.totals["208"] == 700
    assert report.totals["301"] == 50
    assert report.coverage["208"].known_items == 2
    assert report.coverage["208"].gram_percent == 1
    assert report.coverage["301"].known_items == 1
    assert report.coverage["301"].gram_percent == 0.25
    assert has_missing_or_partial_coverage(report)
    handoff = assistant_handoff_lines(report)
    assert any("Sanity-check quantities" in line for line in handoff)
    assert any("unknown/partial nutrients" in line for line in handoff)


def test_report_tracks_detailed_fatty_acids_without_double_counting_ala(tmp_path):
    conn = connect(tmp_path / "nutrition.db")
    init_db(conn)
    upsert_food_detail(
        conn,
        {
            "fdcId": 1,
            "description": "Seeds, chia seeds, dried",
            "foodNutrients": [
                {"nutrient": {"number": "619", "id": 1270, "name": "PUFA 18:3", "unitName": "g"}, "amount": 17.83},
                {
                    "nutrient": {
                        "number": "851",
                        "id": 1404,
                        "name": "PUFA 18:3 n-3 c,c,c (ALA)",
                        "unitName": "g",
                    },
                    "amount": 17.83,
                },
                {
                    "nutrient": {
                        "number": "646",
                        "id": 1293,
                        "name": "Fatty acids, total polyunsaturated",
                        "unitName": "g",
                    },
                    "amount": 23.7,
                },
            ],
        },
    )
    upsert_food_detail(
        conn,
        {
            "fdcId": 2,
            "description": "Fish, salmon, raw",
            "foodNutrients": [
                {"nutrient": {"number": "629", "id": 1278, "name": "PUFA 20:5 n-3 (EPA)", "unitName": "g"}, "amount": 1},
                {"nutrient": {"number": "621", "id": 1272, "name": "PUFA 22:6 n-3 (DHA)", "unitName": "g"}, "amount": 0.9},
            ],
        },
    )
    meal = ParsedMeal(
        raw_text="chia and salmon",
        date=date(2026, 6, 24),
        items=[
            ParsedItem(food_alias="chia", quantity_g=10),
            ParsedItem(food_alias="salmon", quantity_g=100),
        ],
    )
    commit_meal(conn, meal, "2026-06-24", [(meal.items[0], 1, 10), (meal.items[1], 2, 100)])

    report = load_report(conn, date(2026, 6, 24), date(2026, 6, 24))

    assert round(report.totals["619"], 3) == 1.783
    assert round(report.totals["646"], 2) == 2.37
    assert round(report.totals["EPA_DHA"], 2) == 1.9
    assert report.coverage["EPA_DHA"].known_items == 1


def test_local_label_payload_accepts_detailed_fats():
    payload = label_food_payload(
        fdc_id=9_000_001,
        name="Test omega label",
        serving_g=10,
        calories=None,
        protein=None,
        fat=1,
        saturated_fat=0.1,
        trans_fat=0,
        cholesterol=5,
        carbs=None,
        fiber=None,
        sodium=None,
        linoleic_acid=0.2,
        ala=0.3,
        epa=0.04,
        dha=0.05,
        dpa=0.01,
        mufa=0.4,
        pufa=0.6,
        default_quantity_g=None,
    )

    nutrients = {
        nutrient["nutrient"]["number"]: nutrient["amount"]
        for nutrient in payload["foodNutrients"]
    }

    assert nutrients["629"] == 0.4
    assert nutrients["621"] == 0.5
    assert nutrients["645"] == 4
    assert nutrients["646"] == 6


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
    assert targets["328"].target == 15
    assert targets["323"].target == 15
    assert targets["421"].target == 425
    assert targets["606"].target is not None


def test_alias_history_and_food_sources(tmp_path):
    conn = connect(tmp_path / "nutrition.db")
    init_db(conn)

    upsert_alias(conn, "test food", 1, default_quantity_g=100, reason="first mapping")
    upsert_alias(conn, "test food", 2, default_quantity_g=120, reason="corrected mapping")
    add_food_source(
        conn,
        fdc_id=2,
        source_type="local-label",
        source_ref="/tmp/label.jpg",
        label_text="serving_g=100; calcium_mg=200",
        raw_payload={"fdcId": 2},
    )

    history = list_alias_history(conn, alias="test food")
    sources = list_food_sources(conn, fdc_id=2)

    assert len(history) == 2
    assert history[0]["old_fdc_id"] == 1
    assert history[0]["new_fdc_id"] == 2
    assert history[0]["reason"] == "corrected mapping"
    assert sources[0]["source_ref"] == "/tmp/label.jpg"
    assert "calcium_mg" in sources[0]["label_text"]


def test_food_preferences_roundtrip(tmp_path):
    conn = connect(tmp_path / "nutrition.db")
    init_db(conn)

    upsert_food_preference(
        conn,
        food_name="Queso",
        preference="like",
        intensity=4,
        context="calcium",
        notes="Good option when avoiding milk/yogurt",
    )
    upsert_food_preference(
        conn,
        food_name="Yogur",
        preference="avoid",
        intensity=5,
        notes="User dislikes it",
    )

    calcium = list_food_preferences(conn, context="calcium")
    avoid = list_food_preferences(conn, preference="avoid")

    assert calcium[0]["food_name"] == "Queso"
    assert calcium[0]["preference"] == "like"
    assert calcium[0]["intensity"] == 4
    assert avoid[0]["food_name"] == "Yogur"

    upsert_food_preference(
        conn,
        food_name="queso",
        preference="love",
        intensity=5,
        context="calcium",
        notes="Best calcium suggestion",
    )
    updated = list_food_preferences(conn, context="calcium")

    assert len(updated) == 1
    assert updated[0]["food_name"] == "queso"
    assert updated[0]["preference"] == "love"
    assert updated[0]["notes"] == "Best calcium suggestion"

    assert delete_food_preference(conn, "queso", context="calcium") == 1
    assert list_food_preferences(conn, context="calcium") == []
