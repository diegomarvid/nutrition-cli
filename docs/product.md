# Product

## Principle

Do not compete with Cronometer. Win on lower friction and sharper feedback.

The core loop with an assistant should feel like this:

```text
User: hoy comí 500g de muslo de pollo cocido, 1 taza de arroz blanco y una manzana
Assistant: logs it with nutrition log-json, then reports how the day is going
```

Then the app should answer:

```text
Guardado para hoy.
Proteína: alta.
Fibra, magnesio, potasio, calcio, vitamina C/folato/K: bajos.
```

## Roadmap

### v0

- JSON CLI for assistant-authored meal entries
- Text CLI as a secondary convenience
- SQLite
- USDA search/detail
- Alias mapping
- Daily summary

### v1

- Weekly report
- Personal targets
- Suggestions for foods that fix the most repeated gaps
- Audio input through Telegram/WhatsApp

### v2

- UI only after the parser, resolver, and habit loop are useful.

## Non-goals

- Login
- Cloud sync
- Manual nutrition entry as the main path
- LLM-generated nutrient facts
- Requiring an OpenAI/Gemini API key inside the CLI
