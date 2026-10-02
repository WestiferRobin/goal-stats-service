# Testing

Run `make test` from the repository root. It builds the tooling image, runs Ruff and
strict mypy, starts a uniquely named disposable PostgreSQL/Redis stack, migrates it,
and runs unit plus integration tests.

The integration guard requires a per-run ownership receipt mounted only into the test
runner. Endpoints must match the disposable Compose services. Cleanup removes that
exact test project's containers, network, and volumes even after failure. The
persistent development database is never a test target.

Tests generate credentials and policy internally. No `.env.test`, local providers,
manual migrations, or manual teardown is required.
