# UI designs (Stitch)

Source: Stitch project "Weather-Aware Truck Routing" (`11391242130115251533`), design system
`assets/16717622712955924437`. These designs are final: **no more Stitch generation**.
Each screen has a screenshot (`.png`) and Stitch's exported HTML/Tailwind (`.html`) for markup reference.

| File | UI state it defines |
|---|---|
| `01-results` | Results: recommendation banner, 3 route cards, checkpoint popup, forecast slider |
| `02-empty-validation` | First visit, geocode autocomplete dropdown, inline field errors, disabled submit |
| `03-loading` | Analyzing: disabled form, spinner button + cancel, progress stepper, skeleton cards |
| `04-errors` | Provider error (502) with retry/details, timeout, offline, rate-limited (429), place not found, map error card, error toast |
| `05-no-safe-route-warnings` | All routes have No Travel ("Least risky", not "Recommended"), Unknown-weather warning, detour-route notice, Unknown checkpoint popup, success toast |
| `06-heatmap` | Heatmap on, gradient legend, 0–48 h slider, heatmap loading / error / partial states |

## Use the layout and states, NOT these generated extras

Stitch added things that are out of scope or wrong. When implementing, leave them out:

- Top-bar nav (Dispatch, Routes, Fleet Map, Alerts, History), status pills, version/run-ID badges,
  notifications, settings, export, avatar. The top bar is the logo and title, plus a Legend button.
- "Wind Barbs", "Road Cameras", DOT camera links, road surface, elevation, map coordinate footers,
  NOAA/HRRR model names (our weather source is Open-Meteo), "manual dispatch mode", "100 mi" interval.
- Legend threshold text in `02`/`03` is wrong. Use the risk table in `CLAUDE.md` §3.
- `01` popup says "Moderate risk" for 38 mph and 42,000 lb. Per the load rule that is **Severe**.
- Risk colors always come from `frontend/src/lib/risk.ts`.
