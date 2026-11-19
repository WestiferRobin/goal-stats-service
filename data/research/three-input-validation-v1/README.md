# Prompt 3 — three-input prediction research and chronological validation

## A. Implementation summary

A separately versioned Offense/Defense/Form research model now produces deterministic pregame regulation W/D/L probabilities for **320 of the 348** approved historical matches. These are **retrospective reconstructions**, not verified historically published forecasts or production-approved predictions. All nine editions remain in the inventory. All 26 matches from 1991 are excluded from 90-minute scoring; two 1999 matches also lack complete historical ratings.

Three candidate formulations and two simple baselines are implemented in isolated research modules. Candidate B was designated primary by its cross-opponent structure before metrics were calculated; its parameters were not chosen using later performance. Candidate A has lower observed probabilistic losses in 2011–2015, while B and its calibrated variant C have lower losses in 2019–2023. That change in relative performance, limited independent editions, and prior exposure of historical outcomes prevent a robust superiority claim.

**Five-input historical comparison not yet supported by available evidence.** Prompt 2 supplies no independently approved historical Star Power/Clutch estimates. No zero, 50, random, expert-invented, or hypothetical special ratings are inserted. Three-versus-five comparison eligibility is zero.

Run explicitly, offline:

```sh
PYTHONPATH=src .venv/bin/python scripts/evaluation/build_three_input.py
```

The builder verifies the frozen protocol, approved historical packages and ranking projection, then reproduces `predictions.json`, `results.json` and their manifest. It does not connect to a database, invoke production predictions, expose a route, or fit new historical Offense/Defense/Form populations. Existing complete reconstructed populations are verified and reused. The existing regression suite independently checks their reconstruction.

## B. Exact Prompt 3 files

All files below are new. No pre-existing Prompt 1, Prompt 2, backend production, or frontend file is edited.

- `src/research/three_input.py`
- `src/research/model_validation.py`
- `scripts/evaluation/build_three_input.py`
- `tests/unit/research/test_three_input.py`
- `tests/unit/research/test_model_validation.py`
- `data/research/three-input-validation-v1/.gitattributes`
- `data/research/three-input-validation-v1/README.md`
- `data/research/three-input-validation-v1/protocol.json`
- `data/research/three-input-validation-v1/rankings.json`
- `data/research/three-input-validation-v1/predictions.json`
- `data/research/three-input-validation-v1/results.json`
- `data/research/three-input-validation-v1/manifest.json`
- `data/research/three-input-validation-v1/preservation.json`

## C. Three-input model specifications

Every team must supply finite Offense, Defense and Form values in [0,100]. Missing values are excluded rather than imputed. Ranking is deliberately **not an input** to these three-input models. All candidates support pregame **90-minute regulation only**, including regulation draws and excluding extra-time/shootout results. The interface rejects 80-minute requests and unknown production/model versions.

| Label | Exact model version | Role |
|---|---|---|
| A | `odf-reweighted-poisson-research-v1` | Reweighted strength comparator |
| B | `odf-cross-goal-rate-research-v1` | Prespecified primary cross-opponent goal-rate model |
| C | `odf-temperature-research-v1` | Training-only probability calibration of B |
| Freq | `prior-wwc-class-frequency-research-v1` | Historical class-frequency baseline |
| Pois | `prior-wwc-poisson-research-v1` | Training-only symmetric Poisson baseline |

**A:** `s_i=max(1,(.30 O_i+.25 D_i+.20 F_i)/.75)` and `λ_i=2.6*s_i/(s_home+s_away)`. Dividing by .75 explicitly renormalizes the original three retained weights to .4, 1/3 and 4/15. The numerical floor prevents a zero denominator when real observed ratings are zero; it does not stand in for missing data. A is a new implementation with no Star/Clutch arguments. A common positive rescaling cancels in the strength ratio when the floor is inactive, so dividing by .75 does not itself create a new probabilistic effect. A deliberately tests the retained relative O/D/F weighting hypothesis; it is not an evidence-supported five-input prediction. Its limitation is structural: stronger Defense increases aggregate strength rather than directly suppressing the opponent's goal rate; total expected goals stays fixed at 2.6.

**B:** for team i against j,

`λ_i = 1.3 * exp(log(2)*(O_i-D_j)/100 + log(1.5)*(F_i-F_j)/100)`.

