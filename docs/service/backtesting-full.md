# Full historical Backtesting: implementation and evidence coverage

The `womens-world-cup-full-v1` package accounts for the existing 348 World Cup
matches across nine editions. It extends the existing evaluation service, prediction
adapter and metric functions. No prediction, Monte Carlo or rating formulas changed.
The existing recorded package and two-match pilot are preserved.

## Coverage audit

No caller assumption package was supplied. The retrospective audit uses a named
empty request solely to expose missing-input exclusions; it is not a hypothetical
performance experiment. **No historical accuracy results are claimed.**

| Edition | Total | Verified labels | Rating complete | Strict eligible | Retrospective eligible | Excluded | Remaining evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1991 | 26 | 26 | 19 | 0 | 0 | 26 | Special inputs / availability; 7 rating gaps; 80-minute validation |
| 1995 | 26 | 26 | 19 | 0 | 0 | 26 | Special inputs / availability; 7 rating gaps |
| 1999 | 32 | 32 | 26 | 0 | 0 | 32 | Special inputs / availability; 6 rating gaps |
| 2003 | 32 | 32 | 32 | 0 | 0 | 32 | Special inputs / availability |
| 2007 | 32 | 32 | 31 | 0 | 0 | 32 | Special inputs / availability; 1 rating gaps |
| 2011 | 32 | 32 | 29 | 0 | 0 | 32 | Special inputs / availability; 3 rating gaps |
| 2015 | 52 | 52 | 48 | 0 | 0 | 52 | Special inputs / availability; 4 rating gaps |
| 2019 | 52 | 52 | 52 | 0 | 0 | 52 | Special inputs / availability |
| 2023 | 64 | 64 | 64 | 0 | 0 | 64 | Special inputs / availability |
| Total | 348 | 348 | 320 | 0 | 0 | 348 | See exact exclusions below |

`data/evaluation/womens-world-cup-full-v1/coverage.json` records exact per-match
exclusions, participant coverage and ranking-release evidence. Counts overlap:

- 348 lack observed historical Star Power/Clutch and verified historical source
  publication availability (strict mode).
- 348 lack caller Star Power/Clutch assumptions (the empty retrospective audit).
- 28 have insufficient offense/defense/form coverage for at least one participant.
- 26 use the unvalidated 80-minute model horizon and fail the 90-minute adapter gate.
- 87 have at least one ranking gap; rankings remain optional, as before.

Rating-incomplete participants (affected match appearances):

- 1991: Brazil (3), Nigeria (3), United States (2).
- 1995: Brazil (2), Canada (1), Nigeria (1), Australia (3).
- 1999: Nigeria (3), Germany (1), Ghana (2).
- 2007: New Zealand (1).
- 2011: Germany (3).
- 2015: Ecuador (3), Spain (1).

## Sources, duration and unresolved evidence

