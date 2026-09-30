# GoalStats monolithic backend

Python 3.12, Flask/Gunicorn, PostgreSQL/SQLAlchemy/Alembic, Redis,
Pydantic/flask-openapi3 and pytest. RoadToTheFinal football predictions, history,
live updates and tournaments run in this application with one database.
Item + Action remain compatibility routes. Source CSV datasets live in `data/`.
Flat `src/`; factory: `main:create_app()`; one pinned `requirements.txt`.

See the [football API and import guide](docs/service/football.md) and
[standalone SQL scripts](sql/README.md). The same API supports React or Wix server code.

## Run locally

Install **Python 3.12, GNU Make and Docker with Compose**, then start Docker Desktop.
Open a terminal in `backend/template-goalstats-service` (the directory containing
this README and `Makefile`). You do not need to run the RoadToTheFinal app, React,
or Wix to use this backend.

Check that the tools are available:

```sh
python3.12 --version
docker compose version
make --version
```

The scripts use a Unix-style environment (macOS/Linux). Python must be **3.12**;
`python3` pointing to a different version is not sufficient. Initial setup needs
internet access to download Python dependencies and Docker images.

Then run:

```sh
make dev
```

This sets up `.venv` and private configuration, starts PostgreSQL/Redis, applies
LOCAL database migrations, imports the root `data/` CSVs, and runs the host app.
Open **<http://127.0.0.1:5300/swagger>** (or your configured host port).
Use the same command on subsequent runs. Existing credentials and data are preserved;
repeat imports do not overwrite existing records. The command stops if preparation fails.
No Docker application image build is needed for this host workflow.

| Task | Command |
| --- | --- |
| Set up and run locally | `make dev` |
| Prepare everything, then run/debug in an IDE | `make init` |
| Import CSV data into an already migrated LOCAL database | `make seed` |
| Fast tests without Docker | `make quick-test` |
| Lint, formatting and types | `make check` |
| Full unit and database integration tests | `make test` |
| Diagnose local setup | `make doctor` |
| Show all commands | `make help` |

Stop the host app with **Ctrl-C**, then stop providers with:

```sh
make providers-stop
```

PostgreSQL data persists. Restart `make dev` after source changes; the host process
does not auto-reload. `make dev` / `make init` explicitly migrate and seed; importing
or starting the Flask application directly still does neither automatically.

**PyCharm / VS Code:** run `make init`, select `.venv/bin/python`, and Run/Debug
`src/main.py`. Stop any existing host app before starting another on the same port.
These shortcuts use LOCAL configuration and reject `ENV=dev`.

Live-provider calls additionally require `API_FOOTBALL_KEY` in the server environment.
CSV-based predictions need no external key. See the [football guide](docs/service/football.md).

## Verify your first run