Offense therefore raises the team's own rate, the opponent's Defense lowers it, and relative Form affects both teams in opposite directions. Equal balanced profiles give 1.3 goals each. A full 100-point Offense-minus-Defense difference multiplies the rate by two; a full Form difference multiplies it by 1.5. Valid input extremes bound each mean between approximately .433333 and 3.9. The intercept and effect multipliers are frozen, mathematically explicit hypotheses, **not empirically validated physical conversions of percentiles into scoring rates**. No home-field advantage or ranking bonus is smuggled into the three inputs.

For A/B, independent Poisson score marginals yield `P(home)=Σ_{x>y}P(x)P(y)`, `P(draw)=Σ_{x=y}P(x)P(y)` and `P(away)=Σ_{x<y}P(x)P(y)`. The implementation bounds each omitted marginal tail by `2.5e-13`, normalizes the retained joint outcome mass, and explicitly preserves home/away equality for equal means. This last step prevents floating-point accumulation order from breaking a mathematical tie. Exact argmax ties use the existing metrics convention: home, then draw, then away. Accuracy of symmetric baselines consequently depends on the registry's side ordering and must not be interpreted as a home-advantage discovery.

**C:** `q_k = p_B,k^(1/T) / Σ_j p_B,j^(1/T)`. A frozen grid `[.75,1,1.25]` is searched only on the 32 rating-complete 2007 cases using mean log loss; exact objective ties use grid order. The selected parameter is **T=.75**, version `odf-temperature-2007-v1`, with training through **2007-09-30**. At least 20 calibration cases are required. Calibration rejects other editions, duplicate cases, invalid outcomes, and cases on or after the prediction date. C is scored only from 2011 onward. Temperature changes probability confidence but preserves class ordering, so it cannot improve accuracy relative to B except through a numerical defect; the mathematical behavior is tested. C is a calibrated W/D/L distribution, not a newly fitted Poisson score distribution.

The canonical protocol hash is `43f1bd4637788464199d2ad9becb57c951fa99487000a61184dac7bc48e2110e`. It was frozen before calculating metrics. No candidate weights, grid values, cohort thresholds or selection criterion changed after observing performance. The small symmetry correction implements the already-specified independent-Poisson/tie mathematics; it is not an outcome-fitted parameter adjustment.

