# Backend documentation

Begin with the repository [README](../README.md). Ordinary contributors need only
`make setup`, `make infra`, `make run`, `make deploy`, `make seed`, `make test`, `make stop`, and `make help`.

`make run` uses host Flask; `make deploy` uses Docker Flask. Both use Docker
PostgreSQL/Redis and the same development database. Setup prepares Python 3.12 `.venv`.

- [Architecture](service/architecture.md): request flow through the monolith.
- [Football API and data](service/football.md): routes, predictions, and CSVs.
- [Environment](service/environment.md): the `.env.local` contract.
- [Development internals](service/development.md): host development and lifecycle ownership.
- [Testing](testing/overview.md): isolation and ownership guarantees.

Maintainer-only references:

- [Workflow verification](testing/certification.md).
- [Standalone SQL](../sql/README.md).

Install Python 3.12, Docker/Compose, and GNU Make. PostgreSQL/Redis installations
on the host are unnecessary. Startup prepares the schema with Alembic; dataset
imports require an explicit operation and never run automatically.

The supported lifecycle entry points are `scripts/development/local.sh` and `scripts/testing/test.sh`.
`make test` is the single automated verification command. Alembic migrations remain
part of normal startup; historical dataset import remains an explicit operation.
Dated backend certification and task acceptance reports are historical evidence.

## Explicit historical seeding

`make seed DATASET=womens-world-cup DRY=true` previews all nine editions.
Use `DRY=false` to write, or select an individual ID such as `womens-world-cup-2023`.
Omitted `DRY` means `false`; empty/other values and legacy `DRY_RUN` are rejected.
Contracts remain in `data/womens-world-cup/`, with pinned source in `data/raw/`.
The command requires prepared infrastructure and schema; it never starts services,
migrates or selects prototype data. Each edition commits separately, so earlier
commits survive later failure and unchanged imports can be safely retried. Dry-run
team estimates are edition-local, not additive. Startup imports nothing.
See [seed prerequisites, safeguards and reporting](interface/make.md#explicit-historical-seeding) for the full contract.
