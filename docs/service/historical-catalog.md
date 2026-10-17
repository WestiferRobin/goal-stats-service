# Historical catalog

Current architecture: five application tables, independent domain routers and no
prototype data fallback. See [API contracts](frontend-api.md), [import/retirement
safeguards](football.md) and [source integrity](../../data/README.md).

The approved 1991–2023 selection contains 44 teams, nine editions, 348 matches and
1,081 goals. The importer retains exact source checksum, date/participant selection,
provenance, stable identities, conflict rejection and per-edition transactions.
Historical inputs populate teams, competitions and matches only. Unavailable
strength ratings remain null; scenarios require explicit assumptions.

Catalog and insights reads use normalized repositories. Comparisons preserve dates,
home/away orientation, competition identity and score basis. They never invent
in-play statistics. Scenario/prediction records survive repeated historical imports.

Fresh startup does not seed. Runtime readiness requires five tables at head
`d91e6a4b208f`. The retirement migration blocks populated prototype tables pending
external preservation and coordinated archival. No persistent migration/import was
performed in Prompt 1. `make test` runs ordinary Unit + Integration tests, excluding
the pinned-source test. `make certify` includes actual pinned-source verification
and requires at least 95% combined statement and branch coverage. Synthetic fixtures
are not source proof.

Both commands run locally through `.venv`; Docker supplies disposable PostgreSQL
and Redis. Certification checksum-verifies the approved source and mounts it on a
read-only filesystem. It fails if mandatory historical-source verification cannot
execute. No prototype CSV fallback exists.
