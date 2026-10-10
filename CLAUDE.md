# Spotter Labs Assessment: Weather-Aware Truck Routing

React + Django app that helps a truck driver pick the safest route based on weather along the route at the
truck's arrival time, the load weight and the travel time.

**Deadline: under 48 hours (started 2026-10-09).** Correctness and clarity matter more than extra features.
If something is not in the requirements below, don't build it.

## Grading weights (use these to decide where time goes)

| Weight | Area |
|---|---|
| **40%** | Routes, weather, risk and recommendation logic |
| **35%** | UI, map and heatmap smoothness and performance |
| 10% | Code quality |
| 5% | Documentation and walkthrough |

Deliverables: GitHub repo, hosted app, 5–10 min Loom walkthrough.

---

## 1. Requirements (from the assessment)

**Input:** origin, destination, departure date/time, load weight (lb), sampling interval (10 / 25 / 50 miles).

**The app must:**
1. Generate **3 route options** from a routing API.
2. Sample weather every **10 / 25 / 50 miles**, using the truck's **estimated arrival time at each checkpoint**.
3. Classify weather risk using the risk and load rules (§3).
4. Recommend the best route (§4).
5. Show all routes, checkpoints, risk levels, ETAs and route summaries on a map.
6. Show a **weather heatmap** along the trip corridor with a **0–48 h forecast slider**.

---

## 2. Stack and external APIs

| Layer | Choice |
|---|---|
| Backend | Django + Django REST Framework, `httpx` for outbound calls, Django cache (locmem) |
| Frontend | React + Vite + TypeScript, MapLibre GL (`react-map-gl`), `deck.gl` (route/checkpoint/heatmap layers) |
| Hosting | Backend on Render or Railway (gunicorn), frontend on Vercel or Netlify |

| Need | Provider | Notes |
|---|---|---|
| Routing | **HERE Routing v8** (`transportMode=truck`, `alternatives=2`, `vehicle[grossWeight]`) | ORS alternatives only work on short trips (~100 km), so don't use it for this. Mapbox Directions is the fallback. |
| Geocoding | HERE Geocode/Autosuggest (same key) | |
| Weather | **Open-Meteo** forecast API (free, no key, takes many coordinates per call) | Hourly `wind_speed_10m`, `wind_gusts_10m`, `rain`, `showers`, `snowfall`; `wind_speed_unit=mph`, `precipitation_unit=inch`, `timezone=UTC` |

If the router returns fewer than 3 routes, generate more by adding a via-waypoint offset sideways from the
route's midpoint. Say so in the response and the README.

API keys live **only** in backend env vars. React only talks to our Django API.

---

## 3. Risk rules (single source of truth: `risk_engine.py`)

### Levels and numeric scale (our choice; the spec doesn't give one, so document it)

| Level | Score |
|---|---|
| LOW | 0 |
| MODERATE | 1 |
| HIGH | 2 |
| SEVERE | 3 |
| NO_TRAVEL | 4 |
| UNKNOWN | has no score; it is never treated as LOW |

### Weather thresholds (units: mph, in/hr)

Boundary convention: **a threshold value belongs to the higher category** (half-open intervals `[lo, hi)`),
except where the spec says `>` explicitly, in which case the value itself stays in the lower category.

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind (mph) | `< 25` | `[25, 35)` | `[35, 45)` | `[45, 55)` | `≥ 55` |
| Rain (in/hr) | `< 0.10` | `[0.10, 0.25)` | `[0.25, 0.50)` | `[0.50, 1.00]` | `> 1.00` |
| Snow (in/hr) | `< 0.5` | `[0.5, 1.0)` | `[1.0, 2.0)` | `[2.0, 3.0]` | `> 3.0` |

Spec as given (source of truth):

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind | <25 mph | 25–34 | 35–44 | 45–54 | ≥55 mph |
| Rain | <0.10 in/hr | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | >1.00 |
| Snow | <0.5 in/hr | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | >3.0 |

