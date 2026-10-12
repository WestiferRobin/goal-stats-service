# Phase 1 historical catalog

PostgreSQL is the implementation database, following the compatibility audit and
Task #2 schema/dataset contract. Older project drafts use MySQL terminology; the
implementation uses PostgreSQL identity columns and signed types with checks.

`src/models/team.py`, `competition.py`, and `match.py` define the historical
tables, independent of the prototype prediction structures:

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

The consolidated `a7c93e25d104_init_models.py` baseline creates all application
models, including the historical catalog, scenarios, predictions and prototype
tables. It contains no imports or backfills. Guarded forward revision `c8d42f19e630`
retires empty Item/Action tables and preserves all eight retained application tables.
Persistent upgrades are deferred until frontend coordination; no restamping is needed. See
[development](development.md#schema-changes) for older-database compatibility.
Downgrading this initial revision drops all application tables; migration tests
exercise that operation only in disposable databases.

During the original acceptance on 2026-10-08, the former catalog revision
`e3a71c92b406` was applied additively; legacy schema and full-record digests remained
unchanged. Those dated results describe the pre-consolidation history.
The current API, prediction engine and prototype importer retain their tables and
formats. Alembic continues to own `alembic_version`.

Historical matches are observed facts; scenarios are user-supplied prediction state.
Keeping them separate prevents a hypothetical score or minute from changing a real
result. Normalized scenarios and saved predictions now use their own tables and APIs;
they do not rewrite observed match results.

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


## Nine-edition importer contracts

The nine approved contracts live in `data/womens-world-cup/`; original source bytes
remain in `data/raw/` and prototype inputs remain isolated in `data/prototype/`.
The pinned source supports nine approved basic-results contracts for 1991–2023,
covering 348 matches, 44 distinct teams and 1,081 goals. The 2011 edition has 16
participants. See [approved dataset IDs](../../data/README.md#approved-runtime-dataset-ids)
and [operator procedures](football.md#historical-import-operations).

`load_manifest(dataset_id)` resolves only an explicit nine-ID allowlist. Each
checked-in manifest is joined to its typed coverage approval entry; dataset/edition,
dates, counts, exact participants, goals, source revision/checksum and identity/order
policies are validated. Coverage's runtime flags are historical Prompt 2 evidence;
all nine are now supported. Extra fields, unsupported sources and arbitrary paths
are rejected. The nine manifest files themselves are unchanged.

The CLI requires an explicit source directory and target/host/database authorization.
It verifies the full source checksum before parsing and rejects duplicate/conflicting
input identities. Each edition imports atomically under the existing advisory lock.
Unchanged reimports preserve IDs, provenance and timestamps; dry-run uses a read-only
transaction. Stored fact conflicts fail without overwriting records.

The existing 2023 source identity algorithm and persistent records are unchanged.
No additional editions have been imported into persistent development PostgreSQL.
Historical imports never read prototype CSVs or write prototype tables. Prediction
ratings remain unavailable; source ordering/venue limitations remain documented in
the coverage evidence. No schema changes or supplementary metadata are introduced.


## Startup isolation

`make run` and `make deploy` apply existing Alembic migrations and start Flask without
importing any dataset. Existing records are preserved; fresh catalogs are empty.
The explicit prototype compatibility importer and guarded historical importer remain
available independently of startup, readiness and the application factory.
The existing `/demo` depends on prototype teams/ratings and may be unusable on a fresh
database until prototype data is explicitly supplied or the frontend is migrated.
Prototype examples are not verified historical facts. Explicit `make seed` uses the guarded historical importer; see the [Make interface](../interface/make.md#explicit-historical-seeding).

See [Prompt 6 integration evidence](../testing/data-integration.md) for actual pinned-source
imports into disposable PostgreSQL, ownership boundaries, and the certification handoff.
