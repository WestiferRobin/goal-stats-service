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
```

Then load the bundled teams/history:

```sh
psql -X -v ON_ERROR_STOP=1 -f sql/003_seed_football.sql
```

The two schema scripts are alternatives, not sequential steps. They run once;
the upgrade checks its starting revision. The seed is safe to repeat and preserves
existing rows. Each file has its own transaction. Schema scripts include the same
revision bookkeeping as Alembic, so normal `make migrate` can resume afterward.
No script drops tables or deletes existing records.

The seed contains 32 teams, 13 completed matches, and 3 unlabeled snapshots. The
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
