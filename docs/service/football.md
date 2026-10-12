# GoalStats monolith and RoadToTheFinal

One Flask/Gunicorn application hosts the football model, JSON API, CSV import,
backtests, tournament simulator and optional live-provider adapter. PostgreSQL
owns teams, imported history and saved match snapshots. Redis remains optional.
No other GoalStats service or sibling repository is needed at runtime.

The model came from the historical RoadToTheFinal `app.py`, `live_feed.py`, and
three CSV datasets at revision `8f17bc42e30f436f5cd860f2791695421160ccd2`.
The model was extracted without Flask, sessions, template rendering or import-time
network/file writes. RoadToTheFinal routes remain supported; Item/Action routes are retired.
The directory and Compose project keep their existing names so local volumes and
workspace tooling continue to work; this is now the backend application, not a
requirement to scaffold more microservices.

## Startup and explicit imports

```sh
make setup
make run
```

`make run` starts host Flask; `make deploy` starts Docker Flask. Both apply the same
migrations through one-off Docker app commands before startup. Neither imports datasets.
Existing records remain available; fresh databases contain no historical or prototype
records. Stop host Flask before repeating `make run` or switching
to `make deploy`. `make infra` starts providers only and does not import.

The three source CSVs live in the project-root `data/prototype/` folder. Both host and
container importers use that folder by default, independently of the working
directory. The SQL exporter reads the same files.

The explicitly invoked prototype importer validates all three files before writing and commits the batch
atomically. File order is part of imported record identity. Maintainers can run the
Flask `import-football` command inside the application container for a nonstandard
data directory. [SQL alternatives](../../sql/README.md) are advanced reference only.

## Frontend contract

Swagger is at `/swagger`; football routes use `/api/v1`. JSON field names are
snake_case. Validation failures return 400 Problem Details; unknown teams or
snapshots return 404. POST bodies must be JSON objects.

The following routes are the retained prototype compatibility API. Their ratings and
history come from prototype tables, not the verified historical catalog.

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
`API_FOOTBALL_KEY` in `.env.local`, never frontend code. Provider calls occur only on explicit refresh.
Fresh results are stored in PostgreSQL; failures return the latest previously real
update with `source: "cached"` and its original `observed_at`, or 503 if none exists.
Cached reads do not create new timeline entries. No demo stats are substituted.
Provider team matching requires exact normalized names; aliases need an explicit
mapping if the provider's names differ. Production provider access has not been
verified with a real key by this change.

## Normalized Goal Stats APIs

Historical catalog routes under `/api/v1/catalog/teams`, `/api/v1/catalog/competitions`
and `/api/v1/catalog/matches` use `teams`, `competitions` and `matches`.
Scenario creation/list/detail routes under `/api/v1/scenarios` persist user-supplied
state. Scenario prediction creation/history and `/api/v1/predictions/{prediction_id}`
provide saved predictions. See `/swagger` for request and response contracts.
These APIs coexist with prototype compatibility routes; the original prediction engine
and calculations remain unchanged. Historical results do not supply prototype ratings.

## Data and model limits

Bundled prototype data has 32 teams, 13 historical-result-shaped rows, and 3 unlabeled
snapshots; these are not independently verified historical matches. Completed
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

`make test` covers format/types, probability invariants, validation, data leakage, stage counting,
repeatable imports, shared live fallback, persistence and migration/model agreement.
Integration tests run only against automatically owned disposable TEST providers.


## Historical catalog status

