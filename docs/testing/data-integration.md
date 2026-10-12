# Data architecture integration — Prompt 6

Migration-history note: dated revision-chain evidence below predates consolidation
into `a7c93e25d104_init_models.py`. The head ID and schema are preserved; see
[the current migration workflow](../service/development.md#schema-changes).

Acceptance date: 2026-10-11. Branch: `member/wes`; baseline commit: `4fcdeff`.
This records integration of Prompts 1–5; earlier dated reports remain historical evidence.

## Requirements and ownership

The shared Product Decisions, Draft Database Product Document, RoadToFinal README,
[Team Tasks](https://docs.google.com/document/d/18Jels3BXdCcmjEnUsNuy_2hGuGodRqSP5QjSnV4VKiM/edit),
and CS 514 deliverables establish team browsing, match/scenario inputs, predictions,
persistence, and stable APIs as Phase 1 work. The nine-edition expansion is the current
project objective, rather than an original Phase 1 minimum. Live feeds, advanced
analytics, new prediction ratings and frontend migration remain separate work.

| Source/operation | Destination | Boundary |
| --- | --- | --- |
| Pinned `data/raw/martj42-womens-results/1855e313ae8bcd0330426e62c8e4cf15ce45077c/results.csv` + approved manifests/coverage | `teams`, `competitions`, `matches` | Guarded historical CLI, one explicitly selected edition per transaction |
| `data/prototype/teams.csv` | `football_teams` | Explicit compatibility import only |
| `data/prototype/match_history.csv`, `historical_snapshots.csv` | `football_history` | Compatibility examples; not verified World Cup results |
| Prototype snapshot API | `football_snapshots` | User-requested snapshot persistence, never historical dataset import |
| Scenario and prediction APIs | `scenarios`, `predictions` | User inputs and saved computed results, not imported match facts |
| Alembic startup preparation | Schema and `alembic_version` | No dataset imports |
| SQL exporter | Files under `sql/` | Offline metadata/CSV export; never executes SQL against PostgreSQL |

The Flask `import-football` command selects historical loading only with an approved
`--dataset`, explicit `--directory`, target, expected host and expected database.
Omitting the dataset selects the existing prototype compatibility importer. The host
`python -m football.import_data` entry point also loads prototype CSVs explicitly and
uses fixed local configuration. Neither is called by startup or API handlers.
Historical loading has no prototype fallback. There are no cross-system foreign keys.

Startup remains configuration validation → provider readiness → existing Alembic
preparation → Flask. Empty normalized and prototype tables are valid. The frontend
`/demo` still depends on prototype APIs/ratings; this review does not migrate it.
Historical scores do not supply prediction ratings. The development database still
contains only 2023. The explicit `make seed` command is now available; this historical acceptance did not seed development data.

## Approved contracts

Full source SHA-256: `de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0`.
The CSV contains 11,650 rows; approved selection contains 348 matches and 44 distinct teams.

| Edition | Dates | Matches | Participants | Goals |
| --- | --- | ---: | ---: | ---: |
| 1991 | November 16–30 | 26 | 12 | 99 |
| 1995 | June 5–18 | 26 | 12 | 99 |
| 1999 | June 19–July 10 | 32 | 16 | 123 |
| 2003 | September 20–October 12 | 32 | 16 | 107 |
| 2007 | September 10–30 | 32 | 16 | 111 |
| 2011 | June 26–July 17 | 32 | 16 | 86 |
| 2015 | June 6–July 5 | 52 | 24 | 146 |
| 2019 | June 7–July 7 | 52 | 24 | 146 |
| 2023 | July 20–August 20 | 64 | 32 | 164 |
| Total | | 348 | 44 distinct | 1,081 |

Exact participant sets, required fields, full checksum, selection dates, scores and
fixture identities are checked by the runtime parser. Team keys and source-record-key
algorithm remain unchanged. China/Taiwan and England/Scotland stay distinct; no aliases
were introduced. Scores include extra time but exclude shootout tallies. This is pinned
secondary-source acceptance, not official FIFA certification. Existing source-order and
venue limitations remain documented in `data/verification/`.

## Actual-source disposable acceptance

`tests/acceptance/test_pinned_historical_source.py` requires `/input/results.csv` on a
read-only directory mount. Missing source or ownership verification fails rather than
skipping or substituting synthetic data. It reuses existing disposable-schema fixtures,
existing CLI, production parser/importer and read-only verification SQL without patching
manifests, checksums or historical import logic.

The test ran through a temporary copy of `scripts/test.sh` using the same unique project,
provider ownership receipt, tmpfs providers and scoped cleanup. The only harness changes
were an absolute repository working directory, a read-only bind of the pinned directory
to `/input`, and selection of the focused tests including `tests/acceptance`. No maintained
command dispatcher or Make target was added. To repeat this maintainer acceptance, retain
all ownership checks in that harness and add the source mount to its `owned_run`; invoke
`pytest -q -p no:cacheprovider tests/acceptance` through `scripts/testing/test_ownership.py` inside
that owned runner. Do not point this test at development PostgreSQL.

Acceptance checks:

- Existing migrations create empty tables in an owned disposable schema.
- Flask readiness, catalog, prototype routes and the complete OpenAPI definition work.
- Nine explicit CLI imports produce 44 teams, nine competitions and 348 matches.
- Importing 2023 first, then older editions, preserves every original 2023 row.
- Complete SQL verification validates participant sets, dates, goals, provenance,
  competition identities, uniqueness and referential integrity.
- All nine repeat imports insert zero records; full-row snapshots remain identical.
- Prototype, scenario and prediction tables remain empty throughout historical import.
- Closing the application cache/pool and creating a fresh Flask instance against the
  same schema preserves full rows and the complete OpenAPI definition. This is an
  in-process application/pool recreation, not a persistent-stack container restart.
- Foreign-key inspection confirms no relationships cross the prototype/catalog boundary.

The ordinary suite separately tests explicit prototype imports, atomic conflict refusal,
read-only dry-run, wrong target/head rejection, fresh host startup, migrations, APIs,
prediction behavior and Docker resource ownership. `make test` remains the standard
verification command and does not require the ignored source or run this opt-in test.

## Persistent preservation and handoff

Persistent checks are read-only. Full sorted row JSON SHA-256 comparisons cover IDs,
source keys, scores, provenance, timestamps, relationships, scenario inputs and saved
prediction results—not only counts. Baseline: 32 historical teams, one competition,
64 matches, three scenarios, four predictions; 32 prototype teams, 16 history rows and
zero snapshots. Current-mode SQL and metadata parity checks pass against this state.

The Alembic chain remains `b7f42e9c1a60` → `d94f81ab2301` → `e3a71c92b406` →
`f6b82d14c903` → `a7c93e25d104`. No migration or runtime changes were needed in Prompt 6.
Raw source and prototype CSVs, manifests, migrations, engine, `.env.local`, public Make
interface and persistent records are preserved. Source remains Git-ignored and excluded
from Docker images; only the disposable acceptance runner receives the read-only mount.

Prompt 7 should certify these boundaries and evidence before the separately authorized
seeding implementation. It must not treat disposable acceptance as development seeding,
infer prediction ratings from scores, or assume the frontend has migrated.

## Executed results

- Focused suite, including actual pinned-source acceptance: **546 passed** in 110.98s.
- Canonical `make test`: **861 passed** in 127.33s; Ruff lint and formatting passed
  (178 files), strict mypy passed (79 source files).
- Both owned projects cleaned up successfully and preserved preexisting resources.
- Full live OpenAPI JSON is identical before/after: 25 paths, 36 operations;
  canonical SHA-256 `3d01a9d6b8d1730ed7661b306ab516991209b5de5d1d1877dd5217a17e38b22b`.
- All development table row digests are unchanged; no persistent migrations/imports
  ran. Existing GoalStats and Prizm containers and Docker volumes are unchanged.
- No runtime defect was found. Prompt 6 adds only opt-in acceptance coverage and
  documentation; no files were deleted, no commits/pushes made, and no seed target added.

Session logs were recorded at `/tmp/goal-stats-prompt6-focused.log`,
`/tmp/goal-stats-prompt6-make-test.log`, `/tmp/goal-stats-prompt6-source.log`, and
`/tmp/goal-stats-prompt6-persistent-sql.log`. These temporary files are local session
artifacts; the repository test source and this report provide the durable handoff.

## Explicit historical seeding

`make seed DATASET=womens-world-cup DRY=true` previews all nine editions.
Use `DRY=false` to write, or select an individual ID such as `womens-world-cup-2023`.
Omitted `DRY` means `false`; empty/other values and legacy `DRY_RUN` are rejected.
Contracts remain in `data/womens-world-cup/`, with pinned source in `data/raw/`.
The command requires prepared infrastructure and schema; it never starts services,
migrates or selects prototype data. Each edition commits separately, so earlier
commits survive later failure and unchanged imports can be safely retried. Dry-run
team estimates are edition-local, not additive. Startup imports nothing.
See [seed prerequisites, safeguards and reporting](../interface/make.md#explicit-historical-seeding) for the full contract.

### Seed implementation verification — 2026-10-12

The host dispatch suite passed 105 tests, including actual GNU Make argument forwarding.
`make test` passed 903 tests with eight explicit skips for GNU Make dispatch because
GNU Make is absent from the tooling image; those eight cases passed on the host.
The separate pinned-source acceptance passed its complete test using a temporary copy
of the standard test harness, retaining its ownership receipt and cleanup checks and
adding only the read-only `/input` mount and acceptance-test selection.

That acceptance previewed all nine editions without writes, imported 2023 first, saved
a scenario and prediction, then imported the remaining editions. It verified 44 teams,
nine competitions and 348 matches, unchanged original 2023 records and saved user rows,
empty prototype tables, zero-insert repeats and preservation across application restart.
The standard disposable suite separately exercises later-edition transaction failure,
preservation of earlier commits, retry, conflicts, wrong targets and stale schema.

Make-to-shell forwarding and Docker arguments were tested with recording Docker commands;
real PostgreSQL acceptance exercised the existing guarded CLI. The local-only seed wrapper
was not redirected to a test database or run in write mode against development PostgreSQL.
