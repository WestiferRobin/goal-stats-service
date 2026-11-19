# GoalStats — final historical Backtesting integration and verification

## A. Executive verdict

**Operational for evidence-gated historical inspection and explicitly selected retrospective research replay across all nine editions and all 348 matches. Not approved for strict historical accuracy claims or as an independently validated forecasting system.**

Recovered O/D/F coverage improves from **320 to 340 matches**, supported by reconstructed populations. Two uncalibrated three-input research models score **320 eligible 90-minute cases**; the calibrated-temperature model scores **200 cases from 2011 onward**. All 26 1991 cases remain represented and excluded from prediction. Historical Star Power/Clutch availability is zero; no caller assumption package was supplied or invented. Strict historical eligibility remains zero.

The existing five-input model, production prediction formulas, rating calculator and Monte Carlo mathematics are unchanged. Research metrics below are actual retrospective calculations, not synthetic-test accuracy or evidence of prospective forecasting.

## B. Implementation summary

The confirmed integration gap was that Prompt 3's research predictions and validation diagnostics existed offline but were not selectable through Backtesting. Prompt 5 connects their pinned artifacts to the **existing evaluation service and endpoint**, with no duplicate evaluator or new endpoint. The adapter verifies the approved manifest and every artifact checksum, retains the 348-case inventory, checks case identity, pre-match cutoffs, regulation labels and reconstructed population hashes, and rejects invalid horizons or future calibration.

The API now supports an explicit three-input model selection and a distinct `retrospective_replay` mode. This mode accepts no hypothetical Star Power/Clutch values and requires the recovered evidence version used by Prompt 3. Strict mode remains available for these models but excludes all cases for unverified historical publication timing and does not expose replay comparison scores as strict results. Research classification is enforced in both request/response contracts and the frontend decoder.

The frontend provides research-model selection, strict/replay selection, per-case probabilities and provenance, separate 80/90-minute treatment, chronological-period summaries, common-cohort baseline comparisons and detailed calibration/uncertainty metadata. Changes to selections invalidate stale output. Pagination metrics are explicitly page-scoped; comparative diagnostics are separately labeled as edition/full-cohort scoped. Aggregation is permitted only within matching model, horizon, mode and source versions.

Prompts 1–4's pinned artifacts and mathematical implementations remain unchanged. The 80-minute interface remains evidence-blocked. No special estimator was promoted or silently inserted into scoring.

## C. Exact file inventory

`preservation.json` records **every uncommitted Prompt 1–5 file** in both repositories, its Git status and SHA-256 (self-referential package metadata is identified separately), plus the exact Prompt 5 changes relative to the pre-work snapshot. It also records all preserved baseline file hashes. `manifest.json` hashes this final evidence package.

Prompt 5 modifies these existing service files:

- `src/schemas/evaluation/request.py`
- `src/schemas/evaluation/response.py`
- `src/services/evaluation.py`
- `tests/integration/routers/test_evaluation_full.py`
- `tests/unit/schemas/contract_fingerprints.json` — expected evaluation API fingerprint only; the non-evaluation API preservation assertion remains unchanged.

Prompt 5 adds `src/services/evaluation_research.py`, `tests/unit/services/test_evaluation_research.py`, and this final report package (`.gitattributes`, `README.md`, `coverage.json`, `preservation.json`, `manifest.json`).

App modifications: `src/features/analytics/domain/backtesting.ts`, `src/features/analytics/domain/backtesting.test.ts`, `src/features/analytics/components/backtesting-panel.tsx`, and `tests/e2e/backtesting.normalized.spec.ts`. No app files are added. Prior Prompt 1–4 changes remain present. Test logs, disposable infrastructure receipts, browser artifacts and build output remain outside the reviewed source additions.

## D. Historical coverage

All regulation labels are preserved. “Ratings” means both teams have complete reconstructed Offense/Defense/Form; it does not establish scientific duration compatibility or historically verified publication availability.

