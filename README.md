# Weather-Aware Truck Routing

Helps a truck driver choose the safest of three routes. The app checks the weather along each route
**at the time the truck is expected to be there**, classifies the risk using the load weight, and
recommends a route.

| | |
|---|---|
| App | _add the Netlify URL_ |
| API | https://spotter-truck-routing.onrender.com/api/health |
| Walkthrough | _add the Loom URL_ |

The API runs on Render's free tier, which sleeps when idle. The first request after a quiet spell
takes 30–60 s.

## How it works

```
origin, destination, departure, load, interval
  → geocode both places (HERE), using the origin's timezone for the departure
  → 3 truck routes (HERE Routing v8, truck mode, gross weight)
  → checkpoints every 10/25/50 mi plus start and end, each with an ETA
  → hourly forecast at every checkpoint (Open-Meteo), read at that checkpoint's ETA
  → risk level per checkpoint (wind with load rules, rain, snow)
  → miles per risk level per route → ranking → recommendation and reasons
```

The logic lives in `backend/routing/services/`. `risk.py`, `checkpoints.py` and `scoring.py` are pure
functions with no Django or HTTP, and `analysis.py` runs the steps in order. The frontend only
displays what the API returns and has no copy of the rules.

### APIs and why

| Need | Provider | Why |
|---|---|---|
| Routing | HERE Routing v8 (`transportMode=truck`) | Real truck routing that respects the vehicle's weight and returns up to 3 alternatives on long trips. OpenRouteService only gives alternatives on short trips. |
| Geocoding | HERE Geocode + Autosuggest | Same key; also returns each place's IANA timezone |
| Weather | Open-Meteo | Free, no key, hourly forecasts, many locations in one request |
| Map tiles | OpenFreeMap | Free, no key |

Weather data is by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0), credited on the map.
API keys are used only by the backend. The browser only talks to the Django API.

## Risk rules

### Weather thresholds

Units: wind in mph (sustained, 10 m), rain and snow in in/hr.

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind | < 25 | 25 – < 35 | 35 – < 45 | 45 – < 55 | ≥ 55 |
| Rain | < 0.10 | 0.10 – < 0.25 | 0.25 – < 0.50 | 0.50 – 1.00 | > 1.00 |
| Snow | < 0.5 | 0.5 – < 1.0 | 1.0 – < 2.0 | 2.0 – 3.0 | > 3.0 |

**Boundaries:** the spec's ranges share their end values (0.25 appears in both Moderate and High). A
value exactly on a boundary goes to the **higher** level. The exception is the spec's explicit
"> 1.00" rain and "> 3.0" snow, where the boundary value itself stays Severe.

### Load rules (wind only; they can raise a level, never lower it)

| Wind | Load | Result |
|---|---|---|
| ≥ 55 mph | any | No Travel |
| 45 – < 55 mph | > 30,000 lb | No Travel |
| 35 – < 45 mph | > 40,000 lb | Severe |

Exactly 30,000 and 40,000 lb do **not** trigger the rules.

A checkpoint's level is the worst of wind (after load rules), rain and snow. If any value is missing,
or the ETA is beyond the forecast, the checkpoint is **Unknown**. It is never counted as Low, and the
UI shows it in grey.

### Numeric scale

The spec gives no scale, so we use Low 0, Moderate 1, High 2, Severe 3, No Travel 4. Unknown has no
number.

## Recommendation

**Miles per level.** Each stretch between two consecutive checkpoints counts its real length at the
**worse** of its two ends. This errs on the side of caution and handles a last stretch shorter than the
interval. A stretch touching an Unknown checkpoint counts as Unknown.

**Average risk** is the distance-weighted mean level over the known miles.

**Ranking** compares routes on this list, in order. The first value that differs decides, and there is
no weighted score:

```
(No Travel miles, Severe miles, High miles, Unknown miles, average risk, travel time)
```

This is the spec's order (Severe miles, High miles, average risk, time) with two additions:
- No Travel is put first, because it is worse than Severe.
- Unknown miles come after High, so missing data can't make a route look safe.

A route with No Travel miles is still ranked but flagged as not drivable. The response explains why the
winner won, and each other route says what it lost on (e.g. "More Severe miles: 10 vs 0 on Route B").

## Checkpoints and ETAs

- Checkpoints are placed every 10, 25 or 50 miles along the route line, plus the start and destination.
- **ETA = departure + HERE's driving time to that point.** HERE gives a time for each piece of road,
  and points in between are interpolated by distance. Slow stretches therefore get realistic ETAs.
