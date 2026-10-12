# Historical verification evidence

[womens-world-cup-coverage.json](womens-world-cup-coverage.json) records verification
of the pinned Mart Jürisoo CSV on 2026-10-11. All nine selections pass: **348 matches,
44 distinct participants, 1,081 goals**. The full source has 11,650 rows. Its revision
and SHA-256 are fixed in every manifest and the coverage artifact.

## Prepared contract schema

Each manifest in `../womens-world-cup/` retains the existing 2023 field structure. The logical
prepared contract joins a manifest to its coverage `editions` entry by `dataset_id`.
The companion entry declares exact sorted `participants`, `participant_count`,
`total_goals`, date bounds, match count, `fixture_sha256`, `score_basis`,
`home_away_policy: preserve_source_order`, `identity_policy: source-record-key-v1`,
`approval_status: approved_pinned_basic_results` and `runtime_supported`.

When this evidence was generated, only 2023 was supported by the runtime importer.
The artifact’s `runtime_supported` values preserve that historical state and are not
the current runtime allowlist. They have not been rewritten.

The current importer validates all nine approved editions: 1991, 1995, 1999, 2003,
2007, 2011, 2015, 2019 and 2023. It joins each manifest to typed approval metadata
and validates participants, goals, ordering and identity policy. The existing 2023
manifest and source-record-key algorithm remain unchanged.

Runtime support does not mean the data has been imported. The persistent development
catalog currently contains only 2023: 32 teams, one competition and 64 matches.
Additional editions require explicit authorized imports; startup imports nothing.

## Reproduce the read-only source verification

From the repository root, with development dependencies installed and the exact
pinned CSV in `data/raw/martj42-womens-results/1855e313ae8bcd0330426e62c8e4cf15ce45077c/results.csv`:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B scripts/database/verify_historical_contracts.py
```

An optional positional file path selects source bytes, never an alternate manifest,
revision or checksum. Missing or mismatched bytes fail; this tool does not download,
rewrite evidence, access PostgreSQL, or import records. It checks UTF-8 decoding,
headers, all source-row dates and nonnegative SMALLINT scores, required fields,
neutral values, selection boundaries, complete World Cup coverage, exact participant
sets, goal totals, repeated/reversed associations and contradictory fixture facts.
Failures identify the source ordinal for malformed or duplicate rows.

Each fixture digest hashes UTF-8 compact JSON (`ensure_ascii=False`, sorted object
keys, separators comma/colon), containing full selected row dictionaries sorted by
`date`, `home_team`, `away_team`. It preserves source labels, scores, home/away order,
city/country and neutral fields while being independent of CSV row order. Combined
with the pinned full-file checksum, this detects fixture changes even when counts
and total goals still agree. It is a reproducibility check, not independent proof
that every upstream fact is correct.

`make test` is the standard automated verification command. Its synthetic fixtures
exercise rejection paths without depending on the ignored raw CSV. It also validates
all nine tracked manifest/coverage pairs and current nine-edition runtime support.
The source verifier preserves the original evidence flags while checking source facts.

## Identity, semantics and limitations

All 44 source labels are retained. No reviewed aliases are needed or registered.
The coverage artifact records the reviewed external names (China PR, Chinese Taipei,
Korea DPR, Korea Republic, USA and Côte d'Ivoire); these are not automatic mappings.
China/Taiwan and England/Scotland remain distinct. No unresolved source-label identity
was found among the selected records.

Scores include extra time and exclude shootout goals. Home/away order and optional
venue/neutral values retain source semantics. No stadium, stage, regulation-time
split, shootout details, rankings or prediction ratings are fabricated or certified.

Secondary references in the artifact describe **prior conversation audit evidence**,
not a comparison rerun by this verifier. That audit reported agreement on all 348
dates, participant pairs and scores after accounting for source ordering. Secondary
agreement is not official FIFA certification, and source independence is not proven.
Ordering and city/country disagreements remain unresolved; no source bytes are changed
to reconcile them. Approval is limited to the pinned basic-results contract.

Raw sources remain ignored and excluded from Docker images. Prototype RoadToTheFinal
inputs remain separate, with unchanged startup behavior. No historical import,
persistent database migration or `make seed` implementation is part of this step.

## Explicit historical seeding

`make seed DATASET=womens-world-cup DRY=true` previews all nine editions.
Use `DRY=false` to write, or select an individual ID such as `womens-world-cup-2023`.
Omitted `DRY` means `false`; empty/other values and legacy `DRY_RUN` are rejected.
Contracts remain in `data/womens-world-cup/`, with pinned source in `data/raw/`.
The command requires prepared infrastructure and schema; it never starts services,
migrates or selects prototype data. Each edition commits separately, so earlier
commits survive later failure and unchanged imports can be safely retried. Dry-run
team estimates are edition-local, not additive. Startup imports nothing.
See [seed prerequisites, safeguards and reporting](../../docs/interface/make.md#explicit-historical-seeding) for the full contract.
