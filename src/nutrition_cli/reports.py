from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from rich.console import Console
from rich.table import Table

from .models import NutrientTarget


TARGETS = {
    "208": NutrientTarget(number="208", label="Calories", unit="kcal", target=2500),
    "203": NutrientTarget(number="203", label="Protein", unit="g", target=120),
    "204": NutrientTarget(number="204", label="Fat", unit="g", target=80),
    "205": NutrientTarget(number="205", label="Carbs", unit="g", target=300),
    "291": NutrientTarget(number="291", label="Fiber", unit="g", target=28),
    "301": NutrientTarget(number="301", label="Calcium", unit="mg", target=1300),
    "307": NutrientTarget(number="307", label="Sodium", unit="mg", target=2300),
    "303": NutrientTarget(number="303", label="Iron", unit="mg", target=8),
    "304": NutrientTarget(number="304", label="Magnesium", unit="mg", target=420),
    "306": NutrientTarget(number="306", label="Potassium", unit="mg", target=4700),
    "309": NutrientTarget(number="309", label="Zinc", unit="mg", target=11),
    "320": NutrientTarget(number="320", label="Vitamin A", unit="ug", target=900),
    "401": NutrientTarget(number="401", label="Vitamin C", unit="mg", target=90),
    "417": NutrientTarget(number="417", label="Folate", unit="ug", target=400),
    "418": NutrientTarget(number="418", label="B12", unit="ug", target=2.4),
    "430": NutrientTarget(number="430", label="Vitamin K", unit="ug", target=120),
}

DISPLAY_ORDER = [
    "208",
    "203",
    "204",
    "205",
    "291",
    "301",
    "307",
    "303",
    "304",
    "306",
    "309",
    "320",
    "401",
    "417",
    "418",
    "430",
]

UPPER_LIMIT_NUMBERS = {"208", "204", "307"}


@dataclass
class Report:
    start_date: date
    end_date: date
    days: int
    totals: dict[str, float]
    units: dict[str, str]
    item_count: int
    unresolved_items: list[str]


def load_report(conn, start: date, end: date) -> Report:
    rows = conn.execute(
        """
        SELECT
          mi.food_alias,
          mi.quantity_g,
          mi.fdc_id,
          fn.nutrient_number,
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
    item_ids = 0
    seen_items = set()
    for row in rows:
        item_key = (row["food_alias"], row["fdc_id"], row["quantity_g"])
        if item_key not in seen_items:
            seen_items.add(item_key)
            item_ids += 1
        if row["fdc_id"] is None or row["quantity_g"] is None:
            unresolved.add(row["food_alias"])
            continue
        if row["nutrient_number"] is None:
            continue
        totals[row["nutrient_number"]] += (row["amount_per_100g"] or 0) * row["quantity_g"] / 100
        units[row["nutrient_number"]] = row["unit"]

    return Report(
        start_date=start,
        end_date=end,
        days=(end - start).days + 1,
        totals=dict(totals),
        units=units,
        item_count=item_ids,
        unresolved_items=sorted(unresolved),
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

    table = Table(show_header=True, header_style="bold")
    table.add_column("Nutrient")
    table.add_column("Amount", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("Status")

    low_labels = []
    high_labels = []
    over_labels = []
    for number in DISPLAY_ORDER:
        target = TARGETS[number]
        amount = report.totals.get(number, 0)
        daily_amount = amount / report.days
        percent = daily_amount / target.target if target.target else 0
        if number in UPPER_LIMIT_NUMBERS:
            if percent >= 1.1:
                status = "[red]high[/]"
                over_labels.append(target.label)
            elif percent >= 0.75:
                status = "[yellow]ok[/]"
            else:
                status = "[green]low[/]"
        else:
            if percent >= 1.1:
                status = "[green]high[/]"
                high_labels.append(target.label)
            elif percent >= 0.75:
                status = "[yellow]ok[/]"
            else:
                status = "[red]low[/]"
                low_labels.append(target.label)
        table.add_row(
            target.label,
            f"{daily_amount:,.1f} {target.unit}/day",
            f"{target.target:g} {target.unit}",
            status,
        )

    console.print(table)

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
