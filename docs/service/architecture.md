# Monolithic backend architecture

The [football domain](football.md) is hosted in the same process and PostgreSQL
database as the compatibility Item/Action resources below. Football uses the shared
Database transaction boundary directly; its pure prediction model has no Flask or
provider dependencies. PostgreSQL replaces browser-session timelines, CSV appends
and per-worker live caches. All modules deploy together.


```text
Route → Service → Repository → SQLAlchemy Session → PostgreSQL
              └→ Resource Cache → Redis JSON adapter → Redis

ORM entity → frozen Pydantic response → explicit JSON serialization → HTTP
```

The application factory explicitly connects resources → caches → services → Blueprint
factories. Each application owns its Engine/session factory, Redis pool, cache adapters
and stateless services. Routers capture their service through a typed factory argument;
each database operation creates its own Session and repositories. Services,
repositories, and cache adapters do not depend on Flask globals. One requirements
file and Python 3.12 remain the dependency/runtime contract.

## Resource contracts

| Methods | Path | Behavior |
| --- | --- | --- |
| GET, POST | `/items` | List / create Item |
| GET, PUT, DELETE | `/items/<item_id>` | Read / update / delete Item |
| GET, POST | `/actions` | List / create Action with body `itemId` |
| GET, PUT, DELETE | `/actions/<action_id>` | Read / update / delete Action |
| GET, POST | `/items/<item_id>/actions` | List / create with parent from URL |

POST returns 201 plus canonical Location; Item Location is `/items/<id>` and either
Action creation form uses `/actions/<id>`. GET/PUT return 200; DELETE returns an
empty 204. Missing resources/parents return 404 Problem Details. An existing parent
with no children returns an empty list. There are no nested Action get/update/delete
routes. Requests reject unknown fields. Nested creation and Action update do not
accept `itemId`. Action's parent is immutable through this API.

Names are required, nonblank, and at most 200 characters. Names need not be unique.
Item status is `active` or `archived`; new Items are active. Action type is `create`,
`update`, or `delete`. Numeric and quoted-number enum values are rejected. IDs are
UUIDs; input UUID zero is rejected. Malformed UUID paths are routing 404s, while
invalid body UUIDs are validation 400s. Pydantic schemas convert to snake_case
Python attributes, UUIDs, and StrEnums. Services receive validated command objects and validate ID arguments.

Item JSON: `id`, `name`, `status`, `createdAt`, `updatedAt`.
Action JSON: `id`, `itemId`, `name`, `type`, `createdAt`, `updatedAt`.
No ORM state or relationship graphs are returned. Timestamps are UTC-aware; updates
preserve creation time and advance modification time, including unchanged PUTs.
Lists order by creation time and UUID as tie-breaker.

## Database and transactions

`items` has a UUID PK, required bounded/nonblank name, constrained string status,
and non-null timezone-aware timestamp columns. `actions` has the same core fields,
a constrained action type, and an indexed FK to `items` with ON DELETE CASCADE.
No Python-side cascade graph is needed. Alembic revision `b7f42e9c1a60` establishes
this fresh Python schema. Python supplies UUID/timestamp defaults on ORM insertion;
direct SQL writers must supply those values explicitly.

Each service operation owns a fresh transaction/session. Repositories can query,
add, delete, or flush, but do not commit. A successful context exit commits; any
failure rolls back and closes. Pydantic responses are built inside the session; cache writes
or invalidation happen after successful exit. A failed flush/commit cannot trigger
successful mutation-related cache changes.

Update/delete lock their target rows. Action creation locks its parent before
inserting, serializing it with parent deletion; the database FK remains the final
relationship invariant. Overlapping operations may observe either legitimate
ordering. There is no generic repository, DI framework, or custom UnitOfWork class.

## Cache behavior

RedisCache owns bounded GET/SET/DEL, JSON, and safe failure logging. Resource caches
own `{prefix}:items:<uuid>` and `{prefix}:actions:<uuid>` keys, schema validation,
identity checking, and TTL (default 300 seconds). Prefixes separate services and
environments. Cache payloads use explicit scalar schemas, never pickle or ORM objects.

