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
  food preferences, audit history, and meal logs.
- Do not commit databases, secrets, API keys, private food logs, profile data, or
  package-label photos.

## First Checks

When starting work in this repo, prefer:

```bash
uv run nutrition doctor
uv run nutrition profile show
uv run nutrition preference list
uv run nutrition fdc-status
```

If the profile is missing and the user wants meaningful high/low feedback, ask
for birth date, sex/gender target category, height, weight, and activity level,
then save it with `nutrition profile set`.

If preferences are sparse and the user is asking for food suggestions, ask what
they like, dislike, or avoid, then save it with `nutrition preference add`.
Treat preferences with `preference=avoid` and allergy/intolerance context or
notes as hard constraints, not taste preferences.

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
5. If the user names a specific branded/local product, search for product-level
   nutrition evidence before falling back to a generic USDA food. Prefer the
   manufacturer's product page, then retailer product pages, barcode/product
   databases, or package photos from the user.
6. If product-level evidence is found, add it with `nutrition label add` and
   include source/evidence. Use `--source-type web-label` for nutrition tables
   found online, `--source-type product-page` for product pages without a full
   label, and `--source-type local-label` for user-provided package labels.
7. Check preferences before giving suggestions:

```bash
uv run nutrition preference list
```

8. After logging, run the relevant report:

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

The table is evidence, not the final answer. Before giving the user the spoken
report, do a final consistency pass:

- Check whether quantities make sense against the user's wording. If a number
  looks too large or too small, inspect `nutrition audit log` and ask/correct
  rather than blindly trusting it.
- Check whether the chosen food mapping is plausible. A generic USDA food can be
  close enough, but branded foods, package labels, cooked/raw swaps, bones,
  drained weights, and household portions can materially change the result.
- For branded products, check whether `nutrition audit sources` has a product
  page, web label, barcode/database record, or package-photo source. If not,
  do a web/product search when internet access is available and store the result
  locally before reusing it.
- Check coverage. A status with `?`, `unknown`, or low Data coverage is not as
  strong as a fully covered measured value.
- Check outliers. Very high calories, sodium, fat, protein, or surprisingly high
  micronutrients should be explained or sanity-checked.
- If the CLI and common sense disagree, say so. The final answer should reflect
  the assistant's judgment, with the CLI cited as supporting evidence.

For every analysis, use this structure:

1. Summarize measured highs/lows from the CLI table.
2. Name important `unknown` or partial-coverage nutrients instead of skipping
   them.
3. Mention any suspect quantities, mappings, or outliers that may need
   correction.
4. For gaps and suspicious values, take a position in prose using nutrition knowledge and, when
   useful, reputable sources. Mark it as "AI judgment", "inference", or
   "research-based opinion".
5. Separate measured facts from inferred advice.
6. Give practical food suggestions that fit the user's stored and stated
   preferences. Do not suggest disliked or avoided foods unless you explicitly
   call out why there is no better option. Allergy or intolerance avoids are
   stronger: do not suggest them unless the user explicitly overrides that
   constraint.

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

For a specific branded product, preserve provenance:

```bash
uv run nutrition label add "brand product name" \
  --serving-g 30 \
  --calories 94 \
  --protein 7.3 \
  --fat 7.2 \
  --source-type web-label \
  --source-ref "https://example.com/product-page" \
  --alias "user phrase for this product"
```

If sources disagree, prefer the manufacturer label when it clearly matches the
product, mention the discrepancy in prose, and keep the chosen source in
`food_sources`.

## Preferences

Use preferences as durable local memory for recommendations:

```bash
uv run nutrition preference add "cheese" --preference like --intensity 4 --context calcium
uv run nutrition preference add "yogurt" --preference avoid --intensity 5 --notes "User dislikes it"
uv run nutrition preference list
```

Preference values are `love`, `like`, `neutral`, `dislike`, and `avoid`.
Contexts are optional and free-form, for example `calcium`, `omega-3`,
`breakfast`, `snacks`, `allergy`, or `intolerance`.

If an `avoid` preference has allergy/intolerance context or notes, treat it as a
safety constraint. Prefer safe alternatives and ask before recommending related
foods that may carry the same concern.

## Development

Keep changes small and local to the request. Before committing code changes:

```bash
uv run --extra dev pytest
git diff --check
```

For public-repo readiness, scan for personal data and secrets before pushing.