| Edition | Matches / verified labels | Ratings before → after | A/B eligible | C eligible | A/B excluded |
|---|---:|---:|---:|---:|---:|
| 1991 | 26 / 26 | 19 → 20 | 0 | 0 | 26 |
| 1995 | 26 / 26 | 19 → 26 | 26 | 0 | 0 |
| 1999 | 32 / 32 | 26 → 30 | 30 | 0 | 2 |
| 2003 | 32 / 32 | 32 → 32 | 32 | 0 | 0 |
| 2007 | 32 / 32 | 31 → 32 | 32 | 0 | 0 |
| 2011 | 32 / 32 | 29 → 32 | 32 | 32 | 0 |
| 2015 | 52 / 52 | 48 → 52 | 52 | 52 | 0 |
| 2019 | 52 / 52 | 52 → 52 | 52 | 52 | 0 |
| 2023 | 64 / 64 | 64 → 64 | 64 | 64 | 0 |
| **Total** | **348 / 348** | **320 → 340** | **320** | **200** | **28** |

A/B are the uncalibrated three-input models; C is the calibrated-temperature model. Star Power available, Clutch available, five-input historical eligible, 80-minute eligible, and strict historical eligible are **zero for every edition**. The 80-minute protocol applies only to 1991; its other editions are not applicable, rather than additional 80-minute exclusions.

Eight cases remain rating-incomplete: IDs **3, 5, 10, 11, 16, 17, 57, 65**. A/B exclude **28 unique cases**: all 26 from 1991 plus two from 1999. Six of the eight rating-incomplete cases overlap the 1991 horizon exclusion. C excludes **148 unique cases**, including 120 otherwise rating-complete 90-minute cases before its calibration becomes applicable. Exclusion reason counts overlap and are never summed to obtain excluded population size.

`coverage.json` contains all 348 case IDs, teams, dates, cutoffs, regulation scores, horizons, rating availability, per-model eligibility, exact exclusion reason codes, actual probabilities/outcomes where eligible, per-edition metrics and source hashes. It also contains actual service request/manifest identities and the before/after matrix. Every match appears once in each model's eligible/excluded partition.

## E. Model coverage and requirements

| Model | Inputs and formulation | Operational classification | Eligible |
|---|---|---|---:|
| `road-to-the-final-heuristic-v2` | Existing five-input production formula, rankings and event behavior | Existing production behavior preserved; historical scoring still evidence-gated | 0 with available historical evidence and no assumptions |
| `odf-reweighted-poisson-research-v1` (A) | `s=max(1,(.30O+.25D+.20F)/.75)`; `lambda_i=2.6*s_i/(s_h+s_a)` | Research-only, retrospective 90-minute replay | 320 |
| `odf-cross-goal-rate-research-v1` (B) | `lambda_i=1.3*exp(log(2)*(O_i-D_j)/100 + log(1.5)*(F_i-F_j)/100)` | Research-only, retrospective 90-minute replay; predeclared primary candidate | 320 |
| `odf-temperature-research-v1` (C) | Normalize `p_B^(1/T)`; `T=.75`, selected on 2007 only | Research-only, applicable from 2011 onward | 200 |
| `odf-exposure-80-evidence-blocked-v1` | Candidate `lambda_i=80*r_per_team_minute*exp(beta_OD*(O_i-D_j)/100+beta_F*(F_i-F_j)/100)`; no fitted parameters | Explicit research interface; numerical prediction blocked | 0/26 |

A/B/C reuse the existing frozen Prompt 3 implementation and artifacts. They are not replacements for the five-input production engine. Their historical requirements are model-specific: complete O/D/F, pinned inputs and regulation labels, 90-minute horizon, and for C a strictly earlier calibration cutoff. They do not borrow or manufacture Star Power/Clutch.

Prompt 2's role-balanced regularized adjusted plus-minus Star Power candidate and adjusted prior-regulation residual Clutch candidate remain research-only. Their definitions, source inventory, cutoffs, uncertainty/missingness and versions remain in `historical-special-ratings-v1`; there is no independently approved numeric coverage to integrate.

## F. Actual accuracy results

