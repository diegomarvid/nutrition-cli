from __future__ import annotations

import sys
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from .config import default_db_path, fdc_api_key
from .database import (
    commit_meal,
    connect,
    cached_food,
    delete_alias,
    delete_user_profile,
    food_description,
    get_alias,
    get_user_profile,
    init_db,
    list_aliases,
    upsert_user_profile,
    upsert_alias,
    upsert_food_detail,
)
from .fdc_client import FdcClient, FdcError, FdcRateLimitError, RateLimitInfo, ensure_food_cached
from .parser import parse_meal
from .reports import DISPLAY_ORDER, build_targets, load_report, render_report, target_context, week_window
from .seed_data import seed_common_foods, seed_food
from .units import estimate_grams, normalize_unit
from .models import ParsedMeal, UserProfile


app = typer.Typer(help="Local-first nutrition logger.")
alias_app = typer.Typer(help="Manage personal food aliases.")
label_app = typer.Typer(help="Manage local label-based foods.")
profile_app = typer.Typer(help="Manage the local user profile used for target estimates.")
app.add_typer(alias_app, name="alias")
app.add_typer(label_app, name="label")
app.add_typer(profile_app, name="profile")
console = Console()


def db_option() -> Path:
    return default_db_path()


def open_db(path: Path):
    conn = connect(path)
    init_db(conn)
    return conn


def parse_date(value: str | None) -> date:
    if value is None:
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


@app.command()
def init(
    db: Path = typer.Option(default_factory=db_option, help="SQLite database path."),
    setup_profile: bool = typer.Option(
        True,
        "--profile/--no-profile",
        help="Prompt for local profile setup when running interactively.",
    ),
) -> None:
    """Create the local SQLite database."""
    conn = open_db(db)
    if setup_profile and sys.stdin.isatty() and get_user_profile(conn) is None:
        if typer.confirm("Set local profile for nutrition target estimates now?", default=True):
            prompt_and_save_profile(conn, existing=None)
    conn.close()
    console.print(f"Initialized [bold]{db}[/]")


@app.command()
def doctor(
    db: Path = typer.Option(default_factory=db_option, help="SQLite database path."),
) -> None:
    """Show local configuration and API-key status."""
    conn = open_db(db)
    aliases = len(list_aliases(conn))
    profile = get_user_profile(conn)
    conn.close()
    api_key = fdc_api_key()
    table = Table(show_header=False)
    table.add_column("Key")
    table.add_column("Value")
    table.add_row("DB", str(db))
    table.add_row("Aliases", str(aliases))
    table.add_row("Profile", "configured" if profile else "missing (run `nutrition profile set`)")
    table.add_row("FDC key", "DEMO_KEY (testing)" if api_key == "DEMO_KEY" else "configured")
    table.add_row("Model", "assistant in chat; no OpenAI key inside CLI")
    console.print(table)


@app.command("seed-common")
def seed_common(
    db: Path = typer.Option(default_factory=db_option, help="SQLite database path."),
) -> None:
    """Seed a tiny local cache for common foods used in early testing."""
    conn = open_db(db)
    count = seed_common_foods(conn)
    console.print(f"Seeded {count} common foods into [bold]{db}[/].")


@app.command()
def search(
    query: str = typer.Argument(..., help="Food search query."),
    limit: int = typer.Option(8, min=1, max=20),
) -> None:
    """Search USDA FoodData Central."""
    client = FdcClient()
    try:
        candidates = client.search(query, limit=limit)
    except FdcRateLimitError as exc:
        console.print(format_rate_limit(exc.rate_limit))
        raise typer.Exit(1) from exc
    except FdcError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc
    render_candidates(candidates)


@app.command("fdc-status")
def fdc_status() -> None:
    """Make one tiny FDC request and show current rate-limit headers."""
    client = FdcClient()
    try:
        _, rate_limit = client.status_probe()
    except FdcRateLimitError as exc:
        console.print(format_rate_limit(exc.rate_limit))
        raise typer.Exit(1) from exc
    except FdcError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc
    console.print(format_rate_limit(rate_limit, ok=True))


