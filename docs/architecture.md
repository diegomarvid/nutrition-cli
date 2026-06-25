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
SQLite meal_logs + meal_items
        |
        v
cached food_nutrients + user_profiles + reports
```

## Data boundaries

The assistant may infer structure and quantities from the user's message. It must not invent nutrient values.

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

The status labels are a display heuristic: less than 75% of target is `low`,
75% to 110% is `ok`, and more than 110% is `high`. Calories, fat, and sodium
are treated as upper-limit-style values where `high` is a warning.

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
- `meal_logs`: raw text + parsed JSON
- `meal_items`: structured items from each log
- `foods`: cached FDC food metadata
- `food_nutrients`: cached nutrient values per 100g
- `food_portions`: cached household measures used to convert cups, pieces, etc. to grams
- `user_profiles`: local profile used to estimate daily target ranges

Personal runtime state belongs outside the repo, usually in
`~/.nutrition/nutrition.db`.
