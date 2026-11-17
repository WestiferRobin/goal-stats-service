# Monolithic backend architecture

The backend hosts five normalized Goal Stats domains in one Flask process and
PostgreSQL database. RoadToTheFinal supplies reusable mathematics, not production
records. The pure engine has no Flask or provider dependency.

```text
Route → Service → Repository → SQLAlchemy Session → PostgreSQL
Readiness → shared Redis provider
```

The application factory explicitly constructs resources and services, then injects
services into Blueprint factories. Each application owns its Engine/session factory
and Redis pool. Each database operation owns its session and repositories. Services
and repositories do not depend on Flask globals. Python 3.12 and one requirements
file remain the runtime contract.

## Normalized service ownership

`TeamService`, `CompetitionService`, `MatchService`, `ScenarioService`, and
`PredictionService` live in singular modules under `src/services/`. Repositories
own SQL construction; services own business validation, response serialization,
and transaction boundaries. Scenario creation shares one session across team,
match, and scenario repositories; updates validate combined state under a row lock.

Scenario and prediction services use the same `ScenarioRepository` projection for
scenario values and participant names. Prediction generation captures those values
inside a read transaction, closes it before calculation, validates the unchanged
engine output, and appends a saved result in a separate transaction. Retrieval uses
saved inputs and output without recalculation.

The five domain routers are registered independently. There is no FootballService
or prototype router. The 16 application operations include the original normalized
catalog/scenario/prediction APIs plus full-history team summaries, preview, historical insights and hypothetical
knockout simulation. See [the exact API contracts](frontend-api.md).

MatchService and CompetitionService receive TeamService directly. PredictionService
receives ScenarioService and TeamService. Each retains only its own repository.
Preview and simulation capture normalized names in a short caller-owned transaction,
then calculate without holding database connections. Insights validates IDs and reads
all three result lists within one caller-owned transaction.

## Schema ownership

The five normalized domains own packages under `schemas/team/`, `competition/`,
`match/`, `scenario/`, and `prediction/`. Path, query, create, and patch contracts
live in `request.py`; output contracts live in `response.py`. Competition requests describe explicit simulation assumptions. Prediction requests
include preview inputs; saved prediction generation remains bodyless.

Only Scenario needs `base.py`: it owns shared state, constrained types, configuration,
and examples. `ScenarioResponse` still inherits `ScenarioCreate`, and prediction
input snapshots still inherit `ScenarioResponse`. Prediction's nested saved-output
contracts remain together in its response module. Existing class names, validators,
field annotations, and validation/serialization JSON schemas are preserved.

Package initializers explicitly re-export the original domain objects, so public
imports such as `from schemas.scenario import ScenarioCreate` remain stable. Internal
sibling imports target defining modules to avoid package initialization cycles.
There are no duplicate definitions or conflicting flat domain schema files.

`schemas/engine.py` owns shared statistics, modifiers, and prediction report
components used by the normalized workflows. Legacy validation has moved to the
corresponding domain contracts; there is no active `schemas/football.py`.
`schemas/common.py` owns shared contract configuration, count/identity bounds,
pagination, possession validation, and shared primitives. Problem Details remains unchanged.

Schema-module separation changes no PostgreSQL definitions, historical imports,
prediction formulas, or cache behavior. Router files retain their routes and
handlers. Direct entity-service wiring preserves these same schema contracts.

## Model ownership

The five normalized models have individual modules under `src/models/`: `team.py`,
`competition.py`, `match.py`, `scenario.py`, and `prediction.py`. The shared base,
metadata naming convention, and nonblank constraint helper remain in `base.py`.

Six application mappings are registered: teams, competitions, matches,
scenarios, predictions and the provider-neutral users identity table. Zero users
is valid; no account workflows are enabled. Alembic adds normal migration metadata.
Reusable calculation and source-parsing code remains in `src/football/`.

## Database and transactions

Each operation owns a fresh transaction/session. Repositories query, add or flush,
but do not commit. Successful context exit commits; failure rolls back and closes.
Scenario updates lock their target row. Database foreign keys and check constraints
remain the final relationship/state invariants. There is no generic repository,
DI framework, or custom UnitOfWork class.

The original `a7c93e25d104` migration remains unchanged. Forward revision
`c8d42f19e630` locks both retired tables, refuses nonempty tables, and drops actions
before items. The subsequent `d91e6a4b208f` revision retires only empty, current-user-owned
prototype tables without CASCADE, preserving all five normalized tables.
Downgrade recreates empty legacy tables with their original constraints and indexes;
it does not recover data. See [retirement](../testing/item-action-backend-retirement.md).