The byte-preserved [RSSSF edition archives](https://www.rsssf.org/tablesw/wwc2023f.html)
expressly permit reuse with author acknowledgement. All nine authors, URLs, content
revisions, checksums and source locations are recorded in the registry. Catalog
reconciliation uses date, edition and exact reviewed team aliases, explicitly reverses
orientation when necessary, and rejects duplicates, missing identities and score
conflicts. All 348 final scores agree; this is not independent corroboration because
martj42 lists RSSSF as an upstream source. The two pilot FIFA reports retain priority.

1991 uses 80-minute regulation, supported by [U.S. Soccer's historical account](https://www.ussoccer.com/stories/2023/07/womens-world-cup-memories-10-most-memorable-uswnt-world-cup-matches).
1995–2023 use a separate 90-minute protocol. Original regulations for the first eight
editions remain unacquired; unknown extra-time maxima are null rather than guessed.
Observed extra-time, golden-goal and shootout procedures are recorded per match.

The 1999 Brazil–Nigeria and 2003 Germany–Sweden golden goals are excluded from
regulation scores. FIFA and RSSSF disagree on the recorded goal minute by one minute
in each case, but agree that it occurred after regulation. Both discrepancies remain
in the relevant registry rows; neither changes the certified regulation draw.

For 1999 Brazil–Norway, the RSSSF third-place entry indicates a shootout without
extra time. Contemporary reporting explicitly confirms this procedure:
[Lisa Dillman, Los Angeles Times, July 11, 1999](https://www.latimes.com/archives/la-xpm-1999-jul-11-sp-55079-story.html).
A candidate FBref listing describes extra time, so that listing was not imported or
used to override the reviewed evidence. Its disagreement is retained here; the
regulation result is 0–0 under either account.

[StatsBomb's public-data agreement](https://github.com/hudl/open-data/blob/master/LICENSE.pdf)
restricts redistribution and commercial exploitation. No StatsBomb event data was
imported into this package. The source review records the agreement checksum.

## API and Analytics

The existing backend endpoint and frontend proxy accept the full dataset ID, an
optional edition and a bounded selection of up to 348 cases. Entire-catalog integrity
checks run before filtering. Every case carries duration/protocol, label evidence,
rating coverage, ranking provenance, status and explicit reasons.

Analytics offers all nine editions, all-348 selection, strict/retrospective modes,
manual participant inputs and explicitly named assumption-package JSON. Fields are
blank until the caller enters values. Summary tables include catalog and selected
counts, labels, ratings, eligibility and metrics. Numerical metrics only aggregate
eligible 90-minute cases; the 1991 protocol summary is unavailable. The existing
probability table, confusion matrix and provenance remain available for eligible cases.

## Exact remaining work

1. Acquire and review original 1991–2019 regulations and any original reports needed
   to strengthen archive-only labels; preserve unknown rules until verified.
2. Resolve the two golden-goal minute discrepancies without changing the agreed
   regulation scores, and further corroborate the 1999 third-place procedure.
3. Acquire the original 2023 regulations PDF bytes for a reproducible binary checksum.
4. Establish pre-cutoff observational Star Power/Clutch and publication availability
   before enabling strict historical scoring.
5. Obtain caller-provided versioned hypothetical values before claiming any
   retrospective performance results.
6. Improve documented earlier-results coverage for the 28 rating-incomplete cases
   through a separately reviewed source version; do not fill missing ratings.
7. Validate a mathematically appropriate 80-minute model before scoring 1991. Do not
   rescale or change the current model implicitly.

Automated scoring uses explicitly test-only numerical assumptions. Test outputs are
not historical observations and are not a user-approved performance report.

## Verification and preservation

Backend `make certify` passed: 1,768 unit/integration tests, Ruff, formatting,
Mypy (95 source files), 95.028271% combined coverage, and owned-resource cleanup.
The full-cohort integration test validates all 696 explicit participant inputs,
probabilities, independent aggregate loss, deterministic replay, edition selection,
reference-population reconstruction, cutoff enforcement and read-only database use.
Its 301 eligible cases use **test-only** assumptions; this is not a historical result.

The canonical local database's counts and row-content SHA-256 fingerprints matched
before and after the implementation for all ten tables: matches (348), competitions
(9), teams (44), ranking releases (96), ranking observations (16,525), FIFA mappings
(44), rating runs (1), team ratings (44), scenarios (0), predictions (0).

Both repositories remain on `member/wes-v2`; no commit or push was made. Service HEAD
remains `6df91f3b819a5a8ae28589ba17259ee4509a0ec9`; app HEAD remains
`374983a6432d5e3a3b821bee7471e7737261425d`. Existing pilot changes are preserved.
No migration, canonical import, prediction formula or Monte Carlo change was made.

Exact overlapping exclusion codes:

| Code | Strict | Empty retrospective audit |
| --- | ---: | ---: |
| `historical_source_availability_unverified` | 348 | 0 |
| `historical_star_power_clutch_evidence_missing` | 348 | 0 |
| `explicit_star_power_clutch_assumptions_missing` | 0 | 348 |
| `historical_ratings_insufficient` | 28 | 28 |
| `model_80_minute_horizon_unvalidated` | 26 | 26 |
| `regulation_duration_incompatible` | 26 | 26 |

The empty retrospective audit is named `coverage-audit-no-values-v1` only for request
traceability. It contains no assumptions and is not a caller-approved assumption package.

Frontend normalized verification passed: 433 unit tests (25 files), TypeScript,
production build, all 34 API-backed browser tests, and all 9 Home/Demo browser
regressions. ESLint exited successfully with three existing warnings in unchanged
About, Project and Home files. The runner used Node 24.22.3 and npm 11.19.1.
Owned test containers/network were removed and baseline Docker volumes preserved.

Verification logs: `/tmp/goalstats-full-backend-checks.log` and
`/tmp/goalstats-full-frontend-checks.log`. Browser artifacts are under the app's
`artifacts/goalstats-normalized-1d70a259816f44c4b238ae262ba79f70/` directory.
Backend coverage/JUnit artifacts are under
`.host-sessions/certify-goal-stats-service-test-b9e0da5f57bf819ff0bb327a.LgpNRT/`.

## Exact uncommitted file inventory

Includes the preserved pilot implementation and the full-cohort extension.

### goal-stats-service

```text
data/evaluation/womens-world-cup-2023-opening-pilot-v1/README.md
data/evaluation/womens-world-cup-2023-opening-pilot-v1/manifest.json
data/evaluation/womens-world-cup-2023-opening-pilot-v1/rating-reconstruction.json
data/evaluation/womens-world-cup-2023-opening-pilot-v1/regulations-evidence.json
data/evaluation/womens-world-cup-full-v1/README.md
data/evaluation/womens-world-cup-full-v1/coverage.json
data/evaluation/womens-world-cup-full-v1/manifest.json
data/evaluation/womens-world-cup-full-v1/ratings.json
data/evaluation/womens-world-cup-full-v1/registry.json
data/evaluation/womens-world-cup-full-v1/rules.json
data/evaluation/womens-world-cup-full-v1/source-review.json
data/evaluation/womens-world-cup-full-v1/sources/wwc03f.html
data/evaluation/womens-world-cup-full-v1/sources/wwc07f.html
data/evaluation/womens-world-cup-full-v1/sources/wwc2011f.html
data/evaluation/womens-world-cup-full-v1/sources/wwc2015f.html
data/evaluation/womens-world-cup-full-v1/sources/wwc2019f.html
data/evaluation/womens-world-cup-full-v1/sources/wwc2023f.html
data/evaluation/womens-world-cup-full-v1/sources/wwc91f.html
data/evaluation/womens-world-cup-full-v1/sources/wwc95f.html
data/evaluation/womens-world-cup-full-v1/sources/wwc99f.html
docs/service/backtesting-full.md
docs/service/backtesting.md
scripts/evaluation/build_full.py
src/football/backtesting_evidence.py
src/routers/evaluation.py
src/schemas/evaluation/request.py
src/schemas/evaluation/response.py
src/services/evaluation.py
src/services/evaluation_full.py
src/services/evaluation_pilot.py
tests/integration/football/test_historical_import.py
tests/integration/routers/test_evaluation.py
tests/integration/routers/test_evaluation_full.py
tests/integration/routers/test_evaluation_pilot.py
tests/unit/schemas/contract_fingerprints.json
tests/unit/services/test_evaluation.py
tests/unit/services/test_evaluation_full.py
tests/unit/services/test_evaluation_pilot.py
```

### goal-stats-app

```text
scripts/normalized/prepare.py
src/app/api/football/[...path]/route.test.ts
src/app/api/football/[...path]/route.ts
src/features/analytics/components/backtesting-panel.test.tsx
src/features/analytics/components/backtesting-panel.tsx
src/features/analytics/domain/backtesting.fixtures.ts
src/features/analytics/domain/backtesting.test.ts
src/features/analytics/domain/backtesting.ts
tests/e2e/backtesting.normalized.spec.ts
```
