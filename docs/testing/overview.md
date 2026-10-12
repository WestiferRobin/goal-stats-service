# Testing

`make test` is the single supported automated verification command. It requires
Docker/Compose and Python 3.12, builds the tooling image, runs Ruff lint and formatting
checks and strict mypy, then executes `tests/unit` and `tests/integration`.

The suite includes application contracts, prediction calculations, migration/schema
checks, startup/configuration safety, provider ownership and runner cleanup tests.
State-changing integration tests use disposable PostgreSQL and Redis. No dedicated
smoke, coverage or lifecycle certification mode runs automatically or has a supported
command dispatcher.

## Isolation and cleanup

Each run generates a unique `goal-stats-service-test-<24 hex digits>` project and fresh
credentials. Providers use tmpfs, expose no host ports and mount no persistent volumes.
Tests never load `.env.local` or fall back to development infrastructure.

Before migrations or fixtures connect, the host verifies provider container IDs,
Compose labels, health, credentials, database name, private network and disposable
storage. A read-only receipt binds the runner hostname, project and exact provider URLs.
Missing or mismatched receipts fail closed. Inherited application, test-target and
Compose overrides are rejected without printing their values.

Normal completion, failures, SIGINT and SIGTERM clean only the owned runner and project.
Cleanup never uses global prune or volume deletion. The runner checks for owned resource
leaks and preservation of preexisting containers, networks and volumes. Focused shell
tests exercise failure and signal cleanup with recording Docker executables; the normal
integration run exercises real provider ownership and completion cleanup.

## Migration and API coverage

Alembic remains in use. Integration tests compare metadata, detect schema drift and
outdated revisions, generate revisions only in temporary directories against disposable
databases, and verify PostgreSQL read-only enforcement. Startup migration tests remain.

Flask integration tests cover catalog, Scenario and Prediction APIs, immutable prediction
inputs, history and compatibility endpoints. Retained HTTP reference tests under
`tests/smoke` are excluded from collection and have no supported launcher; they are not
claimed as executed by `make test`. See [HTTP testing scope](smoke.md).

## Pinned historical source acceptance

[Prompt 6 integration evidence](data-integration.md) describes the separate, explicit
acceptance test under `tests/acceptance`. It requires the actual pinned CSV mounted
read-only and ownership-verified disposable providers. It is outside the ordinary
`make test` selection, so routine verification does not depend on ignored local data.

## Testing scripts

- `scripts/testing/test.sh` implements `make test` and scopes disposable resource cleanup.
- `scripts/testing/test_resources.py` inspects Docker providers on the host and issues
  the ownership receipt before test execution.
- `scripts/testing/test_ownership.py` validates that receipt and runner configuration
  before commands or database fixtures proceed.
- `scripts/testing/http_client.py` supplies HTTP assertions to retained smoke fixtures;
  those reference tests remain excluded from normal collection and have no launcher.

These helpers support the single public test command; they do not add testing modes.