- Weather is the forecast hour **nearest each checkpoint's ETA**, never the weather at departure.
- **Departure is local time at the origin.** "06:00" from Salt Lake City means 06:00 Mountain time.
  Times are UTC inside the backend. The UI shows departure and checkpoint times in the origin's
  timezone and arrival in the destination's, with timezone labels.

## Heatmap (0–48 h)

- The frontend asks for the routes' bounding box plus 0.5° of padding.
- The backend builds a grid of up to 120 points over it, fetches each point's forecast once, and scores
  all 49 hours with the same risk rules and the trip's load.
- The slider only changes which hour is drawn; it never fetches again. The grid is drawn as a smooth,
  interpolated image, and points without data stay transparent.

## Caching

Django's cache API is backed by **Redis** when `REDIS_URL` is set, and by an in-process cache when it
isn't. The code is the same either way.

| Data | Key | Expires after |
|---|---|---|
| Geocode / autosuggest | `v2:geo:` / `v1:suggest:` + hash of the text | 7 d / 24 h |
| Truck routes | `v2:route:{origin}:{destination}:{gross-weight band}:{departure hour}` | 6 h |
| Weather | `v1:wx:{lat}:{lon}` (0.1° cell, about 11 km), the full hourly series | 30 min |

- **Recomputed on every request:** risk, scores and ranking are never cached, so a rule change applies
  immediately.
- **Failures aren't cached:** a failed provider call is never stored.
- **Redis is optional:** if it's unreachable, the app calls the providers directly, and rate limiting
  lets requests through.

**Why Redis in production:** gunicorn runs several worker processes, and an in-process cache gives each
worker its own copy. With Redis, the workers share one cache and one set of rate-limit counters, and
the cache survives restarts. Measured locally with 2 gunicorn workers:

- **Repeat analysis:** 4.7 s, then 0.06 s from cache.
- **Shared rate limit:** the 20/min limit held across both workers, and the 21st request got 429.
- **Redis stopped:** requests still returned 200.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/routes/analyze` | `{origin, destination, departure_time, load_lb, interval_mi}` → routes, checkpoints, metrics, recommendation |
| GET | `/api/heatmap?bbox=&start=&load_lb=` | Grid × 49 hours of risk scores |
| GET | `/api/geocode?q=` | Place suggestions |
| GET | `/api/health` | Liveness check |

Input is validated with DRF serializers:
- `interval_mi` must be 10, 25 or 50.
- `load_lb` must be 1–80,000.
- The departure must fall inside the forecast: from today 00:00 UTC (or 1 hour ago, whichever is
  later) to 23:00 UTC on the 14th day.
- Origin and destination must differ, both as text and as geocoded places (at least 0.5 mi apart).

Status codes:

| Code | Meaning |
|---|---|
| 400 | Invalid input, with errors per field |
| 422 | No truck route found |
| 429 | Rate-limited |
| 502 | A provider failed |
| 503 | A provider is rate-limiting us; `Retry-After` says when to retry |
| 504 | A provider timed out |

Errors never include tracebacks or provider details.

## Assumptions

- **Wind:** risk uses sustained wind (`wind_speed_10m`). Gusts are shown but not scored, because the
  spec's thresholds read as sustained speeds. This is one constant, so it's easy to change.
- **Rain:** rain = `rain + showers`.
- **Truck weight for routing:** HERE needs the **gross** weight, so we send load + 30,000 lb (empty
  tractor and trailer), rounded up to the next 5,000 lb. Rounding lets nearby loads share cached routes
  and errs heavier, never lighter. The load rules use the exact load entered.
- **Departure:** wall-clock time at the origin. Up to 1 hour in the past is accepted, for "leaving
  now".
- **Countries:** geocoding is limited to the USA, Canada and Mexico.

## Known limitations

- **Forecast horizon:** 14 whole UTC days from today 00:00, so the latest departure is 23:00 UTC on
  day 14, not now + 14 days. Open-Meteo forecasts 16, but anything over 14 days costs more than
  one call per location (see below). Checkpoints with ETAs beyond the forecast are Unknown.
- **Generated detours:** when HERE returns fewer than 3 routes, extra routes are forced through a
  point beside the main route's midpoint. The app tries 8% of the trip length first, then 15%, and
  keeps detours at most 1.5× the main route's length. These are labelled "(detour)", flagged in the
  API (`is_fallback_alternative`) and shown with their extra distance. They are what-if options, not
  routes a dispatcher would plan.
- **The app ranks routes; it doesn't plan around weather.** If a storm covers all three routes, the
  app picks the least bad one. The "depart later" suggestion and the heatmap help choose a better time
  to leave instead.
- **Heatmap resolution:** the 120-point cap means long corridors get a coarser grid (about 1.5°
  between points from Denver to the East Coast). Checkpoint risk is not affected, because each
  checkpoint's own forecast is fetched.
- **Weather rate limits:** Open-Meteo's free tier is limited per IP: 600 calls a minute and 10,000 a
  day, where each location in a request counts as one call. A new trip costs one call per 0.1° cell
  along its routes, and a new heatmap up to 120. Repeated trips, load changes and slider moves come
  from the cache and cost nothing. When the limit is hit, the API returns 503 with `Retry-After`, and
  the UI counts down before retrying. The free tier is for non-commercial use; production use would
  need Open-Meteo's paid plan, which only adds an API key.
- **Weather precision:** forecasts are hourly and per 0.1° cell.
- **Truck details:** only weight is sent to HERE. Height, axle count and hazmat restrictions are not
  modelled.
- **Load maximum:** the limit is 80,000 lb, which is the federal **gross** limit. With the 30,000 lb
  empty-truck assumption, any load above 50,000 lb is over the legal gross weight.

## Local setup

### Backend (Python 3.12+, deployed on 3.14)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env          # set DJANGO_SECRET_KEY and HERE_API_KEY (developer.here.com)
.venv/bin/python manage.py runserver
```