> The spec's rain/snow ranges share endpoints (e.g. 0.25 appears in both Moderate and High). Our convention puts a
> shared endpoint in the higher category, except for the explicit `>` at the No Travel edge, where the endpoint
> (1.00 rain, 3.0 snow) stays in Severe. Document this in the README.

### Load rules (wind only, applied **after** the base wind level, and **never downgrade**)

- wind `≥ 55` → NO_TRAVEL for any load
- wind `[45, 55)` **and** load `> 30,000 lb` → NO_TRAVEL
- wind `[35, 45)` **and** load `> 40,000 lb` → SEVERE
- Exactly 30,000 and 40,000 lb do **not** trigger these rules (strict `>`).

`checkpoint_level = max(wind_level_after_load, rain_level, snow_level)`. If any input is missing, the level is UNKNOWN.

**Assumptions to document:** we classify on sustained `wind_speed_10m` (gusts are shown but not scored), and
rain = `rain + showers`. Both are constants, so they're easy to change.

---

## 4. Route recommendation (single source of truth: `scoring_service.py`)

**Miles attribution:** each stretch between two consecutive checkpoints counts its *actual* length at the
**worse** of its two endpoint levels. This is conservative and handles a final segment shorter than the interval.

**Per-route metrics:** `no_travel_mi`, `severe_mi`, `high_mi`, `unknown_mi`, `avg_risk` (distance-weighted
over known miles), `duration_s`.

**Ranking:** sort ascending on an explicit tuple. **Never use a weighted sum.**

```
(no_travel_mi, severe_mi, high_mi, unknown_mi, avg_risk, duration_s)
```

- The spec's order is Severe miles, then High miles, then average risk, then time. We add `no_travel_mi` in front
  because No Travel is strictly worse than Severe. `unknown_mi` comes after High because unknown risk must not
  look safe.
- A route with any NO_TRAVEL miles can still be ranked, but it is flagged "not drivable".
- Return a human-readable reason with the recommendation, e.g. "B: 0 severe mi vs 50 on A; +18 min".

---

## 5. Checkpoints and weather at the ETA (`checkpoint_service.py`)

1. Walk the route polyline and add up haversine distance. Put a checkpoint every N miles **plus the start and the
   destination**.
2. ETA = `departure + cumulative duration`. Use the provider's **per-section/span durations** and interpolate
   inside a section. Fall back to the distance ratio only if those durations are missing, and document that.
3. All datetimes are **timezone-aware UTC** internally. Convert to local time only in the UI.
4. Weather lookup: send all checkpoints for all routes in **one batched Open-Meteo call**, then take the hourly
   value **nearest the checkpoint's ETA**. Never use departure-time weather for the whole trip.
5. If an ETA is outside the forecast horizon, or the provider failed, the checkpoint is UNKNOWN and gets an
   explicit reason.
6. Cache weather by `(round(lat,2), round(lon,2), hour)` to avoid duplicate requests.

---

## 6. Heatmap (0–48 h)

- Backend: build a point grid over the bbox of all routes plus ~30 mi buffer, spacing ~15–25 km, capped at ~300 points.
- Make **one batched fetch** of 49 hourly values per point. Compute a risk score per point per hour **on the backend**
  using the same `risk_engine` functions.
- Response is compact: `{points: [[lon,lat],...], hours: [iso...], scores: [[...per point], ...per hour]}`.
- Frontend: deck.gl `HeatmapLayer`. The slider only changes which hour index is drawn, so **no refetch on slide**.
  Memoize data and use `updateTriggers`.

---

