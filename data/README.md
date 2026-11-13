# Approved Women's World Cup data

Local runtime/tooling images package approved manifests and verification evidence;
developer `data/raw/` remains excluded. The production image separately downloads and
checksum-verifies the pinned `results.csv` into `/app/data/bootstrap/` for explicit
production bootstrap. See [Render deployment](../docs/service/render.md). Prototype
CSVs and their importer remain retired; reference mathematics uses explicit inputs.

## Selected historical source

[Mart Jürisoo's Women's International Football Results](https://github.com/martj42/womens-international-results)
is the selected source. [The manifest](womens-world-cup/womens-world-cup-2023.json) pins
revision `1855e313ae8bcd0330426e62c8e4cf15ce45077c` and full `results.csv` SHA-256
`de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0`.
The attribution reference is the pinned upstream README; the license reference is
the author's linked Kaggle dataset page. No license text is bundled or redefined here.

The selection is exactly `tournament = FIFA World Cup`, with inclusive dates
`2023-07-20` through `2023-08-20`. The completed 2023 Women's World Cup provides a
bounded, relevant Phase 1 dataset with 64 matches, 32 senior women's national teams,
and one competition. These counts describe the **subset**, not the full upstream
CSV. The pinned full file contains 11,650 result rows. It has been verified in memory;
the local `data/raw/` copy is not tracked or copied into images. Production builds
download the same pinned bytes separately for the explicit bootstrap mode.

The explicit mapping is `FIFA World Cup` → `FIFA Women's World Cup`, edition `2023`,
category `women_senior_national`. No edition is inferred from arbitrary dates.
Scores include extra time and exclude penalty shootout goals, as described in the
[pinned source README](https://github.com/martj42/womens-international-results/blob/1855e313ae8bcd0330426e62c8e4cf15ce45077c/README.md).
The score basis is `including_extra_time_no_shootout`.

## Pure validation contract

`src/football/historical_dataset.py` defines the typed manifest, historical team,
competition and match records, normalization and identity helpers. It performs no
network requests, database writes, import transactions, or CLI selection changes.

The historical adapter in `src/football/datasets.py` enforces this contract:

1. Verify the **full upstream bytes** against the manifest SHA-256 before selecting
   rows. Decode CSV as UTF-8 (an optional BOM is allowed); reject missing, extra, reordered or duplicate
   required headers, malformed CSV rows, and extra unheaded fields.
2. Select only the declared tournament and inclusive date interval. Invalid dates
   in candidate tournament rows must be reported, not silently filtered out. Pass
   selected rows to `parse_selected_record`; it rejects unknown tournament mappings
   and dates outside this contract.
3. Reject missing/blank dates, home/away labels, scores or tournament values.
   Dates must be valid ISO `YYYY-MM-DD`; scores must be decimal nonnegative integers
   within PostgreSQL SMALLINT (0–32767), with no fractions, signs, NaN or infinity.
   Both teams must be distinct after normalization and reviewed alias resolution.
4. Keep all nine required headers even where values are optional. Blank `city`,
   `country` and `neutral` become NULL. Nonblank neutral values must be TRUE/FALSE
   (case insensitive). Retain original team/tournament labels verbatim as provenance.
5. Normalize display labels with Unicode NFKC, Unicode whitespace collapse and trim.
   Identity keys additionally casefold and reapply NFKC. Preserve accents and
   punctuation; do not guess country renamings or use fuzzy matching. Only explicit,
   reviewed entries in `reviewed_team_aliases` may map team labels; it is initially
   empty. Store normalized catalog keys and enforce model length limits.
6. Leave all model ratings and FIFA ranking fields NULL. This source provides no
   such values; copying prototype ratings would invent attribution. Historical teams
   need not be prediction-ready.
7. Report duplicate and conflicting source identities before writing, using
   `identity_issues`. A repeated identity with changed scores or other match facts is
   a conflict; never overwrite it silently. Compare against already stored records
   as well as this batch, and validate expected subset counts before any commit.
8. Persist into `teams`, `competitions`, and `matches` using the separate transaction
   orchestrator. Keep unverified prototype records separate.

`source_row` is the CSV record's one-based ordinal including the header (first data
record = 2), not necessarily a physical line number for quoted multiline fields.
`source_version`, full-file checksum, source URL, original labels and source row
are required provenance; the database supplies a timezone-aware `imported_at`.

## Stable match identity

`source_record_key` is lowercase SHA-256 of UTF-8 compact JSON (`ensure_ascii=False`,
separators `,` and `:`, no trailing newline), with this ordered array:

```text
[source namespace, category, competition name_key, edition_label,
 ISO match date, normalized source home label, normalized source away label]
```

Namespace, category, competition key and edition come from the validated manifest.
Home/away labels use `name_key` before reviewed aliases. Scores, row ordinals, source
revision and file checksum are excluded. Reordering CSV records or correcting scores
therefore preserves identity; a correction is a reportable conflict. Home/away order
is significant. The database uniqueness boundary is `(source, source_record_key)`.

## Import status

Source verification is separate from persistent database contents. This phase does
not seed development data or assert that it is loaded. Verify the selected database
read-only before any separately authorized import. Startup never seeds.

## Historical import behavior

Use the canonical `flask --app 'main:create_app()' import-football` command with
`--dataset womens-world-cup-2023`, `--directory`, `--target`, `--expect-host`, and
`--expect-database`. Omitted dataset/directory selections fail; no prototype import mode remains.
Historical import never runs automatically during `make run` or `make deploy`.
The importer reads an existing file; downloading is an explicit operator step.
There is no alternate manifest or checksum-bypass CLI flag.

The entire CSV checksum is checked before parsing. Rows with malformed field counts
or missing selection values are rejected instead of silently excluded. Other
competitions and valid dates outside the selected interval are filtered out; invalid
or future dates in the source tournament are rejected. Optional blank values are
NULL, while zero scores remain zero. Selected distinct counts must match the manifest.
Exact duplicate input identities and conflicting input facts both abort the batch.
Exact participant identities and total goals must also match the approved contract.
This differs from reimporting an unchanged edition, which safely inserts zero rows.

After validation, the importer verifies the configured and connected host/database,
connected user, migration head, and required mapped columns. It never applies
migrations. Write mode obtains a transaction-scoped advisory lock to serialize
cooperating catalog importers, compares all existing identities, and inserts only
new teams, competition and matches, in that order. All inserts share one transaction.
Failures roll back new rows; preexisting rows, ratings and provenance are preserved.
PostgreSQL identity sequences can have gaps after rolled-back writes.

Unchanged reimports skip existing records, retaining their primary keys, timestamps,
source version and provenance. Differences in resolved teams/competition, date,
scores, score basis, city, country or neutral status abort the entire batch. Source
version/checksum/row changes alone do not change identity or overwrite provenance.
The current release still accepts only the pinned manifest version; a future source
revision requires an explicit reviewed contract change. Other-source matches and
existing records absent from the batch are preserved, with no cross-source merging.

`--dry-run` uses a PostgreSQL REPEATABLE READ, READ ONLY transaction. It performs
validation and comparison but no inserts, sequence allocation, updates or migrations.
A dry-run is a snapshot; a later write repeats all checks against its own transaction.

The CLI prints a JSON summary. It includes `dataset`, `source`, `source_version`,
`rows_read`, `rows_selected`, `rows_filtered_out`, `teams_inserted`,
`competitions_inserted`, `matches_inserted`, `unchanged`, `duplicate_input`,
`rejected`, `conflicts`, and `committed`. `insert_counts` is `proposed` for dry-run,
`committed` after successful write commit, and `not_committed` on failure.
Failed writes reset all inserted counts to zero. `rows_selected` includes duplicate
selected CSV rows; expected counts refer to distinct identities. `rejected` counts
invalid records, or one dataset-level failure for a checksum/header/count rejection.
`issues` supplies source row/key details without echoing arbitrary source values.

A failed run exits nonzero. Fix the reported input/target/schema issue, then repeat a
dry-run. For checksum mismatch, obtain the exact pinned source; never edit the manifest
to bless an unknown file. For conflicts, review reported stable identities and their
stored/source facts separately; this release has no overwrite flag. For database or
commit-acknowledgment failures, verify connectivity and rerun a dry-run: idempotent
comparison safely reveals any already-committed records. Do not delete tables or
reset the database to recover an import.

See [local and cloud procedures](../docs/service/football.md#historical-import-operations)
for exact commands, TLS requirements and acceptance steps.


## Approved runtime dataset IDs

- `womens-world-cup-1991`
- `womens-world-cup-1995`
- `womens-world-cup-1999`
- `womens-world-cup-2003`
- `womens-world-cup-2007`
- `womens-world-cup-2011` (16 participants)
- `womens-world-cup-2015`
- `womens-world-cup-2019`
- `womens-world-cup-2023`

All use the same pinned full CSV. Historical `--directory` must be explicitly
provided and contain `results.csv`; prototype files are never a fallback. Each
edition has one atomic transaction. Enabling these IDs does not import them:
the persistent development catalog still contains only the existing 2023 edition.
Historical imports do not populate prediction ratings or modify prototype tables.

## Explicit historical seeding

`make seed DATASET=womens-world-cup DRY=true` previews all nine editions.
Use `DRY=false` to write, or select an individual ID such as `womens-world-cup-2023`.
Omitted `DRY` means `false`; empty/other values and legacy `DRY_RUN` are rejected.
Contracts remain in `data/womens-world-cup/`, with pinned source in `data/raw/`.
The command requires prepared infrastructure and schema; it never starts services,
migrates or selects prototype data. Each edition commits separately, so earlier
commits survive later failure and unchanged imports can be safely retried. Dry-run
team estimates are edition-local, not additive. Startup imports nothing.
See [seed prerequisites, safeguards and reporting](../docs/interface/make.md#explicit-historical-seeding) for the full contract.
