# Backend documentation

Begin with the repository [README](../README.md). Ordinary contributors need only
`make setup`, `make infra`, `make run`, `make deploy`, `make test`, `make stop`, and `make help`.

`make run` uses host Flask; `make deploy` uses Docker Flask. Both use Docker
PostgreSQL/Redis and the same development database. Setup prepares Python 3.12 `.venv`.

- [Architecture](service/architecture.md): request flow through the monolith.
- [Football API and data](service/football.md): routes, predictions, and CSVs.
- [Environment](service/environment.md): the `.env.local` contract.
- [Development internals](service/development.md): host development and lifecycle ownership.
- [Testing](testing/overview.md): isolation and ownership guarantees.

Maintainer-only references:

- [Built-system smoke testing](testing/smoke.md).
- [Release certification](testing/certification.md).
- [Standalone SQL](../sql/README.md).

Install Python 3.12, Docker/Compose, and GNU Make. PostgreSQL/Redis installations
on the host are unnecessary; migrations and data import are handled by the workflow.
