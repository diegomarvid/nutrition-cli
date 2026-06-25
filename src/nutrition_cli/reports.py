from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from rich.console import Console
from rich.table import Table

from .database import get_user_profile
from .models import NutrientTarget, UserProfile


def nutrient(
    number: str,
    label: str,
    unit: str,
    target: float | None,
    category: str,
    nutrient_id: int | None = None,
    note: str | None = None,
) -> NutrientTarget:
    return NutrientTarget(
        number=number,
        label=label,
        unit=unit,
        target=target,
        category=category,
        nutrient_id=nutrient_id,
        note=note,
    )


BASE_TARGETS = {
    "208": nutrient("208", "Calories", "kcal", 2500, "energy", nutrient_id=1008),
    "203": nutrient("203", "Protein", "g", 50, "macros", nutrient_id=1003),
    "204": nutrient("204", "Fat", "g", 80, "macros", nutrient_id=1004),
    "606": nutrient("606", "Saturated fat", "g", 20, "macros", note="limit-style target"),
    "605": nutrient("605", "Trans fat", "g", 0, "macros", note="as low as possible"),
    "601": nutrient("601", "Cholesterol", "mg", None, "macros"),
    "205": nutrient("205", "Carbs", "g", 300, "macros", nutrient_id=1005),
    "269": nutrient("269", "Total sugars", "g", None, "macros"),
    "291": nutrient("291", "Fiber", "g", 28, "macros", nutrient_id=1079),
    "618": nutrient("618", "Linoleic acid", "g", 17, "fatty acids", note="omega-6 AI"),
    "619": nutrient("619", "Alpha-linolenic acid", "g", 1.6, "fatty acids", note="omega-3 AI"),
    "629": nutrient("629", "EPA", "g", None, "fatty acids", note="omega-3; no official DRI target"),
    "621": nutrient("621", "DHA", "g", None, "fatty acids", note="omega-3; no official DRI target"),
    "631": nutrient("631", "DPA", "g", None, "fatty acids", note="omega-3; no official DRI target"),
    "EPA_DHA": nutrient("EPA_DHA", "EPA + DHA", "g", None, "fatty acids", note="derived tracked value"),
    "645": nutrient("645", "Monounsaturated fat", "g", None, "fatty acids", nutrient_id=1292),
    "646": nutrient("646", "Polyunsaturated fat", "g", None, "fatty acids", nutrient_id=1293),
    "301": nutrient("301", "Calcium", "mg", 1000, "minerals", nutrient_id=1087),
    "305": nutrient("305", "Phosphorus", "mg", 700, "minerals", nutrient_id=1091),
    "303": nutrient("303", "Iron", "mg", 8, "minerals", nutrient_id=1089),
    "304": nutrient("304", "Magnesium", "mg", 420, "minerals", nutrient_id=1090),
    "306": nutrient("306", "Potassium", "mg", 3400, "minerals", nutrient_id=1092),
    "307": nutrient("307", "Sodium", "mg", 2300, "minerals", nutrient_id=1093, note="limit-style target"),
    "309": nutrient("309", "Zinc", "mg", 11, "minerals", nutrient_id=1095),
    "312": nutrient("312", "Copper", "mg", 0.9, "minerals", nutrient_id=1098),
    "315": nutrient("315", "Manganese", "mg", 2.3, "minerals", nutrient_id=1101),
    "317": nutrient("317", "Selenium", "ug", 55, "minerals", nutrient_id=1103),
    "320": nutrient("320", "Vitamin A", "ug", 900, "vitamins", nutrient_id=1106),
    "401": nutrient("401", "Vitamin C", "mg", 90, "vitamins", nutrient_id=1162),
    "328": nutrient("328", "Vitamin D", "ug", 15, "vitamins", nutrient_id=1110),
    "323": nutrient("323", "Vitamin E", "mg", 15, "vitamins", nutrient_id=1109),
    "430": nutrient("430", "Vitamin K", "ug", 120, "vitamins", nutrient_id=1185),
    "404": nutrient("404", "Thiamin (B1)", "mg", 1.2, "vitamins", nutrient_id=1165),
    "405": nutrient("405", "Riboflavin (B2)", "mg", 1.3, "vitamins", nutrient_id=1166),
    "406": nutrient("406", "Niacin (B3)", "mg", 16, "vitamins", nutrient_id=1167),
    "415": nutrient("415", "Vitamin B6", "mg", 1.3, "vitamins", nutrient_id=1175),
    "417": nutrient("417", "Folate", "ug", 400, "vitamins", nutrient_id=1177),
    "418": nutrient("418", "B12", "ug", 2.4, "vitamins", nutrient_id=1178),
    "410": nutrient("410", "Pantothenic acid", "mg", 5, "vitamins", nutrient_id=1170),
    "421": nutrient("421", "Choline", "mg", 550, "vitamins", nutrient_id=1180),
}

