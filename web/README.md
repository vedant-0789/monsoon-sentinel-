# Monsoon Sentinel — web app

Next.js 16 + Tailwind 4 + MapLibre GL. Two views over the same API:

| Route | For | What it shows |
|---|---|---|
| `/` | Citizens (mobile-first) | Plain-language alert, heavy-rain chance with reasons, "check my street" (GPS or tap), streets to watch, one-tap flooding report |
| `/control` | City disaster cell (desktop) | Alert counts, live street map, ranked response zones with recommended action, rain-cell grid, hotspot status, incoming citizen reports |

English, मराठी and हिंदी throughout. Add `?date=YYYY-MM-DD` to replay any monsoon day 2001–2024 (e.g. `/?date=2024-07-25`).

```bash
npm install                 # also copies MapLibre's web worker into public/
NEXT_PUBLIC_API_URL=http://localhost:8077 npm run dev -- --port 3007
```

The API must be running (see the main README).
