# Teams enrichment implementation verification — 2026-11-15

Implemented locally on `member/wes` in both repositories. No commit or push.
Backend HEAD remains `476d3af485fa301f1b66d83f1cfce7eb83e25067`;
frontend HEAD remains `81d05d82f7ff5f1efbea4c418a34c8ba39536079`.

## Database and sources

Applied additive migration `f31a6e208b47` after an owned disposable migration test
and a local database backup. It adds ranking_releases, ranking_observations,
fifa_team_mappings, rating_runs and team_ratings. Existing table columns/rows are
not changed. Populated enrichment downgrade is guarded and tested.

Imported all 96 FIFA releases currently listed by the official page, from
2003-07-16 through 2026-10-20: 16,525 observations and 44 catalog mappings. Source
packages remain under ignored `.host-sessions/fifa-enrichment-20261115`; release
IDs, actual publication dates, source hashes, URLs, retrieval metadata and raw
observations are retained. A repeated apply inserted zero observations and zero
ratings. Missing/unranked observations never silently borrow older rankings.

Calculated one immutable cohort from the existing 11,650-row pinned international
results source, through 2026-06-10. No broader matches were added to the World Cup
catalog. All 44 teams have FIFA Rank/Points/Date. Forty-three have all three
experimental ratings. Equatorial Guinea has only five matches in the four-year
window and one qualifying Form match; all three ratings remain null with an
explicit insufficient-evidence reason.

Full coverage: [44-team CSV](../../data/verification/teams-enrichment-2026-11-15.csv).
Machine-readable validation/provenance: [JSON](../../data/verification/teams-enrichment-2026-11-15.json).
Model and replay instructions: [enrichment documentation](team-enrichment.md).

## Held-out model results

Mean joint Poisson negative log likelihood; lower is better:

| Holdout end | Matches | Global baseline | Opponent-adjusted | With Form diagnostic |
|---|---:|---:|---:|---:|
| 2025-06-10 | 338 | 3.539238 | 3.159408 | 3.213133 |
| 2026-06-10 | 360 | 4.135178 | 3.306850 | 3.327796 |

Opponent adjustment improves these two holdouts by 10.73% and 20.03%. Form does
not improve that scoring model in either holdout. It is a descriptive recent
performance percentile, not a demonstrated predictive improvement. No prediction
or Monte Carlo formulas consume these new profile values. Source scores include
extra time and exclude shootouts; ratings are per recorded match, not per 90.
There are no calibrated uncertainty intervals or general accuracy guarantees.

## Verification

- Canonical backend `make test`: **1,655 passed, 0 failed, 1 deselected**;
  356.46 seconds. The normal workflow excludes its certification-only pinned-source
  test; the actual source checksum was independently verified by the executed importer.
- Backend Ruff lint/format and strict mypy: passed (85 source files).
- Frontend Vitest: **307 passed, 0 failed** (19 files), with Node 24.
- Owned browser runner: **15 normalized tests + 9 Home/demo tests passed**.
- Frontend type checking passed; source lint has zero errors and three preexisting
  warnings. Broad host `npm run lint` also scans old generated browser artifacts;
  its artifact errors are unrelated to source. The fresh isolated runner passes.
- Live USA/Germany page: exact FIFA points, ranking date, model cutoff and ratings
  render; hidden Star Power/Clutch cards absent; history page 2 works; no browser
  errors. Matches retains all four Star Power/Clutch input controls.
- All 44 live API records pass ranking, finite-range-or-null, shared-cohort and
  prediction-isolation assertions. Team list/detail retain one SELECT per request.
- Replay produces identical run ID and zero inserts.
- All original rows in teams, competitions, matches, scenarios, predictions and
  users have identical before/after hashes. World Cup totals remain 348 matches,
  44 teams, nine editions and 1,081 goals.
- Local scenario/prediction tables were empty. Populated saved-prediction,
  migration-preservation and Monte Carlo regressions passed in disposable tests.
- Owned test containers/networks/images were cleaned up by their runners. Existing
  persistent resources remain; the backend was restarted to load the new code.

Earlier test runs detected outdated schema/head assertions and extra catalog
queries; these were corrected. The final full backend run is green. Initial
frontend worker errors were caused by shell Node 20; Node 24 runs are green.

## Remaining limitations

1. Equatorial Guinea cannot honestly receive ratings under the documented minimum
   evidence policy. More qualifying results are needed; no filler scores were used.
2. Ratings are experimental and dated June 2026. FIFA observations are dated
   October 2026. The UI shows both dates rather than implying equal freshness.
3. Form has no demonstrated incremental predictive benefit in these holdouts.
4. Public/commercial deployment requires applicable FIFA source-use permission;
   this implementation and acquisition do not establish redistribution rights.
5. No commit or push was performed.

## Files changed

### Backend

- `alembic/env.py`
- `sql/001_fresh_database.sql`
- `sql/README.md`
- `sql/verify_historical_import.sql`
- `src/infra/repositories/team.py`
- `src/infra/resources/db.py`
- `src/schemas/team/response.py`
- `src/services/team.py`
- `tests/integration/infra/repositories/test_prediction.py`
- `tests/integration/infra/resources/test_db.py`
- `tests/integration/routers/test_team.py`
- `tests/integration/test_main.py`
- `tests/unit/schemas/contract_fingerprints.json`
- `tests/unit/schemas/team/test_response.py`
- `tests/unit/services/test_team.py`
- `alembic/versions/f31a6e208b47_team_enrichment.py`
- `data/verification/teams-enrichment-2026-11-15.csv`
- `data/verification/teams-enrichment-2026-11-15.json`
- `docs/service/team-enrichment.md`
- `src/football/enrichment.py`
- `src/football/team_ratings.py`
- `src/models/enrichment.py`
- `tests/integration/football/test_enrichment.py`
- `tests/unit/football/test_enrichment.py`
- `docs/service/team-enrichment-verification.md` (this report)

### Frontend

- `src/features/teams/components/teams-view.test.tsx`
- `src/features/teams/components/teams-view.tsx`
- `src/lib/football.ts`