DISPLAY_ORDER = [
    "208",
    "203",
    "204",
    "606",
    "605",
    "601",
    "205",
    "269",
    "291",
    "618",
    "619",
    "629",
    "621",
    "631",
    "EPA_DHA",
    "645",
    "646",
    "301",
    "305",
    "303",
    "304",
    "306",
    "307",
    "309",
    "312",
    "315",
    "317",
    "320",
    "401",
    "328",
    "323",
    "430",
    "404",
    "405",
    "406",
    "415",
    "417",
    "418",
    "410",
    "421",
]

UPPER_LIMIT_NUMBERS = {"606", "605", "307"}
HIGH_WARNING_NUMBERS = {"208", "204", *UPPER_LIMIT_NUMBERS}
NO_TARGET_STATUS = "[dim]tracked[/]"
LOW_COVERAGE_THRESHOLD = 0.75
NUTRIENT_NUMBER_ALIASES = {
    "851": "619",  # 18:3 n-3 c,c,c (ALA), used by some FDC records.
}
ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very-active": 1.9,
}


@dataclass
class NutrientCoverage:
    total_items: int
    known_items: int = 0
    total_grams: float = 0
    known_grams: float = 0

    @property
    def item_percent(self) -> float | None:
        if self.total_items == 0:
            return None
        return self.known_items / self.total_items

    @property
    def gram_percent(self) -> float | None:
        if self.total_grams <= 0:
            return self.item_percent
        return self.known_grams / self.total_grams


@dataclass
class Report:
    start_date: date
    end_date: date
    days: int
    totals: dict[str, float]
    units: dict[str, str]
    item_count: int
    unresolved_items: list[str]
    coverage: dict[str, NutrientCoverage]
    profile: UserProfile | None = None


