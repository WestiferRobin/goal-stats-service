# Repository identity and template history

This repository now hosts the GoalStats monolithic backend, including the
RoadToTheFinal football domain. The inherited Item/Action business domains are retired.
New contributors should follow the [README](../../README.md), not scaffold another
service. The repository, database and Docker names below are retained to preserve
existing tooling, credentials and volumes.

The implementation inherited flat Python modules, Flask Blueprints, explicit
resource construction, Pydantic contracts, synchronous PostgreSQL access and
Gunicorn from the original template. The identity table is a maintenance reference.

## Stable scaffold anchors

| Identity | Current value |
| --- | --- |
| Repository | `goal-stats-service` |
| Source/import root | `src/` (flat modules; no service package directory) |
| Factory | `main:create_app()` |
| Image/runtime slug | `goal-stats-service` |
| Image tags | `goal-stats-service:runtime`, `goal-stats-service:tooling` |
| Public local Compose project | `goalstats-service-local` |
| Disposable projects | `goal-stats-service-test-<24 hex digits>` |
| Public development database | `goal_stats_service_local` |
| TEST database | `goalstats_test_runtime` |
| Cache namespace | `goal-stats-service:<env>:v1` |
| API display title | `GoalStats Monolith API` |
| Logger identity | `goal_stats_service` (service label, not an import/package) |
| Internal Compose services | `app`, `runner`, `postgres`, `redis` |
| Disposable tool container | `<test-project>-quality`, `<test-project>-runner` |
| CI concurrency | `goal-stats-service-${{ github.workflow }}-${{ github.ref }}` |

Later scaffolding must update identity producers, consumers, safety guards, fixtures,
Docker/Compose references, and observations together. There is no Python package-directory identity to transform. Flat module names,
source paths and generic `goalstats_*` resource extension keys remain stable.
Do not use broad textual substitution. The migration revision is not an identity
placeholder: preserve baseline `a7c93e25d104` and retirement child `c8d42f19e630`.

Dependencies remain Python 3.12 and one pinned `requirements.txt`. No generic
provider framework, async architecture, authentication platform, queues, or gRPC
is included. PostgreSQL and Redis are runtime providers; API-Football is optional for live refresh.

## Flat Python execution contract

`src/main.py` exports `create_app` and explicitly connects application-owned resources,
shared Redis provider and services to typed Blueprint factories. Routes capture services directly;
`app.extensions` retains resource references for diagnostics and cleanup, not service lookup.
Modules import directly from `enums`, `exceptions`, `settings`,
`models`, `schemas`, `infra`, `services`, and `routers`. There is no
intermediate service package and no `src` package to import.

Pytest declares `pythonpath = src scripts/development scripts/database scripts/testing`;
Alembic uses its configuration-relative
`prepend_sys_path`; mypy declares `mypy_path = src`. Docker explicitly sets
`PYTHONPATH=/app/src`, shared by Gunicorn, LOCAL Flask CLI and migration/test runners. CI calls the same Make/Docker workflows. Host
factory commands must explicitly expose the source directory, for example
`PYTHONPATH=src flask --app 'main:create_app()' run`. No developer shell path
configuration is assumed by the public Make workflows.

The remaining `goal_stats_service` occurrences are intentional service identities:
the local database name (and explicit prototype import compatibility checks) and the isolated
application logger label. They are not Python package references. Generic TEST
identities and unrelated-resource sentinels remain intentionally generic.

## Host development and propagation

Host Flask is the public `make run` workflow; `make deploy` runs Docker Flask locally. Flat `src/`, `main:create_app()`, Python 3.12,
one `requirements.txt`, retained domain behavior, HTTP/OpenAPI, database schema/migration
history, Redis semantics and health/readiness contracts stay unchanged. Direct
`src/main.py` adds only a LOCAL development entrypoint. `src/` is not a package;
script execution naturally exposes it, pytest uses its configured paths, Alembic
uses its existing prepend path, and Docker/Gunicorn use their existing PYTHONPATH.

Track only portable `.vscode/settings.json`, `.vscode/launch.json`, and optional
`.vscode/extensions.json`. Ignore `.idea/`, `.venv/`, `.env.local`, and
`.host-sessions/`. No extra dotenv example or dependency manifest is introduced.

Scaffolding must preserve the public configuration schema, setup-created Python 3.12
venv, Docker test receipt ownership and POSIX IDE launch. Reject all real env files and
internal state from payloads; generated services use `.env.local`, while tests create
ephemeral configuration internally. Identity literals are transformed only in reviewed paths.

Direct `src/main.py` means LOCAL host development. The `load_local()` helper in
`src/settings/environment.py` also serves explicit host preparation/import commands; factory and Alembic
configuration use `load_application()` without reading machine files. Portable VS Code app launch must not inject
an env file; PyCharm Python script Run needs no environment profile. Scaffold guards
must validate this shared loader and preserve its source bytes without identity rewrites.

API body DTOs use `*Request`, resource/list DTOs use `*Response`, and path/shared
contracts use `*Schema` (including `ProblemDetailSchema`). Domain exceptions live
in `exceptions/base.py` (DomainError) and `services/prediction.py` (ScenarioNotReady); Flask handling lives in
`exceptions/handlers.py`. Normalized Goal Stats contracts use singular entity modules under `schemas/`; shared
calculation contracts live in `schemas/engine.py`, and prototype-specific requests
remain in `schemas/football.py`.

Shared primitives stay in `schemas/common.py`; singleton cross-cutting contracts
such as `schemas/problem.py` need no package hierarchy. Imports name the defining
module explicitly; empty package markers do not re-export schemas.

## Public lifecycle contract

The eight public commands are setup, infra, run, deploy, seed, test, stop, and help.
`scripts/development/local.sh` owns the public lifecycle. Both application locations share
`goalstats-service-local_postgres-data`, `.env.local`, migrations, imports and cache
namespace. Tests use independently generated disposable project identities.
Setup starts nothing; infra starts only providers; run/deploy share Docker preparation.
Ctrl-C/IDE Stop ends host Flask; stop removes Docker resources without deleting data.
Host development supports macOS/Linux/WSL and manual restart. Disposable integration
tests run inside the verified Docker runner; IDE pytest runs provider-free unit tests.
