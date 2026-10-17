# Testing

`make test` runs the standard automated verification workflow. It requires
Docker/Compose and the repository Python 3.12 `.venv`. It verifies pinned dependencies,
runs host Ruff lint/format and strict mypy, then executes `tests/unit` and
`tests/integration` together in one host pytest invocation. Run `make setup` if the
environment is missing or invalid; testing never installs packages or falls back to
system Python. Docker runs only disposable PostgreSQL and Redis.

Unit tests verify isolated behavior. Integration tests exercise Flask APIs, PostgreSQL,
Redis and component interactions. Shared fixtures own disposable resources.
The suite includes application contracts, prediction calculations, migration/schema
checks, startup/configuration safety, provider ownership and runner cleanup tests.
State-changing integration tests use disposable PostgreSQL and Redis.
`make certify` measures the complete Unit + Integration
suite with a 95% combined statement-and-branch coverage requirement. `make test`
continues to run without a coverage gate. See [certification](certification.md) for
report locations, failure semantics and the measurement boundary.

## Test ownership and shared fixtures

Domain schema unit tests live under `tests/unit/schemas/{team,competition,match,scenario,prediction}/`.
Service unit tests remain under `tests/unit/services/`; pure prediction calculations,
settings, and shared utilities retain their existing suites. Routers have integration
tests, with no router unit-test category. Shared Redis resource tests live in
`tests/unit/infra/resources/test_redis.py` and
`tests/integration/infra/resources/test_redis.py`; no business cache is implied.

Root `tests/conftest.py` is the only conftest and registers the eight shared fixture
plugins. Function-scoped service doubles and transaction probes live in
`tests/fixtures/scenarios.py`. Database-backed catalog fixtures, scenario builders,
CLI helpers and saved-scenario fixtures live in `tests/fixtures/historical_database.py`.
They retain ownership-verified disposable schemas, fixture names and cleanup.
Importing fixture plugins or collecting tests does not connect to providers.

Each of the eight router modules has a matching integration test file. Catalog
checks are partitioned by Team, Competition and Match; shared OpenAPI assertions live
in `routers/test_openapi.py`. The saved Scenario → Prediction HTTP workflow lives in
`routers/test_prediction.py`, with its unchanged `router_contract.json` beside it.
Application error-handler integration lives in `integration/test_main.py`.

The five repositories have separate integration files. Prediction owns the combined
persistence rollback check; lock cases remain with the repository taking the lock.
Scenario and Prediction service integration files preserve cross-domain transaction
and orchestration behavior. Schema unit tests mirror request, response and base
modules where existing assertions warrant them; `schemas/test_common.py` preserves
the approved schema fingerprints and package export identities.

Historical CLI integration lives in `integration/football/test_cli.py`. Importer,
multi-edition and read-only historical SQL checks live in
`integration/football/test_historical_import.py`. Script-owned unit tests remain
explicit exceptions to the `src/` naming mirror. No empty modules are created for
uncovered source files. Standalone migration tests remain removed; embedded upgrade,
data-preservation and schema-readiness assertions remain with their owning tests.
There are no acceptance, workflow, router-unit or domain-cache test categories.

## Isolation and cleanup

Each run generates a unique `goal-stats-service-test-<24 hex digits>` project and fresh
credentials for both providers. Providers use tmpfs and Docker-allocated ports bound
only to `127.0.0.1`, with no persistent volumes. PostgreSQL has a generated user and
password; Redis requires a separate generated password.
Tests never load `.env.local` or fall back to development infrastructure.

Before migrations or fixtures connect, the host verifies provider container IDs,
Compose labels, health, credentials, database name, private network and disposable
storage. A private version-3 receipt binds the session, project, network, full container
IDs, actual port mappings and exact provider URLs. Live Docker metadata is rechecked
before commands and fixture activation; authenticated connections precede commands.
Missing or mismatched receipts fail closed. Inherited application, test-target and
Compose overrides are rejected without printing their values.

Normal completion, failures, SIGINT and SIGTERM stop the owned host process groups
and wait for children before cleaning only the owned project.
Cleanup never uses global prune or volume deletion. The runner checks for owned resource
leaks and preservation of preexisting containers, networks and volumes. Focused shell
tests exercise failure and signal cleanup with recording Docker executables; the normal
integration run exercises real provider ownership and completion cleanup.

## Migration and API coverage