These are **retrospective research replay metrics**, not strict historical accuracy, independent model certification, or prospective forecasts. All numbers use eligible cases only, natural-log loss with the existing 1e-15 floor, multiclass Brier sum in [0,2], and the existing deterministic argmax tie order. No model/horizon mixture is averaged.

| Model/cohort | N | Accuracy | Log loss | Brier |
|---|---:|---:|---:|---:|
| A, all eligible exploratory cases | 320 | 58.1250% | 0.996108832 | 0.594895749 |
| B, same 320 cases | 320 | 55.3125% | 0.983639486 | 0.585582747 |
| C, 2011–2023 only | 200 | 55.0000% | 0.987453447 | 0.588490637 |

**C's 200-case row must not be compared directly with the 320-case rows.** On the identical 200-case comparison cohort:

| Model/baseline | N | Accuracy | Log loss | Brier |
|---|---:|---:|---:|---:|
| A | 200 | 57.0000% | 1.004180581 | 0.600273428 |
| B | 200 | 55.0000% | 0.995907993 | 0.594364914 |
| C | 200 | 55.0000% | 0.987453447 | 0.588490637 |
| Prior class frequency | 200 | 51.0000% | 1.034033082 | 0.622503180 |
| Prior shared Poisson | 200 | 51.0000% | 1.053000357 | 0.638771963 |

Values are rounded for display; machine-readable Prompt 3 diagnostics retain full precision, exact cohort IDs/hashes, exclusion counts and paired differences. The uncalibrated baseline-common cohort has 294 cases; 1995 has no earlier approved 90-minute World Cup baseline sample. It is separately identified in the UI and diagnostics.

Confusion matrices use rows actual H/D/A and columns predicted H/D/A:

- A, N=320: `[[126,0,44],[34,0,24],[32,0,60]]`
- B, N=320: `[[120,0,50],[34,0,24],[35,0,57]]`
- C, N=200: `[[75,0,27],[24,0,15],[24,0,35]]`

**Draw recall is zero in all three reported cohorts.** Draw probabilities exist, but no draw is the most-likely predicted class. This is a material model limitation; aggregate accuracy is not a sufficient approval criterion.

Five-input historical metrics and all 1991 prediction metrics remain null. No missing caller assumption package was created. Synthetic tests exercise formulas and contracts but contribute no observations or reported historical accuracy.

## G. Historical evidence and publication uncertainty

The original martj42 CSV remains byte-identical: SHA-256 `de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0`, revision `1855e313ae8bcd0330426e62c8e4cf15ce45077c`. The approved recovery overlay adds **69 fixtures**, increasing the rating source from **11,650 to 11,719 rows**. Duplicate/reversed duplicate/conflicting results are rejected; identity mappings, source attribution and every historical reference population remain explicit. Merged-source hash: `22259e986df3cbf5970eea96a4ea4a884dad06ca5846d904da73f1d65237df85`.

Recovery improves numeric rating coverage by 20 cases; it does not establish Star Power/Clutch, regulation-only training-score semantics, comparable match durations, or historical publication availability. Archive/match dates are not proof that every input was available at the original cutoff. Source dependence is disclosed: martj42 cites RSSSF, so their agreement is not an independent observation.

1991 uses verified 80-minute regulation and two 40-minute halves. Its two extra-time fixtures (IDs 19 and 21) retain regulation draws, not their later winning final scores. The pinned [Prompt 4 rules audit](../duration-80-v1/rules-audit.json) separates primary technical-report evidence, attributed archive evidence and unresolved original tournament procedures. Original tournament-specific extra-time/advancement/shootout exceptions, golden-goal certification and measured added-time exposure remain unresolved. None is silently inferred from modern regulations.

The 1991 training investigation has 605 pre-tournament final-score candidates, but **zero qualified exposure training or calibration observations**. Nominal duration, regulation-only goals and historical publication evidence are missing jointly. Existing ratings also mix unverified durations and recorded scores that may include extra time. No 80/90 rescaling was accepted as validation.

## H. Chronological validation, calibration and leakage checks

The unchanged Prompt 3 protocol separates:

