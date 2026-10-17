# Item/Action retirement preparation

> Historical Prompt 1 snapshot: Item/Action were active when this preparation was
> completed. See [Prompt 2 retirement status](item-action-backend-retirement.md) for
> the current checkout and deployment restrictions. The evidence below is preserved.

Item/Action remain active. This preparation does not remove routes, change the
schema, or complete frontend coordination. Production code and SQL are unchanged.

## Baseline

The [preparation baseline](item-action-retirement-baseline.json) records HEAD,
worktree status, repository hashes, full-record digests, Docker identities/states,
and volumes before test changes. It contains hashes, not credentials or records.
Branch: `member/wes`; HEAD: `5259b8e`; Alembic repository/database head:
`a7c93e25d104`; ten application mappings plus `alembic_version`; 976 collected tests.

Persistent counts: teams 44, competitions 9, matches 348, scenarios 3, predictions 4,
football_teams 32, football_history 16, football_snapshots 0, items 0, actions 0.

`tests/integration/router_inventory.json` preserves all seven blueprints and 39
Flask rules. `tests/unit/schemas/contract_fingerprints.json` preserves complete
OpenAPI and 42 schema fingerprints. `tests/integration/football/router_contract.json`
preserves normalized workflow responses and errors. Do not remove Item/Action
expectations until their removal is intentional and authorized. During retirement,
review only the retired OpenAPI paths/components; retain normalized schema hashes.

The twelve retirement operations are GET/POST `/items`, GET/PUT/DELETE
`/items/<uuid:item_id>`, GET/POST `/actions`, GET/PUT/DELETE
`/actions/<uuid:action_id>`, and GET/POST `/items/<uuid:item_id>/actions`.

## Test classification and coverage

| Tests/fixtures | Classification and preparation |
| --- | --- |
| `tests/unit/infra/caches/test_domain.py` | DOMAIN-ONLY adapter contracts remain unchanged; generic tests moved to `test_provider.py` beside it. |
| `tests/integration/infra/caches/test_redis.py` | DOMAIN-ONLY cache-aside, invalidation, stale-child, and failed-commit cache assertions retained. |
| `tests/integration/infra/caches/test_provider.py` | SHARED: direct JSON, misses, TTL expiration, namespace separation, corrupt payloads, exact-key deletion, ACL recovery; Scenario HTTP writes/reads survive ACL and connection outages; readiness tests use Team table/columns. |
| `tests/fixtures/redis.py` | SHARED, unchanged: owned provider and per-app namespace cleanup, no global flush. |
| `tests/fixtures/database.py` | SHARED: owned database cleanup follows registered metadata in reverse FK order, with no Item/Action table-name dependency. All application tables are cleaned only inside the ownership-verified disposable database. |
| `tests/integration/infra/resources/test_db.py` | SHARED, unchanged: real commit/rollback, closed sessions, pool release, authentication failures, readiness. Uses a test-only probe table. |
| `tests/integration/infra/repositories/test_goal_stats.py` | SHARED/RETAINED, unchanged: real caller-owned sessions, no repository commits/rollbacks, uncommitted visibility, rollback, locking, ordering, joins and identity behavior. |
| `tests/unit/services/test_services.py` | DOMAIN-ONLY cache behavior retained, including overlapping Item/Action operations. Its generic isolation guarantee now also has real ScenarioService coverage in `tests/integration/football/test_service_transactions.py`. No replacement production cache introduced. |
| `tests/integration/infra/repositories/test_persistence.py` | DOMAIN-ONLY Item/Action ordering, constraints, cascade and update/delete race retained. Retained repository and DB tests already cover generic ownership/rollback/FKs; do not invent Scenario deletion to imitate a retired API. |
| `tests/fixtures/item.py`, Item/Action router/schema unit tests | DOMAIN-ONLY, unchanged until Prompt 2. |
| `tests/unit/exceptions/test_exceptions.py` | SHARED import-isolation check now imports DomainError's module; legacy exception-specific cases remain. |
| `tests/integration/routers/test_resources.py` | DOMAIN-ONLY HTTP contracts retained. Shared safety resides in `test_errors.py` and normalized API tests. |
| `tests/integration/routers/test_errors.py` | SHARED safe Problem Details, private-data protection, malformed JSON, validation and Allow headers retained; malformed JSON now also exercises Scenario and prototype prediction endpoints. |
| `tests/integration/football/test_scenarios_api.py` | RETAINED; missing-record checks now verify Problem Details shape/media type and unsupported DELETE verifies 405/Allow. Existing invalid-state, rollback and private-error tests remain. |
| `tests/integration/test_main.py` | SHARED resource isolation now uses Team/Competition; template extension presence is a separate DOMAIN-ONLY assertion. Existing five-entity injection/isolation, import side effects and ten-table baseline remain. |
| `tests/integration/routers/test_openapi.py`, route inventory, schema fingerprints | SHARED plus current domain baseline; unchanged until intentional API retirement. |
| `tests/integration/migrations/*` | SHARED plus historical domain schema cases; current ten-table/head expectations retained. See migration handoff below. |
| `tests/integration/migrations/test_catalog.py`, `tests/integration/football/test_{scenarios,predictions}_api.py` | RETAINED real PostgreSQL FK/check-constraint enforcement and failed-write rollback; retained coverage does not depend on Item/Action repositories. |
| Other normalized, prototype, settings, SQL export, importer, error, ownership and workflow tests | UNRELATED/RETAINED unchanged. |

