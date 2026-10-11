# Phase 1 historical catalog

PostgreSQL is the implementation database, following the compatibility audit and
Task #2 schema/dataset contract. Older project drafts use MySQL terminology; the
implementation uses PostgreSQL identity columns and signed types with checks.

`src/models/catalog.py` defines three new tables, independent of the prototype
prediction structures:

| Table | Identity | Relationships and rules |
| --- | --- | --- |
| `teams` | Integer identity `team_id`; unique `(name_key, category)` | Required nonblank name/key/category; optional ratings in [0,100], optional positive FIFA rank; populated ratings/ranking metadata require nonblank attribution |
| `competitions` | Integer identity `competition_id`; unique `(name_key, edition_label, category)` | Required nonblank identity fields; edition mapping is explicit |
| `matches` | Integer identity `match_id`; unique `(source, source_record_key)` | Required competition and distinct home/away team FKs, all with ON DELETE RESTRICT; date; nonnegative SMALLINT scores; required provenance |

Match foreign keys and `match_date` are indexed. Scores are required. Optional
venue/neutral fields are nullable. SHA-256 values must be exactly 64 lowercase hex
characters; source row must be positive; required text provenance cannot be blank.
`imported_at` defaults to PostgreSQL `now()` in a timezone-aware timestamp column.
The rating range checks also reject PostgreSQL NaN and positive/negative infinity.

Historical teams may have NULL ratings and rankings: match results are not evidence
for heuristic prediction inputs. An attributed rating is required only when a rating
is present, and ranking attribution is required for either rank or ranking date.
The dataset module never supplies either. Normalized catalog keys are produced by
the dataset contract; PostgreSQL enforces key uniqueness and nonblank values.

## Migration and compatibility

Migration `e3a71c92b406` has parent `d94f81ab2301` and only creates `teams`,
`competitions`, `matches`, their constraints and indexes. It has no backfill/import
or legacy alterations. Its reverse removes only these three new tables; like any
downgrade, it would discard their contents and is not a data-preserving operation.
Migration tests use disposable databases only. During local acceptance on 2026-10-08,
revision `e3a71c92b406` was applied additively to the existing development database;
legacy schema and full-record digests remained unchanged.

`football_teams`, `football_history`, `football_snapshots`, `items`, `actions`, and
existing migration files remain unchanged. Alembic continues to own `alembic_version`.
The existing API, prediction engine and prototype importer continue to use their
current tables and data formats. The additive migration contains no routes or CLI
changes; the seven-command Make workflow is unchanged. Normal future startup will
apply the new migration through its existing mechanism.

Historical matches are observed facts; scenarios are user-supplied prediction state.
Keeping them separate prevents a hypothetical score or minute from changing a real
result. Normalized scenario/prediction persistence is deferred to later tasks.

## Dataset and validation

The [dataset contract](../../data/README.md) pins the upstream file, explicit 2023
Women's World Cup selection, category, score interpretation, stable identity,
normalization, validation rules and expected counts. Local acceptance verified 32
teams, one competition and 64 matches, with unchanged reimport and restart digests.
See the [acceptance evidence](task2-acceptance.md) and
[operator procedure](football.md#historical-import-operations).

Tests compare Alembic and all standalone SQL schema paths against SQLAlchemy metadata,
check constraints with real PostgreSQL writes, and verify a populated prototype
schema upgrades without changing its structure or records. Existing football API,
engine and importer regression tests continue through `make test`.