| Period | Editions | A/B eligible | C eligible | Interpretation |
|---|---|---:|---:|---|
| Development | 1995, 1999, 2003 | 88 | 0 | Exploratory development-period performance |
| Calibration | 2007 | 32 | 0 | Temperature fitting data; not independent validation |
| Validation | 2011, 2015 | 84 | 84 | Chronologically later retrospective validation |
| Later retrospective cohort | 2019, 2023 | 116 | 116 | Already-exposed historical outcomes, not pristine holdout |

T=.75 was selected from [.75,1,1.25] using the 32 calibration cases. It is never applied to 1991–2007. Primary model B and the A/B fixed coefficients were heuristic research specifications, not scientifically estimated historical parameters. Baselines use only earlier approved development editions through 2003 and freeze thereafter. All reconstructed case inputs use the previous calendar day; same-day and future results are excluded. Full population hashes bind each replay to the prior reconstruction. Future ranking releases are rejected; research models do not use rankings. No future player observations or unapproved special estimates enter scoring.

On the 84-case validation cohort, B log loss is approximately 1.043917 and C is 1.046378: temperature calibration does **not** improve that validation loss. On the later 116 cases, B is approximately .961143 and C .944784. This variation, prior outcome exposure, zero draw recall and limited independent edition counts prevent a production-validation claim.

The pinned diagnostics include 5-bin class calibration, class support/precision/recall, 1,000 deterministic bootstrap replicates (seed 20261116), descriptive 95% intervals and paired common-cohort differences. For example, B's all-exploratory accuracy interval is approximately [.50298,.60571]. These are retrospective descriptive intervals, not guarantees of future performance; the two-edition validation grouping provides limited independent information.

The 80-minute candidate separately proposes training before 1990, disjoint calibration through 1991-11-15 and evaluation from 1991-11-16 onward. It has no fitted parameters and remains blocked. The 2007 temperature is never transferred to 1991. All frozen source/model versions and protocol hashes are retained.

## I. API/frontend behavior and reproducibility

Existing endpoint: `POST /api/v1/evaluations/backtests`.

Example full research request:

```json
{
  "dataset_id": "womens-world-cup-full-v1",
  "recovery_package_id": "international-results-recovery-v1",
  "prediction_model_version": "odf-cross-goal-rate-research-v1",
  "research_model_version": "odf-exposure-80-evidence-blocked-v1",
  "mode": "retrospective_replay",
  "offset": 0,
  "limit": 348
}
```

`research_model_version` here selects the separate blocked 1991 protocol; `prediction_model_version` selects the 90-minute model. For a specific 90-minute edition, omit the 1991 selector and set `edition` to that year. To inspect strict gates, use `mode: strict_historical`. The existing five-input defaults and explicit `retrospective_assumptions` workflow remain intact. Research replay rejects caller assumptions, unknown models, incompatible data selections and unapproved artifacts.

Case probabilities/outcomes are populated only when the selected model's requirements pass. Excluded predictions remain null; all cases, reasons and regulation evidence remain visible. The API returns model/source/version hashes, case cutoffs, input provenance, model/horizon groups and research classification. Strict research results contain no replay comparison scores. The temperature model's early editions remain excluded rather than backfilling later calibration.

Actual read-only canonical-service replay verified all 348 cases for original/recovered strict selection and each research model. Live disposable API tests verify deterministic results, strict exclusions, calibrated horizons, pagination, source errors and additive metric aggregation over two disjoint pages of the same B cohort. Frontend checks cover all editions, full selection, strict/replay mode, model changes, missing evidence, metrics/matrix, common cohorts, provenance, retries, timeouts and stale-result handling. The normalized suite exercises the actual backend rather than substituting mocked success responses; existing synthetic error/contract tests remain clearly test-only.

Reproduce offline methodology using the existing `scripts/evaluation/build_recovery.py`, `build_special_research.py`, `build_three_input.py`, and `build_duration_audit.py` in their documented environments; their outputs are preserved, not regenerated under new parameter choices. Reproduce the user workflow with the request above or Analytics model selection. Compare request manifests and pinned data/model hashes, not merely rounded displayed scores. `coverage.json` records the requests and identities used for this audit.

