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
`food_portions`, `user_profiles`, `food_preferences`, and audit tables for
aliases, sources, and resolution events. If you run it in an interactive
terminal, it can also prompt for a local profile used to estimate daily targets.
Commands that open the database also run the schema/migration setup, but
`nutrition init` is the explicit first step.

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

## Assistant workflow

Agent-specific operating rules live in [`AGENTS.md`](AGENTS.md). In particular,
that file defines how assistants should handle `unknown` and partial-coverage
nutrients: do not invent numeric totals, but do not ignore important gaps. It
also requires a final sanity check of quantities, food mappings, coverage, and
outliers before turning the CLI table into a spoken report.

The intended flow is:

1. The user describes food in natural language.
2. The assistant turns that into structured meal JSON.
3. The CLI stores the log locally, resolves foods through aliases, local labels,
   or USDA FoodData Central, and computes source-based nutrient totals.
4. The assistant reads the profile, preferences, daily report, and audit trail
   as evidence.
5. The assistant does a final judgment pass before answering: quantities,
   cooked/raw state, bones, drained weights, duplicate items, food mappings,
   missing nutrients, partial coverage, and outliers should all make sense.
6. The final summary separates measured facts from uncertainty and AI judgment,
   then gives practical recommendations that fit the user's preferences.

The CLI is deliberately not the final narrator. It gives the assistant a
structured evidence packet; the assistant is responsible for noticing when the
evidence is incomplete, suspicious, or inconsistent with the user's description.

When using this repo with an LLM assistant, the assistant should start by checking:

```bash
uv run nutrition doctor
uv run nutrition profile show
uv run nutrition preference list
```

If the profile is missing, ask the user for:

- birth date
- sex/gender target category used for nutrient estimates
- height
- weight
- activity level

Then save those values locally:

```bash
uv run nutrition profile set \
  --birth-date YYYY-MM-DD \
  --sex male \
  --height-cm 180 \
  --weight-kg 78 \
  --activity light \
  --no-interactive
```

The profile is required for better "high/low" feedback. It is still local
runtime data and must not be committed.

Before giving food suggestions, the assistant should check local food
preferences:

```bash
uv run nutrition preference list
uv run nutrition preference add "cheese" --preference like --intensity 4 --context calcium
uv run nutrition preference add "yogurt" --preference avoid --intensity 5 --notes "User dislikes it"
```

Preferences are local runtime data. They can store foods the user likes,
dislikes, avoids, or especially prefers in a context such as `calcium`,
`breakfast`, `snacks`, `omega-3`, `allergy`, or `intolerance`. Avoid
preferences with allergy/intolerance context or notes should be treated as hard
recommendation constraints by assistants.

Recommendation criteria should be preference-aware:

- Prefer foods the user likes or has accepted before.
- Avoid foods marked `dislike` unless there is a clear reason to mention them.
- Never recommend `avoid` foods with allergy/intolerance context unless the user
  explicitly overrides that constraint.
- If a likely recommendation conflicts with preferences, say so and offer a
  safer alternative.

## Where the numbers come from

The CLI keeps food facts and daily targets separate.

Food nutrient values come from:

