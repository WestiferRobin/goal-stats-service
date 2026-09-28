# GoalStats monolith and RoadToTheFinal

One Flask/Gunicorn application hosts the football model, JSON API, CSV import,
backtests, tournament simulator and optional live-provider adapter. PostgreSQL
owns teams, imported history and saved match snapshots. Redis remains optional.
No other GoalStats service or sibling repository is needed at runtime.

The source was `frontend/RoadToTheFinal/{app,live_feed}.py` and its three CSVs
at revision `8f17bc42e30f436f5cd860f2791695421160ccd2`.
The model was extracted without Flask, sessions, template rendering or import-time
network/file writes. Existing Item/Action routes remain available for compatibility.
The directory and Compose project keep their existing names so local volumes and
workspace tooling continue to work; this is now the backend application, not a
requirement to scaffold more microservices.

## Start and import

```sh
make providers
make build
make migrate
PYTHONPATH=src .venv/bin/python -m football.import_data
.venv/bin/python src/main.py
```

The three source CSVs live in the project-root `data/` folder. Both host and
container importers use that folder by default, independently of the working
directory. The SQL exporter reads the same files.

The host importer uses the same private `.env.local` settings as direct startup.
It validates all three files before writing and commits the batch atomically.
Repeated imports preserve existing rows. To use another directory, pass it as the
positional argument; it must contain `teams.csv`, `match_history.csv` and
`historical_snapshots.csv`. File order is part of imported record identity.

In a configured container, `flask --app main:create_app import-football` imports
the bundled files; `--directory /path/to/csvs` selects another set. Startup never
runs migrations or imports automatically. [SQL alternatives](../../sql/README.md)
cover fresh databases, existing template upgrades and repeatable seed data.

## Frontend contract

Swagger is at `/swagger`; football routes use `/api/v1`. JSON field names are
snake_case. Validation failures return 400 Problem Details; unknown teams or
snapshots return 404. POST bodies must be JSON objects.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/teams` | Team ratings and ranking metadata |
| POST | `/api/v1/predictions` | Stateless prediction from supplied match state |
| POST | `/api/v1/snapshots` | Persist state and prediction; returns 201 + Location |
| GET | `/api/v1/snapshots/{id}` | Retrieve a saved prediction |
| GET | `/api/v1/snapshots?team1=Spain&team2=England` | Saved timeline, newest first |
| GET | `/api/v1/history` | Imported completed matches and historical snapshots |
| GET | `/api/v1/insights?team1=Spain&team2=England` | Head-to-head and team history from CSV |
| GET | `/api/v1/backtests` | Pregame/available snapshot comparison against labeled winners |
| POST | `/api/v1/tournaments/simulate` | Monte Carlo bracket in supplied team order |
| POST | `/api/v1/live/refresh` | Explicit API-Football refresh, or labeled cached fallback |

History and timeline accept `limit` (1–200, default 50) and `offset` (default 0).
Saved snapshots are shared match records, not private user sessions.

```js
const response = await fetch('/api/v1/predictions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    team1: 'Spain', team2: 'England', minute: 65,
    team1_stats: { goals: 1, shots: 8, shots_on_target: 4, possession: 60 },
    team2_stats: { goals: 0, shots: 5, shots_on_target: 2, possession: 40 }
  })
});
if (!response.ok) throw new Error(`Prediction failed: ${response.status}`);
const prediction = await response.json();
```

React can use a same-origin `/api` proxy. Wix can call the same API from its server
code. The backend does not choose, deploy or alter either frontend. Direct browser
calls across origins require deployment-specific CORS/proxy configuration; no
wildcard CORS policy is enabled here.

`probabilities` and `advancement` are fractions totaling 1. `momentum_percent` and
confidence are percentages. `expected_goals_remaining` means additional goals,
not the final expected score. Scores and top scorelines retain the original
Poisson model. Statistics default to zero and possession to 50/50; supplied
possession must total 100. `extra_minute`, `status`, cards, goalkeeper saves,
blocked shots, corners, big chances and bounded manual `modifiers` are supported.

Tournament body: `{"teams":["Spain","England","France","Germany"],"simulations":1000}`.
Use 4, 8, 16 or 32 distinct teams, and 1,000–2,000 simulations. Results use percent.
The original semifinal counter was corrected to count each team once per stage.

For live refresh, send `{"team1":"Spain","team2":"England"}`. Supply
`API_FOOTBALL_KEY` in the server process environment (or container secret injection),
not `.env.local` or frontend code. Provider calls occur only on explicit refresh.
Fresh results are stored in PostgreSQL; failures return the latest previously real
update with `source: "cached"` and its original `observed_at`, or 503 if none exists.
Cached reads do not create new timeline entries. No demo stats are substituted.
Provider team matching requires exact normalized names; aliases need an explicit
mapping if the provider's names differ. Production provider access has not been
verified with a real key by this change.

## Data and model limits

Bundled data has 32 teams, 13 completed matches, and 3 unlabeled snapshots. Completed
matches have final outcomes but no in-match snapshots; the three snapshots have no
known final outcome. Backtests therefore report 13 pregame evaluations, zero
labeled snapshot evaluations, and three skipped unlabeled rows. Final scores never
enter the historical prediction inputs. Historical rows lack dates, so insights
return CSV order and do not claim to represent recent form. The original external
H2H/recent-form JSON file cache is replaced here with imported historical insights.

Ratings and formulas are heuristic source data, not recalibrated or independently
verified forecasts. The source model retains a small remaining-goal floor at and
after minute 90; status strings do not turn probabilities into settled outcomes.
The extracted engine and historical/live mappers retain the source's dynamic Python
types; the new request, persistence and service boundaries are typed and validated.

## Verification

`make check`, `.venv/bin/python -m pytest tests/unit`, and `make integration` cover
format/types, probability invariants, validation, data leakage, stage counting,
repeatable imports, shared live fallback, persistence and migration/model agreement.
Integration tests run only against automatically owned disposable TEST providers.