@app.command()
def food(
    fdc_id: int,
    db: Path = typer.Option(default_factory=db_option, help="SQLite database path."),
) -> None:
    """Fetch and cache one FDC food by id."""
    conn = open_db(db)
    client = FdcClient()
    try:
        payload = ensure_food_cached(conn, client, fdc_id)
    except FdcRateLimitError as exc:
        console.print(format_rate_limit(exc.rate_limit))
        raise typer.Exit(1) from exc
    except FdcError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc
    console.print(f"Cached [bold]{payload.get('description', fdc_id)}[/] ({fdc_id})")


@app.command()
def log(
    text: str = typer.Argument(..., help="Natural language meal text."),
    day: str | None = typer.Option(None, "--date", help="Log date, YYYY-MM-DD. Defaults to today."),
    db: Path = typer.Option(default_factory=db_option, help="SQLite database path."),
    resolve: bool = typer.Option(True, help="Resolve unknown aliases against USDA."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Use the first USDA candidate without prompting."),
) -> None:
    """Log a meal from free text with the small built-in rules parser."""
    conn = open_db(db)
    log_date = parse_date(day)
    meal = parse_meal(text, forced_date=log_date)
    save_meal(conn, meal, log_date, resolve=resolve, yes=yes)


@app.command("log-json")
def log_json(
    payload: str | None = typer.Argument(None, help="ParsedMeal JSON, or omit to read stdin."),
    file: Path | None = typer.Option(None, "--file", "-f", help="Read ParsedMeal JSON from a file."),
    day: str | None = typer.Option(None, "--date", help="Override log date, YYYY-MM-DD."),
    db: Path = typer.Option(default_factory=db_option, help="SQLite database path."),
    resolve: bool = typer.Option(True, help="Resolve unknown aliases against USDA."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Use the first USDA candidate without prompting."),
) -> None:
    """Log a meal from structured JSON produced by an assistant."""
    conn = open_db(db)
    raw_payload = read_json_payload(payload, file)
    data = json.loads(raw_payload)
    if isinstance(data, list):
        data = {"raw_text": "", "items": data}
    data.setdefault("raw_text", "")
    if day is not None:
        data["date"] = parse_date(day).isoformat()
    meal = ParsedMeal.model_validate(data)
    log_date = parse_date(day) if day is not None else meal.date or date.today()
    save_meal(conn, meal, log_date, resolve=resolve, yes=yes)


def save_meal(conn, meal: ParsedMeal, log_date: date, resolve: bool, yes: bool) -> None:
    if meal.needs_clarification:
        for question in meal.needs_clarification:
            console.print(f"[yellow]{question}[/]")
    client = FdcClient()
    resolved = []
    item_notes = []

    for item in meal.items:
        alias = item.food_alias
        alias_row = get_alias(conn, alias)
        fdc_id = item.fdc_id or (int(alias_row["fdc_id"]) if alias_row else None)

        if fdc_id is None and resolve:
            fdc_id = resolve_alias(conn, client, item.food_alias, yes=yes)

        if fdc_id is not None:
            ensure_cached_quietly(conn, client, fdc_id)
            if alias_row is None:
                upsert_alias(conn, alias, fdc_id, notes=food_description(conn, fdc_id))

        grams, note = estimate_item_grams(conn, item, alias_row, fdc_id)
        if note:
            item_notes.append(f"{item.food_alias}: {note}")
        resolved.append((item, fdc_id, grams))

    meal_log_id = commit_meal(conn, meal, log_date.isoformat(), resolved)
    console.print(f"Guardado para [bold]{log_date.isoformat()}[/] (log #{meal_log_id}).")

    for note in item_notes:
        console.print(f"[yellow]{note}[/]")

    report = load_report(conn, log_date, log_date)
    render_report(report, console)


def estimate_item_grams(conn, item, alias_row, fdc_id: int | None) -> tuple[float | None, str | None]:
    if item.quantity_g is None and alias_row is not None:
        default_quantity_g = alias_row["default_quantity_g"]
        if default_quantity_g is not None:
            unit = normalize_unit(item.unit)
            if item.quantity is None:
                return float(default_quantity_g), f"used alias default quantity: {default_quantity_g:g}g"
            if unit in {None, "unit", "serving", "portion", "porcion", "porción", "can", "lata"}:
                grams = float(default_quantity_g) * item.quantity
                return grams, f"used alias default quantity: {item.quantity:g} x {default_quantity_g:g}g"
    return estimate_grams(conn, item, fdc_id)


def read_json_payload(payload: str | None, file: Path | None) -> str:
    if file is not None:
        return file.read_text()
    if payload is not None:
        return payload
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise typer.BadParameter("Provide JSON as an argument, with --file, or on stdin.")


@app.command()
def day(
    day: str | None = typer.Option(None, "--date", help="Report date, YYYY-MM-DD. Defaults to today."),
    db: Path = typer.Option(default_factory=db_option, help="SQLite database path."),
    brutal: bool = typer.Option(True, help="Print blunt summary."),
) -> None:
    """Show one-day nutrient report."""
    conn = open_db(db)
    target = parse_date(day)
    render_report(load_report(conn, target, target), console, brutal=brutal)


@app.command()
def week(
    ending: str | None = typer.Option(None, "--ending", help="Week ending date, YYYY-MM-DD. Defaults to today."),
    db: Path = typer.Option(default_factory=db_option, help="SQLite database path."),
    brutal: bool = typer.Option(True, help="Print blunt summary."),
) -> None:
    """Show a seven-day nutrient report."""
    conn = open_db(db)
    end = parse_date(ending)
    start, end = week_window(end)
    render_report(load_report(conn, start, end), console, brutal=brutal)


@app.command()
def targets(
    day: str | None = typer.Option(None, "--date", help="Target date, YYYY-MM-DD. Defaults to today."),
    db: Path = typer.Option(default_factory=db_option, help="SQLite database path."),
) -> None:
    """Show the current profile-based nutrient target panel."""
    conn = open_db(db)
    profile = get_user_profile(conn)
    target_date = parse_date(day)
    target_map = build_targets(profile, target_date)
    console.print(target_context(profile, target_date))

    table = Table(show_header=True, header_style="bold")
    table.add_column("Category")
    table.add_column("Nutrient")
    table.add_column("Target", justify="right")
    table.add_column("Note")
    for number in DISPLAY_ORDER:
        target = target_map[number]
        target_value = "no target" if target.target is None else f"{target.target:g} {target.unit}"
        table.add_row(target.category, target.label, target_value, target.note or "")
    console.print(table)


@alias_app.command("add")
def alias_add(
    alias: str,
    fdc_id: int,
    default_unit: str | None = typer.Option(None),
    default_quantity_g: float | None = typer.Option(None, help="Default grams when this alias is logged without quantity."),
    notes: str | None = typer.Option(None),
    db: Path = typer.Option(default_factory=db_option, help="SQLite database path."),
) -> None:
    """Map a personal alias to an FDC food id."""
    conn = open_db(db)
    ensure_cached_quietly(conn, FdcClient(), fdc_id)
    upsert_alias(
        conn,
        alias,
        fdc_id,
        default_unit=default_unit,
        default_quantity_g=default_quantity_g,
        notes=notes,
    )
    console.print(f"Alias [bold]{alias}[/] -> {fdc_id} ({food_description(conn, fdc_id)})")


@alias_app.command("list")
def alias_list(
    db: Path = typer.Option(default_factory=db_option, help="SQLite database path."),
) -> None:
    """List aliases."""
    conn = open_db(db)
    rows = list_aliases(conn)
    table = Table()
    table.add_column("Alias")
    table.add_column("FDC ID")
    table.add_column("Default g", justify="right")
    table.add_column("Food")
    table.add_column("Notes")
    for row in rows:
        default_g = "" if row["default_quantity_g"] is None else f"{row['default_quantity_g']:g}"
        table.add_row(
            row["alias"],
            str(row["fdc_id"]),
            default_g,
            food_description(conn, row["fdc_id"]),
            row["notes"] or "",
        )
    console.print(table)


@alias_app.command("remove")
def alias_remove(
    alias: str,
    db: Path = typer.Option(default_factory=db_option, help="SQLite database path."),
) -> None:
    """Remove an alias."""
    conn = open_db(db)
    count = delete_alias(conn, alias)
    console.print("Removed." if count else "Alias not found.")


@label_app.command("add")
def label_add(
    name: str = typer.Argument(..., help="Food/product name."),
    serving_g: float = typer.Option(..., help="Serving size in grams from the label."),
    calories: float | None = typer.Option(None, help="Calories per serving."),
    protein: float | None = typer.Option(None, help="Protein grams per serving."),
    fat: float | None = typer.Option(None, help="Fat grams per serving."),
    carbs: float | None = typer.Option(None, help="Carbohydrate grams per serving."),
    fiber: float | None = typer.Option(None, help="Fiber grams per serving."),
    sodium: float | None = typer.Option(None, help="Sodium milligrams per serving."),
    default_quantity_g: float | None = typer.Option(None, help="Default grams when logged without quantity."),
    alias: list[str] = typer.Option([], "--alias", "-a", help="Alias to create. Can be repeated."),
    db: Path = typer.Option(default_factory=db_option, help="SQLite database path."),
) -> None:
    """Add a local food from package label values."""
    conn = open_db(db)
    fdc_id = next_local_food_id(conn)
    payload = label_food_payload(
        fdc_id=fdc_id,
        name=name,
        serving_g=serving_g,
        calories=calories,
        protein=protein,
        fat=fat,
        carbs=carbs,
        fiber=fiber,
        sodium=sodium,
        default_quantity_g=default_quantity_g,
    )
    upsert_food_detail(conn, payload)
    aliases = [name, *alias]
    for alias_name in aliases:
        upsert_alias(
            conn,
            alias_name,
            fdc_id,
            default_quantity_g=default_quantity_g,
            notes=f"Local label: {name}",
        )
    console.print(f"Added local label food [bold]{name}[/] as {fdc_id}.")


def next_local_food_id(conn) -> int:
    row = conn.execute("SELECT MAX(fdc_id) AS max_id FROM foods WHERE fdc_id >= 9000000").fetchone()
    max_id = row["max_id"] if row and row["max_id"] is not None else 8999999
    return int(max_id) + 1


def label_food_payload(
    *,
    fdc_id: int,
    name: str,
    serving_g: float,
    calories: float | None,
    protein: float | None,
    fat: float | None,
    carbs: float | None,
    fiber: float | None,
    sodium: float | None,
    default_quantity_g: float | None,
) -> dict:
    nutrients = []
    for number, nutrient_id, nutrient_name, unit, value in [
        ("208", 1008, "Energy", "kcal", calories),
        ("203", 1003, "Protein", "g", protein),
        ("204", 1004, "Total lipid (fat)", "g", fat),
        ("205", 1005, "Carbohydrate, by difference", "g", carbs),
        ("291", 1079, "Fiber, total dietary", "g", fiber),
        ("307", 1093, "Sodium, Na", "mg", sodium),
    ]:
        if value is None:
            continue
        nutrients.append(
            {
                "nutrient": {
                    "number": number,
                    "id": nutrient_id,
                    "name": nutrient_name,
                    "unitName": unit,
                },
                "amount": value / serving_g * 100,
            }
        )

    portions = []
    if default_quantity_g is not None:
        portions.append(
            {
                "amount": 1.0,
                "gramWeight": default_quantity_g,
                "measureUnit": {"name": "serving"},
                "modifier": "default serving",
            }
        )

    return {
        "fdcId": fdc_id,
        "description": name,
        "dataType": "Local Label",
        "servingSize": serving_g,
        "servingSizeUnit": "g",
        "foodNutrients": nutrients,
        "foodPortions": portions,
    }


@profile_app.command("set")
def profile_set(
    birth_date: str | None = typer.Option(None, help="Birth date, YYYY-MM-DD."),
    sex: str | None = typer.Option(None, help="male, female, or other. Spanish aliases also work."),
    height_cm: float | None = typer.Option(None, help="Height in centimeters."),
    weight_kg: float | None = typer.Option(None, help="Weight in kilograms."),
    activity: str | None = typer.Option(
        None,
        "--activity",
        "--activity-level",
        help="sedentary, light, moderate, active, or very-active.",
    ),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Prompt for missing fields in a TTY."),
    db: Path = typer.Option(default_factory=db_option, help="SQLite database path."),
) -> None:
    """Create or update the local profile used for target estimates."""
    conn = open_db(db)
    existing = get_user_profile(conn)
    provided_any = any(
        value is not None
        for value in [birth_date, sex, height_cm, weight_kg, activity]
    )
    prompt = interactive and sys.stdin.isatty() and not provided_any
    if not prompt and not provided_any and existing is None:
        console.print("[yellow]No profile values provided. Run interactively or pass profile options.[/]")
        raise typer.Exit(1)
    profile = collect_profile(
        existing=existing,
        birth_date=birth_date,
        sex=sex,
        height_cm=height_cm,
        weight_kg=weight_kg,
        activity_level=activity,
        prompt=prompt,
    )
    upsert_user_profile(conn, profile)
    render_profile(profile)


@profile_app.command("show")
def profile_show(
    db: Path = typer.Option(default_factory=db_option, help="SQLite database path."),
) -> None:
    """Show the local profile."""
    conn = open_db(db)
    profile = get_user_profile(conn)
    if profile is None:
        console.print("[yellow]No profile configured. Run `nutrition profile set`.[/]")
        return
    render_profile(profile)


@profile_app.command("clear")
def profile_clear(
    db: Path = typer.Option(default_factory=db_option, help="SQLite database path."),
) -> None:
    """Delete the local profile."""
    conn = open_db(db)
    removed = delete_user_profile(conn)
    console.print("Profile deleted." if removed else "No profile configured.")


def prompt_and_save_profile(conn, existing: UserProfile | None) -> UserProfile:
    profile = collect_profile(
        existing=existing,
        birth_date=None,
        sex=None,
        height_cm=None,
        weight_kg=None,
        activity_level=None,
        prompt=True,
    )
    upsert_user_profile(conn, profile)
    render_profile(profile)
    return profile


def collect_profile(
    *,
    existing: UserProfile | None,
    birth_date: str | None,
    sex: str | None,
    height_cm: float | str | None,
    weight_kg: float | str | None,
    activity_level: str | None,
    prompt: bool,
) -> UserProfile:
    data = {
        "birth_date": existing.birth_date.isoformat() if existing and existing.birth_date else None,
        "sex": existing.sex if existing else None,
        "height_cm": existing.height_cm if existing else None,
        "weight_kg": existing.weight_kg if existing else None,
        "activity_level": existing.activity_level if existing else None,
    }
    updates = {
        "birth_date": birth_date,
        "sex": sex,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "activity_level": activity_level,
    }
    for key, value in updates.items():
        if value is not None:
            data[key] = value

    if prompt:
        data["birth_date"] = prompt_optional("Birth date (YYYY-MM-DD)", data["birth_date"])
        data["sex"] = prompt_optional("Sex/gender for nutrient targets (male/female/other)", data["sex"])
        data["height_cm"] = prompt_optional("Height in cm", format_optional_number(data["height_cm"]))
        data["weight_kg"] = prompt_optional("Weight in kg", format_optional_number(data["weight_kg"]))
        data["activity_level"] = prompt_optional(
            "Activity (sedentary/light/moderate/active/very-active)",
            data["activity_level"] or "light",
        )

    try:
        return UserProfile.model_validate(data)
    except ValidationError as exc:
        console.print(f"[red]Invalid profile:[/] {exc}")
        raise typer.Exit(1) from exc


def prompt_optional(label: str, default: str | None) -> str | None:
    default = default or ""
    value = typer.prompt(label, default=default, show_default=bool(default))
    value = value.strip()
    return value or None


def format_optional_number(value: float | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return f"{value:g}"


def render_profile(profile: UserProfile) -> None:
    table = Table(show_header=False)
    table.add_column("Field")
    table.add_column("Value")
    age = profile.age_on(date.today())
    table.add_row("Birth date", profile.birth_date.isoformat() if profile.birth_date else "")
    table.add_row("Age", "" if age is None else str(age))
    table.add_row("Sex/gender target category", profile.sex or "")
    table.add_row("Height", "" if profile.height_cm is None else f"{profile.height_cm:g} cm")
    table.add_row("Weight", "" if profile.weight_kg is None else f"{profile.weight_kg:g} kg")
    table.add_row("Activity", profile.activity_level or "")
    console.print(table)


def resolve_alias(conn, client: FdcClient, alias: str, yes: bool) -> int | None:
    try:
        candidates = client.search(alias, limit=6)
    except FdcRateLimitError as exc:
        console.print(format_rate_limit(exc.rate_limit))
        return None
    except FdcError as exc:
        console.print(f"[yellow]Could not resolve {alias}: {exc}[/]")
        return None
    if not candidates:
        console.print(f"[yellow]No USDA candidates for {alias}[/]")
        return None
    if yes:
        chosen = candidates[0]
        upsert_alias(conn, alias, chosen.fdc_id, notes=chosen.description)
        return chosen.fdc_id
    if not sys.stdin.isatty():
        console.print(f"[yellow]Unresolved {alias}; rerun in a TTY or use --yes.[/]")
        return None

    console.print(f"[bold]Choose food for:[/] {alias}")
    render_candidates(candidates, numbered=True)
    choice = typer.prompt("Candidate number, or 0 to skip", default="1")
    try:
        index = int(choice)
    except ValueError:
        return None
    if index <= 0 or index > len(candidates):
        return None
    chosen = candidates[index - 1]
    upsert_alias(conn, alias, chosen.fdc_id, notes=chosen.description)
    return chosen.fdc_id


def render_candidates(candidates, numbered: bool = False) -> None:
    table = Table()
    if numbered:
        table.add_column("#", justify="right")
    table.add_column("FDC ID", justify="right")
    table.add_column("Type")
    table.add_column("Description")
    table.add_column("Brand")
    for index, food_candidate in enumerate(candidates, start=1):
        row = [
            str(food_candidate.fdc_id),
            food_candidate.data_type or "",
            food_candidate.description,
            food_candidate.brand_owner or "",
        ]
        if numbered:
            row.insert(0, str(index))
        table.add_row(*row)
    console.print(table)


def ensure_cached_quietly(conn, client: FdcClient, fdc_id: int) -> None:
    if cached_food(conn, fdc_id) is not None:
        return
    try:
        payload = client.detail(fdc_id)
    except FdcError as exc:
        if seed_food(conn, fdc_id):
            console.print(f"[yellow]USDA unavailable for {fdc_id}; used local seed data.[/]")
            return
        if isinstance(exc, FdcRateLimitError):
            console.print(format_rate_limit(exc.rate_limit))
            return
        console.print(f"[yellow]Could not fetch FDC {fdc_id}: {exc}[/]")
        return
    upsert_food_detail(conn, payload)


def format_rate_limit(rate_limit: RateLimitInfo, ok: bool = False) -> str:
    parts = []
    if ok:
        parts.append("[green]FDC API reachable.[/]")
    else:
        parts.append("[red]FDC API rate-limited.[/]")
    if rate_limit.limit is not None:
        parts.append(f"limit={rate_limit.limit}")
    if rate_limit.remaining is not None:
        parts.append(f"remaining={rate_limit.remaining}")
    if rate_limit.retry_after_seconds is not None:
        retry_at = datetime.now() + timedelta(seconds=rate_limit.retry_after_seconds)
        hours = rate_limit.retry_after_seconds / 3600
        parts.append(f"retry_after={rate_limit.retry_after_seconds}s (~{hours:.1f}h, {retry_at:%Y-%m-%d %H:%M})")
    return " ".join(parts)