## J. Test results

| Check | Final result |
|---|---|
| Backend `make certify` unit/integration/API contracts | **1,937 passed, 0 failed**, 1,797.31 seconds |
| Combined coverage | **95.806923%**, 5,895/6,153 covered statement/branch opportunities; 95% gate passed |
| Statement / branch coverage | **96.725389% / 92.469880%** |
| Ruff | Passed |
| Formatting | Passed, 266 files already formatted |
| Mypy | Passed, 105 source files |
| Frontend unit/component tests | **437 passed, 0 failed**, 25 files |
| TypeScript | Passed |
| ESLint | Passed, 0 errors; 3 warnings in unchanged files |
| Production build | Passed |
| Normalized browser E2E, final full run | **37 passed, 0 failed**, 4.8 minutes |
| Home/Demo browser E2E | **9 passed, 0 failed**, 20.1 seconds |
| Actual canonical read-only replay | All seven 348-case configurations verified; frontend decoder accepted all seven |
| Database / Docker preservation | Passed; all audited canonical table counts/hashes unchanged, owned disposable resources removed, pre-existing resources preserved |

Backend and browser suites ran sequentially against disposable infrastructure. The backend certification includes independent historical reconstruction, original production mathematics, Monte Carlo, API contracts, deterministic full research replay and pagination aggregation. The normalized browser suite includes live Backtesting for all editions, the 1991 blocked protocol, explicit research models and common-cohort diagnostics, plus Teams, Matches, Predictions, Analytics and real tournament simulations. Node 24.22.3 and npm 11.19.1 were pinned by the existing runner.

**First-run failure disclosure:** the first normalized run had **35 passed / 2 failed** in existing tests, before Home/Demo ran. The prediction-save test failed at its initial five-second team-catalog wait (HTTP 200 arrived after approximately 4.9 seconds), before saving. The intentional outage test exceeded its 15-second backend-readiness deadline; the service subsequently started. A fresh complete run of the **unchanged source, tests, timeouts and assertions** passed all 37 tests, followed by all nine Home/Demo tests. No automatic retries or relaxed assertions were used to obtain this result. These transient timing failures remain a test-environment reliability limitation, not hidden successful results.

The three lint warnings concern existing image elements in About/Project and an unused Home parameter. Initial dependency installation reported **seven moderate npm advisories** against the unchanged dependency lockfile; no dependency changes were introduced, and this audit does not certify the application as vulnerability-free. The changed-file scan found no private-key, AWS access-key or GitHub-token signatures; server-owned artifact paths and enum selectors do not introduce caller-controlled file access.

Local evidence (ignored/outside source additions): backend certification log `/tmp/goalstats-prompt5-certify.log` and report directory `.host-sessions/certify-goal-stats-service-test-f9ef1e477dc1e17e65d47e2e.2XGaai`; first browser log `/tmp/goalstats-p5-normalized.log` and app artifact directory `artifacts/goalstats-normalized-fa3ff201283d40f389defbde8dad062a`; successful browser log `/tmp/goalstats-p5-normalized-rerun.log` and artifact directory `artifacts/goalstats-normalized-d39f439c0ec144f1bd92430e0bed4c74`. These machine-local logs are not required to run the checked-in tests and are not included in the release package.


## K. Database preservation

Read-only before/after verification matched all ten tables exactly. Hashes cover deterministically serialized full table content.

| Table | Rows before = after | SHA-256 before = after |
|---|---:|---|
| `matches` | 348 | `5bbe9c69d840f15e425080ea8c9168eb09070a450c145a49864821824065bba5` |
| `competitions` | 9 | `e5644f1fa058ac1d2a05dca4fd5a3ffeeb86cb8ae9936536883d7d3f7908ac73` |
| `teams` | 44 | `8dec28a6f861bca1afdd2309b2168801eae87822f5dd99c83f4ca46eaf541530` |
| `ranking_releases` | 96 | `537be0c5774d58e6ecb98f496bb9523ac3833e18c7a32d7a5b3c0638c1770c1e` |
| `ranking_observations` | 16525 | `9bd708d2dbd142c7f1f5c5d1a230d0ec7a5e8de48c659a4022b4bb919edaf7e9` |
| `fifa_team_mappings` | 44 | `f2fe7036c527193cfce0f149d7c880054f9541b741a15d98d1ef4c0fc17de07e` |
| `rating_runs` | 1 | `50504dcc4f4e5649182b538f38b44b0a8344e794f69523db8699dcf36af0ec6d` |
| `team_ratings` | 44 | `f687088ef79e9265f90f11bb242f1949311ba623403dc69b72f18a41aba84cbd` |
| `scenarios` | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| `predictions` | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |


