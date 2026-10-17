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
or prototype router. The 15 application operations include the original normalized
catalog/scenario/prediction APIs plus preview, historical insights and hypothetical
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

Exactly five application mappings are registered: teams, competitions, matches,
scenarios and predictions. Alembic adds only normal migration metadata. Reusable
calculation and source-parsing code remains in `src/football/`.

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
