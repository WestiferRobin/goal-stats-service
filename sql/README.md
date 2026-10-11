# PostgreSQL fallback scripts

Run from this repository root using `psql` and your intended PostgreSQL database.
`PGDATABASE`, `PGHOST`, `PGPORT`, `PGUSER` and a password file can supply connection
settings. Do not put credentials in these checked-in files.

Choose **one** schema path:

```sh
# Empty database only: creates all tables and records the Alembic head.
psql -X -v ON_ERROR_STOP=1 -f sql/001_fresh_database.sql

# OR an existing template database at b7f42e9c1a60:
psql -X -v ON_ERROR_STOP=1 -f sql/002_upgrade_template.sql

# OR an existing football database at d94f81ab2301:
psql -X -v ON_ERROR_STOP=1 -f sql/002_upgrade_existing.sql

# OR an existing catalog database at e3a71c92b406:
psql -X -v ON_ERROR_STOP=1 -f sql/004_upgrade_scenarios.sql

# OR an existing scenario database at f6b82d14c903:
psql -X -v ON_ERROR_STOP=1 -f sql/005_upgrade_predictions.sql
```

Then load the bundled teams/history:

```sh
psql -X -v ON_ERROR_STOP=1 -f sql/003_seed_football.sql
```

The five schema scripts are alternatives, not sequential steps. They run once;
the upgrade checks its starting revision. The seed is safe to repeat and preserves
existing rows. Each file has its own transaction. Schema scripts include the same
revision bookkeeping as Alembic, so the existing startup migration workflow can resume afterward.
No script drops tables or deletes existing records.

The unchanged seed contains 32 prototype teams, 13 historical-result-shaped prototype
rows, and 3 unlabeled snapshots. These are not verified historical matches. The
source filename + row number identifies an imported historical record; keep source
row order stable on repeat imports. New rows append; existing ratings/history are
not overwritten. Corrections need an explicit database change, not a reimport.

To regenerate SQL after changing migrations or bundled data (offline; the dummy
URL is only used to select the PostgreSQL dialect):

```sh
APP_ENV=test \
DATABASE_URL=postgresql+psycopg://sql_export:sql_export@127.0.0.1/goalstats_test_export \
PYTHONPATH=src .venv/bin/python scripts/export_football_sql.py
```

## Normalized historical catalog

All schema paths include `teams`, `competitions`, and `matches` at revision
`e3a71c92b406`, generated from the same additive Alembic migration as the ORM
schema. `002_upgrade_existing.sql` requires exactly `d94f81ab2301`; the template
upgrade retains its original starting revision. Each upgrade guards its revision
before changing anything. No legacy schema is altered by the catalog migration.

The legacy seed still targets only `football_teams` and `football_history` and is
byte-for-byte unchanged. None of these scripts imports the selected 64 historical
matches. The explicit historical CLI importer has now populated and verified the
existing local development catalog. See the
[dataset contract](../data/README.md) and [catalog schema](../docs/service/historical-catalog.md).


## Read-only historical acceptance

`verify_historical_import.sql` checks actual PostgreSQL identity, revision, source
counts, participating teams, duplicate identities, orphaned references, joins,
legacy counts and a stable record digest. It uses a read-only transaction:

```sh
docker compose --env-file .env.local -p goalstats-service-local \
  -f docker/compose.local.yml exec -T postgres \
  psql -X -v ON_ERROR_STOP=1 -U goalstats -d goal_stats_service_local \
  < sql/verify_historical_import.sql
```

Verified local results on 2026-10-08: 32 teams, one competition, 64 matches;
zero duplicate identity groups and zero orphaned matches. Reimport inserted zero
records and preserved IDs/provenance. The same records survived stop/restart using
the existing PostgreSQL volume. Legacy counts remained 32 teams, 16 history rows,
zero snapshots. See [technical evidence](../docs/service/task2-acceptance.md).

Do not rerun a fresh-schema script on the populated development database. Apply
future additive migrations using the supported workflow. A failed import should be
diagnosed and dry-run again; do not reset tables or delete volumes. Historical imports
remain explicit one-off CLI operations. Cloud runtime is unverified.


## Scenario persistence

The scenario migration is `f6b82d14c903`, an additive child of `e3a71c92b406`.
All full/upgrade schema exports now include `scenarios`; `004_upgrade_scenarios.sql`
is the guarded upgrade specifically from the historical catalog revision.
The scenario migration itself creates only its table and indexes, preserving
catalog and prototype records. The generated upgrade continues through later
migrations to the current head. No backfill or rating substitution is performed.
Foreign keys restrict deletion of referenced teams/matches. Checks enforce distinct
teams, statistic bounds, finite/ranged ratings and modifier totals, and possession
totals. Match-participant agreement is validated transactionally by the API.
See [the frontend contract](../docs/service/frontend-api.md#saved-scenarios-prompt-2).


## Saved predictions

The current head is `a7c93e25d104`, parent `f6b82d14c903`. All schema paths include
`predictions`; `005_upgrade_predictions.sql` upgrades exactly the scenario revision.
This additive table references scenarios with restrictive deletion, permits multiple
predictions per scenario, and stores immutable effective inputs plus variable report
details in JSONB. Explicit probability columns enforce 0–1 and sum-to-one within
1e-9; expected-goals columns reject negative/nonfinite values and score columns
reject negatives. The upgrade does not change or backfill any existing records.
