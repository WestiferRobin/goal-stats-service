# Prompt 4 — 1991 regulation exposure audit

## A. Implementation summary

GoalStats can represent and inspect all 26 1991 cases through an explicit, separately versioned 80-minute research interface. It **cannot yet report scientifically defensible prediction accuracy for those cases**. This release implements the precise evidence-blocked alternative allowed by sections 5 and the final acceptance criteria. It deliberately does not implement a numerical predictor, fit parameters, or manufacture probabilities in the absence of qualified exposure training evidence.

Model identifier: `odf-exposure-80-evidence-blocked-v1`. Classification: research only; validation status: evidence blocked. All 348 historical matches and nine editions remain supported by the existing endpoint. All 26 1991 cases remain excluded. Existing 90-minute predictions and Monte Carlo mathematics are unchanged.

## B. Exact files changed

See `preservation.json` for the exact Prompt 4 additions and modifications relative to the pre-work file fingerprints. Existing Prompt 1–3 uncommitted changes remain present. The modified service/request/integration test and frontend files contain additive Prompt 4 changes; prior research artifacts and mathematical implementations remain byte-identical.

Service modifications: `src/schemas/evaluation/request.py`, `src/services/evaluation.py`, `tests/integration/routers/test_evaluation_full.py`, and `tests/unit/schemas/contract_fingerprints.json` (only the expected full OpenAPI hash for the new optional selector).

Service additions: `src/football/duration_research.py`, `src/research/duration_audit.py`, `scripts/evaluation/build_duration_audit.py`, `tests/unit/research/test_duration_audit.py`, and `data/research/duration-80-v1/{.gitattributes,README.md,coverage.json,rules-audit.json,preservation.json,manifest.json}`.

App modifications: `src/features/analytics/domain/backtesting.ts`, `src/features/analytics/domain/backtesting.test.ts`, `src/features/analytics/components/backtesting-panel.tsx`, and `tests/e2e/backtesting.normalized.spec.ts`. No app files were added.

## C. Historical rules

`rules-audit.json` distinguishes primary findings, attributed archive evidence and unresolved procedures, with URLs, document hashes and page locators. Original pinned rules/registry files are not overwritten.