Leave the terminal running. In [Swagger](http://127.0.0.1:5300/swagger), expand
an endpoint, click **Try it out**, and then **Execute**:

1. `GET /api/v1/teams` should return `200` and **32 teams** from the bundled CSV.
2. `POST /api/v1/predictions`: replace the example body with:

   ```json
   {"team1": "Spain", "team2": "England", "minute": 0}
   ```

   Expect `200` with `probabilities`, `advancement`, and `top_scorelines`.
   Win/draw/loss probabilities are fractions totaling 1.
3. `GET /api/v1/backtests` should report **13 evaluated** and **3 skipped_unlabeled**
   for the bundled data. These counts confirm the import, not model accuracy.

A `200` with an empty list or `evaluated: 0` means the request worked but the
football data is missing. Run `make seed` in a second terminal and Execute again.
`GET /health` checks the process; `GET /ready` checks providers and schema, not seed data.

`POST /api/v1/live/refresh` is optional. It requires a separately supplied
`API_FOOTBALL_KEY` and a currently live matching fixture. A `503` can mean no key,
provider failure, or no matching live fixture and no prior real result to return.
`source: "cached"` is an older stored update; only `source: "real"` is fresh data.
The key is not included in Git or the CSV files, and `.env` is not auto-loaded.

## Where to work

| Location | What it contains |
| --- | --- |
| `src/routers/football.py` | Football HTTP routes |
| `src/schemas/football.py` | Request validation and prediction response contract |
| `src/services/football.py` | Predictions, history, snapshots and backtests |
| `src/football/` | Prediction model, CSV importer and live-provider adapter |
| `src/models/football.py` | PostgreSQL table models |
| `data/` | `teams.csv`, `match_history.csv`, `historical_snapshots.csv` |
| `alembic/versions/` | Versioned database migrations |
| `sql/` | Alternative SQL setup/seed scripts and instructions |
| `tests/` | Application unit, integration and smoke tests |
| `scripts/tests/` | Development-workflow tests |

`make seed` adds missing records; it does **not** overwrite existing ratings/history.
Editing a CSV then reseeding will not update an already imported row. Imported history
uses filename + row number as identity; keep existing row order stable.

## Tests and quality

```sh
make quick-test                      # fast feedback, no Docker/providers/env files
make check                           # lint, format check, strict mypy
make integration                     # automatic owned disposable TEST providers
make test                            # unit + integration
```

`make unit` provides containerized unit verification. `make coverage` reports full
application coverage; `make tooling` tests workflow code. For individual IDE
integration tests, leave `make test-providers` running in a terminal; stop it with
Ctrl-C afterward. Never point destructive tests at LOCAL/DEV providers.

Before a release or infrastructure change: `make smoke`, `make certify-host`, and
`make certify`. These heavier checks create and clean isolated resources; they do
not replace quick unit feedback. `make migration-check` checks model/schema drift.
Schema authors use `make migration MESSAGE="description"` and review the result.

## Docker application alternative

```sh
make init
make build
make run
make logs
make stop
```

This example prepares and seeds LOCAL before switching to the Docker app.
Do not run the host app at the same time. `make run` alone does not migrate or seed.

LOCAL uses mounted source/reload at <http://127.0.0.1:5100/swagger>. Advanced Docker commands (`build`, `migrate`, `run`, `logs`, `stop`)
also accept `ENV=dev` for built non-root Gunicorn at <http://127.0.0.1:5200/swagger>.
DEV has separate credentials/data and no source mount: run `make build ENV=dev`,
`make migrate ENV=dev`, then `make run ENV=dev`. LOCAL seed data is not copied to DEV;
see the [container import instructions](docs/service/football.md#start-and-import).
Rebuild after source edits.
Both modes use `.env.local`. `stop` removes selected containers/network but keeps
PostgreSQL data. `ENV=local` is the default, not required typing.

## Troubleshooting and reference

| Symptom | What to do |
| --- | --- |
| `python3.12` not found | Install Python 3.12 and ensure that executable is on your PATH. |
| Cannot connect to Docker | Start Docker Desktop, wait until it is running, then retry `make dev`. |
| `make` cannot find `dev` | Change into this service directory, not the workspace or frontend directory. |
| Port 5300 is occupied | Stop the other terminal/IDE app, or change `HOST_APP_PORT` in `.env.local`. |
| Full LOCAL Docker app is active | Run `make stop` before switching to `make dev` or `make init`. |
| Empty teams/backtests | Run `make seed` after migrations; refresh the Swagger request. |
| Missing tables or database unavailable | Stop the host app and run `make dev` to prepare providers and schema. |
| PostgreSQL password mismatch | Restore the original `.env.local` credentials; do not delete the volume. |
| Live refresh returns 503 | Check the server key and live fixture availability; CSV predictions remain usable. |
| Browser cannot connect | Keep `make dev` running and use its printed Swagger URL. |

Run `make doctor` for read-only interpreter, dependencies, Docker, configuration
and port checks. Stop a running host app before checking its port availability.
Change machine ports/preferences only in private `.env.local`; defaults are host
5300, Docker LOCAL 5100, DEV 5200, PostgreSQL 55432 and Redis 56379.

`make help` discovers commands; this README owns onboarding; [docs](docs/README.md)
explain [architecture](docs/service/architecture.md), [configuration](docs/service/environment.md),
[Make behavior](docs/interface/make.md), [testing](docs/testing/overview.md) and
[certification](docs/testing/certification.md). No workflow stages, commits or pushes.