GET-by-ID is cache-aside; a miss queries PostgreSQL and fills Redis. Lists remain
uncached. Creation does not fill the cache. Update/delete invalidate after commit.
Malformed/incomplete/wrong-identity cache payloads are misses. Redis connection,
permission, or serialization failures do not invalidate successful PostgreSQL work.
Logs omit raw URLs, credentials, payloads, and provider error messages.

An Action cache hit still checks database row existence. If cascade deletion removed
it, the service discards the cached child and returns 404, even if Redis deletion
fails. Item deletion never scans child cache keys or couples itself to ActionCache.
This existence check is not atomic with overlapping deletions.

Cache and PostgreSQL are not one transaction. Failed invalidation or concurrent
cache fills can leave stale values until TTL expiry. The child check protects
absent Actions, not freshness of still-existing rows. Item cache hits do not query
the database. Do not claim stronger consistency than these guarantees.

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
`/swagger/v1/swagger.json`. LOCAL reloads source; DEV uses a non-root built Gunicorn
image; TEST owns disposable providers. See [Development](development.md) for runtime
identities and cleanup. No User or prediction domain is present.

## Package placement

| Module/package | Responsibility |
| --- | --- |
| `main.py` | Factory, explicit resource/cache/service construction, Blueprint registration, direct LOCAL startup diagnostics |
| `routers/item.py`, `routers/action.py` | Typed HTTP adapters; Action owns nested Item→Action operations |
| `routers/infra.py` | Operational HTTP endpoints `/health` and `/ready` |
| `exceptions/handlers.py` | HTTP error mapping and object-body request guard |
| `routers/openapi.py` | Generated response metadata and native local Swagger Blueprint |
| `schemas/item/`, `schemas/action/` | Domain Pydantic contracts: `request.py`, `response.py`, and `base.py` |
| `schemas/common.py`, `schemas/problem.py` | Shared constraints/timestamp codec and Problem Details |
| `services/item.py`, `services/action.py` | Independent application operations and transaction ownership |
| `infra/base.py` | Infrastructure readiness/state evaluation; no HTTP handling |
| `infra/repositories` | Concrete session-bound SQLAlchemy queries and writes |
| `infra/caches` | Cache identity, Pydantic payload validation and serialization |
| `infra/resources` | Engine/sessionmaker and Redis ownership, readiness, disposal |
| `models` | SQLAlchemy database models and one authoritative Base |
| `enums` | ItemStatus and ActionType |
| `settings` | Concern-based typed configuration with explicit private file loading |
| `exceptions/base.py`, `exceptions/item.py`, `exceptions/action.py` | Application exceptions without HTTP status fields |

All paths are beneath flat `src/`. Package markers are empty; mapped classes are
imported explicitly wherever metadata registration is required. There is no `src`
package, service-name package, global settings singleton or dependency-injection framework.

Pydantic commands reject unknown fields and internal snake_case HTTP aliases. Services
construct frozen responses from ORM attributes before closing the transaction.
Routes explicitly serialize responses with `model_dump(mode="json", by_alias=True)`.
Cache adapters use the same response schemas and preserve UTC `+00:00` timestamps.
They do not import services. Services never import Flask.

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

Each domain owns a schema package: `request.py` contains `*Request` body DTOs,
`response.py` contains `*Response` resource/list DTOs, and `base.py` contains
`*Schema` path/query contracts or genuine reusable domain foundations. `base.py`
does not require a generic domain base class: ItemPathSchema and ActionPathSchema
are its current responsibilities. Additional domain files contain `*Schema`
contracts only when a distinct responsibility requires them.

Cross-domain primitives remain in `schemas/common.py`; singleton contracts such as
`schemas/problem.py` remain flat. Package markers are empty, and callers import
from defining modules explicitly, for example `schemas.item.request` and
`schemas.item.response`. `ActionWriteRequest` is shared by Action updates and
nested creation; `ActionCreateRequest` adds `itemId`.
`ProblemDetailSchema` defines the unchanged Problem Details JSON contract.
The request/problem component names follow these Python names in OpenAPI;
fields, constraints, statuses and media types are unchanged.