## 7. API contract

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/routes/analyze` | `{origin, destination, departure_time, load_lb, interval_mi}` → routes, checkpoints, metrics, recommendation |
| `GET` | `/api/heatmap?bbox=&start=` | corridor grid × 49 hours of risk scores |
| `GET` | `/api/geocode?q=` | autocomplete suggestions |

Validation (DRF serializers): `interval_mi ∈ {10, 25, 50}`; `load_lb` positive and ≤ 80,000 (US legal max,
documented); `departure_time` is ISO, timezone-aware, and within forecast range; origin ≠ destination.

Status codes: `200` ok, `400` invalid input (DRF error format), `502` upstream provider failure,
`504` provider timeout. Never return tracebacks or provider internals.

The frontend **must not re-implement business rules**. It only renders what the API returns, including levels,
colors keys, ETAs and the recommendation.

---

## 8. Repo layout (monorepo)

```
./                       CLAUDE.md, README.md, .gitignore, .editorconfig
backend/                 Django 6.1 + DRF 3.18, Python venv in backend/.venv
├── config/              settings.py (all config from env), urls.py (/api/ → routing)
├── routing/
│   ├── serializers.py   input validation + response shape
│   ├── views.py         thin: validate → service → Response
│   ├── urls.py          /api/health (+ analyze, heatmap, geocode)
│   ├── exceptions.py    ProviderError 502 / ProviderTimeout 504 / PlaceNotFound 400 / NoRouteFound 422
│   ├── cache.py         get_or_fetch / get_many_or_fetch: read-through, fail-open, never caches failures
│   ├── throttling.py    ScopedRateThrottle that fails open when Redis is down
│   ├── services/
│   │   ├── domain.py        plain dataclasses shared by services (Place, RoutePath, Checkpoint, ...)
│   │   ├── risk.py          PURE: thresholds + load rules → RiskLevel | None (unknown)
│   │   ├── checkpoints.py   PURE: polyline sampling + ETAs from provider span timings
│   │   ├── scoring.py       PURE: miles per level (worse end of each stretch) + ranking tuple
│   │   ├── http.py          get_json: timeouts, typed errors, never logs URLs (they hold API keys)
│   │   ├── here.py          HERE geocode / autosuggest / truck routes (+ detour fallback)
│   │   ├── weather.py       Open-Meteo batched hourly forecasts, unit-normalized
│   │   ├── heatmap.py       corridor grid × 49 h, same weather cache + risk rules
│   │   └── analysis.py      orchestration
│   └── tests/           pytest + pytest-django; HTTP mocked with respx (conftest has fixtures)
├── requirements.txt / requirements-dev.txt (pinned)
├── pyproject.toml       pytest + ruff config
└── .env.example         (commit); .env is gitignored
frontend/                React 19 + TS (strict) + Vite 8, Tailwind 4, MapLibre + deck.gl, Redux Toolkit + RTK Query
├── src/
│   ├── redux/           store.ts (configureStore), hooks.ts (typed hooks), api.ts (RTK Query endpoints +
│   │                    cache times), errors.ts (ApiError normalizer), types.ts (API contract — keep in sync
│   │                    with the DRF serializers)
│   ├── config/env.ts    validated VITE_* env
│   ├── features/        trip · analysis · results · heatmap
│   ├── components/      map · layout · ui
│   └── lib/, hooks/     pure helpers (format, datetime, risk colors) and small hooks
└── .env.example         (commit); .env.local is gitignored. VITE_* values are public; no secrets.
```

- Use **npm 11** for the frontend (`npx npm@11 install`). npm 10 crashes on this dependency tree.
- Import alias: `@/` → `frontend/src/`.
- **All API calls go through RTK Query** (`src/redux/api.ts`); never call `fetch` from components.
  `analyzeRoutes` is a *query* (POST, but side-effect free) so identical inputs hit the cache.
  Cache lifetimes: analysis 10 min, heatmap 15 min, geocode 60 min. No focus/reconnect refetch.
  Every error is normalized to `ApiError {status, code?, message, fieldErrors?}`.
- **Frontend structure:** `features/trip` (form, validation, slice, `useAnalysis`), `features/analysis`
  (progress, error copy), `features/results` (cards, banners, pure `derive.ts`), `features/heatmap`
  (slider, `useHeatmap`), `components/map` (MapView, popup, legend, overlays, `heatmapGrid.ts`).
- **UI components: shadcn/ui** (Radix base, `components.json`, generated into `src/components/ui/`, lowercase
  files; edit them freely, it's our code). Used: button, input, label, card, badge, alert (+ app tones
  danger/warning/info/purple/success), switch, slider, toggle-group, skeleton, spinner, sonner.
  App-level compositions live outside `ui/`: `components/StatusAlert.tsx`, `components/ui/RiskChip.tsx`.
  `cn()` from `@/lib/utils` (clsx + tailwind-merge) for all conditional classes.
  Forms: **react-hook-form + zod** (`tripSchema`). Place search: **Headless UI `Combobox`** rendered with
  shadcn `Input`; shadcn has no free-text async autocomplete. Theme: Inter font, primary = blue-700.
- **Styling tokens (no raw shades in app code):** colours, fonts and sizes are CSS variables in
  `src/index.css` and used through Tailwind classes by role: `text-foreground`, `text-muted-foreground`,
  `text-subtle`, `bg-muted`, `border-border`, `border-input`, `text-primary`, `text-destructive`,
  `text-success`, `text-warning`; sizes from Tailwind's scale plus `text-2xs` (11px). Status tones
  (green/amber/violet) are defined only as `Alert` and `Badge` variants. Risk colours come only from
  `src/lib/risk.ts` (deck.gl needs them in JS). Repeated pieces are components (`InputIcon`,
  `StatusAlert`), not custom CSS classes. `@custom-variant dark` stays: it stops the OS dark mode from
  triggering shadcn's `dark:` classes.
- **Map rendering:** deck.gl `MapboxOverlay` with `interleaved={false}` (interleaved crashes with MapLibre 6).
  The overlay UI sits at `z-10` and popups at `z-index: 2` so they stay above deck's canvas. The heatmap is
  a regular grid rasterised to a bilinear-filtered `BitmapLayer` (not `HeatmapLayer`). Missing samples stay
  transparent, and the slider only rebuilds that hour's texture.
- Frontend has **no tests or mocks** for now (removed by request); it needs the real backend to run.
- Dev server: use port 5174 locally (`npm run dev -- --port 5174`). Docker holds `*:5173` on this machine.
- **Designs are final and live in `docs/design/`** (screenshots + Stitch HTML, with a README mapping each
  screen to a UI state and listing the generated extras to ignore). Don't generate more Stitch designs.
  Source: Stitch project `11391242130115251533`, design system `assets/16717622712955924437`.
- Checks: backend `pytest`, `ruff check .`, `ruff format --check .`, `manage.py check`;
  frontend `typecheck`, `lint` (oxlint), `format:check` (prettier), `build`.

### Cache (Redis via Django's RedisCache; in-process fallback when REDIS_URL is empty)

| Data | Key | TTL |
|---|---|---|
| Geocode / autosuggest | `v1:geo:` / `v1:suggest:` + sha256(normalized query) | 7 d / 24 h |
| Truck routes | `v1:route:{origin}:{dest}:{gross weight bucket}:{departure hour}` | 6 h |
| Weather | `v1:wx:{lat}:{lon}` (0.1° cell) → full hourly series; lookup by nearest hour | 30 min |

Risk/ranking are never cached (always recomputed). Failed fetches are never cached. Bump `v1` when a
cached payload changes shape. Redis outages degrade to direct fetches; throttling fails open.
Local Redis: `docker compose up -d redis` + `REDIS_URL=redis://localhost:6379/0`.