The [historical catalog](historical-catalog.md) supports nine approved Women's World
Cup editions. Its explicit importer retains checksums, provenance, conflict rejection,
idempotency and per-edition transactions. Startup never seeds data.

Revision `e42b7c19a603` adds users (`user_id`, `created_at`) and nullable scenario
`owner_user_id` with a restrictive FK and composite owner/time/ID index. Predictions
inherit ownership through scenarios; saved JSON and public API shapes are unchanged.
Existing shared APIs remain shared. Downgrade locks scenarios/users and refuses
any user rows or non-NULL owners. See the [ownership design](architecture.md#ownership-and-migration-acceptance)
for preservation, deployment and Task 13/14 boundaries.

## Normalized entity cache decisions

PostgreSQL remains authoritative for all five normalized entities. None currently
has a demonstrated performance requirement for Redis caching. The existing shared
Redis provider remains available; the retired adapters are removed. A model and
repository do not imply that an entity needs a cache. No normalized cache modules,
placeholder files, service dependencies, keys, or TTLs are introduced.

| Entity | Decision | Reason and reconsideration criteria |
| --- | --- | --- |
| Team | DEFER | The 44-team catalog has no demonstrated database pressure. Future identity keys must distinguish normalized IDs from prototype identities; response schemas can serialize the catalog, but optional rating changes would require invalidation. Never substitute prototype ratings. |
| Competition | DEFER | Nine editions are inexpensive to read directly. Seeding can change list membership; TTL-only caching would permit incomplete or stale lists. Reconsider only with measured demand and import-aware invalidation. |
| Match | DEFER | The 348-match catalog already uses filtered, ordered, paginated repository reads. Caching adds filter/pagination key combinations and import invalidation without demonstrated benefit. Future caches must preserve every filter, ordering, identity, and source-provenance field. |
| Scenario | NO CACHE | Mutable scenarios and prediction input capture require current database state, row locking, and preserved rating snapshots. Direct repository reads retain existing transaction and concurrency guarantees. |
| Prediction | NO CACHE | Read saved inputs, model versions, and exact outputs directly without recalculation. New append-only records change history lists immediately; detail caching can be reconsidered if measured retrieval demand justifies it. |

A local read-only observation (one warmup and ten reads per query) found median
repository times of approximately 0.82 ms for 44 teams, 0.61 ms for nine competitions,
and 2.76 ms for the default 50-match page. These are warm local observations, not a
production load benchmark or concurrency guarantee. They establish no reason to
add cache complexity; production access patterns should guide any future decision.

Historical imports continue writing PostgreSQL through the explicit importer.
There are no normalized cache entries to invalidate after seeding. Prediction
calculation continues outside database transactions using captured inputs, and
retrieval returns the saved result. Redis outages cannot introduce stale normalized
scenario state or alter prediction calculations.

## Shared Redis provider

RedisCache retains bounded GET/SET/DEL, JSON serialization, namespace isolation,
TTL support and safe failure logging. Connection, ACL and corrupt-payload failures
remain safe misses where supported. Logs omit URLs, credentials, payloads and raw
provider error messages. There are no active business cache adapters. Obsolete
Item/Action keys may expire naturally; retirement does not flush Redis.

## Operations and errors

`/health` is provider-independent liveness. `/ready` requires exact Alembic heads
and usable mapped columns; missing revision/table/column or unavailable PostgreSQL
is 503 Unhealthy. With PostgreSQL ready, a successful bounded Redis GET gives
200 Healthy; missing/unavailable Redis gives 200 Degraded. Consumers waiting for
startup must require 200 and Healthy. Full schema drift checks use Alembic, not
per-request schema autogeneration.

App-owned Redis resources are closed when their app/test/CLI owner is retired,
not at request teardown. Domain operations close their SQLAlchemy sessions. There is no request-scoped
session facility. Import
and factory construction never connect, migrate, seed, or call external APIs.

Safe Problem Details handlers own validation, domain, framework, and unexpected
errors. flask-openapi3 generates OpenAPI 3.1.0 documenting resource schemas, enum values, validation statuses,
canonical Location headers, and the Problem Details response. `/health` and `/ready`
are documented under `infra`, including their plain-text responses and readiness statuses.
Swagger is served at `/swagger` with local pinned assets and the generated spec at
`/swagger/v1/swagger.json`. `make run` uses foreground host Flask with manual/IDE
restart; `make deploy` retains Docker Flask source reload with its browser debugger
disabled. Both use the same LOCAL providers and data. Private DEV tooling uses a built
Gunicorn image; TEST owns disposable providers. See [Development](development.md)
for runtime identities and cleanup.

## Package placement

| Module/package | Responsibility |
| --- | --- |
| `main.py` | Factory, explicit resource/service construction, Blueprint registration, direct LOCAL startup diagnostics |
| `routers/infra.py` | Operational HTTP endpoints `/health` and `/ready` |
| `exceptions/handlers.py` | HTTP error mapping and object-body request guard |
| `routers/openapi.py` | Generated response metadata and native local Swagger Blueprint |
| `schemas/common.py`, `schemas/problem.py` | Shared constraints/timestamp codec and Problem Details |
| `infra/base.py` | Infrastructure readiness/state evaluation; no HTTP handling |
| `infra/repositories` | Concrete session-bound SQLAlchemy queries and writes |
| `infra/resources/redis.py` | Shared optional Redis provider and readiness |
| `infra/resources` | Engine/sessionmaker and Redis ownership, readiness, disposal |
| `models` | SQLAlchemy database models and one authoritative Base |
| `settings` | Concern-based typed configuration with explicit private file loading |
| `exceptions/base.py`, `services/prediction.py` | Application exceptions without HTTP status fields |

All paths are beneath flat `src/`. Domain schema package initializers provide explicit
public exports; other existing package markers retain their roles. Mapped classes are
imported explicitly wherever metadata registration is required. There is no `src`
package, service-name package, global settings singleton or dependency-injection framework.

Shared `Contract` configuration rejects unknown fields and non-finite numbers.
Domain contracts preserve their individual strictness, defaults, nullability, and
validators; no new field aliases are introduced. Normalized services validate response
contracts and serialize them with `model_dump(mode="json")`; routers return the service
results through `jsonify`. Response contracts are not generally frozen; Problem Details
is explicitly frozen. Responses preserve their existing timestamp contracts. Services
never import Flask.

Request validation produces safe 400 responses through the extension callback.
A small native guard refuses malformed/non-object/non-JSON bodies before binding.
Pydantic errors constructing server output remain 500 errors, never request errors.
The OpenAPI document is generated from these schemas; there is no duplicate YAML.
The extension's automatic UI is disabled. Native routes serve pinned local Swagger
assets, and docs-disabled mode exposes neither the UI, assets nor document.

Prizm's concern-based settings separation is retained without its platform features,
process-wide dotenv mutation or cached settings. Gunicorn remains WSGI. No async
sessions, authentication platform, queues, gRPC or provider registries are introduced.

### API schema naming

The five normalized domains use singular schema packages; shared prediction components
live in `schemas/engine.py`. Preview, simulation and comparison contracts belong
to their respective domain packages.
Cross-domain primitives remain in `schemas/common.py`; singleton contracts such as
`schemas/problem.py` remain flat. Consumers can retain the stable domain-package imports;
schema package internals import defining modules directly.
`ProblemDetailSchema` defines the unchanged safe error JSON contract.

## Ownership and migration acceptance

**Task 1: DONE — Database architecture and ownership preparation complete for the
current scope.** The active chain is
`a7c93e25d104 → c8d42f19e630 → d91e6a4b208f → e42b7c19a603`.
The six application tables are `teams`, `competitions`, `matches`, `scenarios`,
`predictions`, and `users`; `alembic_version` is migration metadata.

| Table | Relationships, constraints and indexes |
| --- | --- |
| teams | Stable integer ID; unique name/category; bounded nullable ratings and attribution |
| competitions | Stable integer ID; unique name/edition/category; nonblank labels |
| matches | Restrictive competition/two-team FKs; distinct teams; nonnegative scores; unique source/record key; FK/date indexes and provenance |
| scenarios | Restrictive team/optional-match FKs; explicit rating snapshots, bounded state and possession sum; reference and creation-time/ID indexes |
| predictions | Restrictive scenario FK; bounded probabilities, object-shaped saved JSON; scenario/time/ID and global time/ID indexes |
| users | Stable `user_id` identity primary key and database-default `created_at`; zero rows valid |

`scenarios.owner_user_id` is nullable with no default/backfill and references
`users.user_id` using `ON DELETE RESTRICT`. Its composite index is
`(owner_user_id, created_at, scenario_id)`. Predictions inherit ownership through
their scenario; no duplicated owner field is stored in prediction JSON. Existing
IDs, timestamps, original columns and saved snapshots remain intact. Public response
and calculation-input projections exclude the internal owner column.

The ownership migration contains no application-data writes. Downgrade locks
scenarios/users, requires zero users and all owners NULL, and drops ownership
objects without CASCADE. Populated identities, ownership or unexpected dependencies
block reversal atomically. Do not clear data to bypass guards; downgrade to `base`
is not a record-preserving rollback. Earlier retirement revisions also reject
populated legacy tables rather than deleting their data.

The [SQL export](../../sql/README.md) follows the same Alembic chain. Existing
`tests/unit/test_sql_exports.py` checks deterministic offline parity;
`tests/integration/infra/resources/test_db.py` checks actual schema parity,
original-column preservation, failed DDL, lock timeouts, downgrade dependencies
and populated-user refusal. Full-row digests change shape when a nullable column
is added: compare original columns first, verify NULL owners, then establish a
new full-row baseline. No preservation claim follows from a lone post-upgrade hash.

For a separately authorized deployment: verify target/schema identity, backup and
restore capability; rehearse on disposable infrastructure; measure lock duration;
drain traffic/writers and use one migration actor; migrate before starting the
matching application; verify exact head, six-table readiness, original records and
shared workflows before restoring traffic. Ordinary index creation and ALTER TABLE
can block writers. Keep bounded lock/statement timeouts and abort on failure.
Old-code/new-schema and new-code/old-schema combinations are operationally
unsupported because readiness and metadata expectations differ. This is not a
zero-downtime or production deployment certification.

No login, user assignment, per-user filtering or authorization is active. Saved
records remain shared, not private. Tasks 13/14 must define authentication,
legacy-record policy and cross-user isolation before private accounts are released.

## Task 9 acceptance

**DONE — Required backend architecture implementation verified.** This conclusion
covers the current [Engineering Backlog](https://docs.google.com/document/d/1nsJYQbk84yOqcpXeAhxrXTRAZtPNignpOJSuN26Wlg0/edit)
and [Weekly Team Tasks](https://docs.google.com/document/d/1D_mUhoDmvOqDpT08I0w_yk_jOd5jw2wTEj-nAtbDf0I/edit)
scope, not production deployment certification or course approval.

| Requirement | Implemented evidence |
| --- | --- |
| Flask factory and route registration | `src/main.py` constructs and injects app-owned services; registered Flask methods and generated OpenAPI both contain 16 application operations |
| Service/repository separation and transactions | `src/services/` owns validation/transactions; `src/infra/repositories/` owns SQL; row locking protects scenario edits |
| Validation and errors | Strict Pydantic contracts, safe Problem Details, framework/domain handlers and rollback |
| Full-history summaries | Team repository aggregates all matching records, independent of history pagination; accepted definitions and empty states in the API contract |
| Prediction integration | Preview is unsaved; generation appends captured inputs/output; saved reads never recalculate |
| Monte Carlo integration | Competition service captures normalized identities, closes its read transaction, then runs request-local seeded simulation |
| Scenario persistence | Create/list/detail/PATCH and per-scenario saved prediction history use PostgreSQL |
| Health/readiness | Provider-independent liveness; exact migration head and mapped-column probes; bounded Redis readiness |
| Production boundary | `main.py` checks a configured bearer service token on non-GET/HEAD/OPTIONS requests in production; this is service authentication, not per-user authorization |
| Deferred identity | Tasks 13/14 remain separate; schema ownership preparation does not make shared records private |

No additional runtime architecture change is required for this audited scope.

Documentation acceptance verification on 2026-11-13, based on runtime commit
`d8d7452138431570cece9c1d8cdafa338d41cb0b`: Flask registration and generated OpenAPI
independently counted 16 application operations; the historical verifier passed
all nine editions and the committed checksum. Canonical `make test` reported
**1,636 passed, one deselected in 295.38s**, Ruff lint PASS, 211 files formatted,
strict mypy PASS (81 source files), and tests/resource cleanup PASS. The deselected
pinned-source integration test belongs to `make certify`, which was not rerun in
this documentation audit. A temporary read-only Markdown checker resolved all 91
relative links; `git diff --check` passed. No runtime, schema, source-data or
frontend changes were made. This is local verification, not a claim of GitHub CI
or production deployment success.