- **Verified primary:** 80-minute regulation, two 40-minute halves. The FIFA technical report records two extra-time matches and no shootouts. [FIFA technical report, part 2](https://www.ussoccerhistory.org/wp-content/uploads/2025/01/pcq1fcktjwzzyi2gsm7c-compressed.pdf), PDF page 3; [part 1](https://www.ussoccerhistory.org/wp-content/uploads/2025/01/igmaj4jv8erfljjbs47z-compressed.pdf), PDF page 10.
- **Contemporaneous general rules, not certified tournament-specific adoption:** July 1991 IFAB Law VII permits referee-added lost time and extension for a penalty kick. Its penalty-mark procedure uses alternating kicks, five initially with early termination, then equal-kick sudden death. Shootouts determine a winner outside the match. These facts do not establish every 1991 tournament exception. [IFAB Laws 1991/92](https://downloads.theifab.com/downloads/laws-of-the-game-1991-92?l=en), PDF pages 18 and 60–63.
- **Supported archive evidence:** all 26 matches have reviewed completed-match records and regulation labels. Match 19 Denmark–Germany was 1–1 in regulation, 1–2 after extra time. Match 21 Norway–Italy was 2–2 in regulation, 3–2 after extra time. Both are **draws** for this protocol. Each row preserves its [RSSSF source](https://www.rsssf.org/tablesw/wwc91f.html), hash, archive line and orientation.
- **Unresolved:** original tournament regulations; exact extra-time period lengths certified from those regulations; tournament-specific advancement, shootout and abandonment exceptions; golden-goal applicability certified from primary rules; measured added-time exposure. A bibliographic reference to regulations without the actual document is not verification. Existing registry flags are preserved but are not promoted to newly verified original rules.

The regulation label means the score after two 40-minute halves and associated added time, before extra time or shootouts. Nominal 80 minutes is not ball-in-play time. No advancement prediction is offered.

## D. 80-minute research model

The isolated interface is in `src/football/duration_research.py`; it imports no prediction engine. Its immutable-by-release specification records the candidate equation:

`lambda_i = 80 × r_per_team_minute × exp(beta_OD × (O_i − D_j)/100 + beta_F × (F_i − F_j)/100)`.

This proposes regulation-minute exposure, cross-opponent attack/defense and relative Form, followed by independent Poisson goals and home-win/draw/away-win classes. It assumes proportional nominal-duration exposure and conditional independent goal counts; both require validation. It is **a specification, not an estimated model**. `r`, `beta_OD`, `beta_F`, parameter version, training/calibration end dates, probabilities and metrics are null. Neither 2.6×80/90 nor Prompt 3's 1.3, log(2), log(1.5), or 2007-fitted temperature is adopted as an evidence-backed 1991 parameter.

The existing engine remains nominally 90 minutes: 2.6 pregame expected goals, strength weights .30/.25/.20/.15/.10, ranking adjustments, duration-dependent remaining-time/event logic, and the existing Clutch-based advancement split. These calculations and Monte Carlo routines are not called for the blocked 1991 research path and were not edited.

## E. Duration-aware calibration

The approved merged results provide **605 pre-tournament candidate fixtures**: 467 before 1990-01-01 and 138 from 1990-01-01 through 1991-11-15. Of the 605, 525 precede calendar year 1991 and 80 occurred in 1991 before tournament kickoff. Qualified training observations: **0**. Qualified calibration observations: **0**.

The exact shortfall is jointly source-verified nominal duration, regulation-only goals and historical publication timing for every proposed observation, together with comparable historical O/D/F inputs and sufficient identifiable variation. The approved training schema records final scores and does not supply these fields. Some finals include extra-time goals. Match dates alone do not establish what was available historically. No row is silently assigned 90 minutes or treated as regulation-only.

Candidate inventories and their hashes are in `coverage.json` (candidate and manifest-object hashes use canonical service JSON serialization); these are not approved training datasets. No fitting, rescaling, temperature selection, optimization or evaluation-label tuning occurred. There is no scientifically justified fitted parameter or uncertainty interval to report. A future numeric version needs independent review of sample sufficiency and identifiability; a guessed minimum sample threshold is not introduced.

## F. Historical rating compatibility

The unchanged recovered calculator supplies complete O/D/F triples for 20 of the 26 cases; IDs **3, 5, 10, 11, 16, 17** remain incomplete. Availability is distinct from compatibility. Ratings use recorded final-score goals and reference populations of unverified duration; extra-time inclusion and mixed exposure may distort strengths and percentiles. The size and direction of that distortion have not been estimated. Dividing final scores by guessed durations would not solve unknown regulation labels.

No new duration-normalized rating method or cold-start imputation is released. Missing ratings remain exclusions. Complete ratings also remain incompatible pending validation. Full-population hashes, source-row counts and participant values are retained per case.

## G. All 26 cases

The table below reports observed regulation labels, not scored predictions. Every row has 80-minute regulation, research compatibility **unverified**, prediction eligibility **excluded**, and no probabilities. Common blockers: missing qualified duration training, unvalidated rating compatibility, absent independent validation, unverified historical source availability and unresolved original tournament procedures. Incomplete rows also have the historical-ratings exclusion. Exact reasons and source provenance are machine-readable in `coverage.json`.

| ID | Date | Teams | Regulation score/outcome | O/D/F complete |
|---|---|---|---|---|
| 1 | 1991-11-16 | China – Norway | 4–0 / home_win | Yes |
| 2 | 1991-11-17 | Denmark – New Zealand | 3–0 / home_win | Yes |
| 3 | 1991-11-17 | Japan – Brazil | 0–1 / away_win | No |
| 4 | 1991-11-17 | Sweden – United States | 2–3 / away_win | Yes |
| 5 | 1991-11-17 | Germany – Nigeria | 4–0 / home_win | No |
| 6 | 1991-11-17 | Taiwan – Italy | 0–5 / away_win | Yes |
| 7 | 1991-11-19 | Norway – New Zealand | 4–0 / home_win | Yes |
| 8 | 1991-11-19 | China – Denmark | 2–2 / draw | Yes |
| 9 | 1991-11-19 | Japan – Sweden | 0–8 / away_win | Yes |
| 10 | 1991-11-19 | Brazil – United States | 0–5 / away_win | No |
| 11 | 1991-11-19 | Italy – Nigeria | 1–0 / home_win | No |
| 12 | 1991-11-19 | Taiwan – Germany | 0–3 / away_win | Yes |
| 13 | 1991-11-21 | China – New Zealand | 4–1 / home_win | Yes |
| 14 | 1991-11-21 | Norway – Denmark | 2–1 / home_win | Yes |
| 15 | 1991-11-21 | Japan – United States | 0–3 / away_win | Yes |
| 16 | 1991-11-21 | Brazil – Sweden | 0–2 / away_win | No |
| 17 | 1991-11-21 | Taiwan – Nigeria | 2–0 / home_win | No |
| 18 | 1991-11-21 | Italy – Germany | 0–2 / away_win | Yes |
| 19 | 1991-11-24 | Denmark – Germany | 1–1 / draw | Yes |
| 20 | 1991-11-24 | China – Sweden | 0–1 / away_win | Yes |
| 21 | 1991-11-24 | Norway – Italy | 2–2 / draw | Yes |
| 22 | 1991-11-24 | United States – Taiwan | 7–0 / home_win | Yes |
| 23 | 1991-11-27 | Sweden – Norway | 1–4 / away_win | Yes |
| 24 | 1991-11-27 | Germany – United States | 2–5 / away_win | Yes |
| 25 | 1991-11-29 | Sweden – Germany | 4–0 / home_win | Yes |
| 26 | 1991-11-30 | Norway – United States | 1–2 / away_win | Yes |

## H. Backtesting API/frontend integration

Existing endpoint: `POST /api/v1/evaluations/backtests`; no new endpoint, duplicate evaluation service, persistence or migration.

Select `dataset_id: womens-world-cup-full-v1`, `research_model_version: odf-exposure-80-evidence-blocked-v1`, and `edition: 1991` (or omit edition for all nine). Select the existing `international-results-recovery-v1` recovery package for the recovered 20/26 rating coverage. Default behavior remains unchanged; invalid model identifiers and incompatible dataset/edition selections are rejected.

Per-case `evidence_record.research` identifies horizon, model, validation status, rating availability/compatibility, observed regulation outcome, provenance and explicit exclusion reasons. The three-input interface does not falsely require Star Power/Clutch. Assumptions cannot override blockers. Excluded `probabilities` and scored `outcome` remain null; the observed label is reported separately.

For explicit research selection, the existing `protocol_summaries` identify separate 80- and 90-minute model groups. The 80-minute group's metrics are null. Top-level model/metrics retain their existing 90-minute meaning and `metrics_horizon_minutes: 90`; no cross-horizon accuracy is formed. Frontend selection and result copy make this separation explicit and reject inconsistent research metadata. Pagination remains bounded; selecting all editions with limit 348 returns the complete inventory.

## I. Chronological validation

Protocol specification hash: `81f1e7e22980e476c9ce38df34d12fcdb98a57e2d1708c47abf1c043f634c274`.

Training candidate period ends before 1990; separate calibration ends 1991-11-15; evaluation is 1991-11-16 through 1991-11-30. Parameters would have to freeze before tournament kickoff, with no within-tournament refitting. Existing reconstructed ratings retain strictly previous-calendar-day cutoffs. Current-tournament outcomes may occur in later pre-match rating populations, as historically preceding observations, but are not parameter-training or calibration observations. Their duration compatibility remains blocked.

This protocol was specified retrospectively, with historical outcomes already exposed in prior work. It is not a historically registered specification, pristine holdout or genuine prospective forecast. All model parameters remain absent, so no future-derived parameter can leak into a released 1991 prediction. The 26 labels are used only for inventory and regulation classification, not fitting or scoring.

## J. Tests and verification

Final backend certification: **1,914 passed, 0 failed**, including pinned-source unit/integration, existing Backtesting and Monte Carlo regressions. Combined coverage **95.826377%** (5,740/5,990), above the 95% gate. Statement coverage 96.738670%; branch coverage 92.429022%. The isolated duration interface has 100% statement/branch coverage. Ruff passes; all 263 Python files pass formatting; Mypy passes for 104 source files. Owned test-resource cleanup and preservation pass.

Focused checks: 56 passed across duration/three-input/schema tests; after the optional request selector's expected OpenAPI fingerprint was updated, 25 schema/OpenAPI checks passed (3 PostgreSQL cases deselected in that focused command and covered by full certification). Counts overlap; they are not added to the full-suite total.

Final serial frontend run on pinned Node **24.22.3**, npm **11.19.1**: **436 tests passed across 25 files**; lint, TypeScript and production build passed. Chromium normalized real-API E2E: **36 passed, 0 failed**. Existing Home/static Demo E2E: **9 passed, 0 failed**. The new research-selection test passed for both 348-case and 26-case requests; existing 90-minute prediction and tournament simulation browser regressions passed. Disposable resources were cleaned up and baseline volumes preserved.

Browser artifacts: `goal-stats-app/artifacts/goalstats-normalized-3cc612e502354816ad34d0b1f025c724/`. Full log: `/tmp/goalstats-p4-normalized-current.log`.

Corrected or superseded attempts are retained in local logs: an early backend run was intentionally interrupted to correct an HTTP-status test assertion; one completed run had 1,913 passes and one stale OpenAPI fingerprint failure, then the clean full rerun above passed. The app directory's default Node 20 run produced 185 passes and 18 worker-start errors; Node 24.22.3 reruns passed. One browser run had 35 passes and one exact-label locator failure; the selector was corrected. A concurrent rerun encountered an existing recovery-request HTTP 504/worker timeout and was stopped and cleaned up; the final browser run is serial. No production formula, eligibility threshold or test expectation about scientific validity was relaxed.

Backend certification artifacts: `.host-sessions/certify-goal-stats-service-test-04d1af62b6fe6516fa6a8d70.JUMBB7/`. Full log: `/tmp/goalstats-prompt4-certify-current.log`.

The blocked interface intentionally has no numeric expected-goal/probability operation: expected-goal estimation, 80-minute probability normalization and independent accuracy validation cannot be certified from the available evidence. Tests verify no fabricated parameters/probabilities, deterministic reports, 26/348 inventory, cutoff/horizon rejection, ET/regulation separation, missing ratings, explicit selection, 80/90 isolation and metric separation. Existing Prompt 3 numerical probability tests and production/Monte Carlo regressions run unchanged.

## K. Database preservation

All before/after table fingerprints match:

| Table | Rows | SHA-256 |
|---|---:|---|
| matches | 348 | `5bbe9c69d840f15e425080ea8c9168eb09070a450c145a49864821824065bba5` |
| competitions | 9 | `e5644f1fa058ac1d2a05dca4fd5a3ffeeb86cb8ae9936536883d7d3f7908ac73` |
| teams | 44 | `8dec28a6f861bca1afdd2309b2168801eae87822f5dd99c83f4ca46eaf541530` |
| ranking_releases | 96 | `537be0c5774d58e6ecb98f496bb9523ac3833e18c7a32d7a5b3c0638c1770c1e` |
| ranking_observations | 16525 | `9bd708d2dbd142c7f1f5c5d1a230d0ec7a5e8de48c659a4022b4bb919edaf7e9` |
| fifa_team_mappings | 44 | `f2fe7036c527193cfce0f149d7c880054f9541b741a15d98d1ef4c0fc17de07e` |
| rating_runs | 1 | `50504dcc4f4e5649182b538f38b44b0a8344e794f69523db8699dcf36af0ec6d` |
| team_ratings | 44 | `f687088ef79e9265f90f11bb242f1949311ba623403dc69b72f18a41aba84cbd` |
| scenarios | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| predictions | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

Canonical database access was read-only. Test migrations and seed data were confined to disposable owned test infrastructure. No canonical matches, ratings, predictions or other records were changed.

## L. Git state

Both repositories remain on `member/wes-v2`, with HEAD unchanged:

- Service: `396eedbb0107d87c81d466cb860d07c13b1f3334`
- App: `799740f8ec7807d3b6798845879d5506e44d93ae`

All Prompt 1–4 changes remain uncommitted. No branch switch, reset, stash, merge, rebase, commit or push occurred. Original historical evidence, production engine, rating calculator, Monte Carlo and Prompt 2–3 research files are preserved. `preservation.json` lists the exact permitted additive changes and baseline fingerprints.

## M. Prompt 5 dependencies

1. Obtain and review original tournament regulations for unresolved rules; record source rights and historical timing.
2. Recover pre-tournament duration-annotated, regulation-only training and disjoint calibration observations, with source hashes and pre-match input provenance.
3. Validate separately versioned duration-compatible ratings, reference populations and cold-start policy; do not alter the production calculator to hide incompatibility.
4. Fit and freeze a new numeric model only after evidence and sample-sufficiency review. Validate out of time; disclose prior outcome exposure and quantify uncertainty. Do not retroactively call the 26 cases independent if used for tuning.
5. Preserve the complete 348-case inventory, separate horizon/model metrics and all remaining special-rating exclusions. No Star Power/Clutch assumption package has been supplied, and none was invented.

**Answer:** the infrastructure supports an explicit 80-minute research protocol and all 26 cases today. Scientifically defensible prediction evaluation remains blocked by the documented evidence shortfall. Zero eligible cases and unavailable accuracy are the supported result of this release.