### Database decision: none

`DATABASES = {}`. Analysis is stateless and computed per request from live provider data. Nothing needs to be
persisted (no users, saved trips or history in the requirements). `django.contrib.auth/sessions/admin` are not
installed. DRF runs with no authentication classes and `UNAUTHENTICATED_USER=None`. The provider cache is
LocMemCache (per process). Don't add models, Celery, Redis or auth just to look thorough. If saved trips are
ever required, add Postgres then.

---

## 9. Engineering rules

**Project-specific (highest priority):**
1. `risk_engine` and `scoring_service` are **pure functions**: no Django, no HTTP, no DB.
2. **One unit system internally**: mph, in/hr, miles, seconds, UTC datetimes. Convert at provider boundaries only.
3. Weather is evaluated **at the checkpoint ETA**, always.
4. Ranking is **deterministic and lexicographic** (§4).
5. Provider JSON parsing stays **inside provider modules**. Everything else uses internal dataclasses.
6. **Unknown is never Low.** Missing data shows up in the response and the UI.

**General Django/Python:**
- PEP 8, type hints on public functions, small single-purpose functions, comments explain *why*.
- Validate all input with DRF serializers. Never trust the frontend.
- Thin views. Logic goes in services, and only where it's substantial.
- Every outbound call has explicit timeouts (connect ~3s, read ~10s). Catch `httpx` errors at the provider
  boundary, raise a typed `ProviderError`, and map it to 502/504 in the view. **No `except Exception: pass`.**
