# GoalStats monolithic backend

Python 3.12, Flask/Gunicorn, PostgreSQL/SQLAlchemy/Alembic, Redis,
Pydantic/flask-openapi3 and pytest. RoadToTheFinal football predictions, history,
live updates and tournaments run in this application with one database.
Item + Action remain compatibility routes. Source CSV datasets live in `data/`.
Flat `src/`; factory: `main:create_app()`; one pinned `requirements.txt`.

See the [football API and import guide](docs/service/football.md) and
[standalone SQL scripts](sql/README.md). The same API supports React or Wix server code.

## First time: host / IDE development

Install **Python 3.12, GNU Make and Docker with Compose**. Start Docker Desktop
on macOS. From the repository root:

```sh
make help
make setup
make doctor
make providers
make migrate
PYTHONPATH=src .venv/bin/python -m football.import_data
.venv/bin/python src/main.py
```

Setup creates/reuses `.venv`, installs/verifies requirements and creates private,
ignored `.env.local` (machine configuration) and `.env.test` (TEST policy only).
It preserves existing credentials and valid installations. It never starts the
normal application or migrates its database. Existing legacy configuration may
require a brief PostgreSQL authentication check before safe migration.

Providers starts only PostgreSQL and Redis. Migrate starts providers if necessary
and builds a missing runtime image automatically. Neither command starts Flask.

Open **<http://127.0.0.1:5300/swagger>**. `/health` checks liveness; `/ready` checks
providers and schema. Startup never migrates automatically.

**PyCharm:** select `.venv/bin/python`, open `src/main.py`, click Run/Debug.
**VS Code:** select `.venv`, choose **Flask: host LOCAL**, press F5.
No environment profile, env-file setting or manual URLs are needed. `src/` as a
Sources Root is optional editor assistance. The direct entrypoint works from the
root or `src/` directory, binds loopback, and disables Flask debugger/reloader.

## Daily development

```sh
make providers
# IDE Run/Debug src/main.py, or:
.venv/bin/python src/main.py
```

Host source edits need an application restart. After dependency changes, run
`make setup` and `make build`. After migration changes, run `make build` then
`make migrate`: an existing image is reused until explicitly rebuilt.

To stop: stop the application in the IDE or with Ctrl-C, then:

```sh
make providers-stop
```

PostgreSQL data persists. Redis is disposable cache data. Never delete a database
volume to repair a password mismatch; restore its original configuration.

## Tests and quality

```sh
.venv/bin/python -m pytest tests/unit  # fast feedback, no Docker/providers/env files
make check                           # lint, format check, strict mypy
make integration                     # automatic owned disposable TEST providers
make test                            # unit + integration
```

`make unit` provides containerized unit verification. `make coverage` reports full
application coverage; `make tooling` tests workflow code. For individual IDE
integration tests, leave `make test-providers` running in a terminal; stop it with
Ctrl-C afterward. Never point destructive tests at LOCAL/DEV providers.

Before a release/template change: `make smoke`, `make certify-host`, and
`make certify`. These heavier checks create and clean isolated resources; they do
not replace quick unit feedback. `make migration-check` checks model/schema drift.
Schema authors use `make migration MESSAGE="description"` and review the result.

## Docker application alternative

```sh
make build
make migrate
make run
make logs
make stop
```

LOCAL uses mounted source/reload at <http://127.0.0.1:5100/swagger>. Add `ENV=dev`
to these commands for built non-root Gunicorn at <http://127.0.0.1:5200/swagger>.
DEV has separate credentials/data and no source mount; rebuild after source edits.
Both modes use `.env.local`. `stop` removes selected containers/network but keeps
PostgreSQL data. `ENV=local` is the default, not required typing.

## Troubleshooting and reference

Run `make doctor` for read-only interpreter, dependencies, Docker, configuration
and port checks. Stop a running host app before checking its port availability.
Change machine ports/preferences only in private `.env.local`; defaults are host
5300, Docker LOCAL 5100, DEV 5200, PostgreSQL 55432 and Redis 56379.

`make help` discovers commands; this README owns onboarding; [docs](docs/README.md)
explain [architecture](docs/service/architecture.md), [configuration](docs/service/environment.md),
[Make behavior](docs/interface/make.md), [testing](docs/testing/overview.md) and
[certification](docs/testing/certification.md). No workflow stages, commits or pushes.
