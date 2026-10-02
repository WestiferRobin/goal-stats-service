# GoalStats backend

Goal Stats has two repositories:

- `goal-stats-app` is the website users interact with.
- `goal-stats-service` is everything behind the website: the API, football logic,
  database access, migrations, and starter data.

The simple request flow is: browser → `goal-stats-app` → `goal-stats-service` →
database and football logic. This repository is `goal-stats-service`.

## Start here

Install Git, Docker with Compose v2, and GNU Make. Use macOS, Linux, WSL, or native
Windows with Docker Desktop and Git for Windows installed in its standard location.
You do not need to install Python, PostgreSQL, or Redis.

Clone `goal-stats-app` and `goal-stats-service` side by side, start Docker, then
start this backend first:

From the directory containing this README:

```sh
make setup
make run
```

`make setup` creates `.env.local` from `.env.example` when missing and builds the
Docker images. It starts nothing and never replaces an existing `.env.local`.
`make run` starts the database/cache, applies migrations, imports bundled football
CSVs, and starts the API. These are automatic implementation details.

Open <http://127.0.0.1:5100/swagger>. Verify:

- `GET /health` returns `200` and `Healthy`.
- `GET /ready` returns `200` and `Healthy`.
- `GET /api/v1/teams` returns 32 teams.
Leave it running. In another terminal, follow the Start Here section in the
`goal-stats-app` README and open <http://127.0.0.1:3000/demo>.

| Command | Meaning |
| --- | --- |
| `make setup` | Prepare this repository for first use; start nothing. |
| `make run` | Start or restart the backend. |
| `make test` | Run normal contributor checks and tests. |
| `make stop` | Stop backend services without deleting saved data. |
| `make help` | Show the beginner commands. |

After source changes, repeat `make run`. Tests use disposable providers and cannot
touch the development database. Normal startup safely re-applies migrations and
imports only missing bundled records.

## Configuration

`.env.example` documents the only developer settings. `.env.local` is the ignored,
machine-local copy. Defaults work without editing. `API_FOOTBALL_KEY` is optional
and needed only for live-provider refresh.

If you change `APP_PORT`, use that port in the URLs above. Do not change
`POSTGRES_PASSWORD` after the database volume is created unless you intend to reset
that local database.

## Where to work

| Location | Purpose |
| --- | --- |
| `src/routers/football.py` | Flask football/API endpoints |
| `src/schemas/football.py` | Request and response validation |
| `src/services/football.py` | Football application logic |
| `src/football/` | Prediction model, import, and provider adapter |
| `src/models/football.py` | Database models |
| `alembic/versions/` | Database migrations |
| `data/` | Bundled source/seed CSV files |
| `tests/` | Unit and integration tests |

See [docs](docs/README.md) for architecture and internal maintenance details.

## Common first-run errors

- Docker connection error: start Docker Desktop and wait for it to finish starting.
- `make` not found: install GNU Make and reopen the terminal.
- Port already allocated: stop an older Goal Stats instance and retry.
- Password failure after editing configuration: restore the original password because
  the persistent database retains its original credential.
- Empty football results: confirm `make run` completed successfully and retry it.
