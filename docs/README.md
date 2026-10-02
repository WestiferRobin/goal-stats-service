# Backend documentation

Begin with the repository [README](../README.md). Ordinary contributors need only
`make setup`, `make run`, `make test`, `make stop`, and `make help`.

- [Architecture](service/architecture.md): request flow through the monolith.
- [Football API and data](service/football.md): routes, predictions, and CSVs.
- [Environment](service/environment.md): the `.env.local` contract.
- [Development internals](service/development.md): maintainer-only mechanisms.
- [Testing](testing/overview.md): isolation and ownership guarantees.

Maintainer-only references:

- [Built-system smoke testing](testing/smoke.md).
- [Release certification](testing/certification.md).
- [Standalone SQL](../sql/README.md).

Docker, PostgreSQL, Redis, Alembic, and seeding are implementation details, not
prerequisites for beginning feature work.