- Use `logging`, not `print`. Never log API keys.
- Secrets come from env vars (`HERE_API_KEY`, `DJANGO_SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`).
- DRF throttling on `/analyze` and `/heatmap`, since they're expensive.
- Production: `DEBUG=False`, gunicorn, HTTPS, `python manage.py check --deploy` passes.

---

## 10. Required tests (mock all providers; no live API calls in tests)

- [ ] Each wind/rain/snow threshold just below, at and just above every boundary
- [ ] Load rules at exactly 30,000 and 40,000 lb, and just above each
- [ ] Wind ≥ 55 is NO_TRAVEL for any load; load rules never downgrade a level
- [ ] Checkpoints: short route (< interval), route not divisible by interval, start and end included
- [ ] ETAs use cumulative section durations; weather is picked at the ETA hour, not departure
- [ ] Ranking: each of the tuple priorities decides the winner in its own test case
- [ ] Missing weather becomes UNKNOWN, never LOW
- [ ] Routing error, weather timeout and malformed provider JSON return 502/504 with a clean error body
- [ ] Invalid input: missing fields, interval 15, negative load, naive datetime → 400
- [ ] End-to-end `/analyze` (mocked) returns routes, checkpoints, ETAs, metrics and recommendation

Run before every commit: `pytest` and `python manage.py check`.

---

## 11. Frontend rules

- Layout: left panel with the form, route summary cards (recommended route highlighted) and reasons. Map on the right.
- Map: 3 route lines (recommended one thicker or brighter). Checkpoint dots colored by level, with a popup
  showing ETA, wind/rain/snow and level. UNKNOWN gets a distinct gray/hatched style. Plus a legend.
- Heatmap toggle and 0–48 h slider showing the absolute time label.
- Performance: deck.gl layers, `useMemo` for derived layer data, no refetch on slider move, debounced geocode input.
- Loading, empty and error states for every request.
- Risk colors: LOW green, MODERATE yellow, HIGH orange, SEVERE red, NO_TRAVEL dark purple/black, UNKNOWN gray.

---

## 12. 48-hour plan

| Block | Hours | Work |
|---|---|---|
| **Day 1 AM** | 0–4 | Scaffold Django + React, env config. `risk_engine` + `scoring_service` with **full tests** |
| **Day 1 PM** | 4–10 | `routing_provider` (HERE), `checkpoint_service`, `weather_provider`, `analysis_service`, `/analyze` + API tests |
| **Day 1 Eve** | 10–14 | React form + map: routes, checkpoints, popups, summary cards, recommendation |
| **Day 2 AM** | 14–20 | `/heatmap` endpoint + deck.gl heatmap + slider. Error/loading states |
| **Day 2 PM** | 20–26 | Deploy backend + frontend, fix CORS/env issues, smoke test on hosted URLs |
| **Day 2 Eve** | 26–32 | README (setup, env vars, APIs, assumptions, rules, limitations). Polish |
| **Buffer** | 32–40 | Bug fixes, record the Loom (demo first, then a walkthrough of risk/ranking code and tests) |

**Loom tip:** demo a route through active bad weather and show the recommendation change as load weight
crosses 30k / 40k lb.

## 13. README must include

Setup (backend + frontend), env vars, chosen APIs and why, the risk/load tables with the boundary convention,
the ranking tuple, the numeric risk scale, miles attribution, assumptions (boundary convention, sustained wind, rain + showers,
max load), known limitations (forecast horizon, fallback alternatives, heatmap grid resolution), and hosted URLs.
