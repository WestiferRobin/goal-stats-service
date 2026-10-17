# Goal Stats and the RoadToTheFinal reference engine

Goal Stats uses one normalized Women's World Cup database. RoadToTheFinal is the
attributed reference implementation of the unchanged mathematics, not a second
team catalog, persistence service or production dataset.

See [API contracts](frontend-api.md) and [architecture](architecture.md).

## Historical import operations

Run `make seed DATASET=womens-world-cup DRY=true` to inspect proposed imports;
remove `DRY=true` only for an explicitly authorized target. This phase did not seed
persistent resources. The Make workflow requires prepared infrastructure and the
pinned source, verifies the runtime fingerprint, and imports each edition separately.

The underlying Flask `import-football` command requires an approved `--dataset`,
explicit `--directory`, `--target`, `--expect-host` and `--expect-database`.
Cloud targets additionally require `--confirm-production` and verified TLS.
Checksums, approved selections, conflicts, source provenance and idempotency remain
unchanged. Missing dataset selection fails; no prototype fallback or standalone
prototype importer exists. Imports never modify scenarios or predictions.

## Preserved and deferred capabilities

The pure formatter is `football/report.py`. Preview, saved generation and simulation
use explicit inputs; identity validation uses TeamService and normalized records.
Historical comparisons use MatchService and MatchRepository.

`football/historical.py`, `live.py` and `provider.py` preserve reference parsing and
provider helpers, with their tests. No active HTTP route calls them. Historical
backtesting needs time-correct ratings and observed match state; the old advancement
winner metric is not a three-way accuracy metric. Live adaptation needs verified
competition/participant mapping, timestamps and an unknown-statistics policy.
Reference parser defaults must not be presented as observed historical facts.

## Persistence retirement

Head `d91e6a4b208f` follows `c8d42f19e630`. It locks the three prototype tables,
requires ordinary tables owned by the current migration user in the current schema,
refuses populated tables and drops without CASCADE. Unexpected dependencies abort
transactionally. Normalized records are untouched.

Before any persistent upgrade, inventory dependencies and records, verify external
backups and agree archival/rollback. Populated tables deliberately block migration;
this migration never deletes their rows or fabricates missing original ratings.
Downgrade recreates empty schema, not lost data. Fresh installs and disposable
upgrades are tested. No persistent migration is authorized by this implementation.

## Phase boundaries

Prompt 1 adapted backend behavior and corresponding tests. Prompt 2 implemented
mandatory real-source certification and macOS read-only mounting; Prompt 3 performs
independent final certification. `make test` runs ordinary Unit + Integration tests
with the pinned-source test excluded. `make certify` includes actual pinned-source
verification and requires at least 95% combined statement and branch coverage.

Tests run locally through `.venv`, with Docker providing disposable PostgreSQL and
Redis. Certification checksum-verifies the approved source and mounts it on a
read-only filesystem. If mandatory historical-source verification cannot execute,
certification fails; no prototype CSV fallback exists. A passing ordinary suite
is not proof of development seeding or final production certification.
