from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date as Date, datetime
from pathlib import Path
from typing import Any, Iterable

from .models import ParsedItem, ParsedMeal, UserProfile


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS food_aliases (
  alias TEXT PRIMARY KEY,
  fdc_id INTEGER NOT NULL,
  default_unit TEXT,
  default_quantity_g REAL,
  notes TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meal_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,
  raw_text TEXT NOT NULL,
  parsed_json TEXT NOT NULL,
  confidence REAL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meal_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  meal_log_id INTEGER NOT NULL REFERENCES meal_logs(id) ON DELETE CASCADE,
  food_alias TEXT NOT NULL,
  fdc_id INTEGER,
  quantity REAL,
  quantity_unit TEXT,
  quantity_g REAL,
  preparation TEXT,
  confidence REAL,
  raw_item_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_meal_logs_date ON meal_logs(date);
CREATE INDEX IF NOT EXISTS idx_meal_items_fdc ON meal_items(fdc_id);

CREATE TABLE IF NOT EXISTS foods (
  fdc_id INTEGER PRIMARY KEY,
  description TEXT NOT NULL,
  data_type TEXT,
  brand_owner TEXT,
  serving_size REAL,
  serving_size_unit TEXT,
  fetched_at TEXT NOT NULL,
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS food_nutrients (
  fdc_id INTEGER NOT NULL REFERENCES foods(fdc_id) ON DELETE CASCADE,
  nutrient_number TEXT NOT NULL,
  nutrient_id INTEGER,
  nutrient_name TEXT NOT NULL,
  amount_per_100g REAL NOT NULL,
  unit TEXT NOT NULL,
  PRIMARY KEY (fdc_id, nutrient_number)
);

CREATE TABLE IF NOT EXISTS food_portions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fdc_id INTEGER NOT NULL REFERENCES foods(fdc_id) ON DELETE CASCADE,
  amount REAL,
  gram_weight REAL NOT NULL,
  measure_unit_name TEXT,
  modifier TEXT,
  sequence_number INTEGER
);

CREATE INDEX IF NOT EXISTS idx_food_portions_fdc ON food_portions(fdc_id);

CREATE TABLE IF NOT EXISTS user_profiles (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  birth_date TEXT,
  sex TEXT,
  height_cm REAL,
  weight_kg REAL,
  activity_level TEXT,
  updated_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    ensure_schema_migrations(conn)
    conn.commit()


def ensure_schema_migrations(conn: sqlite3.Connection) -> None:
    alias_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(food_aliases)").fetchall()
    }
    if "default_quantity_g" not in alias_columns:
        conn.execute("ALTER TABLE food_aliases ADD COLUMN default_quantity_g REAL")


def get_user_profile(conn: sqlite3.Connection) -> UserProfile | None:
    row = conn.execute("SELECT * FROM user_profiles WHERE id = 1").fetchone()
    if row is None:
        return None
    return UserProfile(
        birth_date=Date.fromisoformat(row["birth_date"]) if row["birth_date"] else None,
        sex=row["sex"],
        height_cm=row["height_cm"],
        weight_kg=row["weight_kg"],
        activity_level=row["activity_level"],
    )


def upsert_user_profile(conn: sqlite3.Connection, profile: UserProfile) -> None:
    conn.execute(
        """
        INSERT INTO user_profiles(
          id, birth_date, sex, height_cm, weight_kg, activity_level, updated_at
        )
        VALUES (1, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          birth_date = excluded.birth_date,
          sex = excluded.sex,
          height_cm = excluded.height_cm,
          weight_kg = excluded.weight_kg,
          activity_level = excluded.activity_level,
          updated_at = excluded.updated_at
        """,
        (
            profile.birth_date.isoformat() if profile.birth_date else None,
            profile.sex,
            profile.height_cm,
            profile.weight_kg,
            profile.activity_level,
            now_iso(),
        ),
    )
    conn.commit()


def delete_user_profile(conn: sqlite3.Connection) -> int:
    cur = conn.execute("DELETE FROM user_profiles WHERE id = 1")
    conn.commit()
    return cur.rowcount


def get_alias(conn: sqlite3.Connection, alias: str) -> sqlite3.Row | None:
    normalized = normalize_alias(alias)
    return conn.execute("SELECT * FROM food_aliases WHERE alias = ?", (normalized,)).fetchone()


def upsert_alias(
    conn: sqlite3.Connection,
    alias: str,
    fdc_id: int,
    default_unit: str | None = None,
    default_quantity_g: float | None = None,
    notes: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO food_aliases(alias, fdc_id, default_unit, default_quantity_g, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(alias) DO UPDATE SET
          fdc_id = excluded.fdc_id,
          default_unit = excluded.default_unit,
          default_quantity_g = excluded.default_quantity_g,
          notes = excluded.notes
        """,
        (normalize_alias(alias), fdc_id, default_unit, default_quantity_g, notes, now_iso()),
    )
    conn.commit()


def delete_alias(conn: sqlite3.Connection, alias: str) -> int:
    cur = conn.execute("DELETE FROM food_aliases WHERE alias = ?", (normalize_alias(alias),))
    conn.commit()
    return cur.rowcount


def list_aliases(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM food_aliases ORDER BY alias"))


def insert_meal_log(conn: sqlite3.Connection, meal: ParsedMeal, log_date: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO meal_logs(date, raw_text, parsed_json, confidence, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (log_date, meal.raw_text, meal.as_db_json(), meal.confidence, now_iso()),
    )
    return int(cur.lastrowid)


def insert_meal_item(
    conn: sqlite3.Connection,
    meal_log_id: int,
    item: ParsedItem,
    fdc_id: int | None,
    quantity_g: float | None,
) -> None:
    conn.execute(
        """
        INSERT INTO meal_items(
          meal_log_id, food_alias, fdc_id, quantity, quantity_unit, quantity_g,
          preparation, confidence, raw_item_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            meal_log_id,
            normalize_alias(item.food_alias),
            fdc_id,
            item.quantity,
            item.unit,
            quantity_g,
            item.preparation,
            item.confidence,
            item.model_dump_json(),
        ),
    )


def commit_meal(
    conn: sqlite3.Connection,
    meal: ParsedMeal,
    log_date: str,
    resolved_items: Iterable[tuple[ParsedItem, int | None, float | None]],
) -> int:
    meal_log_id = insert_meal_log(conn, meal, log_date)
    for item, fdc_id, quantity_g in resolved_items:
        insert_meal_item(conn, meal_log_id, item, fdc_id, quantity_g)
    conn.commit()
    return meal_log_id


def cached_food(conn: sqlite3.Connection, fdc_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM foods WHERE fdc_id = ?", (fdc_id,)).fetchone()


def upsert_food_detail(conn: sqlite3.Connection, food: dict[str, Any]) -> None:
    fdc_id = int(food["fdcId"])
    conn.execute(
        """
        INSERT INTO foods(
          fdc_id, description, data_type, brand_owner, serving_size,
          serving_size_unit, fetched_at, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(fdc_id) DO UPDATE SET
          description = excluded.description,
          data_type = excluded.data_type,
          brand_owner = excluded.brand_owner,
          serving_size = excluded.serving_size,
          serving_size_unit = excluded.serving_size_unit,
          fetched_at = excluded.fetched_at,
          raw_json = excluded.raw_json
        """,
        (
            fdc_id,
            food.get("description") or "",
            food.get("dataType"),
            food.get("brandOwner"),
            food.get("servingSize"),
            food.get("servingSizeUnit"),
            now_iso(),
            json.dumps(food, ensure_ascii=False),
        ),
    )
    conn.execute("DELETE FROM food_nutrients WHERE fdc_id = ?", (fdc_id,))
    conn.execute("DELETE FROM food_portions WHERE fdc_id = ?", (fdc_id,))

    nutrients = []
    for nutrient in food.get("foodNutrients", []):
        normalized = normalize_nutrient(nutrient)
        if normalized is not None:
            nutrients.append((fdc_id, *normalized))
    conn.executemany(
        """
        INSERT OR REPLACE INTO food_nutrients(
          fdc_id, nutrient_number, nutrient_id, nutrient_name, amount_per_100g, unit
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        nutrients,
    )

    portions = []
    for portion in food.get("foodPortions", []):
        gram_weight = portion.get("gramWeight")
        if gram_weight is None:
            continue
        measure_unit = portion.get("measureUnit") or {}
        portions.append(
            (
                fdc_id,
                portion.get("amount"),
                gram_weight,
                measure_unit.get("name"),
                portion.get("modifier"),
                portion.get("sequenceNumber"),
            )
        )
    conn.executemany(
        """
        INSERT INTO food_portions(
          fdc_id, amount, gram_weight, measure_unit_name, modifier, sequence_number
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        portions,
    )
    conn.commit()


def normalize_nutrient(nutrient: dict[str, Any]) -> tuple[str, int | None, str, float, str] | None:
    amount = nutrient.get("amount", nutrient.get("value"))
    if amount is None:
        return None
    metadata = nutrient.get("nutrient") or {}
    number = metadata.get("number") or nutrient.get("nutrientNumber")
    name = metadata.get("name") or nutrient.get("nutrientName")
    unit = metadata.get("unitName") or nutrient.get("unitName")
    nutrient_id = metadata.get("id") or nutrient.get("nutrientId")
    if not number or not name or not unit:
        return None
    return str(number), nutrient_id, str(name), float(amount), str(unit)


def food_description(conn: sqlite3.Connection, fdc_id: int) -> str:
    row = cached_food(conn, fdc_id)
    return row["description"] if row else str(fdc_id)


def find_portion_grams(conn: sqlite3.Connection, fdc_id: int, unit: str) -> float | None:
    normalized = normalize_alias(unit)
    rows = conn.execute(
        """
        SELECT * FROM food_portions
        WHERE fdc_id = ?
        ORDER BY sequence_number IS NULL, sequence_number
        """,
        (fdc_id,),
    ).fetchall()
    for row in rows:
        haystack = normalize_alias(" ".join(filter(None, [row["measure_unit_name"], row["modifier"]])))
        if normalized and normalized in haystack:
            amount = row["amount"] or 1
            if amount == 0:
                return row["gram_weight"]
            return row["gram_weight"] / amount
    return None


def normalize_alias(value: str) -> str:
    return " ".join(value.strip().lower().split())
