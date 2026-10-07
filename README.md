# GoalStats backend

Goal Stats has two repositories:

- `goal-stats-app` is the website users interact with.
- `goal-stats-service` is everything behind the website: the API, football logic,
  database access, migrations, and starter data.

The simple request flow is: browser → `goal-stats-app` → `goal-stats-service` →
database and football logic. This repository is `goal-stats-service`.

## Start here: backend development

**`make run` = host Flask + Docker PostgreSQL/Redis.**
**`make deploy` = Docker Flask + Docker PostgreSQL/Redis.**
Both use the same `.env.local`, database, cache configuration, migrations, and football data.

Install Git, GNU Make, Docker with Compose v2, and Python **3.12.x**.
Host development supports macOS, Linux, and WSL. On Windows, use WSL with Python
inside WSL and Docker available there; native Windows host Python is not supported.
Linux Python installations must include `venv` and pip. No host PostgreSQL or Redis
installation is required.

From the repository root with Docker running:

```sh
make setup
make run
```

`make setup` creates `.env.local` only when missing, prepares `.venv`, installs missing
or mismatched pinned dependencies, verifies them, and prepares Docker images. It starts
nothing and never replaces existing configuration or an incompatible venv. If Python
has a different executable path, use `make setup PYTHON=/path/to/python3.12` and the
same override for subsequent lifecycle commands.

`make run` validates host prerequisites, stops this project's Docker Flask if present,
starts database/cache, applies migrations, imports bundled CSVs, then launches host
Flask in the foreground using `.venv`. Ctrl-C stops Flask and leaves providers running.
Restart after source edits; automatic host reload is disabled for predictable debugging.

Open <http://127.0.0.1:5100/swagger>. Verify `/health` and `/ready` return `Healthy`,
and `/api/v1/teams` returns 32 teams on the bundled-data baseline. Then start
`goal-stats-app` following its README.

## Docker infrastructure only

```sh
make infra
```

Stops this project's Docker Flask and starts only PostgreSQL/Redis. It does not migrate
or import. Stop host Flask first if running; an occupied application port is refused.

## Local Docker deployment

```sh
make deploy
```

Deploy the complete backend locally in Docker. No cloud deployment.
This builds the app, starts providers, migrates/imports, and waits for API readiness.
The API remains at port 5100. Stop host Flask with Ctrl-C or IDE Stop before deploying.
To switch back to host development, use `make run`; it stops only Docker Flask.
Neither transition changes credentials or deletes data. Run lifecycle commands sequentially.

## Commands

| Command | Meaning |
| --- | --- |
| `make setup` | Prepare configuration, Python `.venv`, dependencies, and Docker images. |
| `make infra` | PostgreSQL + Redis only; stop Docker Flask. |
| `make run` | Run host Flask for backend development, in the foreground. |
| `make deploy` | Deploy the complete backend locally in Docker. No cloud deployment. |
| `make test` | Lint, format-check, type-check, and run isolated unit/integration tests. |
| `make stop` | Stop Docker resources and preserve PostgreSQL data. |
| `make help` | Explain these seven commands. |

`make test` needs Docker and Make, not the host venv or `.env.local`. Tests use
independently owned disposable providers. They never use the development database.

Stop host Flask with Ctrl-C or IDE Stop, then run `make stop` when finished.
`make stop` never kills host Python processes; a host process left running loses its
providers. PostgreSQL data remains for the next run/deployment.

## Configuration and IDEs

`.env.example` documents the one developer configuration. `.env.local` is its private,
ignored local copy. Do not maintain a second env file or export alternate database/cache
URLs. Conflicting inherited settings are rejected. `APP_PORT` changes the API port for
both workflows. Preserve `POSTGRES_PASSWORD` after volume creation; changing the file
does not rotate the stored database password.

Select `.venv/bin/python` in VS Code/PyCharm and run `src/main.py` from the repository
root. Existing VS Code app launch settings use this entrypoint. To prepare schema/data
for an IDE session, run `make run`, stop Flask, then launch the IDE debugger. On subsequent
sessions with an already prepared database, `make infra` is enough before IDE Run.
See [development details](docs/service/development.md) and
[configuration rules](docs/service/environment.md).

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
- Empty football results: confirm `make run` or `make deploy` completed successfully and retry it.
