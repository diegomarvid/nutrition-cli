# nutrition-cli

Tiny local-first nutrition tracker for assistant-assisted food logging: tell an
LLM assistant what you ate, let it turn the meal into structured JSON, save it to
SQLite, resolve foods against USDA FoodData Central, and get blunt daily/weekly
nutrient summaries.

This is intentionally not a big app. The useful core is:

1. Accept structured meal JSON produced by an assistant.
2. Map personal aliases such as `muslo de pollo` to stable FDC foods.
3. Store logs locally in SQLite.
4. Compute nutrients from cached food data, never from the LLM.

## Fresh setup

Prerequisites:

- Python 3.12+
- `uv`

```bash
git clone https://github.com/<owner>/nutrition-cli.git
cd nutrition-cli
uv venv
uv pip install -e ".[dev]"
```

Create the local SQLite database and schema:

```bash
uv run nutrition init
```

This creates `~/.nutrition/nutrition.db` by default and initializes all tables:
`food_aliases`, `meal_logs`, `meal_items`, `foods`, `food_nutrients`, and
`food_portions`, and `user_profiles`. If you run it in an interactive terminal,
it can also prompt for a local profile used to estimate daily targets. Commands
that open the database also run the schema/migration setup, but `nutrition init`
is the explicit first step.

You can set or update the profile later:

```bash
uv run nutrition profile set
uv run nutrition profile show
```

Optionally seed a few generic starter foods and aliases:

```bash
uv run nutrition seed-common
```

Check the install:

```bash
uv run nutrition doctor
```

Override the DB path with:

```bash
export NUTRITION_DB=/absolute/path/nutrition.db
```

## API keys

Food lookup uses USDA FoodData Central. A real key is strongly recommended for
normal use because `DEMO_KEY` is heavily rate-limited.

Manual step:

1. Go to [FoodData Central Get an API Key](https://fdc.nal.usda.gov/api-key-signup).
2. Enter your name and email address.
3. USDA/data.gov emails you a free API key. In practice this is quick and close to instant.
4. Store the key locally outside the repo:

```bash
mkdir -p ~/.nutrition
printf '%s\n' 'your-key-here' > ~/.nutrition/fdc_api_key
chmod 600 ~/.nutrition/fdc_api_key
```

You can also set it in the shell instead:

```bash
export FDC_API_KEY=...
```

Without it, the CLI falls back to `DEMO_KEY`, which is good enough for quick testing but rate-limited.

USDA's documented default for a real API key is 1,000 requests/hour/IP. `DEMO_KEY`
is much tighter and should only be used for a few exploratory requests. Check the
current headers before a batch:

```bash
uv run nutrition fdc-status
```

No OpenAI API key is needed. The assistant is the model: you say what you ate,
the assistant writes JSON and calls the CLI.

There is still a small deterministic Spanish/English parser for quick manual logs like:

```text
comí 500g de muslo de pollo cocido con piel, 1 taza de arroz blanco cocido y una manzana
```

## Usage

```bash
uv run nutrition search "chicken thigh cooked skin"
uv run nutrition log-json '{"raw_text":"comí 500g de muslo de pollo cocido con piel","items":[{"food_alias":"muslo de pollo cocido con piel","fdc_id":173625,"quantity_g":500,"unit":"g","preparation":"cooked, with skin"}]}'
uv run nutrition log "comí 500g de muslo de pollo cocido con piel, 1 taza de arroz blanco cocido y una manzana"
uv run nutrition day
uv run nutrition week
uv run nutrition profile show
uv run nutrition alias list
```

For non-interactive logging, use the first USDA candidate automatically:

```bash
uv run nutrition log --yes "comí 500g de muslo de pollo cocido, 1 taza de arroz blanco cocido y una manzana"
```

## Add personal data

Personal profile fields, aliases, default portions, cached foods, and meal
history live in your local SQLite database, not in the repository.

The profile currently stores birth date, sex/gender target category, height,
weight, and activity level. Reports use it to estimate calorie targets and to
choose age/sex-based nutrient targets where applicable:

```bash
uv run nutrition profile set \
  --birth-date 1990-01-31 \
  --sex male \
  --height-cm 180 \
  --weight-kg 78 \
  --activity light
```

Map an alias to a USDA/FDC food:

```bash
uv run nutrition search "white rice cooked"
uv run nutrition food 2708408
uv run nutrition alias add "my rice serving" 2708408 --default-quantity-g 390
```

Add a packaged product from its nutrition label:

```bash
uv run nutrition label add "my canned corn" \
  --serving-g 130 \
  --calories 107 \
  --carbs 17 \
  --protein 2.2 \
  --fat 2.5 \
  --fiber 3.8 \
  --sodium 179 \
  --default-quantity-g 285 \
  --alias "my corn can"
```

## Useful env vars

- `NUTRITION_DB`: SQLite path. Default: `~/.nutrition/nutrition.db`
- `FDC_API_KEY` or `NUTRITION_FDC_API_KEY`: USDA FoodData Central API key
- `NUTRITION_FDC_API_KEY_FILE`: API key file. Default: `~/.nutrition/fdc_api_key`

## Notes

The CLI estimates grams for household units using USDA food portions when available. If USDA does not provide a matching portion, it falls back to conservative defaults such as `1 cup = 240g`, `1 egg = 50g`, and `1 apple = 182g`. These estimates are marked in item notes when relevant.

## Repository hygiene

The repo is intended to be safe to make public. Do not commit personal runtime
state:

- `~/.nutrition/nutrition.db`: local meal history, aliases, cached foods
- local profile fields stored inside that database
- `~/.nutrition/fdc_api_key`: local FoodData Central API key
- `.env`
- any `*.db`, `*.sqlite`, or `*.sqlite3` file
