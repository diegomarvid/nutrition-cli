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
  meal_type TEXT,
  raw_text TEXT NOT NULL,
  parsed_json TEXT NOT NULL,
  confidence REAL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meal_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  meal_log_id INTEGER NOT NULL REFERENCES meal_logs(id) ON DELETE CASCADE,
  food_alias TEXT NOT NULL,
  meal_type TEXT,
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

CREATE TABLE IF NOT EXISTS food_resolution_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  meal_log_id INTEGER REFERENCES meal_logs(id) ON DELETE SET NULL,
  meal_item_id INTEGER REFERENCES meal_items(id) ON DELETE SET NULL,
  alias TEXT NOT NULL,
  source TEXT NOT NULL,
  chosen_fdc_id INTEGER,
  chosen_description TEXT,
  candidates_json TEXT,
  reason TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_food_resolution_alias ON food_resolution_events(alias);
CREATE INDEX IF NOT EXISTS idx_food_resolution_fdc ON food_resolution_events(chosen_fdc_id);

CREATE TABLE IF NOT EXISTS alias_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  alias TEXT NOT NULL,
  old_fdc_id INTEGER,
  new_fdc_id INTEGER,
  old_default_quantity_g REAL,
  new_default_quantity_g REAL,
  reason TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alias_history_alias ON alias_history(alias);

CREATE TABLE IF NOT EXISTS food_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fdc_id INTEGER NOT NULL,
  source_type TEXT NOT NULL,
  source_ref TEXT,
  label_text TEXT,
  raw_payload TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_food_sources_fdc ON food_sources(fdc_id);

CREATE TABLE IF NOT EXISTS food_preferences (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  food_name TEXT NOT NULL,
  normalized_food_name TEXT NOT NULL,
  preference TEXT NOT NULL,
  intensity INTEGER NOT NULL DEFAULT 3,
  context TEXT NOT NULL DEFAULT '',
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(normalized_food_name, context)
);

CREATE INDEX IF NOT EXISTS idx_food_preferences_preference ON food_preferences(preference);
CREATE INDEX IF NOT EXISTS idx_food_preferences_context ON food_preferences(context);
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
    meal_log_columns = table_columns(conn, "meal_logs")
    if "meal_type" not in meal_log_columns:
        conn.execute("ALTER TABLE meal_logs ADD COLUMN meal_type TEXT")
    meal_item_columns = table_columns(conn, "meal_items")
    if "meal_type" not in meal_item_columns:
        conn.execute("ALTER TABLE meal_items ADD COLUMN meal_type TEXT")


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


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
    reason: str | None = None,
) -> None:
    normalized_alias = normalize_alias(alias)
    existing = get_alias(conn, normalized_alias)
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
        (normalized_alias, fdc_id, default_unit, default_quantity_g, notes, now_iso()),
    )
    if alias_changed(existing, fdc_id, default_quantity_g):
        conn.execute(
            """
            INSERT INTO alias_history(
              alias, old_fdc_id, new_fdc_id, old_default_quantity_g,
              new_default_quantity_g, reason, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_alias,
                existing["fdc_id"] if existing else None,
                fdc_id,
                existing["default_quantity_g"] if existing else None,
                default_quantity_g,
                reason,
                now_iso(),
            ),
        )
    conn.commit()


def alias_changed(existing: sqlite3.Row | None, fdc_id: int, default_quantity_g: float | None) -> bool:
    if existing is None:
        return True
    if int(existing["fdc_id"]) != int(fdc_id):
        return True
    old_default = existing["default_quantity_g"]
    if old_default is None and default_quantity_g is None:
        return False
    if old_default is None or default_quantity_g is None:
        return True
    return float(old_default) != float(default_quantity_g)


def delete_alias(conn: sqlite3.Connection, alias: str) -> int:
    normalized = normalize_alias(alias)
    existing = get_alias(conn, normalized)
    cur = conn.execute("DELETE FROM food_aliases WHERE alias = ?", (normalized,))
    if existing is not None and cur.rowcount:
        conn.execute(
            """
            INSERT INTO alias_history(
              alias, old_fdc_id, new_fdc_id, old_default_quantity_g,
              new_default_quantity_g, reason, created_at
            )
            VALUES (?, ?, NULL, ?, NULL, ?, ?)
            """,
            (
                normalized,
                existing["fdc_id"],
                existing["default_quantity_g"],
                "alias removed",
                now_iso(),
            ),
        )
    conn.commit()
    return cur.rowcount


def list_aliases(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM food_aliases ORDER BY alias"))


def insert_meal_log(conn: sqlite3.Connection, meal: ParsedMeal, log_date: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO meal_logs(date, meal_type, raw_text, parsed_json, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (log_date, meal.meal_type, meal.raw_text, meal.as_db_json(), meal.confidence, now_iso()),
    )
    return int(cur.lastrowid)


def insert_meal_item(
    conn: sqlite3.Connection,
    meal_log_id: int,
    item: ParsedItem,
    fdc_id: int | None,
    quantity_g: float | None,
    default_meal_type: str | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO meal_items(
          meal_log_id, food_alias, meal_type, fdc_id, quantity, quantity_unit, quantity_g,
          preparation, confidence, raw_item_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            meal_log_id,
            normalize_alias(item.food_alias),
            item.meal_type or default_meal_type,
            fdc_id,
            item.quantity,
            item.unit,
            quantity_g,
            item.preparation,
            item.confidence,
            item.model_dump_json(),
        ),
    )
    return int(cur.lastrowid)


def commit_meal(
    conn: sqlite3.Connection,
    meal: ParsedMeal,
    log_date: str,
    resolved_items: Iterable[tuple[ParsedItem, int | None, float | None]],
) -> int:
    meal_log_id = insert_meal_log(conn, meal, log_date)
    for item, fdc_id, quantity_g in resolved_items:
        meal_item_id = insert_meal_item(conn, meal_log_id, item, fdc_id, quantity_g, default_meal_type=meal.meal_type)
        log_resolution_event(
            conn,
            meal_log_id=meal_log_id,
            meal_item_id=meal_item_id,
            alias=item.food_alias,
            source="meal-log",
            chosen_fdc_id=fdc_id,
            reason="meal item saved",
            commit=False,
        )
    conn.commit()
    return meal_log_id


def log_resolution_event(
    conn: sqlite3.Connection,
    *,
    alias: str,
    source: str,
    chosen_fdc_id: int | None,
    chosen_description: str | None = None,
    candidates: list[dict[str, Any]] | None = None,
    reason: str | None = None,
    meal_log_id: int | None = None,
    meal_item_id: int | None = None,
    commit: bool = True,
) -> None:
    conn.execute(
        """
        INSERT INTO food_resolution_events(
          meal_log_id, meal_item_id, alias, source, chosen_fdc_id,
          chosen_description, candidates_json, reason, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            meal_log_id,
            meal_item_id,
            normalize_alias(alias),
            source,
            chosen_fdc_id,
            chosen_description,
            json.dumps(candidates, ensure_ascii=False) if candidates is not None else None,
            reason,
            now_iso(),
        ),
    )
    if commit:
        conn.commit()


