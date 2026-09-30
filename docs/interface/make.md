# Public Make interface

Make is the stable developer interface; Python owns process/resource orchestration.
The root Makefile defines shared variables and includes these modules:

| Module | Commands |
| --- | --- |
| `install.mk` | `setup` |
| `doctor.mk` | `doctor` |
| `dev.mk` | `dev`, `init`, `seed`, `quick-test`, `providers`, `providers-stop`, `build`, `run`, `stop`, `logs` |
| `db.mk` | `migrate`, `migration`, `migration-check` |
| `test.mk` | `unit`, `integration`, `test`, `smoke`, `test-providers` |
| `coverage.mk` | `coverage` |
| `ci.mk` | `check`, `tooling`, `certify`, `certify-host` |

`make help` groups the interface. `ENV=local` is the default; runtime/database
commands accept `ENV=local|dev` and reject unknown values. TEST is internally managed.
`PYTHON=python3.12` can select the host interpreter. Application dependencies are
installed in `.venv` for host work and in Docker for containers from the one pinned `requirements.txt` using pip.

For new contributors, start with the [README](../../README.md#run-locally).

```sh
make dev          # prepare LOCAL and run the host app
# Ctrl-C stops Flask
make providers-stop
```

For IDE use: `make init`, then Run/Debug `src/main.py`. `make seed` imports CSVs
into an already migrated LOCAL database. `make quick-test` runs host unit tests.
The detailed Docker/database commands below remain available for maintenance.


`setup` creates/reuses Python 3.12 `.venv`, installs/verifies the pinned requirements,
and creates `.env.local` and `.env.test`, preserves valid canonical files, and safely migrates legacy configuration. `doctor` only diagnoses: venv/version/pins/pip consistency, Docker, both configuration
files, repository anchors and ports. Stop a running host app before a free-port check. `run` requires an already
migrated database and never applies migrations. `stop` retains developer DB volumes.
`migration` requires LOCAL and a nonblank message; it writes to `alembic/` for review.

| Command | Exact test/quality scope |
| --- | --- |
| `unit` | `tests/unit`, network-disabled container |
| `integration` | `tests/integration`, disposable PostgreSQL/Redis |
| `test` | `tests/unit tests/integration`, one pytest invocation |
| `coverage` | Same application suite, terminal line coverage |
| `tooling` | `scripts/tests`, network-disabled container |
| `smoke` | `tests/smoke`, real built Gunicorn HTTP system |
| `check` | Ruff lint, Ruff format check, strict mypy; no source edits |
| `certify` | Quality + tooling + application coverage once + built smoke once + lifecycle checks |

Certification additionally induces failed runner/provider/migration/smoke operations
and signals to verify cleanup; these are expected negative scenarios, not repeated
successful suites. Commands propagate failures and do not stage, commit, or deploy.

## IDE DEVELOPMENT commands

| Command | Behavior |
| --- | --- |
| `providers ENV=local` | Start only healthy LOCAL PostgreSQL/Redis; verify bindings/auth; use canonical machine config; no app/migration |
| `providers-stop ENV=local` | Stop only providers; retain PostgreSQL volume, containers and network; refuse active full LOCAL app |
| `test-providers` | Foreground isolated disposable TEST session, dynamic loopback endpoints, private ownership manifest; Ctrl-C/SIGTERM cleanup |
| `certify-host PYTHON=.venv/bin/python` | Python 3.12 host acceptance after installing requirements; disposable providers, CRUD/persistence, individual tests, ownership/signal checks; no IDE UI claim |

`dev.mk` owns LOCAL provider targets, `test.mk` owns `test-providers`, and `ci.mk`
owns `certify-host`; Python orchestration implements them. Provider targets reject
`ENV=dev`. Normal `integration`, `test`, `migrate`, `smoke`, and `certify` retain their
existing workflows. Host certification is additive and allocates its own ports.
See the [README workflow](../../README.md#run-locally) for initial IDE setup.

After `make init`, run/debug `src/main.py` directly:
it derives host URLs from canonical `.env.local` without IDE environment configuration. No `make ide`
command is needed. Host preparation uses current source; Docker workflows require image rebuilds.

## Everyday LOCAL shortcuts

- `make dev`: setup, start LOCAL providers, apply host-code migrations, import `data/`,
  then run Flask in the foreground. Ctrl-C stops the app; `make providers-stop` stops providers.
- `make init`: the same preparation without launching Flask, for IDE Run/Debug.
- `make seed`: import CSVs into the existing LOCAL database, preserving existing rows.
- `make quick-test`: host unit suite using `.venv`, without Docker or providers.

These commands reject `ENV=dev`. The migration/import/app subprocesses use the same
canonical LOCAL configuration; ambient database overrides cannot redirect the shortcuts.
Failures stop the sequence before app startup. Existing advanced commands are unchanged.