Independent Poisson models are a transparent starting point, but their low-score dependence limitations are part of the football-modeling literature; this implementation does not claim to implement a fitted Dixon–Coles correction. See [Dixon and Coles (1997)](https://rss.onlinelibrary.wiley.com/doi/pdf/10.1111/1467-9876.00065). Proper probability scoring motivates prioritizing log loss and Brier over winner-only accuracy; see [Gneiting and Raftery (2007)](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jasa.pdf). Neither paper validates the coefficients or historical cohort used here.

## D. Existing five-input model and preservation

The production engine remains unchanged. Its five numeric inputs are in [0,100], with base strength

`S=.30 Offense+.25 Defense+.20 Form+.15 StarPower+.10 Clutch+ranking_bonus`.

When a rank exists, the bonus is `clip((25-rank)*.08,-2,2)`; otherwise zero. At pregame, with no live events/cards, expected goals allocate total 2.6 according to `max(S,1)` strength shares. The regulation adapter uses the remaining 90-minute ratio and independent Poisson W/D/L calculations. Live modifiers, possession, scoreline, attack pressure and red-card effects remain intact. Star bad-game effects remain `-round(.1*StarPower,1)`, with aggregate event caps unchanged. Clutch still apportions tied advancement mass in proportion to the two Clutch inputs, with equal shares if both are zero. Monte Carlo sampling and tied-simulation advancement are untouched.

The regulation prediction version remains `road-to-the-final-heuristic-v2`; legacy tournament behavior is preserved. Its implementation/regression evidence does not establish historical calibration or independently identify Star Power and Clutch. Historical reconstruction uses results no later than the previous calendar day, not current 2026 ratings. Rankings use the latest existing release strictly before the match.

Prompt 2's interfaces are unvalidated research methods and have zero historical numeric estimates. They are not imported as observations or automatically approved. No five-input predictions, accuracy metrics or sensitivity assumptions are generated in this package. Existing production evaluation metrics are reused without editing them. Future three-versus-five comparisons must also acknowledge that the five-input engine has an optional ranking bonus and different goal mathematics; differences cannot automatically be attributed to Star Power/Clutch alone.

## E. Historical coverage and provenance

| Edition | Inventory | Rating complete | A/B eligible | C eligible | Five-input eligible | Three-v-five common | A/B excluded | Both ranks present |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1991 | 26 | 20 | 0 | 0 | 0 | 0 | 26 | 0 |
| 1995 | 26 | 26 | 26 | 0 | 0 | 0 | 0 | 0 |
| 1999 | 32 | 30 | 30 | 0 | 0 | 0 | 2 | 0 |
| 2003 | 32 | 32 | 32 | 0 | 0 | 0 | 0 | 32 |
| 2007 | 32 | 32 | 32 | 0 | 0 | 0 | 0 | 32 |
| 2011 | 32 | 32 | 32 | 32 | 0 | 0 | 0 | 32 |
| 2015 | 52 | 52 | 52 | 52 | 0 | 0 | 0 | 52 |
| 2019 | 52 | 52 | 52 | 52 | 0 | 0 | 0 | 52 |
| 2023 | 64 | 64 | 64 | 64 | 0 | 0 | 0 | 61 |
| Total | **348** | **340** | **320** | **200** | **0** | **0** | **28** | **261** |

The 26 horizon exclusions overlap six missing-rating cases in 1991; exclusion reasons therefore must not be naively summed. The remaining two A/B exclusions are 1999 match IDs **57 and 65**. The full eight rating gaps, including 1991, are 3, 5, 10, 11, 16, 17, 57 and 65. No thresholds were lowered. Every case retains its ID/key, teams, date, cutoff, original regulation horizon, rating evidence, full-population hash/size, source-prefix hash, ranking provenance, model probabilities or reasons for exclusion, and parameter-training provenance in `predictions.json`.

Rating source/model: `international-recorded-score-poisson-v1`, original international-results revision `1855e313ae8bcd0330426e62c8e4cf15ce45077c`, plus the approved `international-results-recovery-v1` overlay. The original source SHA256 is `de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0`. Original full evidence manifest SHA256: `47c947db3f117a14761930da3c0dcfa3b68b50e94b6e12904b9bf7ddc75a0a28`. Recovery manifest SHA256: `45593e9139180f48ec931846d6316f62dfc975386c28c58167c0e737f42ce31b`. The merged source, individual registry label sources and all reference populations remain pinned in the artifacts.

The unchanged historical rating calculator uses its 1461-day result window, minimum eight matches/recent-activity requirements and 365-day Form reconstruction with the existing minimum Form sample. It uses full eligible reference populations, never only the evaluated teams. Prompt 1's 69 approved fixtures supply the recovery overlay; nothing is re-imported or duplicated here. Cached populations are accepted only after the existing source-prefix, cutoff, model and population hash checks pass. The existing full regression independently refits all 137 cutoff populations.

`rankings.json` is a read-only projection of existing canonical release/observation/mapping records. It preserves release dates, IDs, source URLs/hashes, retrieved dates, observed ranks/points and missing reasons for all 348 cases. Its SHA256 is `2ec1a17e75b3096f58274811c96e51b9bfd12f9fe0d7fa08636cd98fce1c162b`. No external dataset or current rating was imported. Ranking availability is recorded but cannot alter A/B/C probabilities. Three 2023 cases lack both-team complete ranks, which does not exclude a genuinely three-input model.

Historical event-time cutoffs are enforced; complete historical **publication availability is not verified**. These are retrospectively reconstructed features from later archives. In addition, the underlying rating calculator fits recorded final scores that sometimes include extra time and earlier matches of different duration. The new model's evaluation targets are reviewed regulation-only labels, but its input measurement model has those inherited limitations. This research does not silently relabel the original calculator as a regulation-calibrated model.

## F. Frozen chronological protocol

| Purpose | Editions | Eligible A/B cases | Use of outcomes |
|---|---|---:|---|
| Horizon excluded | 1991 | 0 | Never used to train the 90-minute baselines or score these models |
| Development | 1995, 1999, 2003 | 88 | Train simple baselines using earlier development editions; A/B coefficients are fixed hypotheses |
| Calibration | 2007 | 32 | Select C temperature only; calibration objective is in-sample selection evidence |
| Out-of-time validation | 2011, 2015 | 84 | Evaluate frozen mappings and temperature; no parameter selection |
| Retrospective later evaluation | 2019, 2023 | 116 | Evaluate unchanged specifications; no tuning or winner promotion |

Baseline training uses only reviewed 90-minute World Cup records in development editions through 2003, strictly before the predicted edition. It requires at least 20 cases. Thus no such baseline exists for 1995; 1999 uses 26 prior cases, 2003 uses 58, and 2007 onward uses the same 90 development matches. Those 90 labels include cases that do not need complete ratings to estimate a class frequency or shared goal rate. Baseline parameters are not refitted on validation or later evaluation outcomes.

A/B have no learned prediction parameters. C calibration is solely 2007 and is frozen before 2011. Existing O/D/F feature reconstruction still updates at each match cutoff using earlier observed results, including earlier matches in an evaluation period, as a live reconstruction would. This is a **prequential feature policy**, not a single-origin forecast that forbids later observed results forever. The evaluated match's own result and future results never enter its features. Future outcomes cannot enter baseline or temperature training.

All 348 registry outcomes were already visible during earlier data audits. Consequently 2019–2023 is a retrospectively designated later evaluation period, **not an untouched or prospective test set**. Its role is to reveal out-of-time behavior of frozen specifications, not certify generalization. All-edition pooled results in `results.json` are explicitly exploratory and combine development, calibration and later periods; they must not be presented as independent test performance. No further candidate selection is performed from validation or later metrics in this task.

The model versions, source hashes, parameter versions, training cases/hashes, cohort membership hashes and protocol hash allow deterministic replay. A change to formulas, thresholds, temperature grid, splits or selection policy requires a new reviewed protocol/version before further comparison. Numerical implementation corrections must preserve the declared mathematical specification rather than tune predictions to outcomes.

## G. Baseline comparisons

The frequency baseline applies one-count Laplace smoothing: `(count_class+1)/(n+3)`. The Poisson baseline estimates a shared per-team regulation goal mean `Σ(home_goals+away_goals)/(2n)` from the same prior training window, then uses independent Poisson W/D/L probabilities. From 2007 onward, the training mean is **1.8166666667**, using 90 matches through **2003-10-12**, parameter version `development-only-baselines-v1`, training hash `e6a525c26641900d7ae2957acecaf81af1ce3ac47e5911869c9779d0b30169ca`.

The preserved FIFA ranks are ordinal and do not themselves specify a defensible three-way probability map. No ranking-to-W/D/L calibration was independently fixed/trained in this task, so a ranking baseline is deferred rather than fabricated. Likewise, an additional independently fitted opponent-adjusted regulation-results baseline would require a separately specified regulation training corpus/model. B already consumes opponent-adjusted historical ratings, but is not mislabeled an independently trained results baseline.

Comparisons use explicit intersections:

- A versus B: 320 cases across the exploratory full inventory.
- A/B versus both simple baselines: 294 common cases; 1995 has no prior 90-minute baseline training sample.
- A/B/C and both baselines: 200 common cases from 2011 onward.
- Validation comparison: the same 84 cases for all five research/baseline models.
- Later retrospective comparison: the same 116 cases for all five research/baseline models.
- Three-input versus existing five-input: **0 cases**.

No accuracy percentages from different case sets are treated as directly comparable. `results.json` stores exact included match IDs, cohort hashes and excluded-from-group counts for every comparison. Identical evaluation cases do not imply identical training information: the simple baselines deliberately use much less information than the historical rating calculator.

## H. Model metrics, calibration and uncertainty

All following performance tables use model versions defined in section C, the source/model versions in section E, the frozen protocol and periods in section F, and the same cohort within each table. Log loss uses natural logarithms and the existing `1e-15` numerical floor; multiclass Brier is the sum over three classes, range [0,2]. Accuracy is secondary. These are retrospective regulation-outcome evaluations, not prospective forecasts or five-input comparisons.

Brackets show **descriptive 95% bootstrap percentile intervals**, not reliable confirmatory confidence intervals. The reproducible procedure uses 1,000 resamples, seed 20261116, and whole-edition blocks when at least two editions exist. Each model in a comparison receives the same sampled indices, enabling paired loss differences. Individual-edition reports use within-edition match resampling, which assumes independence that repeated teams may violate. Each validation/later table has only **two edition clusters**: the resulting intervals can be extremely narrow for paired differences and are not a sound basis for significance claims or model promotion. They omit source uncertainty, model selection uncertainty and systematic misspecification.

**2011–2015 validation: 84 identical cases; no within-period exclusions**

| Model | Log loss [interval] | Brier [interval] | Accuracy [interval] |
|---|---|---|---|
| A | 1.028016 [1.014652, 1.049733] | 0.617432 [0.607818, 0.633055] | 52.38% [50.00%, 56.25%] |
| B (primary) | 1.043917 [1.030534, 1.065664] | 0.629602 [0.620328, 0.644673] | 47.62% [46.15%, 50.00%] |
| C | 1.046378 [1.033205, 1.067783] | 0.633074 [0.624702, 0.646678] | 47.62% [46.15%, 50.00%] |
| Freq | 1.059819 [1.031439, 1.077284] | 0.636118 [0.614869, 0.649195] | 50.00% [48.08%, 53.12%] |
| Pois | 1.071180 [1.066843, 1.073849] | 0.649542 [0.646973, 0.651123] | 50.00% [48.08%, 53.12%] |

**2019–2023 retrospective later evaluation: 116 identical cases; no within-period exclusions**

| Model | Log loss [interval] | Brier [interval] | Accuracy [interval] |
|---|---|---|---|
| A | 0.986920 [0.955740, 1.012254] | 0.587848 [0.568103, 0.603891] | 60.34% [56.25%, 65.38%] |
| B (primary) | 0.961143 [0.922281, 0.992719] | 0.568848 [0.544008, 0.589031] | 60.34% [56.25%, 65.38%] |
| C | 0.944784 [0.890099, 0.989216] | 0.556206 [0.522391, 0.583681] | 60.34% [56.25%, 65.38%] |
| Freq | 1.015361 [0.980762, 1.043472] | 0.612644 [0.597913, 0.624613] | 51.72% [51.56%, 51.92%] |
| Pois | 1.039836 [1.006596, 1.066843] | 0.630973 [0.611280, 0.646973] | 51.72% [51.56%, 51.92%] |


Full confusion matrices, class precision/recall/support, classwise five-bin reliability tables, intervals, paired differences and all per-edition outputs are in `results.json`. Undefined precision is null rather than zero when a class is never selected.

For primary B, mean predicted draw probability is **25.53%** versus **22.62%** observed in validation, and **24.91%** versus **17.24%** observed in later evaluation. C reduces those means to **23.03%** and **22.09%**, respectively, but these aggregate frequencies do not prove calibration at individual probability levels. B never selects draw as its highest-probability class in either period: draw recall is **0/19** and **0/20**. It nevertheless assigns nonzero draw probabilities. This demonstrates why plausible mathematical probabilities and decent winner accuracy do not establish appropriate empirical calibration.

A has lower observed log loss and Brier than B/C in validation. In later evaluation, C has the lowest observed losses among these frozen candidates; A, B and C all have 60.34% accuracy. These are period-specific observations, not proof that C is generally superior. B remains the prespecified primary; no candidate is promoted into production. A direct conclusion about the existing five-input model is impossible with zero defensible comparison cases.

## I. Scientific limitations

The apparent gains are small/moderate descriptive differences in a retrospectively exposed, selected competition cohort. Only two later editions support each main comparison, teams recur across games and editions, and group/knockout mixtures and football eras change. Class frequencies depend on fixture side ordering; symmetric baseline accuracy reflects the documented argmax tie policy. Missing O/D/F cases are not plausibly guaranteed missing at random.

The chosen percentile-to-goal mapping is not estimated from a comprehensive prior regulation corpus. A/B do not model home advantage, player availability, score dependence or uncertainty in historical ratings. C uses only 32 calibration cases and a coarse fixed grid; better in-sample calibration loss does not validate its generalization. Its worse validation losses and better later losses provide mixed evidence. Source timestamps distinguish when events occurred from when archive snapshots were retrieved; strict historical availability remains unverified. Original final-score feature estimation also carries duration/extra-time mismatch into the input ratings.

The bootstrap intervals are conditional on the observed features/labels and frozen models. With only two clusters, they cannot reliably quantify the population of future tournaments; intervals excluding zero are not sufficient evidence of superiority. Per-match intervals likewise do not solve team/tournament dependence. Future comparisons need genuinely unexposed data, prespecified paired scoring tests, enough independent clusters, sensitivity analyses and independent source/construct review. No new model was tuned to minimize final-period losses.

To compare with five inputs, obtain independently approved pre-match Star Power/Clutch evidence, preserve its uncertainty and provenance, and evaluate both models on identical supported regulation cases. Distinguish the extra constructs from differences in goal-rate mapping and ranking usage. In general, regulation outcomes alone cannot identify the existing `.15*StarPower+.10*Clutch` contribution as two separate valid constructs.

## J. Test results

Focused research suites: **69 passed, 0 failed**, comprising 35 new Prompt 3 cases plus 34 preserved Prompt 2 cases. The two new modules have **100% statement and branch coverage** (215 statements, 98 branches). Ruff lint and formatting pass; strict Mypy passes for 102 source files. Tests cover model isolation, exact Poisson symmetry, known probabilities, extreme/invalid/missing ratings, input sensitivity, horizon rejection, temperature ordering, historical cutoffs, frozen training/calibration separation, future-data rejection, ranking integrity, duplicate cases, deterministic replay, same-cohort comparisons, uncertainty, full nine-edition accounting and frozen artifact hashes.

The initial full run passed all 1,903 tests and its 95.805142% coverage gate, but the wrapper reported a Docker resource-preservation failure during cleanup. Its owned test resources were removed and canonical database fingerprints remained unchanged. The precise cause was not retained by that wrapper; a subsequent full run passed with a separately retained Docker baseline, independently verified after cleanup.

Full backend certification: **1,903 passed, 0 failed**, in 1261.42 seconds. Combined statement/branch coverage: **95.805142%**; statement coverage **96.720960%**, branch coverage **92.375602%**. The 95% combined coverage gate and disposable-resource cleanup both passed. Full and focused test counts overlap; do not add them. Existing Backtesting and Monte Carlo regressions are included. The complete source/test/evaluation-artifact hash inventory confirms that none changed during certification. Frontend tests, TypeScript/build and browser E2E are not applicable because Prompt 3 changes no frontend file, contract or user-facing functionality.

## K. Database preservation

Canonical tables are accessed only for read-only snapshots and the historical ranking projection. The offline model builder never accesses a database. Full certification uses its own disposable test services; canonical records are not migrated or updated. Before/after counts and complete fingerprints match exactly and are recorded in `preservation.json`.

The baseline counts are: matches 348; competitions 9; teams 44; ranking releases 96; ranking observations 16,525; FIFA team mappings 44; rating runs 1; team ratings 44; scenarios 0; predictions 0.

## L. Git state and earlier work

Both repositories remain on `member/wes-v2`. Service HEAD is `396eedbb0107d87c81d466cb860d07c13b1f3334`; app HEAD is `799740f8ec7807d3b6798845879d5506e44d93ae`. No commit, push, merge, rebase, reset, stash or branch switch is performed. All changes remain uncommitted. No secrets, downloaded unapproved datasets, or temporary test artifacts are added to the intended research package.

The start-of-Prompt-3 byte inventory covers all **332 service files and 162 app files** already present, including every Prompt 1 and Prompt 2 change. Final byte-for-byte verification confirms that all 494 pre-existing tracked/nonignored files remain unchanged; evidence and complete Git status are recorded in `preservation.json`. The inherited service modifications include the recovery schema/service/test changes, recovery evidence package and Prompt 2 research files. The five inherited frontend modifications remain `src/features/analytics/domain/backtesting.ts`, `backtesting.test.ts`, `src/features/analytics/components/backtesting-panel.tsx`, `backtesting-panel.test.tsx`, and `tests/e2e/backtesting.normalized.spec.ts`. Prompt 3 adds only the 13 files listed in section B.

## M. Prompt 4 dependencies: 1991 compatibility

All 26 1991 records and their reviewed 80-minute labels are preserved. A 90-minute predictor is never evaluated against them here. Twenty have complete current historical O/D/F inputs, while six still lack them. Prompt 4 must define and version an explicit 80-minute model and its training/calibration rationale, assess whether rate scaling is defensible, and handle any feature-estimation mismatch from mixed match durations. Simply calling the 90-minute model, multiplying a reported accuracy, or assuming identical scoring intensity is not validation.

Any 80-minute parameter estimation must use defensible prior data and cannot borrow later World Cup outcomes to claim an out-of-time 1991 forecast. Appropriate prior 80-minute regulation evidence, source publication provenance, remaining rating recovery, temporal tests and a matching evaluation cohort are dependencies. The five-input evidence gap is separate and persists even if the horizon issue is solved.

**Answer:** a separately versioned three-input model can produce mathematically valid, cutoff-safe **retrospective** W/D/L probabilities for 320 currently supported 90-minute cases. The implementation now has out-of-time descriptive evaluation, with mixed relative performance and unresolved calibration/generalization limits. It is not established as superior or inferior to the five-input model. That comparison requires independently approved historical Star Power/Clutch inputs, identical eligible cohorts and horizons, a genuinely unexposed confirmatory evaluation, and sufficient independent data to assess probabilistic performance and uncertainty.