Checks: `.venv/bin/pytest`, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`,
`.venv/bin/python manage.py check`

All provider calls are mocked in the tests, and any network call a test doesn't mock fails.

### Redis cache (optional locally)

```bash
docker run -d --name spotter-redis -p 6379:6379 redis:7-alpine \
  redis-server --save "" --appendonly no --maxmemory 128mb --maxmemory-policy allkeys-lru
```

Then set `REDIS_URL=redis://localhost:6379/0` in `backend/.env` and restart the server. To see what's
cached: `docker exec spotter-redis redis-cli --scan --pattern 'trw:*'`.

### Frontend (Node 22.13+ or 24, npm 11)

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev                   # http://localhost:5173 (needs the backend running)
```

Checks: `npm run typecheck`, `npm run lint`, `npm run format:check`, `npm run build`

## Environment variables

**Backend** (`backend/.env.example`):

| Variable | Notes |
|---|---|
| `DJANGO_SECRET_KEY` | Required |
| `DJANGO_DEBUG` | `False` in production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames, no scheme |
| `CORS_ALLOWED_ORIGINS` | The frontend's exact origin(s), e.g. `https://app.netlify.app` |
| `HERE_API_KEY` | Required for routing and geocoding |
| `REDIS_URL` | Optional; empty means the in-process cache |
| `NUM_PROXIES` | `1` behind Render's proxy, so rate limits use the client's IP |
| `HTTP_CONNECT_TIMEOUT_S`, `HTTP_READ_TIMEOUT_S` | Provider timeouts, default 3 / 10 s |
| `THROTTLE_ANALYZE_RATE`, `THROTTLE_HEATMAP_RATE`, `THROTTLE_GEOCODE_RATE` | Default 20/min, 20/min, 120/min |

**Frontend** (`frontend/.env.example`). These values are baked into the public bundle, so they must
never contain secrets:

| Variable | Notes |
|---|---|
| `VITE_API_BASE_URL` | e.g. `https://spotter-truck-routing.onrender.com/api` |
| `VITE_MAP_STYLE_URL` | `https://tiles.openfreemap.org/styles/liberty` |

## Deployment

**Redis (Render → New → Key Value):** free plan, in the same region as the API. Copy its
**internal** URL into the API's `REDIS_URL`.

**API (Render → New → Web Service):**

| Setting | Value |
|---|---|
| Root directory | `backend` |
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 60` |
| Health check path | `/api/health` |

Environment: `PYTHON_VERSION=3.14.3`, `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY`,
`DJANGO_ALLOWED_HOSTS=<service>.onrender.com`, `HERE_API_KEY`, `REDIS_URL`, `NUM_PROXIES=1`,
`CORS_ALLOWED_ORIGINS=<frontend URL>`.

**Frontend (Netlify):**

| Setting | Value |
|---|---|
| Base directory | `frontend` |
| Build command | `npm run build` |
| Publish directory | `frontend/dist` |

Environment: `NODE_VERSION=24` (it ships npm 11; npm 10 crashes on this dependency tree),
`VITE_API_BASE_URL`, `VITE_MAP_STYLE_URL`. Changing a `VITE_*` value needs a redeploy.

## Why there is no database

Every analysis is computed on request from live routing and forecast data. Nothing has to outlive the
request: the requirements have no users, saved trips or history. A database would add migrations,
hosting and new ways to fail without meeting any requirement. Repeated provider calls are avoided with
the cache above.