- [USDA FoodData Central](https://fdc.nal.usda.gov/) detail responses, cached in
  SQLite per food.
- Local package labels added by the user with `nutrition label add`.

The LLM assistant can help structure what the user ate, but it should not invent
numeric nutrient values. Reports multiply cached nutrient values per 100 g by
the logged quantity in grams; interpretation of missing data belongs in the
assistant's answer, clearly labeled as judgment or inference.

Daily target values come from public nutrition reference guidance, not from
FoodData Central. The code uses Dietary Reference Intake-style references from
the Food and Nutrition Board / National Academies, surfaced by NIH Office of
Dietary Supplements resources such as:

- [NIH ODS nutrient recommendations](https://ods.od.nih.gov/HealthInformation/nutrientrecommendations.aspx)
- [NIH ODS calcium fact sheet](https://ods.od.nih.gov/factsheets/Calcium-HealthProfessional/)
- [NIH ODS vitamin K fact sheet](https://ods.od.nih.gov/factsheets/VitaminK-Consumer/)
- [NIH ODS omega-3 fact sheet](https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/)

The local profile is used as follows:

- Birth date and sex/gender target category choose age/sex-specific targets for
  nutrients such as calcium, iron, magnesium, potassium, zinc, vitamin A,
  vitamin C, and vitamin K.
- Height, weight, age, sex/gender target category, and activity level estimate
  daily calories using the
  [Mifflin-St Jeor equation](https://www.ncbi.nlm.nih.gov/books/NBK278991/table/diet-treatment-obes.table12est/)
  plus an activity factor.
- Weight estimates a baseline protein target using `0.8 g/kg/day`. This is a
  general adequacy floor, not an athletic or muscle-gain target.
- Fat and carbohydrate targets are rough defaults derived from the estimated
  calorie target. They are practical reporting anchors, not a personalized diet
  prescription.
- Alpha-linolenic acid (ALA) uses age/sex adequate-intake targets. EPA and DHA
  are tracked when source data contains them, but the report does not present an
  official DRI target for them because public recommendations are established
  for ALA, not EPA/DHA.

The "low / ok / high" labels are intentionally simple:

- Less than 75% of the daily target is `low`.
- 75% to 110% is `ok`.
- More than 110% is `high`.
- Sodium, saturated fat, and trans fat are treated as limit-style values. Calories
  and total fat are target-style values, but `high` is still shown as something
  to watch rather than a win.

These targets are useful for habit feedback and gap spotting. They are not a
medical diagnosis, and individual needs can differ from reference values.

The report also shows a `Data` column. This is coverage: how much of the logged
food quantity had a known value for that nutrient. For example, `100%` means
every resolved item had data for that nutrient. `25% (1/2)` means only 25% of
the logged grams, across 1 of 2 resolved items, had that nutrient available. A
status with `?`, such as `low?`, should be read as "possibly low, but the source
data is incomplete", not as a definitive deficiency.

The CLI report is an evidence packet for the assistant, not the final user-facing
analysis. Assistants should sanity-check quantities, mappings, coverage, and
outliers before summarizing; if the table looks inconsistent with the user's
description, correct or flag it rather than repeating it blindly.

A good daily summary should usually cover:

- what was clearly high, low, or on target according to the measured report
- important nutrients that are `unknown` or only partially covered
- any suspicious input that may change the conclusion, such as a raw/cooked
  mismatch or a duplicated portion
- practical next-meal or next-day suggestions shaped by the stored profile,
  targets, allergies/intolerances, and food preferences

Numeric totals should stay tied to the CLI's sources. When the assistant adds
nutrition knowledge beyond the table, it should label that part as judgment,
inference, or research-based opinion.

Current strategy for missing nutrient data:

- Prefer generic USDA Foundation, SR Legacy, or FNDDS foods when micronutrient
  completeness matters.
- Use USDA Branded Foods and package labels for packaged products, but expect
  them to be label-like and often incomplete for micronutrients.
- Use `nutrition label add` for local products when the package label is the
  best source.
- Consider barcode/product sources such as
  [Open Food Facts](https://openfoodfacts.github.io/openfoodfacts-server/api/)
  as a future fallback for packaged foods, especially outside the U.S. These
  databases can be useful, but they are also community/product-label driven, so
  the CLI should still mark coverage instead of pretending every nutrient is
  known.
- Do not silently impute missing micronutrients into numeric totals. Numeric
  report rows stay source-based.
- If any nutrient is unknown or has partial coverage, the assistant must not stay
  silent. It should say what is missing, decide whether the user's foods make
  that nutrient likely low/high/uncertain, and label that as AI judgment or
  research-based opinion rather than as a measured value.
- The assistant should use broad nutrition knowledge and, when useful, look up
  reputable sources for the food or nutrient. For example: if omega-3 data is
  missing but the logged foods are chicken, rice, and processed meat, it can say
  omega-3 is probably low and suggest fish, chia/flax, walnuts, or similar
  sources. That conclusion should not be written back as a numeric nutrient
  total unless source data is added.

## Usage

```bash
uv run nutrition search "chicken thigh cooked skin"
uv run nutrition log-json '{"raw_text":"comí 500g de muslo de pollo cocido con piel","items":[{"food_alias":"muslo de pollo cocido con piel","fdc_id":173625,"quantity_g":500,"unit":"g","preparation":"cooked, with skin"}]}'
uv run nutrition log "comí 500g de muslo de pollo cocido con piel, 1 taza de arroz blanco cocido y una manzana"
uv run nutrition day
uv run nutrition week
uv run nutrition targets
uv run nutrition audit log --date 2026-06-24
uv run nutrition audit resolutions
uv run nutrition profile show
uv run nutrition preference list
uv run nutrition alias list
```

For non-interactive logging, use the first USDA candidate automatically:

```bash
uv run nutrition log --yes "comí 500g de muslo de pollo cocido, 1 taza de arroz blanco cocido y una manzana"
```

## Add personal data

Personal profile fields, aliases, preferences, default portions, cached foods,
and meal history live in your local SQLite database, not in the repository.

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

Store food preferences for future recommendations:

```bash
uv run nutrition preference add "cheese" --preference like --intensity 4 --context calcium
uv run nutrition preference add "milk" --preference avoid --intensity 5
uv run nutrition preference add "example allergen" --preference avoid --intensity 5 --context allergy
uv run nutrition preference list
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
  --source-ref /absolute/path/to/label-photo.jpg \
  --alias "my corn can"
```

Local labels can also store detailed fats when available:

```bash
uv run nutrition label add "omega 3 supplement" \
  --serving-g 1 \
  --fat 1 \
  --epa 0.18 \
  --dha 0.12 \
  --default-quantity-g 1
```

## Audit trail

The local database stores enough detail to review how a meal became nutrients:

- `meal_logs` stores the date, raw text, parsed JSON, confidence, and optional
  top-level meal type.
- `meal_items` stores each structured item, optional item-level meal type
  (`breakfast`, `lunch`, `snack`, `dinner`), quantity, grams, preparation,
  chosen FDC/local food id, and original item JSON.
- `food_aliases` stores reusable personal mappings from phrases to FDC/local
  food ids.
- `food_preferences` stores local likes, dislikes, avoidances, hard allergy or
  intolerance constraints, and contextual recommendation notes for assistants.
- `alias_history` records alias mapping/default-quantity changes.
- `food_resolution_events` records USDA/manual/local-label resolution events,
  including candidate JSON when USDA search was used.
- `foods.raw_json` stores the raw USDA/local food payload used for nutrients.
- `food_sources` stores explicit source/evidence records for local labels, such
  as a package-photo path or source URL.

Useful audit commands:

```bash
uv run nutrition audit log --date 2026-06-24
uv run nutrition audit log --ending 2026-06-24
uv run nutrition audit resolutions --limit 50
uv run nutrition audit alias-history --alias "my corn can"
uv run nutrition audit sources
```

Audit tables start recording from the point this version is used. Older local
databases can still show past logged items because `meal_logs`, `meal_items`,
`foods`, and `food_nutrients` already existed, but they will not have historical
resolution events or alias-history rows for decisions made before the audit
tables existed.

When logging through an assistant, prefer item-level `meal_type` in the JSON if
the user describes a whole day:

```json
{
  "raw_text": "lunch chicken and rice; snack apple",
  "items": [
    {"food_alias": "chicken thigh cooked with skin", "meal_type": "lunch", "quantity_g": 250},
    {"food_alias": "white rice cooked", "meal_type": "lunch", "quantity_g": 200},
    {"food_alias": "apple", "meal_type": "snack", "quantity": 1, "unit": "unit"}
  ]
}
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