Alembic remains in use. Integration tests compare metadata, detect schema drift and
outdated revisions, generate revisions only in temporary directories against disposable
databases, and verify PostgreSQL read-only enforcement. Startup migration tests remain.

Flask test-client integration tests cover catalog, Scenario and Prediction APIs,
immutable prediction inputs, history, preview, historical comparisons, safe errors and
local Swagger assets. Redis integration tests verify cache hits, contents, TTL and
invalidation. Hypothetical tournament tests cover normalized identities, explicit ratings,
bracket bounds, response structure and percentage units. No prototype API is active.
These read-only operations are checked for unchanged application records and absence
of database-writing statements; tournament tests do not require a particular random champion.
These tests do not certify external networking or actual Docker application recreation.

For a manual local availability check after `make run` or `make deploy`, inspect
`/health`, `/ready` and `/swagger`. Use disposable databases for state-changing checks;
do not create persistent records merely to validate the development workflow.

## Pinned historical source certification

`make test` explicitly selects `-m 'not pinned_source'`: all Unit and Integration tests
except the one real-source test. `make certify` selects both directories without a marker
exclusion, including that test in the same coverage/pytest invocation. `pytest.ini` has
no global marker filter; direct full pytest therefore also requires the source/provider
receipts. There is no separate acceptance command, second pytest stage or global seed.

Prepare the approved ignored source at
`data/raw/martj42-womens-results/1855e313ae8bcd0330426e62c8e4cf15ce45077c/results.csv`.
Certification verifies SHA-256
`de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0`
and all nine manifests. It never downloads, edits or substitutes the source.

On macOS the runner creates a private invocation-owned UDRO/HFS+ disk image using
`hdiutil`, mounts it with `-readonly -nobrowse`, and verifies image ownership, canonical
path, filesystem `ST_RDONLY`, and mounted bytes. Chmod and Docker bind flags are not
substitutes. `TEST_PINNED_SOURCE` is set internally for this invocation; inherited
values are rejected. Missing source or unsupported/failed mounting fails certification.

The existing `test_pinned_source_import_repeat_and_application_restart` imports all
nine editions only into its isolated disposable schema. It checks 44 teams, nine
competitions, 348 matches and 1,081 goals, provenance, every source result, catalog
APIs, the Spain–England 2023 final, preview, hypothetical simulation, saved predictions,
repeat import and application/pool recreation. Scenario ratings are explicitly synthetic
assumptions. Other tests retain their small synthetic fixtures. See
[data integration](data-integration.md) for the verification boundary.

Cleanup first reaps owned Python processes. It removes the invocation's raw coverage,
cleans and checks owned Docker resources, then validates the source receipt and exact
image identity before detaching only that device and deleting private source artifacts.
A failed detach or ownership check retains the session directory for recovery and
returns failure; the runner never recursively deletes a mounted source. PASS requires
successful cleanup. SIGINT/SIGTERM preserve their failure status.

## Testing scripts

- `scripts/testing/pinned_source.py` owns read-only source provisioning, verification and cleanup.
- `scripts/testing/test.sh` implements `make test` and scopes disposable resource cleanup.
- `scripts/testing/test_resources.py` inspects Docker providers on the host and issues
  the ownership receipt before test execution.
- `scripts/testing/test_ownership.py` validates that receipt and runner configuration
  before commands or database fixtures proceed.

The runner accepts no arguments for `make test`, or exactly `certify` for
`make certify`. No other modes or forwarded arguments are supported.
`scripts/testing/coverage_report.py` renders the measured reports and evaluates
coverage counts; it does not provision resources or run tests.


## Completed source-mirrored unit ownership

The following suites isolate their modules' behavior while retaining existing integration coverage:

- `tests/unit/exceptions/test_handlers.py`
- `tests/unit/football/test_cli.py`
- `tests/unit/football/test_historical_import.py`
- `tests/unit/football/test_scenario_prediction.py`
- `tests/unit/infra/test_base.py`
- `tests/unit/schemas/match/test_response.py`
- `tests/unit/schemas/scenario/test_response.py`

Shared fixtures remain registered only through root `tests/conftest.py`. `make certify`
requires at least 95% combined statement-and-branch coverage. It retains `coverage.json`
and `coverage.xml` in its unique ignored report directory and removes that invocation's
raw `.coverage` during exit cleanup, including failure paths. Missing reports, insufficient
coverage, test failures or cleanup failures prevent PASS; prior failure codes survive cleanup.
