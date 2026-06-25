# AGENTS.md

This repo is a local-first nutrition CLI used with an LLM assistant. The user
describes meals in natural language; the assistant turns that into structured
food logs, uses the CLI to resolve/store/report nutrients, and then explains the
day in plain language.

## Core Contract

- The CLI owns numeric nutrition facts. Numeric amounts must come from USDA
  FoodData Central, local label entries, cached foods, or explicit local DB
  data.
- The assistant owns interpretation. If source data is missing or partial, do
  not stay silent. Say what is missing and give a clearly labeled AI judgment,
  inference, or research-based opinion.
- Never write AI-guessed nutrient numbers into the numeric totals. If the
  assistant estimates something in prose, label it as an estimate.
- Personal runtime data belongs in the local SQLite DB, not in this repo:
  profile, aliases, default portions, cached foods, label-derived products,
  audit history, and meal logs.
- Do not commit databases, secrets, API keys, private food logs, profile data, or
  package-label photos.

## First Checks

When starting work in this repo, prefer:

```bash
uv run nutrition doctor
uv run nutrition profile show
uv run nutrition fdc-status
```

If the profile is missing and the user wants meaningful high/low feedback, ask
for birth date, sex/gender target category, height, weight, and activity level,
then save it with `nutrition profile set`.

## Logging Meals

When the user tells you what they ate:

1. Convert the description into `ParsedMeal` JSON.
2. Prefer item-level `meal_type` when the user describes a whole day:
   `breakfast`, `lunch`, `snack`, or `dinner`.
3. Use explicit grams when available. If quantity is uncertain, preserve that
   uncertainty in prose and use the best reasonable structured quantity for the
   CLI.
4. Reuse local aliases/default portions before asking the user to repeat known
   product details.
5. If the user provides a package label, add it with `nutrition label add` and
   include source/evidence when possible.
6. After logging, run the relevant report:

```bash
uv run nutrition day --date YYYY-MM-DD
uv run nutrition audit log --date YYYY-MM-DD
```

## Report Interpretation

Treat the CLI report table as the required nutrient checklist. It covers the
important nutrients currently tracked by the project:

- energy and macros: calories, protein, total fat, saturated fat, trans fat,
  cholesterol, carbohydrate, sugars, fiber
- fatty acids: linoleic acid / omega-6, ALA omega-3, EPA, DHA, DPA, EPA + DHA,
  monounsaturated fat, polyunsaturated fat
- minerals: calcium, phosphorus, iron, magnesium, potassium, sodium, zinc,
  copper, manganese, selenium
- vitamins and related nutrients: vitamin A, vitamin C, vitamin D, vitamin E,
  vitamin K, B1, B2, B3, B6, folate, B12, pantothenic acid, choline

For every analysis, use this structure:

1. Summarize measured highs/lows from the CLI table.
2. Name important `unknown` or partial-coverage nutrients instead of skipping
   them.
3. For those gaps, take a position in prose using nutrition knowledge and, when
   useful, reputable sources. Mark it as "AI judgment", "inference", or
   "research-based opinion".
4. Separate measured facts from inferred advice.
5. Give practical food suggestions that fit the user's stated preferences.

Example stance:

> Measured: protein is fine and sodium is high. Unknown: detailed omega-3 data is
> missing. AI judgment: based on the foods logged, omega-3 is probably low
> because there was no obvious fish, chia/flax, walnut, or omega-3 supplement
> source. I would add one of those rather than treating the numeric omega-3 row
> as complete.

The exact food reasoning should come from the assistant's intelligence and
research, not from a fixed regex rule in the CLI.

## Missing Data Rule

The CLI may print:

```text
Assistant rule: unknown/partial nutrients exist. When analyzing this report,
name important gaps and give clearly labeled AI judgment or research-based
opinion instead of ignoring them.
```

When this appears, it is mandatory to address the gaps. Do not answer only with
the measured rows.

## Auditability

Use audit commands when explaining or debugging mappings:

```bash
uv run nutrition audit log --date YYYY-MM-DD
uv run nutrition audit resolutions --limit 50
uv run nutrition audit alias-history --alias "food alias"
uv run nutrition audit sources
```

If an alias or product mapping is wrong, correct it in the local DB and explain
that future logs will reuse the corrected mapping.

## Development

Keep changes small and local to the request. Before committing code changes:

```bash
uv run --extra dev pytest
git diff --check
```

For public-repo readiness, scan for personal data and secrets before pushing.
