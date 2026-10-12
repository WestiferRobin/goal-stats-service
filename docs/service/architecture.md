# Monolithic backend architecture

The backend hosts five normalized Goal Stats domains and the retained RoadToTheFinal
prototype in one Flask process and PostgreSQL database. The pure prediction model
has no Flask or provider dependencies. All modules deploy together.

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

The existing `football` blueprint injects `TeamService`, `CompetitionService`,
and `MatchService` directly for the teams, competitions, and matches endpoints
under `/api/v1/catalog` (including existing team/match detail routes).
Its prototype endpoints continue using `FootballService`; normalized handlers
never fall back to prototype data. Temporary catalog delegation methods are removed.

The existing `scenarios` and `saved_predictions` blueprints import their singular
service modules directly. The application factory constructs each service per app,
sharing that app's database resource. Temporary plural service import shims are
removed. Routers validate requests and serialize service responses; services own
transactions and repositories own persistence. No normalized cache dependencies
are introduced.

All paths, converters, HTTP methods, blueprint/handler names, operation IDs,
request/response schemas, status codes, and Location headers remain unchanged.
Saved prediction generation remains a bodyless POST, separate from the prototype
stateless prediction endpoint. Prototype routes remain active. The twelve Item/Action
operations are retired in this checkout; frontend Home coordination remains pending.
Do not deploy this removal or migrate persistent PostgreSQL before that coordination.

## Schema ownership

Historical team, competition, and match contracts live in `schemas/team.py`,
`competition.py`, and `match.py`. Saved scenario and prediction contracts live in
`scenario.py` and `prediction.py`. Existing class names and JSON/OpenAPI contracts
are preserved; the former plural schema modules have no remaining consumers.

`schemas/engine.py` owns shared statistics, modifiers, and prediction report
components used by both normalized and prototype workflows. `schemas/football.py`
retains prototype matchups, prediction requests, tournaments, and snapshots.
`schemas/common.py` owns shared contract configuration, count/identity bounds,
pagination, possession validation, and shared primitives. Problem Details remains unchanged.

Schema-module separation changes no PostgreSQL definitions, historical imports,
prediction formulas, or cache behavior. Router files retain their routes and
handlers. Direct entity-service wiring preserves these same schema contracts.

## Model ownership

The five normalized models have individual modules under `src/models/`: `team.py`,
`competition.py`, `match.py`, `scenario.py`, and `prediction.py`. The shared base,
metadata naming convention, and nonblank constraint helper remain in `base.py`.

`models/hold/football.py` maps the three active RoadToTheFinal tables; the directory
otherwise contains only its package marker. Exactly eight application tables are
registered by the database resource and Alembic environment. The prediction engine
remains in `src/football/`.

## Database and transactions

Each operation owns a fresh transaction/session. Repositories query, add or flush,
but do not commit. Successful context exit commits; failure rolls back and closes.
Scenario updates lock their target row. Database foreign keys and check constraints
remain the final relationship/state invariants. There is no generic repository,
DI framework, or custom UnitOfWork class.

The original `a7c93e25d104` migration remains unchanged. Forward revision
`c8d42f19e630` locks both retired tables, refuses nonempty tables, and drops actions
before items. It preserves the five normalized and three prototype tables.
Downgrade recreates empty legacy tables with their original constraints and indexes;
it does not recover data. See [retirement](../testing/item-action-backend-retirement.md).

The [historical catalog](historical-catalog.md) supports nine approved Women's World
Cup editions. Its explicit importer retains checksums, provenance, conflict rejection,
idempotency and per-edition transactions. Startup never seeds data.

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

All paths are beneath flat `src/`. Package markers are empty; mapped classes are
imported explicitly wherever metadata registration is required. There is no `src`
package, service-name package, global settings singleton or dependency-injection framework.

Pydantic commands reject unknown fields and internal snake_case HTTP aliases. Services
construct frozen responses from ORM attributes before closing the transaction.
Routes explicitly serialize responses with `model_dump(mode="json", by_alias=True)`.
Responses preserve their existing timestamp contracts. Services never import Flask.

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

The five normalized domains use singular schema modules; shared prediction components
live in `schemas/engine.py`, and prototype contracts in `schemas/football.py`.
Cross-domain primitives remain in `schemas/common.py`; singleton contracts such as
`schemas/problem.py` remain flat. Callers import defining modules explicitly.
`ProblemDetailSchema` defines the unchanged safe error JSON contract.
