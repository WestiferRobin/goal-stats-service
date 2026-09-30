# Test ownership

After setup, use `make quick-test` for fast host unit feedback. Use `make test`
for unit + integration tests with automatically managed disposable providers.
Use `make check` for lint, formatting and types, and `make tooling` after changing
Make/Python workflow code. Plain `pytest` includes integration tests and therefore
requires a provisioned owned TEST session; it is not the quick-start command.

UNIT TESTS FOLLOW LOGIC

INTEGRATION TESTS FOLLOW BOUNDARIES

SMOKE TESTS FOLLOW BUILT SYSTEM

Unit tests cover settings, schemas, service decisions, cache identity/payload logic,
and safe domain errors. Router unit tests are provider-free and use explicit fake
or injected collaborators to check HTTP adaptation, service command construction,
status codes, response bodies, and Location/other headers where appropriate.

Integration tests exercise Flask/flask-openapi3 binding, validation/error handling,
OpenAPI, real PostgreSQL repositories/constraints/transactions, real Redis behavior,
and Alembic history. Smoke tests exercise endpoints of the built application.

`tests/fixtures/` owns settings, app factories, disposable database/Redis fixtures,
named Item/service collaborators, and smoke clients. Root `conftest.py` registers
fixtures and gates smoke collection. There is no global provider registry.

Default pytest selects `tests/unit tests/integration`. Even explicit `pytest tests`
ignores the smoke directory unless `--smoke` is supplied. `make smoke` is the
supported built-system entrypoint: direct smoke selection additionally requires its
owned runtime configuration. Tooling tests live in `scripts/tests`; `make tooling`
and certification run them separately from application unit/integration ownership.

Provider fixtures require explicitly disposable resources. Missing or unverified ownership in
manual pytest runs fails with guidance to start `make test-providers`; Make provisions
providers automatically, so canonical integration/full/coverage runs have zero skips. Invalid or unavailable supplied
providers fail. PostgreSQL uses a dedicated `goalstats_test_*` database within an
ownership-verified disposable provider; that name alone is not proof. Redis keys
use fixture prefixes, and tests that change server-wide ACL state require the same
verified disposable ownership. No shared database/cache fallback is permitted.
Use one provider pair per concurrent pytest process; xdist is not configured.

`make coverage` measures application unit/integration coverage only, inside the
removed TEST runner. Smoke is not used to inflate it. No 100% threshold is imposed.
Migration tests verify fresh upgrade, repeat safety, downgrade/re-upgrade, and
`alembic check`. Revision `b7f42e9c1a60` is preserved.

See [smoke](smoke.md), [certification](certification.md), and
[Make interface](../interface/make.md).

## IDE integration debugging

Both IDEs discover unit and integration tests from the repository root. Collection
never provisions providers; smoke still requires explicit `--smoke`. Unit tests
need no Docker or provider URLs. Run a folder, file, or single node with the repo
`.venv/bin/python -m pytest`; never apply `.env.local` globally to testing.

Run `make test-providers` in a terminal and leave it in the foreground. It starts
fresh disposable TEST PostgreSQL/Redis with generated credentials and dynamic
loopback ports. Private JSON manifests are internal ownership state. Run the desired
integration file/node in PyCharm, or choose `pytest: owned TEST session` in VS Code.
No env profile is needed. Exactly one session must be present; ambiguity fails closed.
Use only one pytest process per session.
The database fixture migrates the disposable database on first use.

Before connecting, fixtures verify the private manifest, active owner lock/PID,
exact Docker project, container IDs, Compose service/project labels, session token,
running/healthy state, isolated network, tmpfs storage, exact loopback publications,
and matching PostgreSQL/Redis URLs and credentials. Arbitrary URLs plus disposable
flags or a test database name are insufficient. Stale or mismatched sessions fail
closed. This protects PostgreSQL schema downgrade/delete operations and server-wide
Redis ACL changes; key prefixes alone do not provide isolation.

Canonical Docker `make integration`/`make test` retain automatic isolated provision,
execution and cleanup. Their runner receives a read-only ownership receipt bound to
its hostname and internal TEST URLs; no Docker socket is mounted into tests. Host
execution cannot opt into that path by setting environment flags. Normal runs do
not require an IDE session. Ctrl-C/SIGTERM on the host owner revokes its manifest,
removes its exact owned resources and private files, and preserves LOCAL/DEV data.
