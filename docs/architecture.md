# Architecture

```text
chat with an assistant
        |
        v
assistant writes structured meal JSON
        |
        v
CLI validates ParsedMeal JSON
        |
        v
food resolver -> food_aliases + USDA candidates
        |
        v
SQLite meal_logs + meal_items + audit tables
        |
        v
cached food_nutrients + user_profiles + reports
```

## Data boundaries

The assistant may infer structure and quantities from the user's message. It must
not invent numeric nutrient values. When nutrient data is missing or partial, the
assistant should still take a clearly labeled position using nutrition knowledge
or research; that judgment belongs in prose, not in numeric totals.

Nutrient amounts come from cached FoodData Central detail responses or from local rows manually inserted by the user.
Packaged-product labels should be added to the local SQLite database with
`nutrition label add`; user-specific products should not be committed to the
repository seed data.

Profile fields such as birth date, sex/gender target category, height, weight,
and activity level are also local runtime data. They belong in `user_profiles`
inside the user's SQLite database, not in source code or public seed data.

## Target model

FoodData Central provides food composition, not personal daily targets. Daily
targets come from public DRI/RDA/AI-style references and profile-based
estimates.

- Age and sex/gender target category select reference values for micronutrients.
- Height, weight, age, sex/gender target category, and activity estimate
  calories with Mifflin-St Jeor plus an activity factor.
- Weight estimates baseline protein at `0.8 g/kg/day`.
- Fat and carbohydrate targets are derived from estimated calories as pragmatic
  reporting anchors.
- ALA omega-3 uses age/sex adequate-intake targets. EPA, DHA, DPA, MUFA, and
  PUFA are tracked when source data contains them; EPA/DHA do not receive an
  official DRI target.

The status labels are a display heuristic: less than 75% of target is `low`,
75% to 110% is `ok`, and more than 110% is `high`. Sodium, saturated fat, and
trans fat are limit-style values. Calories and total fat are target-style values,
but `high` is still shown as a warning.

Every target nutrient also carries coverage. Coverage answers: "for how much of
the logged food did the source data contain this nutrient?" A low value with
partial coverage is not treated as equally certain as a low value with full
coverage.

Missing values are not imputed into numeric totals. The safe hierarchy is:

1. Use complete USDA generic foods for nutrient-rich analysis.
2. Use branded foods and labels for product identity and label nutrients.
3. Add package-label foods locally when the user has the label.
4. Add optional product/barcode sources, such as Open Food Facts, only as another
   source with explicit coverage and provenance.
5. Require the assistant to address every important unknown/partial nutrient in
   prose. It should use its own nutrition judgment and look up reputable sources
   when useful, but it must label this as inference or research-based opinion and
   keep numeric rows source-based.

## API rate limits

Use a personal FoodData Central API key for real use. The public `DEMO_KEY` is
only for tiny exploration and can block quickly. The CLI exposes
`nutrition fdc-status`, which performs one small request and prints the
`X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `Retry-After` headers when
available.

The operational rule is: resolve/cache an ingredient once, then reuse aliases
and default quantities locally. Daily logging should mostly hit SQLite, not
USDA.

## Database

- `food_aliases`: personal alias to FDC food
- `meal_logs`: raw text + parsed JSON + optional top-level meal type
- `meal_items`: structured items from each log, including item-level meal type and chosen FDC/local id
- `foods`: cached FDC food metadata
- `food_nutrients`: cached nutrient values per 100g
- `food_portions`: cached household measures used to convert cups, pieces, etc. to grams
- `user_profiles`: local profile used to estimate daily target ranges
- `food_resolution_events`: records how an alias was resolved, including USDA candidates when available
- `alias_history`: records alias mapping/default-quantity changes
- `food_sources`: records local source/evidence rows, such as label photo paths or URLs

Audit tables are append-only for new decisions. Existing databases migrated from
older versions can still audit logged items through `meal_items` and `foods`,
but past resolution decisions are not reconstructed automatically.

Personal runtime state belongs outside the repo, usually in
`~/.nutrition/nutrition.db`.
