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
