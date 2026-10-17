# GoalStats backend

Goal Stats has two repositories:

- `goal-stats-app` is the website users interact with.
- `goal-stats-service` is everything behind the website: the API, football logic,
  database access, migrations, and explicit data import tooling.

The simple request flow is: browser → `goal-stats-app` → `goal-stats-service` →
database and football logic. This repository is `goal-stats-service`.

For production Docker deployment, see the [Render deployment guide](docs/service/render.md).

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
starts database/cache, applies migrations, then launches host
Flask in the foreground using `.venv`. Ctrl-C stops Flask and leaves providers running.
Restart after source edits; automatic host reload is disabled for predictable debugging.

Open <http://127.0.0.1:5100/swagger>. Verify `/health` and `/ready` return `Healthy`,
and inspect `/api/v1/teams` (empty on a fresh database). Then start
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
This builds the app, starts providers, applies migrations, and waits for API readiness.
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
| `make seed DATASET=… DRY=true` | Preview approved historical imports; omit DRY or use false to write. |
| `make test` | Lint, format-check, type-check, and run isolated unit/integration tests. |
| `make stop` | Stop Docker resources and preserve PostgreSQL data. |
| `make help` | Explain these nine commands. |

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
root. Existing VS Code app launch settings use this entrypoint. To prepare providers and schema
for an IDE session, run `make run`, stop Flask, then launch the IDE debugger. On subsequent
sessions with an already prepared database, `make infra` is enough before IDE Run.
See [development details](docs/service/development.md) and
[configuration rules](docs/service/environment.md).

## Where to work

| Location | Purpose |
| --- | --- |
| `src/routers/football.py` | Flask football/API endpoints |
| `src/schemas/` | Five normalized entity contracts and shared engine contracts |
| `src/services/football.py` | Football application logic |
| `src/football/` | Prediction model, import, and provider adapter |
| `src/models/` | Five normalized Goal Stats models |
| `alembic/versions/` | Database migrations |
| `data/` | Prototype compatibility inputs, approved manifests, ignored raw sources and verification evidence |
| `tests/` | Unit and integration tests |

See [docs](docs/README.md) for architecture and internal maintenance details.

## Common first-run errors

- Docker connection error: start Docker Desktop and wait for it to finish starting.
- `make` not found: install GNU Make and reopen the terminal.
- Port already allocated: stop an older Goal Stats instance and retry.
- Password failure after editing configuration: restore the original password because
  the persistent database retains its original credential.
- Empty football results: fresh databases contain no historical or prototype records.
  Restarting Flask does not populate them; dataset imports require an explicit operation.
  Existing records remain available after startup.

## Verification and schema changes

`make test` is the standard automated verification command. It runs Ruff lint and
format checks, strict mypy, and maintained unit, integration, tooling and ownership
tests against disposable PostgreSQL/Redis. It does not run separate smoke, coverage
or lifecycle certification modes.

Alembic retains the original revisions and adds guarded prototype retirement head
`d91e6a4b208f`. The final schema has five application tables. The new migration
refuses populated prototype tables and unexpected ownership/dependencies. Inventory,
verify backups and coordinate archival before any persistent upgrade; this phase
only verifies disposable resources. `make run` and `make deploy` apply migrations,
so do not use them as a workaround for a retirement refusal.

## Startup and empty databases

Flask construction does not migrate or seed. Local lifecycle commands prepare schema
explicitly. Fresh catalogs remain empty until an authorized historical import.
Production operations use normalized integer IDs and explicit prediction assumptions;
there is no prototype catalog, snapshot API or CSV fallback.

Approved manifests live in `data/womens-world-cup/`; source bytes stay in `data/raw/`.
The importer supports nine editions. Persistent development contents are unverified.
See [backend contracts](docs/service/frontend-api.md) and
[retirement safeguards](docs/service/football.md#persistence-retirement).

## Explicit historical seeding

`make seed DATASET=womens-world-cup DRY=true` previews all nine editions.
Use `DRY=false` to write, or select an individual ID such as `womens-world-cup-2023`.
Omitted `DRY` means `false`; empty/other values and legacy `DRY_RUN` are rejected.
Contracts remain in `data/womens-world-cup/`, with pinned source in `data/raw/`.
The command requires prepared infrastructure and schema; it never starts services,
migrates or selects prototype data. Each edition commits separately, so earlier
commits survive later failure and unchanged imports can be safely retried. Dry-run
team estimates are edition-local, not additive. Startup imports nothing.
See [seed prerequisites, safeguards and reporting](docs/interface/make.md#explicit-historical-seeding) for the full contract.