def add_food_source(
    conn: sqlite3.Connection,
    *,
    fdc_id: int,
    source_type: str,
    source_ref: str | None = None,
    label_text: str | None = None,
    raw_payload: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO food_sources(fdc_id, source_type, source_ref, label_text, raw_payload, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            fdc_id,
            source_type,
            source_ref,
            label_text,
            json.dumps(raw_payload, ensure_ascii=False) if raw_payload is not None else None,
            now_iso(),
        ),
    )
    conn.commit()


def upsert_food_preference(
    conn: sqlite3.Connection,
    *,
    food_name: str,
    preference: str,
    intensity: int = 3,
    context: str | None = None,
    notes: str | None = None,
) -> None:
    normalized = normalize_alias(food_name)
    normalized_context = normalize_context(context)
    conn.execute(
        """
        INSERT INTO food_preferences(
          food_name, normalized_food_name, preference, intensity, context,
          notes, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(normalized_food_name, context) DO UPDATE SET
          food_name = excluded.food_name,
          preference = excluded.preference,
          intensity = excluded.intensity,
          notes = excluded.notes,
          updated_at = excluded.updated_at
        """,
        (
            food_name.strip(),
            normalized,
            preference,
            intensity,
            normalized_context,
            notes,
            now_iso(),
            now_iso(),
        ),
    )
    conn.commit()


def list_food_preferences(
    conn: sqlite3.Connection,
    *,
    preference: str | None = None,
    context: str | None = None,
    limit: int = 100,
) -> list[sqlite3.Row]:
    filters = []
    params: list[Any] = []
    if preference is not None:
        filters.append("preference = ?")
        params.append(preference)
    if context is not None:
        filters.append("context = ?")
        params.append(normalize_context(context))
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(limit)
    return list(
        conn.execute(
            f"""
            SELECT * FROM food_preferences
            {where}
            ORDER BY
              CASE preference
                WHEN 'love' THEN 1
                WHEN 'like' THEN 2
                WHEN 'neutral' THEN 3
                WHEN 'dislike' THEN 4
                WHEN 'avoid' THEN 5
                ELSE 6
              END,
              intensity DESC,
              normalized_food_name
            LIMIT ?
            """,
            params,
        )
    )


def delete_food_preference(conn: sqlite3.Connection, food_name: str, context: str | None = None) -> int:
    normalized = normalize_alias(food_name)
    cur = conn.execute(
        """
        DELETE FROM food_preferences
        WHERE normalized_food_name = ? AND context = ?
        """,
        (normalized, normalize_context(context)),
    )
    conn.commit()
    return cur.rowcount


def list_resolution_events(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT * FROM food_resolution_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
    )


def list_alias_history(conn: sqlite3.Connection, alias: str | None = None, limit: int = 50) -> list[sqlite3.Row]:
    if alias:
        return list(
            conn.execute(
                """
                SELECT * FROM alias_history
                WHERE alias = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (normalize_alias(alias), limit),
            )
        )
    return list(
        conn.execute(
            """
            SELECT * FROM alias_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
    )


def list_food_sources(conn: sqlite3.Connection, fdc_id: int | None = None, limit: int = 50) -> list[sqlite3.Row]:
    if fdc_id is not None:
        return list(
            conn.execute(
                """
                SELECT * FROM food_sources
                WHERE fdc_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (fdc_id, limit),
            )
        )
    return list(
        conn.execute(
            """
            SELECT * FROM food_sources
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
    )


def list_meal_items_for_audit(
    conn: sqlite3.Connection,
    start_date: str,
    end_date: str,
) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT
              ml.date,
              ml.id AS meal_log_id,
              mi.id AS meal_item_id,
              COALESCE(mi.meal_type, ml.meal_type, '') AS meal_type,
              mi.food_alias,
              mi.quantity,
              mi.quantity_unit,
              mi.quantity_g,
              mi.fdc_id,
              f.description,
              f.data_type
            FROM meal_items mi
            JOIN meal_logs ml ON ml.id = mi.meal_log_id
            LEFT JOIN foods f ON f.fdc_id = mi.fdc_id
            WHERE ml.date >= ? AND ml.date <= ?
            ORDER BY ml.date, meal_type, mi.id
            """,
            (start_date, end_date),
        )
    )


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


def normalize_context(value: str | None) -> str:
    if value is None:
        return ""
    return normalize_alias(value)
