# Development internals

The root README owns the supported contributor loop. `make run` handles build,
provider startup, migration, idempotent CSV import, and API startup. `make stop`
preserves PostgreSQL data.

Alembic revisions remain in `alembic/versions/`, and the importer remains in the
application image. Maintainers can use underscore-prefixed internal targets in the
root `Makefile` for migration authoring/checking and release validation. They are
absent from `make help` and are not onboarding requirements.

Do not introduce a parallel host-Python or DEV-mode happy path. Retained internal
tools must stay behind the public five-command interface.