The [normalized catalog](historical-catalog.md) and [pinned dataset contract](../../data/README.md)
prepare real 2023 Women's World Cup records for `teams`, `competitions`, and `matches`.
Local acceptance completed on **2026-10-08 (America/Los_Angeles)**: the catalog contains
32 teams, one competition and 64 verified historical matches. Reimport and restart
preserved every record. Normalized catalog, scenario and prediction APIs coexist
with prototype compatibility APIs. Historical ratings remain NULL. The nine-edition
importer expansion does not change API contracts or prediction calculations.
See [Task #2 evidence](task2-acceptance.md) for actual counts, SQL/API results and safety checks.


## Historical import operations

The no-option `import-football` command remains the prototype importer. The historical
path requires all of `--dataset`, `--directory`, `--target`, `--expect-host`, and
`--expect-database`. The explicitly supplied directory contains the pinned
`results.csv`; `--dry-run` performs read-only comparison. Historical safety/dry-run
flags without `--dataset` are rejected. No new Make command or REST route exists.

The supported IDs are `womens-world-cup-1991`, `womens-world-cup-1995`,
`womens-world-cup-1999`, `womens-world-cup-2003`, `womens-world-cup-2007`,
`womens-world-cup-2011`, `womens-world-cup-2015`, `womens-world-cup-2019`, and
`womens-world-cup-2023`. Each resolves a checked-in manifest plus typed approval
metadata, and all share the same pinned CSV and exact full-file checksum.

For a configured host environment, an explicit read-only invocation is:

```bash
flask --app 'main:create_app()' import-football \
  --dataset womens-world-cup-1991 \
  --directory data/raw/martj42-womens-results/1855e313ae8bcd0330426e62c8e4cf15ce45077c \
  --target local --expect-host 127.0.0.1 --expect-database goal_stats_service_local \
  --dry-run
```

Without `--dry-run`, a separately authorized invocation writes one edition in one
atomic transaction. Duplicate input fixtures or conflicting stored facts abort;
unchanged repeat imports insert zero rows and preserve provenance/timestamps.
No historical import falls back to prototype inputs or writes prototype tables.
The expansion has not imported additional editions into persistent PostgreSQL.
Source ordering and venue limitations remain; no prediction ratings are supplied.

Local authorization requires `goalstats` and `goal_stats_service_local` at either
`postgres:5432` (Docker) or `127.0.0.1:55432` (host). The configured URL must exactly
match both expected flags, and the active driver hostname/database/user are checked
on the import connection. `--target local` cannot authorize an arbitrary endpoint.
For a custom local host port, use the Docker procedure below, whose internal port
remains 5432. Tests use explicit `--target test`, restricted to a local
`goalstats_test_*` database; this label does not provision or reset any database.

Run the following from the repository root when explicitly importing or repeating
local acceptance. This procedure has been verified against the existing Compose
project and PostgreSQL volume. The current catalog is already populated; repeating
the pinned import should report zero inserts and 64 unchanged matches.

```bash
set -e
make infra

gs_compose() {
  docker compose --env-file .env.local -p goalstats-service-local \
    -f docker/compose.local.yml "$@"
}
gs_compose build app

# Validate the configured target and connected database before applying migrations.
gs_compose run --rm --no-deps -T app python - <<'PYTHON'
from sqlalchemy import text
from infra.resources.db import Database
from settings.database import ImportTarget
from settings.environment import load_application

db = Database(load_application().database)
target = ImportTarget("local", "postgres", "goal_stats_service_local")
try:
    target.validate(db.engine.url)
    with db.engine.connect() as connection:
        assert connection.connection.driver_connection.info.host == target.expect_host
        assert connection.scalar(text("SELECT current_database()")) == target.expect_database
        assert connection.scalar(text("SELECT current_user")) == "goalstats"
    print("Local target verified; no data changed.")
finally:
    db.dispose()
PYTHON

gs_compose run --rm --no-deps -T app alembic upgrade head

# Reuse the ignored pinned source, or explicitly acquire it if absent.
# Verify the full file before use; never overwrite an existing source.
IMPORT_INPUT="$PWD/data/raw/martj42-womens-results/1855e313ae8bcd0330426e62c8e4cf15ce45077c"
mkdir -p "$IMPORT_INPUT"
export IMPORT_INPUT
PYTHONPATH=src .venv/bin/python - <<'PYTHON'
import os
import urllib.request
from pathlib import Path
from football.historical_dataset import load_manifest, validate_checksum

manifest = load_manifest()
url = manifest.source_url.replace("https://github.com/", "https://raw.githubusercontent.com/")
url = url.replace("/blob/", "/")
source = Path(os.environ["IMPORT_INPUT"]) / manifest.source_filename
if source.exists():
    validate_checksum(source.read_bytes(), manifest)
else:
    with urllib.request.urlopen(url, timeout=60) as response:
        content = response.read()
    validate_checksum(content, manifest)
    source.write_bytes(content)
print("Pinned CSV checksum verified.")
PYTHON

historical_import() {
  gs_compose run --rm --no-deps -T -v "$IMPORT_INPUT:/input:ro" app \
    flask --app 'main:create_app()' import-football \
    --dataset womens-world-cup-2023 --directory /input \
    --target local --expect-host postgres \
    --expect-database goal_stats_service_local "$@"
}
historical_import --dry-run
historical_import
historical_import --dry-run
historical_import

# Verify source-specific counts and joined relationships.
gs_compose exec -T postgres psql -X -v ON_ERROR_STOP=1 \
  -U goalstats -d goal_stats_service_local <<'SQL'
SELECT source, count(*) AS matches, count(DISTINCT competition_id) AS competitions
FROM matches WHERE source = 'martj42_womens_results' GROUP BY source;
SELECT count(DISTINCT team_id) AS teams FROM (
  SELECT home_team_id AS team_id FROM matches WHERE source = 'martj42_womens_results'
  UNION
  SELECT away_team_id FROM matches WHERE source = 'martj42_womens_results'
) AS participants;
SELECT m.match_date, h.name AS home_team, a.name AS away_team,
       m.home_score, m.away_score, c.name AS competition, c.edition_label,
       m.score_basis, m.neutral, m.city, m.country
FROM matches m
JOIN teams h ON h.team_id = m.home_team_id
JOIN teams a ON a.team_id = m.away_team_id
JOIN competitions c ON c.competition_id = m.competition_id
WHERE m.source = 'martj42_womens_results'
ORDER BY m.match_date, m.match_id;
SQL
make test
```

Stop at any nonzero exit; do not continue to an import after failed target validation,
migration, download or dry-run. For an initially empty catalog, the first dry-run
proposes 32 teams, one competition and 64 matches. The first successful write reports
those committed inserts; both subsequent runs report 64 unchanged matches and zero
inserts. A populated catalog may legitimately require fewer new teams/competitions.
Expected SQL counts are 64 matches, 32 participating teams and one competition.
Compare IDs, `imported_at` and legacy table counts before/after an authorized reimport.
When Flask is running, `/api/v1/teams` and existing prediction endpoints should retain
their prototype contract. Normalized historical records are served separately through
`/api/v1/catalog/teams`, `/api/v1/catalog/competitions` and `/api/v1/catalog/matches`.

For a host command, explicitly supply the validated local host `DATABASE_URL` through
the process environment and use `--expect-host 127.0.0.1` with the same database name.
The Flask factory does not automatically read `.env.local` or derive a URL.
Never print the URL in terminal diagnostics.

### Cloud one-off import

Use the same application image as a one-off job, with an input volume and deployment
secrets supplying `DATABASE_URL`. Do not use the local Compose file for cloud imports.
The URL must specify `sslmode=verify-full` and `sslrootcert` (an absolute mounted CA
path, or `system`). Optional client authentication requires both absolute `sslcert`
and `sslkey` paths. Mount certificates read-only and restrict private-key permissions.
The database also verifies the active connection is TLS-protected.

Example command **inside** the deployment's configured application container:

```bash
FLASK_SKIP_DOTENV=1 flask --app 'main:create_app()' import-football \
  --dataset womens-world-cup-2023 --directory /input \
  --target cloud --expect-host "$EXPECTED_DATABASE_HOST" \
  --expect-database "$EXPECTED_DATABASE_NAME" \
  --confirm-production --dry-run
```

Use the deployment's verified target and explicit migration job before this command.
After reviewing the dry-run, invoke the same command without `--dry-run` to write.
Both modes require production confirmation. `APP_ENV` continues to accept the
existing local/dev/test application profiles; it never authorizes an import or relaxes
cloud safeguards. No cloud URL, credential, certificate or deployment was created by
this implementation. Missing URL/TLS/confirmation fails closed, with no local fallback
or `.env.local` read. Cloud authorization is covered by tests without a real cloud DB;
a provider-specific TLS/deployment smoke test remains an operational acceptance step.

See [dataset behavior and recovery](../../data/README.md#historical-import-behavior)
for idempotency, conflict policy, rollback and JSON summary semantics.


### Read-only SQL and persistence verification

The checked-in script prints database/revision identity, catalog and source counts,
all joined historical results, duplicate/orphan checks, legacy counts and a stable
source-record digest. It runs in a read-only transaction:

```bash
docker compose --env-file .env.local -p goalstats-service-local \
  -f docker/compose.local.yml exec -T postgres \
  psql -X -v ON_ERROR_STOP=1 -U goalstats -d goal_stats_service_local \
  < sql/verify_historical_import.sql
```

Before a persistence check, stop host Flask using Ctrl-C in its own terminal. Use
`make stop`, then `make infra`, and repeat the SQL script. Never remove the volume.
Acceptance retained volume `goalstats-service-local_postgres-data`, all table digests,
and representative match IDs 1, 32 and 64. Start host Flask again with `make run`
when API access is needed. The completed acceptance leaves PostgreSQL/Redis healthy
and host Flask stopped.

Cloud configuration safeguards passed automated tests, but no cloud database was
contacted: **CLOUD RUNTIME: UNVERIFIED**. Local certification does not certify cloud
networking, provider credentials or certificate deployment.


## Startup isolation

`make run` and `make deploy` apply existing Alembic migrations and start Flask without
importing any dataset. Existing records are preserved; fresh catalogs are empty.
The explicit prototype compatibility importer and guarded historical importer remain
available independently of startup, readiness and the application factory.
The existing `/demo` depends on prototype teams/ratings and may be unusable on a fresh
database until prototype data is explicitly supplied or the frontend is migrated.
Prototype examples are not verified historical facts. Historical seeding is available through the explicit `make seed` command.


The SQL verification command defaults to current partial coverage. Complete nine-edition
acceptance is explicitly selected with `goalstats.verify_complete=true`; it is expected
to fail until all approved editions are imported. See [SQL verification modes](../../sql/README.md#read-only-historical-acceptance)
for target assertions and full-record preservation digests. Prototype compatibility SQL
now lives at `sql/prototype/003_seed_football.sql`; it is never historical seed data.

## Explicit historical seeding

`make seed DATASET=womens-world-cup DRY=true` previews all nine editions.
Use `DRY=false` to write, or select an individual ID such as `womens-world-cup-2023`.
Omitted `DRY` means `false`; empty/other values and legacy `DRY_RUN` are rejected.
Contracts remain in `data/womens-world-cup/`, with pinned source in `data/raw/`.
The command requires prepared infrastructure and schema; it never starts services,
migrates or selects prototype data. Each edition commits separately, so earlier
commits survive later failure and unchanged imports can be safely retried. Dry-run
team estimates are edition-local, not additive. Startup imports nothing.
See [seed prerequisites, safeguards and reporting](../interface/make.md#explicit-historical-seeding) for the full contract.
