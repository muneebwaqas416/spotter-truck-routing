# Weather-Aware Truck Routing

Helps a truck driver choose the safest route by weather along the route at the truck's arrival time,
load weight and travel time.

> Hosted app, Loom walkthrough, API details, risk rules and assumptions will be added here as features land.

## Repository layout

```
backend/    Django + DRF API (stateless, no database)
frontend/   React + TypeScript + Vite, MapLibre + deck.gl
```

## Local setup

### Backend (Python 3.12+)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env          # set DJANGO_SECRET_KEY and HERE_API_KEY (developer.here.com)
docker compose up -d redis    # optional: then set REDIS_URL=redis://localhost:6379/0
.venv/bin/python manage.py runserver
```

Checks: `.venv/bin/pytest`, `.venv/bin/ruff check .`, `.venv/bin/python manage.py check`

### Frontend (Node 22.12+, npm 11)

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev                   # http://localhost:5173 (needs the backend running)
```

Checks: `npm run typecheck`, `npm run lint`, `npm run format:check`, `npm run build`

## Why there is no database

Every analysis is computed on request from live routing and forecast data, and nothing needs to outlive
the request: there are no users, no saved trips and no history in the requirements. A database would add
migrations, hosting and failure modes without serving a requirement. Duplicate provider calls are avoided
with Django's in-memory cache instead.