def load_report(conn, start: date, end: date) -> Report:
    target_by_number = {target.number: key for key, target in BASE_TARGETS.items()}
    target_by_id = {
        target.nutrient_id: key
        for key, target in BASE_TARGETS.items()
        if target.nutrient_id is not None
    }
    rows = conn.execute(
        """
        SELECT
          mi.id AS meal_item_id,
          mi.food_alias,
          mi.quantity_g,
          mi.fdc_id,
          fn.nutrient_number,
          fn.nutrient_id,
          fn.amount_per_100g,
          fn.unit
        FROM meal_items mi
        JOIN meal_logs ml ON ml.id = mi.meal_log_id
        LEFT JOIN food_nutrients fn ON fn.fdc_id = mi.fdc_id
        WHERE ml.date >= ? AND ml.date <= ?
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchall()

    totals: dict[str, float] = defaultdict(float)
    units: dict[str, str] = {}
    unresolved = set()
    item_ids = set()
    resolved_items: dict[int, float] = {}
    known_items: dict[str, set[int]] = defaultdict(set)
    known_grams_by_item: dict[str, dict[int, float]] = defaultdict(dict)
    seen_item_nutrients: set[tuple[int, str]] = set()
    for row in rows:
        item_id = int(row["meal_item_id"])
        item_ids.add(item_id)
        if row["fdc_id"] is None or row["quantity_g"] is None:
            unresolved.add(row["food_alias"])
            continue
        quantity_g = float(row["quantity_g"])
        resolved_items[item_id] = quantity_g
        if row["nutrient_number"] is None:
            continue
        raw_number = str(row["nutrient_number"])
        key = NUTRIENT_NUMBER_ALIASES.get(raw_number) or target_by_number.get(raw_number)
        if key is None and row["nutrient_id"] is not None:
            key = target_by_id.get(int(row["nutrient_id"]))
        if key is None:
            continue
        if (item_id, key) in seen_item_nutrients:
            continue
        seen_item_nutrients.add((item_id, key))
        totals[key] += (row["amount_per_100g"] or 0) * quantity_g / 100
        units[key] = row["unit"]
        known_items[key].add(item_id)
        known_grams_by_item[key][item_id] = quantity_g

    add_derived_epa_dha(totals, units, known_items, known_grams_by_item, resolved_items)
    coverage = {}
    total_grams = sum(resolved_items.values())
    for key in BASE_TARGETS:
        item_set = known_items.get(key, set())
        grams_by_item = known_grams_by_item.get(key, {})
        coverage[key] = NutrientCoverage(
            total_items=len(resolved_items),
            known_items=len(item_set),
            total_grams=total_grams,
            known_grams=sum(grams_by_item.values()),
        )

    return Report(
        start_date=start,
        end_date=end,
        days=(end - start).days + 1,
        totals=dict(totals),
        units=units,
        item_count=len(item_ids),
        unresolved_items=sorted(unresolved),
        coverage=coverage,
        profile=get_user_profile(conn),
    )


def render_report(report: Report, console: Console, brutal: bool = True) -> None:
    title = (
        f"{report.start_date.isoformat()}"
        if report.start_date == report.end_date
        else f"{report.start_date.isoformat()} to {report.end_date.isoformat()}"
    )
    console.print(f"[bold]Nutrition report:[/] {title}")
    if report.item_count == 0:
        console.print("No logged items for this period.")
        return

    targets = build_targets(report.profile, report.end_date)
    console.print(target_context(report.profile, report.end_date))

    table = Table(show_header=True, header_style="bold")
    table.add_column("Nutrient")
    table.add_column("Amount", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("Status")
    table.add_column("Data", justify="right")

    low_labels = []
    high_labels = []
    over_labels = []
    for number in DISPLAY_ORDER:
        target = targets[number]
        coverage = report.coverage.get(number, NutrientCoverage(total_items=0))
        daily_amount = report.totals.get(number, 0) / report.days
        status, plain_status = nutrient_status(number, target, daily_amount, coverage)
        if plain_status == "high" and number in HIGH_WARNING_NUMBERS:
            over_labels.append(target.label)
        elif plain_status == "high":
            high_labels.append(target.label)
        elif plain_status == "low":
            low_labels.append(target.label)
        table.add_row(
            target.label,
            format_amount(daily_amount, target, coverage),
            format_target(target),
            status,
            format_coverage(coverage),
        )

    console.print(table)

    if has_partial_coverage(report):
        console.print("[dim]? = source data is partial for that nutrient; check the Data column.[/]")

    for line in assistant_handoff_lines(report):
        console.print(f"[dim]{line}[/]")

    if report.unresolved_items:
        console.print("[yellow]Unresolved items:[/] " + ", ".join(report.unresolved_items))

    if brutal and (low_labels or over_labels):
        console.print()
        console.print("[bold]Comentario brutal:[/]")
        if over_labels:
            console.print("Te pasaste en: " + ", ".join(over_labels[:5]) + ".")
        if "Protein" in high_labels and {"Fiber", "Magnesium", "Potassium"} & set(low_labels):
            console.print(
                "Bien de proteína; flojo en micronutrientes/fibra. Meté legumbres, frutos secos, verduras o fruta real."
            )
        elif low_labels:
            console.print("Lo más flojo: " + ", ".join(low_labels[:8]) + ".")


def week_window(ending: date) -> tuple[date, date]:
    return ending - timedelta(days=6), ending


def nutrient_status(
    number: str,
    target: NutrientTarget,
    daily_amount: float,
    coverage: NutrientCoverage,
) -> tuple[str, str]:
    coverage_percent = coverage.gram_percent
    if coverage.known_items == 0:
        return "[dim]unknown[/]", "unknown"

    suffix = "?" if coverage_percent is not None and coverage_percent < LOW_COVERAGE_THRESHOLD else ""
    if target.target is None:
        return f"{NO_TARGET_STATUS}{suffix}", "tracked"

    if number in UPPER_LIMIT_NUMBERS:
        if target.target == 0:
            plain = "ok" if daily_amount <= 0.1 else "high"
        else:
            percent = daily_amount / target.target
            plain = "high" if percent >= 1.1 else "ok"
        color = "red" if plain == "high" else "yellow"
        return f"[{color}]{plain}[/]{suffix}", plain

    percent = daily_amount / target.target if target.target else 0
    if percent >= 1.1:
        color = "red" if number in HIGH_WARNING_NUMBERS else "green"
        return f"[{color}]high[/]{suffix}", "high"
    if percent >= 0.75:
        return f"[yellow]ok[/]{suffix}", "ok"
    return f"[red]low[/]{suffix}", "low"


def format_amount(daily_amount: float, target: NutrientTarget, coverage: NutrientCoverage) -> str:
    if coverage.known_items == 0:
        return "[dim]unknown[/]"
    return f"{daily_amount:,.1f} {target.unit}"


def format_target(target: NutrientTarget) -> str:
    if target.target is None:
        return "[dim]no target[/]"
    if target.target == 0:
        return f"0 {target.unit}"
    return f"{target.target:g} {target.unit}"


def format_coverage(coverage: NutrientCoverage) -> str:
    percent = coverage.gram_percent
    if percent is None:
        return "[dim]n/a[/]"
    label = f"{percent * 100:.0f}%"
    if coverage.known_items == coverage.total_items:
        return label
    return f"{label} ({coverage.known_items}/{coverage.total_items})"


def has_partial_coverage(report: Report) -> bool:
    for coverage in report.coverage.values():
        percent = coverage.gram_percent
        if coverage.known_items > 0 and percent is not None and percent < LOW_COVERAGE_THRESHOLD:
            return True
    return False


def has_missing_or_partial_coverage(report: Report) -> bool:
    for coverage in report.coverage.values():
        if coverage.known_items == 0 and coverage.total_items > 0:
            return True
        percent = coverage.gram_percent
        if coverage.known_items > 0 and percent is not None and percent < LOW_COVERAGE_THRESHOLD:
            return True
    return False


def assistant_handoff_lines(report: Report) -> list[str]:
    lines = [
        "Assistant handoff: use this table as evidence, not as the final answer. "
        "Sanity-check quantities, food mappings, coverage, and suspicious outliers before summarizing."
    ]
    if has_missing_or_partial_coverage(report):
        lines.append(
            "Assistant rule: unknown/partial nutrients exist. Name important gaps and give clearly labeled "
            "AI judgment or research-based opinion instead of ignoring them."
        )
    return lines


def add_derived_epa_dha(
    totals: dict[str, float],
    units: dict[str, str],
    known_items: dict[str, set[int]],
    known_grams_by_item: dict[str, dict[int, float]],
    resolved_items: dict[int, float],
) -> None:
    totals["EPA_DHA"] = totals.get("629", 0) + totals.get("621", 0)
    units["EPA_DHA"] = "g"
    item_ids = known_items.get("629", set()) & known_items.get("621", set())
    if not item_ids:
        return
    known_items["EPA_DHA"] = item_ids
    known_grams_by_item["EPA_DHA"] = {
        item_id: resolved_items[item_id]
        for item_id in item_ids
        if item_id in resolved_items
    }


def build_targets(profile: UserProfile | None, day: date) -> dict[str, NutrientTarget]:
    targets = {number: target.model_copy() for number, target in BASE_TARGETS.items()}
    if profile is None:
        return targets

    age = profile.age_on(day)
    sex = profile.sex
    if profile.weight_kg is not None:
        targets["203"].target = round(max(0.8 * profile.weight_kg, 1), 1)

    if (
        age is not None
        and sex in {"male", "female"}
        and profile.height_cm is not None
        and profile.weight_kg is not None
    ):
        calories = estimated_daily_calories(profile, age)
        if calories is not None:
            targets["208"].target = calories
            targets["204"].target = round(calories * 0.30 / 9)
            targets["606"].target = round(calories * 0.10 / 9)
            targets["205"].target = round(calories * 0.50 / 4)

    if age is not None and sex in {"male", "female"}:
        apply_age_sex_targets(targets, age, sex)

    return targets


def estimated_daily_calories(profile: UserProfile, age: int) -> float | None:
    if profile.sex not in {"male", "female"} or profile.height_cm is None or profile.weight_kg is None:
        return None
    sex_adjustment = 5 if profile.sex == "male" else -161
    bmr = (10 * profile.weight_kg) + (6.25 * profile.height_cm) - (5 * age) + sex_adjustment
    activity_factor = ACTIVITY_FACTORS.get(profile.activity_level or "light", ACTIVITY_FACTORS["light"])
    return round_to_nearest(bmr * activity_factor, 25)


def apply_age_sex_targets(targets: dict[str, NutrientTarget], age: int, sex: str) -> None:
    if sex == "male":
        targets["291"].target = 38 if age <= 50 else 30
        targets["301"].target = 1000 if age <= 70 else 1200
        targets["305"].target = 700
        targets["303"].target = 8
        targets["304"].target = 400 if age <= 30 else 420
        targets["306"].target = 3400
        targets["309"].target = 11
        targets["312"].target = 0.9
        targets["315"].target = 2.3
        targets["317"].target = 55
        targets["320"].target = 900
        targets["401"].target = 90
        targets["328"].target = 15 if age <= 70 else 20
        targets["323"].target = 15
        targets["430"].target = 120
        targets["404"].target = 1.2
        targets["405"].target = 1.3
        targets["406"].target = 16
        targets["415"].target = 1.3 if age <= 50 else 1.7
        targets["410"].target = 5
        targets["421"].target = 550
        targets["618"].target = 17 if age <= 50 else 14
        targets["619"].target = 1.6
        return

    targets["291"].target = 25 if age <= 50 else 21
    targets["301"].target = 1000 if age <= 50 else 1200
    targets["305"].target = 700
    targets["303"].target = 18 if age <= 50 else 8
    targets["304"].target = 310 if age <= 30 else 320
    targets["306"].target = 2600
    targets["309"].target = 8
    targets["312"].target = 0.9
    targets["315"].target = 1.8
    targets["317"].target = 55
    targets["320"].target = 700
    targets["401"].target = 75
    targets["328"].target = 15 if age <= 70 else 20
    targets["323"].target = 15
    targets["430"].target = 90
    targets["404"].target = 1.1
    targets["405"].target = 1.1
    targets["406"].target = 14
    targets["415"].target = 1.3 if age <= 50 else 1.5
    targets["410"].target = 5
    targets["421"].target = 425
    targets["618"].target = 12 if age <= 50 else 11
    targets["619"].target = 1.1


def round_to_nearest(value: float, step: int) -> float:
    return round(value / step) * step


def target_context(profile: UserProfile | None, day: date) -> str:
    if profile is None:
        return "[dim]Targets: generic adult defaults. Run `nutrition profile set` for profile-based estimates.[/]"

    age = profile.age_on(day)
    parts = []
    if age is not None:
        parts.append(f"age {age}")
    if profile.sex:
        parts.append(profile.sex)
    if profile.height_cm is not None:
        parts.append(f"{profile.height_cm:g}cm")
    if profile.weight_kg is not None:
        parts.append(f"{profile.weight_kg:g}kg")
    if profile.activity_level:
        parts.append(profile.activity_level)
    label = ", ".join(parts) if parts else "partial profile"
    return f"[dim]Targets: profile-based estimate ({label}).[/]"