Canonical service/database checks use read-only historical transactions. Disposable test databases own their schema/seed operations. No canonical matches, competition/team identities, rankings, ratings, scenarios or predictions were changed. No migration files were added. Secrets were not copied into source or reports. The new adapter accepts fixed enum versions and reads only server-owned checksum-pinned artifacts; callers cannot submit research probabilities, source paths or estimator outputs.

## L. Git state

Both repositories remain on `member/wes-v2` with unchanged HEAD:

- Service: `396eedbb0107d87c81d466cb860d07c13b1f3334`
- App: `799740f8ec7807d3b6798845879d5506e44d93ae`

All Prompt 1–5 changes remain uncommitted for review. No branch switch, reset, stash, merge, rebase, commit or push occurred. `preservation.json` records the complete working-tree inventory and distinguishes the Prompt 5 additions from preserved earlier work. Existing production mathematics, Monte Carlo, original sources and all prior research artifacts are byte-identical to the Prompt 5 starting snapshot.

## M. Remaining blockers

1. Historical input publication availability is not verified; strict historical accuracy remains unavailable for all models.
2. No independently approved/validated historical Star Power or Clutch estimates exist. Five-input historical coverage cannot be filled with defaults or a fabricated assumption package.
3. 1991 lacks qualified duration/regulation-goal training and calibration evidence, duration-compatible ratings and complete original rule certification. It has a working blocked interface, not a validated numerical predictor.
4. Eight cases remain O/D/F-incomplete. Recovery did not justify imputing them.
5. Three-input models remain heuristic research candidates with prior outcome exposure, zero draw recall and mixed validation findings. No independent production-approval process has been completed.
6. Historical ratings use recorded scores including possible extra time and unknown training durations. A separately versioned, independently validated correction would be required before claiming regulation-calibrated scientific forecasts.
7. No prospective prediction ledger before real future outcomes was produced by this retrospective task.

## N. Final go/no-go

| Area | Decision | Boundary |
|---|---|---|
| Historical data recovery | **GO** | Reviewed overlay, deterministic reconstruction and 320→340 coverage; source/publication caveats retained |
| Three-input research models | **GO for research replay; NO-GO for production replacement** | Explicit versions, eligible cohorts, diagnostics and limitations |
| Existing five-input production model | **GO to preserve existing functionality** | No new claim of validated historical accuracy; no mathematical change |
| 1991 research protocol | **GO for evidence inspection; NO-GO for prediction/accuracy** | All 26 accounted for; zero eligible |
| Backtesting infrastructure | **GO** | Existing API/UI integrate the supported models with separate gates and horizons |
| Retrospective accuracy reporting | **GO, qualified** | Eligible three-input research cohorts only; disclose exposure and source-timing limits |
| Strict historical accuracy reporting | **NO-GO** | Required historical availability/model evidence missing |
| Prospective forecasting claim | **NO-GO** | No pre-outcome prospective trial performed |
| Team review | **GO** | Complete file/coverage/provenance report and reproducible checks |
| Commit readiness | **GO for review of the research-scoped changes, conditional on retaining the documented limitations** | No commit or push performed; scientific limitations must remain part of the release |

**Final state:** all 348 matches and nine editions are operationally accounted for. Actual three-input retrospective research probabilities and metrics are available through Backtesting. Five-input historical accuracy, strict historical accuracy and 1991 prediction accuracy remain honestly blocked. The existing application and Monte Carlo behavior are preserved.
