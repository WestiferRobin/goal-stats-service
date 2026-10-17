# PostgreSQL schema exports and verification

`001_fresh_database.sql` is generated offline from the unchanged historical Alembic
chain plus forward head `d91e6a4b208f`. Its final schema contains the five normalized
application tables and `alembic_version`. Historical SQL creates then retires legacy
tables; it never seeds prototype records. No prototype seed artifact is supported.

Regenerate with `python scripts/database/export_football_sql.py --mode schema`,
using an explicit PostgreSQL dialect URL. Exporting opens no database connection.
Applying SQL is a separate operation, never part of an audit or export.

The forward retirement locks prototype tables, verifies ownership, rejects records
and drops with RESTRICT. A populated installation must be inventoried, backed up and
archived through a separately reviewed operation. Downgrade restores empty schema
only. Never execute schema SQL against persistent data without target verification.

## Read-only historical acceptance

`verify_historical_import.sql` uses SELECT statements inside a REPEATABLE READ,
READ ONLY transaction. It never imports, migrates, repairs, advances sequences or
writes records. `ON_ERROR_STOP` makes invalid states exit nonzero with failed-check
names. Database identity and Alembic head are reported; an optional expected database
name enables target assertion.

Default **current** mode permits absent editions, but each present approved edition
must be complete and consistent. The complete dataset contains 44 teams, nine competitions and 348 matches.

```sh
docker compose --env-file .env.local -p goalstats-service-local \
  -f docker/compose.local.yml exec -T postgres \
  psql -X -v ON_ERROR_STOP=1 -U goalstats -d goal_stats_service_local \
  < sql/verify_historical_import.sql
```

Explicit **complete** acceptance requires all nine editions, 348 matches and 44
shared team identities. With an already configured `psql` connection:

```sh
PGOPTIONS='-c goalstats.verify_complete=true -c goalstats.verify_database=goal_stats_service_local' \
  psql -X -v ON_ERROR_STOP=1 -f sql/verify_historical_import.sql
```

For the Docker invocation, place `-e PGOPTIONS='-c goalstats.verify_complete=true'`
after `exec` and before `-T postgres`. Complete mode fails if any approved edition is missing or incomplete.

Assertions cover edition/competition identity, counts, exact participant keys, goals,
date bounds, source namespace/revision/checksum/URL, score semantics, source labels,
duplicate identities and orphaned references. Expected facts mirror the checked-in
coverage evidence and are checked for drift by tests. Historical validation scopes
itself to the approved World Cup source and editions; other legitimate sources,
competitions and scenarios are not rejected.

The `preservation` result contains counts and deterministic full-record MD5 digests
for catalog, scenario and prediction tables, including IDs, timestamps
and provenance. Save this JSON before a transition and compare afterward. For an
automated assertion, supply that exact JSON as the session setting
`goalstats.verify_preservation` (for example through a properly quoted libpq
`options` value). Equality is enforced, including table names and row counts.
Without a supplied baseline, digests are evidence only; a single snapshot cannot
prove that earlier records were preserved. MD5 here is a change detector, not an
authenticity or security certificate.

No historical SQL INSERT generator exists. Real data uses the guarded Flask importer.
No prediction ratings are inferred from historical results. Source ordering/venue
limitations remain. Explicit historical `make seed` now invokes the guarded Flask importer; it does not execute these SQL exports. Dated local acceptance
is retained in [Task #2 evidence](../docs/service/task2-acceptance.md).


## Artifact inventory

- `001_fresh_database.sql`: deterministic offline migration-chain export.
- `verify_historical_import.sql`: read-only historical evidence and preservation checks.

The approved seed workflow is `make seed DATASET=womens-world-cup` with explicit
target safeguards. There are no SQL data inserts replacing that importer.
