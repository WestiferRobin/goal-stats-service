# PostgreSQL schema exports and verification

Run from this repository root using `psql` and your intended PostgreSQL database.
`PGDATABASE`, `PGHOST`, `PGPORT`, `PGUSER` and a password file can supply connection
settings. Do not put credentials in these checked-in files.

The schema export is for an **empty database only**:

```sh
psql -X -v ON_ERROR_STOP=1 -f sql/001_fresh_database.sql
```

It is generated from the unchanged initial `a7c93e25d104` revision followed by
`c8d42f19e630`, which safely retires empty Item/Action tables. The final schema has
eight application tables and the new Alembic head. Existing databases use the forward
Alembic migration, not this fresh export. Persistent upgrades and deployment remain
blocked on frontend Home coordination; see the [handoff](../docs/testing/item-action-backend-retirement.md).
Older intermediate revisions must finish the original chain with the previous
checkout; never stamp an incomplete schema as current.

Optional, explicitly invoked prototype compatibility operation (never part of startup):

```sh
psql -X -v ON_ERROR_STOP=1 -f sql/prototype/003_seed_football.sql
```

The schema export runs once in its own transaction and records the Alembic head.
The prototype seed is repeatable and preserves existing rows. Neither artifact
deletes records. The schema export creates the original legacy tables and then
drops them under the guarded forward migration, within the same transaction.

The unchanged seed contains 32 prototype teams, 13 historical-result-shaped prototype
rows, and 3 unlabeled snapshots. These are not verified historical matches. The
source filename + row number identifies an imported historical record; keep source
row order stable on repeat imports. New rows append; existing ratings/history are
not overwritten. Corrections need an explicit database change, not a reimport.

Alembic is authoritative for schema evolution. These SQL files are generated reviewable
exports, not a second migration system. To regenerate schema exports only (offline; the dummy
URL is only used to select the PostgreSQL dialect):

```sh
APP_ENV=test \
DATABASE_URL=postgresql+psycopg://sql_export:sql_export@127.0.0.1/goalstats_test_export \
PYTHONPATH=src .venv/bin/python scripts/database/export_football_sql.py --mode schema
```

## Normalized historical catalog

The baseline includes `teams`, `competitions`, `matches`, `scenarios`, and
`predictions`, as well as the three retained prototype tables. SQL exports contain
schema only; explicit `make seed` imports historical data through the guarded Flask
importer. See the [dataset contract](../data/README.md) and
[catalog schema](../docs/service/historical-catalog.md).

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
competitions, scenarios and prototype data are not rejected.

The `preservation` result contains counts and deterministic full-record MD5 digests
for catalog, scenario, prediction and prototype tables, including IDs, timestamps
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

## Export modes and artifact inventory

| Artifact | Responsibility |
| --- | --- |
| `001_fresh_database.sql` | Generated full schema, empty database only |
| `prototype/003_seed_football.sql` | Explicit RoadToTheFinal compatibility inserts only |
| `verify_historical_import.sql` | Read-only current/complete acceptance and preservation evidence |

`--mode schema` generates only the initial schema file and does not read prototype CSVs.
`--mode prototype` generates only `prototype/003_seed_football.sql`, without database
access. `--mode all` retains the legacy no-option behavior of generating both kinds.
Use `--output-directory /path/to/review-directory` to review output without overwriting
checked-in artifacts. All modes are offline and deterministic. Schema modes require
the explicit dialect configuration shown above; prototype-only mode needs no database
configuration. None of these modes executes its generated SQL.

## CS 514 evidence

The course asks for relational design, database programming and appropriate SQL
concepts, not a particular seed filename or use of every listed database feature.
The schema exports retain primary/foreign keys, checks, indexes, nullable fields,
transactions and schema evolution. Verification demonstrates SELECTs, joins,
aggregations and subqueries. Prototype SQL remains explicit INSERT compatibility
evidence; application services and their tests demonstrate updates and transactions.
The five normalized entities remain teams, competitions, matches, scenarios and
predictions. PostgreSQL is the implemented engine despite older MySQL planning text.
The nine-edition expansion is the current implementation objective, not the Phase 1
minimum stated in the planning documents. No useful SQL evidence has been discarded.

## Scenario and prediction persistence

Both tables are included in the initial baseline. Foreign keys restrict deletion
of referenced teams, matches and scenarios. Scenario checks enforce statistic and
rating bounds; the API validates match-participant agreement transactionally.
Predictions retain immutable input snapshots and JSONB details, with probability,
expected-goals and score constraints. No schema export imports or backfills data.
See [the frontend contract](../docs/service/frontend-api.md).