Do not delete mixed files wholesale. Move or retain shared cases when domain-only
cases are removed. Cache-aside invalidation is specific to the retiring adapters;
generic Redis tests must not depend on adding normalized caches. Generic Pydantic
utilities and `Timestamped` remain: FootballSnapshot uses the latter.

## Frontend handoff (paths relative to goal-stats-app)

`src/app/page.tsx` renders `src/features/home/components/home-view.tsx`, which
calls `listItems` and `listActions`. Forms call `createItem` and `createAction`
server actions. These are active consumers, not unused imports.

| Files | Required coordinated action |
| --- | --- |
| `src/app/page.tsx` | Replace or retire the Home scaffold before backend API removal. |
| `src/features/home/api/items.server.ts` | Remove/replace GET and POST `/items`. |
| `src/features/home/api/actions.server.ts` | Remove/replace GET and POST `/items/<id>/actions`. |
| `src/features/home/domain/actions.ts` | Remove/replace Item/Action server actions and their redirect/revalidation flow. |
| `src/features/home/components/{home-view,item-form,action-form}.tsx` | Replace or retire the consuming UI. |
| `src/features/home/domain/{types,errors}.ts`, `src/features/home/api/decode.server.ts` | Review Home-only contracts/helpers after removing consumers. |
| `src/lib/env/{server.ts,server.test.ts}`, `.env.example`, `scripts/develop.sh` | Review `homeApiBaseUrl` and `SERVICE_API_BASE_URL`; development currently requires that variable. Preserve `FOOTBALL_API_BASE_URL` and the football proxy. |
| `src/features/home/api/{items.server.test,actions.server.test,home-api.test}.ts`, `src/features/home/domain/actions.test.ts`, `src/features/home/components/{home-view,item-form,action-form}.test.tsx` | Replace tests with the chosen Home behavior; do not keep calls to retired endpoints. |
| `tests/e2e/{home,live-home}.spec.ts` | Update live and error-state flows before deployment. |
| `src/lib/api/client.test.ts` | Preserve generic HTTP decoding, error sanitization and transport coverage even if examples change. Preserve shared client/error implementation. |
| `README.md`, `docs/{ARCHITECTURE,DEVELOPMENT,TESTING}.md`, `src/features/README.md`, `src/features/home/README.md` | Update active Home/configuration guidance. |

Frontend files were inspected only. No replacement UI has been selected or built.

## Prompt 2 wiring and migration handoff

Remove Item/Action imports, construction, cache extensions and blueprint registration
from `src/main.py`; remove only their metadata imports/readiness probes from
`src/infra/resources/db.py` and `alembic/env.py`. Remove the legacy exception 404
branch and ID-specific validation detail branch in `src/exceptions/handlers.py`.
Preserve shared errors, database/Redis ownership, readiness policy, CLI, Swagger,
five normalized services and RoadToTheFinal. `models/hold/football.py` stays active.

Do not rewrite `a7c93e25d104_init_models.py`. Add one forward revision. Lock and check
both legacy tables in the same transaction before any drop; refuse nonempty tables;
drop Action before Item without broad CASCADE. Stop old writers first. Define and
test downgrade behavior explicitly; recreating empty tables cannot recover records.
The guard must work with the existing offline SQL exporter (emit executable SQL
rather than requiring a live Python SELECT result during offline generation).

Current-head and historical-initial assertions must be separated in Prompt 2:

- `tests/integration/migrations/test_schema.py`: final head has eight application
  mappings; initial revision still historically creates ten.
- `tests/integration/migrations/test_catalog.py`: preserve initial schema tests;
  do not populate legacy tables then expect a guarded retirement upgrade to succeed.
  Add nonempty refusal and retained-record preservation cases.
- `tests/integration/routers/test_football.py`: update the fresh SQL head assertion.
- `sql/verify_historical_import.sql`: update only the head requirement; retain facts,
  provenance and preservation checks.
- Regenerate `sql/001_fresh_database.sql` with the existing exporter; retain prototype
  SQL and historical migration files. SQL export equality tests must still pass.
- Do not change current expectations to eight tables in preparation.

## Deployment order and remaining blockers

1. Land shared coverage preparation with all current APIs intact.
2. Coordinate frontend Home replacement/removal while old APIs still exist.
3. Deliver backend wiring/domain removal, guarded migration, maintained SQL and
   reviewed API baseline updates together; run full and disposable migration tests.
4. Retire old consumers/writers before deploying the new backend/schema. Refresh
   prepared images separately; the audited runtime image is stale and seed preflight
   must not be bypassed. No persistent image rebuild is part of preparation.
5. Verify retained full-record digests, schema/readiness, API contracts, and Docker
   identities/volumes. Stop for unexpected legacy records or unknown consumers.

Preparation is not authorization to drop tables or deploy a breaking API change.
Frontend coordination and the guarded migration remain outstanding. No broad
architecture refactor is needed.

## Preparation verification

Affected infrastructure, services, schemas, routers, factory, Scenario/Prediction
and migration tests: **345 passed, 0 failed, 0 skipped** using the canonical
ownership-verified disposable PostgreSQL/Redis harness with a focused selection.
Full `make test`: **974 passed, 0 failed, 8 skipped** (982 collected), with Ruff lint,
formatting and strict mypy passing. The eight GNU Make dispatch cases skipped in
the container passed separately on the host: **8 passed, 0 failed, 0 skipped**.
Fresh route/OpenAPI/schema/API response snapshots match the pre-preparation snapshot.
