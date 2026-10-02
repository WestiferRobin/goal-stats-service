# Repository identity and template history

This repository now hosts the GoalStats monolithic backend, including the
RoadToTheFinal football domain. Item/Action routes remain for compatibility.
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
| Coverage source | `src` |
| Factory | `main:create_app()` |
| Image/runtime slug | `goal-stats-service` |
| Image tags | `goal-stats-service:runtime`, `goal-stats-service:tooling` |
| Developer Compose projects | `goal-stats-service-local`, `goal-stats-service-dev` |
| Disposable projects | `goal-stats-service-test-<hex>`, `goal-stats-service-cert-<hex>` |
| Developer databases | `goal_stats_service_local`, `goal_stats_service_dev` |
| TEST database | `goalstats_test_runtime` |
| Cache namespace | `goal-stats-service:<env>:v1` |
| API display title | `GoalStats Monolith API` |
| Logger identity | `goal_stats_service` (service label, not an import/package) |
| Internal Compose services | `app`, `runner`, `postgres`, `redis` |
| Disposable tool container | `goal-stats-service-tool-<hex>` |
| CI concurrency | `goal-stats-service-${{ github.workflow }}-${{ github.ref }}` |

Later scaffolding must update identity producers, consumers, safety guards, fixtures,
Docker/Compose references, and observations together. There is no Python package-directory identity to transform. Flat module names,
source paths, the Item/Action reference domain and generic `goalstats_*` extension
keys remain unchanged.
Do not use broad textual substitution. The migration revision is not an identity
placeholder: preserve `b7f42e9c1a60` unless a separately reviewed migration is needed.

Dependencies remain Python 3.12 and one pinned `requirements.txt`. No generic
provider framework, async architecture, authentication platform, queues, or gRPC
is included. PostgreSQL and Redis are runtime providers; API-Football is optional for live refresh.

## Flat Python execution contract

`src/main.py` exports `create_app` and explicitly connects application-owned resources,
cache adapters and services to typed Blueprint factories. Routes capture services directly;
`app.extensions` retains resource references for diagnostics and cleanup, not service lookup.
Modules import directly from `enums`, `exceptions`, `settings`,
`models`, `schemas`, `infra`, `services`, and `routers`. There is no
intermediate service package and no `src` package to import.

Pytest declares `pythonpath = src scripts`; Alembic uses its configuration-relative
`prepend_sys_path`; mypy declares `mypy_path = src`. Docker explicitly sets
`PYTHONPATH=/app/src`, shared by Gunicorn, LOCAL Flask CLI, migration/test runners
and certification subprocesses. CI calls the same Make/Docker workflows. Host
factory commands must explicitly expose the source directory, for example
`PYTHONPATH=src flask --app 'main:create_app()' run`. No developer shell path
configuration is assumed by the public Make workflows.

The remaining `goal_stats_service` occurrences are intentional service identities:
LOCAL/DEV database names (and their producers/ownership checks) and the isolated
application logger label. They are not Python package references. Generic TEST
identities and unrelated-resource sentinels remain intentionally generic.

## Host development and propagation

Host IDE support is additive to Docker. Flat `src/`, `main:create_app()`, Python 3.12,
one `requirements.txt`, Item/Action behavior, HTTP/OpenAPI, database schema/migration
history, Redis semantics and health/readiness contracts stay unchanged. Direct
`src/main.py` adds only a LOCAL development entrypoint. `src/` is not a package;
script execution naturally exposes it, pytest uses its configured paths, Alembic
uses its existing prepend path, and Docker/Gunicorn use their existing PYTHONPATH.

Track only portable `.vscode/settings.json`, `.vscode/launch.json`, and optional
`.vscode/extensions.json`. Ignore `.idea/`, `.venv/`, `.env.local`, and
`.host-sessions/`. No extra dotenv example or dependency manifest is introduced.

Scaffolding must preserve the shared code-owned configuration schema, private setup,
manifest-based TEST ownership and portable IDE launch. Reject all real env files and
internal state from payloads; generated services use `.env.local`, while tests create
ephemeral configuration internally. Identity literals are transformed only in reviewed paths.

Direct `src/main.py` means LOCAL host development. The `load_local()` helper in
`src/settings/environment.py` also serves explicit host preparation/import commands; factory and Alembic
configuration use `load_application()` without reading machine files. Portable VS Code app launch must not inject
an env file; PyCharm Python script Run needs no environment profile. Scaffold guards
must validate this shared loader and preserve its source bytes without identity rewrites.

API body DTOs use `*Request`, resource/list DTOs use `*Response`, and path/shared
contracts use `*Schema` (including `ProblemDetailSchema`). Domain exceptions live
in `exceptions/base.py`, `item.py`, and `action.py`; Flask handling lives in
`exceptions/handlers.py`. Football uses its own domain module and flat `schemas/football.py` contracts.

Domain API contracts live in `schemas/<domain>/request.py` (`*Request`),
`response.py` (`*Response`), and `base.py` (`*Schema`). The latter owns path/query
schemas and genuine shared domain foundations; it does not require a generic base
class. Other domain schema files contain `*Schema` contracts only when genuinely
needed. Shared primitives stay in `schemas/common.py`, and singleton cross-cutting
contracts such as `schemas/problem.py` need no package hierarchy. Imports name the
defining module explicitly; empty package markers do not re-export schemas.
