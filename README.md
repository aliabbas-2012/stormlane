# StormLane

StormLane compares up to three truck routes between two places and recommends the safest one. The weather is checked along each route every 10, 25 or 50 miles. Each checkpoint is judged by the forecast **for the hour the truck is expected to get there**, not the departure hour. Wind, rain, snow and the truck's load weight set a risk level at every checkpoint. The routes are ranked on how many miles they spend at each level. A corridor heatmap with a 0–48 hour slider shows the weather moving over the trip.

**Live app:** _add the Render URL after deploying (see [Deploy](#deploy))_

![StormLane: three Dallas → Denver routes coloured by risk, with the corridor heatmap at +33 h](docs/screenshot.png)

- [Architecture](#architecture)
- [Run locally](#run-locally)
- [Environment variables](#environment-variables)
- [API reference](#api-reference)
- [Risk & recommendation logic](#risk--recommendation-logic)
- [Assumptions & limitations](#assumptions--limitations)
- [Performance](#performance)
- [Testing & CI](#testing--ci)
- [Deploy](#deploy)
- [What I'd do next](#what-id-do-next)

## Architecture

```mermaid
flowchart LR
  subgraph Browser["Browser: React 18 + TypeScript"]
    Form[TripForm + autocomplete] -->|POST /api/analyze| Q[TanStack Query]
    Q --> Map[MapLibre map<br/>risk-coloured routes, checkpoints]
    Q -->|POST /api/heatmap| Heat[Heatmap layer + 0–48 h slider]
  end

  subgraph Django["Django + DRF (gunicorn, threaded)"]
    Views[Sync DRF views] -->|async_to_sync| Svc[services: analyze, heatmap,<br/>route options, ranking]
    Svc --> Risk[risk/ + geo/<br/>pure functions]
    Svc --> Prov[providers/<br/>httpx.AsyncClient + gather]
  end

  Q -. same origin .-> Views
  Prov --> TomTom[(TomTom routing + search<br/>when keyed)]
  Prov --> OSRM[(OSRM<br/>routing fallback)]
  Prov --> Photon[(Photon<br/>search fallback)]
  Prov --> OM[(Open-Meteo<br/>hourly forecast)]
  Svc <--> PG[(PostgreSQL<br/>cache table + forecast cache)]
```

| Path | What lives there |
|---|---|
| `backend/routing_app/risk/` | Risk levels, threshold classification and load rules. Pure functions with no I/O. |
| `backend/routing_app/geo/` | Polyline codec, haversine, interpolation, checkpoints and segment ownership, ETA series, via points, route overlap, Douglas–Peucker simplification, corridor grid. All pure. |
| `backend/routing_app/providers/` | TomTom / OSRM routing behind a `RoutingProvider` interface, TomTom / Photon geocoding, the batched Open-Meteo client, and the shared retry/timeout policy |
| `backend/routing_app/services/` | Orchestration: route options (the 3-route guarantee), analyze, heatmap, summary metrics, ranking |
| `backend/routing_app/api/` | Serializers, views, URLs and the uniform error format |
| `frontend/src/` | `api/` typed client and hooks · `components/` UI · `lib/` risk colours, formatting, geometry, heatmap maths · `types/` API contract |

The views are synchronous DRF views. Each request runs its external calls concurrently on its own event loop (`async_to_sync` around `asyncio.gather`), and gunicorn serves it with threaded WSGI workers. I chose this over ASGI because DRF has no async views. In production Django also serves the built React app, so the app and the API share one origin.

## Run locally

Requirements: Python 3.12 (via [uv](https://docs.astral.sh/uv/)), Node 20+ (CI uses 24), PostgreSQL 14+.

```bash
# Backend
cd backend
cp .env.example .env              # then set DATABASE_URL (and optionally TOMTOM_API_KEY)
uv sync
uv run python manage.py migrate
uv run python manage.py createcachetable
uv run python manage.py runserver 8000

# Frontend (second terminal)
cd frontend
cp .env.example .env              # leave VITE_API_BASE_URL empty: Vite proxies /api to :8000
npm install
npm run dev                       # http://localhost:5173
```

Click **Try an example: Dallas, TX → Denver, CO** to run a full analysis.

## Environment variables

**Backend** (`backend/.env`)

| Variable | Required | Default / notes |
|---|---|---|
| `SECRET_KEY` | yes | Django secret |
| `DATABASE_URL` | yes | `postgres://USER:PASSWORD@HOST:5432/stormlane` (psycopg 3) |
| `DEBUG` | no | `false`. Production turns on the SSL redirect and HSTS. |
| `ALLOWED_HOSTS` | no | `localhost,127.0.0.1`. `RENDER_EXTERNAL_HOSTNAME` is added automatically. |
| `CORS_ALLOWED_ORIGINS` | no | `http://localhost:5173`. Only needed if the frontend is hosted on another origin. |
| `TOMTOM_API_KEY` | no | Turns on TomTom truck routing and search. Without it the app uses OSRM and Photon. |
| `HTTP_USER_AGENT` | no | Sent to the public APIs, as their usage policies ask |
| `WEB_CONCURRENCY`, `GUNICORN_THREADS` | no | `2` workers × `4` threads |
| `LOG_LEVEL` | no | `INFO` |

**Frontend** (`frontend/.env`)

| Variable | Notes |
|---|---|
| `VITE_API_BASE_URL` | Leave empty for local dev and for the single-origin deploy. Set it only when the API lives elsewhere. |

## API reference

All errors use the same shape: `{"error": {"code": "...", "message": "..."}}`.

### `GET /api/health`
`{"status": "ok"}`. The frontend calls it on load to wake a sleeping backend.

### `GET /api/geocode?q=denv`
Returns up to 6 places as `[{"label": "Denver, Colorado", "lat": 39.74, "lon": -104.98}, …]`. US results come first and results are cached for 24 h. `q` must be 2–200 characters.

### `POST /api/analyze`

```json
{
  "origin":      {"lat": 32.7767, "lon": -96.797,   "label": "Dallas, Texas"},
  "destination": {"lat": 39.7392, "lon": -104.9903, "label": "Denver, Colorado"},
  "departure_time": "2026-10-24T08:00:00-05:00",
  "load_lbs": 38000,
  "interval_miles": 25
}
```

Validation:
- `departure_time` must carry a UTC offset. It may be up to 15 min in the past, and the trip must end inside the 16-day forecast.
- `interval_miles` must be 10, 25 or 50.
- `load_lbs` must be 1–200,000. Loads above 80,000 lb are accepted with a permit warning.
- Origin and destination must be at least 1 mi apart.

The response, trimmed:

```jsonc
{
  "analysis_id": "3f…",                    // used by /api/heatmap
  "departure_time": "2026-10-24T13:00:00Z",
  "provider": "osrm", "truck_profile": false,
  "recommended_route_id": "B",
  "recommendation_reason": "Route B: 0 severe miles (Route A has 38); 22 min longer",
  "ranking": ["B", "C", "A"],
  "no_safe_route": false,
  "warnings": ["Routes use a car profile (OSRM fallback); …"],
  "routes": [{
    "id": "A", "name": "Route A", "synthesized": false, "timing_source": "segments",
    "distance_mi": 794.9, "duration_s": 51600, "arrival_time": "2026-10-25T03:20:00Z",
    "geometry": {"type": "LineString", "coordinates": [[-96.79, 32.77], …]},  // ≤ 2000 points
    "geometry_miles": [0, 0.41, …], "geometry_elapsed_s": [0, 31, …],       // per vertex
    "summary": {"no_travel_miles": 0, "severe_miles": 38.2, "high_miles": 10.1,
                "moderate_miles": 74.0, "low_miles": 672.6, "avg_risk": 0.31,
                "max_level": 3, "worst_checkpoint": {"index": 18, "mile": 450, "level": 3, "reason": "…"}},
    "checkpoints": [{"mile": 450, "lat": 36.1, "lon": -101.9, "eta": "2026-10-24T22:20:00Z",
                     "forecast_hour": "2026-10-24T22:00:00Z", "wind_mph": 48.0, "gust_mph": 61.2,
                     "rain_in_hr": 0.0, "snow_in_hr": 0.2, "level": 3, "drivers": ["wind"],
                     "reason": "wind 48 mph → Severe"}],
    "segments": [{"from_mile": 0, "to_mile": 437.5, "level": 0}, …]
  }]
}
```

Levels are integers: `0` Low, `1` Moderate, `2` High, `3` Severe, `4` No Travel.

### `POST /api/heatmap`
Body: `{"analysis_id": "…"}` (the analysis is kept for 1 hour). Returns a compact columnar payload, gzipped by the server:

```jsonc
{ "cell_deg": 0.39, "points": [[lon, lat], …],   // ≤ 250 corridor points
  "hours": ["…Z", …],                            // 49 hourly frames: departure hour .. +48 h
  "risk": [[0, 0, 1, …], …],                     // [point][hour]; -1 = no model data
  "wind": [[12.3, …], …], "rain": [[0.0, …], …], "snow": [[0.0, …], …] }
```

## Risk & recommendation logic

### Thresholds
These live in `risk/classify.py`. Wind is in mph; rain and snow are in inches per hour.

| | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind (sustained 10 m) | < 25 | 25 – < 35 | 35 – < 45 | 45 – < 55 | **≥ 55** |
| Rain (rain + showers) | < 0.10 | 0.10 – < 0.25 | 0.25 – < 0.50 | 0.50 – 1.00 | **> 1.00** |
| Snow | < 0.5 | 0.5 – < 1.0 | 1.0 – < 2.0 | 2.0 – 3.0 | **> 3.0** |

**Boundaries:** lower bounds are inclusive, so a value exactly on a shared endpoint goes to the higher band (35 mph is High). The No Travel boundaries use the spec's own operators (≥ 55, > 1.00, > 3.0). Inputs are rounded to 4 decimals first, so floating-point sums such as 0.07 + 0.03 still count as 0.10.

**Checkpoint level** is the worst of the wind, rain and snow levels. The load rules in `risk/load_rules.py` are applied after that, and they only ever raise the level:

- wind ≥ 55 mph → No Travel for any load
- 45 ≤ wind < 55 and load > 30,000 lb → No Travel
- 35 ≤ wind < 45 and load > 40,000 lb → Severe

Every result records what set its level. That's the explanation shown in the UI, e.g. `wind 47 mph + load 36,000 lb → No Travel (load rule)`.

### Checkpoints and segment ownership
In `geo/checkpoints.py`, checkpoints sit at mile 0, I, 2I, … and at the destination, interpolated along the full (unsimplified) route. Each checkpoint **owns** the stretch from the midpoint with its previous checkpoint to the midpoint with its next one, clipped to the route ends. Neighbours share their boundaries, so the owned miles add up to exactly the route length, and the tests check this on random routes. A route's miles per level are the sums of its checkpoints' owned miles.

### ETAs
- **Elapsed time** comes from the provider's own per-stretch timing wherever possible:
  - OSRM: `annotations.duration`, rescaled so it sums to the route's duration.
  - TomTom: the cumulative `progress[]` travel times, interpolated by distance.
  - Otherwise the route's total time is spread in proportion to distance.
- **ETA** = departure (UTC) + elapsed time.
- **Forecast hour:** wind is instantaneous in Open-Meteo, so it is read at the hour containing the ETA. Precipitation is a *preceding-hour total*, so the hour containing the ETA, [H, H+1), is the value stamped H+1.

### Ranking
`services/recommend.py` compares routes in this order:

1. Fewest **No Travel** miles. This step is my addition; see below.
2. Fewest **Severe** miles
3. Fewest **High** miles
4. Lowest distance-weighted **average risk** (0–4)
5. Shortest **travel time**

Miles are compared after rounding to the nearest 1 mi, and average risk in 0.05 steps. That stops sampling noise, such as 0.3 mi of Severe, from beating a real difference further down the list. A full tie keeps the provider's order.

The reason compares the winner with the fastest route when the winner isn't the fastest, because "why not the quick one?" is the driver's question. Otherwise it compares with the runner-up. If every route has No Travel miles, the routes are still ranked, and the UI shows a "No safe route at this departure time" banner.

### Three routes
`services/route_options.py`:
1. Ask the provider for its best route plus 2 alternatives.
2. If fewer than 3 come back, route through a waypoint offset perpendicular to the origin→destination midpoint: ±15 % of the straight-line distance first, then ±30 %.
3. Reject any candidate more than 1.5× slower than the fastest route.
4. Reject any candidate with more than 85 % of its points within 1 km of an accepted route.

If only 1–2 distinct routes survive, the app says so instead of padding the list with detours.

## Assumptions & limitations

- **Sustained wind** is classified; gusts are shown for information only. The spec says "wind".
- **Forecast hour = the hour containing the ETA.** Precipitation uses the bucket that covers that hour, as described above.
- **No Travel miles are ranked first.** The spec doesn't list them, but a route through a No Travel zone must never beat one without.
- **No hours-of-service rules, rest stops or fuel stops are modelled.** ETAs assume continuous driving, so long trips are optimistic.
- **Routes may be synthesized through via waypoints.** These are marked "via waypoint" in the UI.
- **Without a TomTom key, routing uses the public OSRM server's car profile.** Truck restrictions and load weight then don't affect the route geometry, only the risk. The UI shows a warning.
- **Forecast resolution:** Open-Meteo picks the best model for each location (roughly 3–13 km grids over the US) and gives hourly values out to 16 days. Forecast skill drops well before day 16. Coordinates are rounded to about 1 km for caching.
- **Open-Meteo's free tier** is for non-commercial use and has limits of 600 calls/min and 10,000/day. Each heatmap uses ≤ 250 locations, and the grid is snapped to fixed points so cached forecasts are reused across trips.
- **Load weight:** accepted up to 200,000 lb, with a warning above the 80,000 lb federal gross limit.
- **Heatmap edges:** the outer edge of the corridor fades to about 85 % intensity because kernels have fewer neighbours there.

## Performance

- **One weather request** covers every checkpoint on all three routes: up to 100 locations per request, with up to 3 requests at once. The heatmap is a single batched fetch for the whole corridor.
- **Caching:**
  - Forecasts: a dedicated Postgres table, one row per rounded location per UTC day, 30 min TTL. Reads are one `SELECT … IN`, writes one bulk upsert.
  - Route options (15 min), geocoding (24 h), analyses and heatmaps: Django's database cache, which all gunicorn workers share.
- **Heatmap scrubbing touches nothing but paint.** The heatmap is fetched once, and one GeoJSON source holds 49 hourly values per point for each metric. Moving the slider or pressing play swaps the `heatmap-weight` expression with `map.setPaintProperty`, throttled with `requestAnimationFrame`. Measured in Chrome on an Intel UHD 620 laptop GPU:
  - 0 network requests while scrubbing or playing
  - frame time p50 / p95 = 16.7 / 16.7 ms
  - 0 of 758 frames over 50 ms
- **Heatmap colours mean risk, not point density.** The corridor is a uniform lattice. The kernel is σ = 0.55 × the lattice spacing, its radius grows ×2 per zoom level, and the intensity is chosen so the rendered density ≈ the encoded weight. Uniform Moderate, Severe and No Travel test fields each render in their own colour.
- **Geometry:** checkpoints are computed on the full route (~10k points). The response sends a Douglas–Peucker simplification (≤ 2000 points, ~16 m tolerance, about 50 ms per route) with each kept vertex's exact mile and elapsed time.
- **Payloads:** `/api/analyze` is ~130 KB (~44 KB gzipped). The heatmap is ~146 KB (~18 KB gzipped).
- **Latency** (Dallas → Denver, OSRM): analyze takes ~4–6 s cold and ~0.25 s warm; the heatmap ~1.5 s cold and ~35 ms warm.
- **Static assets** are served by WhiteNoise, pre-compressed, with permanent `immutable` caching for Vite's fingerprinted files.

## Testing & CI

```bash
cd backend && uv run pytest          # 197 tests, ~3 s, no network (providers are mocked)
cd backend && uv run ruff check . && uv run ruff format --check .
cd frontend && npm run lint && npm run format:check && npm run typecheck && npm run build
```

| Area | What the tests cover |
|---|---|
| Risk engine | Every band edge (24.99 / 25, 34.99 / 35, 0.10, 0.25, 1.00 / 1.0001, 3.0 / 3.0001, …). Each load rule at 30,000 / 30,001 and 40,000 / 40,001 lb. Load rules never lower a level. Combinations of factors. |
| Geo | Polyline round trips, checkpoint spacing, owned miles summing to the route length, ETAs that only increase, via points, overlap, simplification, the corridor lattice |
| Ranking | Every tiebreak level, the tolerances, the no-safe-route case |
| Providers | Mocked HTTP for OSRM, TomTom, Open-Meteo, Photon and the retry policy |
| API | `/api/analyze` and `/api/heatmap` end to end with mocked providers, including every validation error |

GitHub Actions (`.github/workflows/ci.yml`) runs the backend checks against a Postgres 17 service, plus the frontend lint, format, typecheck and build.

## Deploy

A single Docker image (`Dockerfile`) builds the React app and serves it from Django with WhiteNoise. The API and the app share an origin, so no CORS setup is needed. `render.yaml` is a Render Blueprint that creates the web service and a managed Postgres.

1. Push the repo to GitHub.
2. In Render, choose **New → Blueprint** and pick the repo. Render reads `render.yaml` and creates `stormlane` (web) and `stormlane-db` (Postgres), with `DATABASE_URL` and a generated `SECRET_KEY` already wired.
3. Optional: set `TOMTOM_API_KEY` on the web service for truck routing.
4. Wait for the first deploy. `start.sh` runs `migrate` and `createcachetable` on every start (both are idempotent), then gunicorn.
5. Open `https://<service>.onrender.com`, check that `/api/health` returns `{"status":"ok"}`, and run the example trip.
6. **For reviewers, upgrade the web service from Free to a paid instance.** Free instances sleep when idle and take 30–60 s to wake. The frontend pings `/api/health` on load to start that wake-up early. Render's free Postgres also expires after a limited period, so upgrade it too if the demo must stay up.
7. Put the URL in the "Live app" line at the top of this README.

## What I'd do next

- Model hours of service (11 h driving, a 30 min break after 8 h, 10 h off), so ETAs on long trips account for mandatory stops.
- Replace OSRM's car profile with a self-hosted truck profile, or require a TomTom key, so bridge heights and weight limits shape the routes too.
- Suggest a departure time that minimises the ranking key: compare the same routes across the 48 h window and say "leave 3 h later to avoid 40 Severe miles".
- Use gusts as a secondary factor for high-profile empty trailers, which are more sensitive to gusts than loaded ones.
- Add a small Playwright suite for the map interactions and the heatmap's zero-request check. They are verified by scripts today, not in CI.
