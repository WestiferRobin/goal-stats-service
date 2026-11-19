# Historical Star Power and Clutch research — Prompt 2

## A. Implementation summary

No defensible numeric historical Star Power or Clutch rating is currently available from the reviewed inputs. All 348 matches (696 team appearances) retain missing special ratings. This is a feasibility result for the evidence examined, not proof that further archives cannot supply useful data.

Two isolated, versioned aggregation interfaces are implemented: `star-role-rapm-aggregation-research-v1` and `clutch-regulation-residual-contrast-research-v1`. They validate structured evidence, reject incompatible/leaking inputs, return explicit missing reasons, and label any sufficiently supported result as a derived, unvalidated estimate. Synthetic evidence exists only in tests. No player model or baseline forecast was fitted; no accuracy experiment was performed. Production code does not import these modules.

`specification.json` freezes the candidate definitions before comparative experiments. Its canonical method hash is `4fc836ea673f096c88a0e66b3a4e237cfabc0bc0a303d9a8266754743a664fe1`. `manifest.json` pins the specification, source inventory and full feasibility matrix. Rebuild offline with:

```sh
PYTHONPATH=src .venv/bin/python scripts/evaluation/build_special_research.py
```

### Verified existing model contract

Source: `src/football/engine.py`, `src/schemas/scenario/base.py`, existing evaluation adapters and regression tests. The five input ratings are numeric 0–100. Base strength is exactly

`S = .30 Offense + .25 Defense + .20 Form + .15 StarPower + .10 Clutch + ranking_bonus`.

When rank is supplied, the bonus is `clip((25-rank)*.08,-2,2)`; otherwise zero. A star bad-game event contributes `-round(StarPower*.1,1)`; summed events are bounded to ±20. Live strength also incorporates possession (+3 above 55%, −3 below 45%), goals (+8 each), red cards (−12 each), and attack pressure. Attack pressure is `.5*max(shots_on_target,big_chances+defender_blocks+opponent_goalkeeper_saves)+2*shots_on_target+3*big_chances+6*goals`.

Expected goal means allocate `2.6*remaining_ratio` in proportion to `max(live_strength,1)`, then adjust for own/opponent red cards (−.22/+.18 times remaining ratio). The regulation v2 adapter uses `max((90-minute)/90,0)` and nonnegative means; legacy tournament behavior retains its remaining-time/mean floors. Independent Poisson score probabilities are summed for home/draw/away, dynamically truncated with joint omitted mass at most `5e-13`, then normalized. This remains a heuristic goal model, not a calibrated historical likelihood.

Advancement assigns the draw mass in proportion to `Clutch_i/(Clutch_home+Clutch_away)`, with one-half if both are zero. Monte Carlo samples goals and resolves a tied simulation using the same Clutch ratio; it does not model a real penalty shootout. Thus shootout win rate cannot substitute for Clutch. The regulation adapter reports `road-to-the-final-heuristic-v2`; legacy tournament behavior remains unchanged. Confidence is a bounded heuristic based on the gap between the two most likely outcomes, not validated empirical confidence. Existing deterministic regressions and probability invariants demonstrate implementation consistency, not separate construct validity. The 80-minute 1991 horizon remains a separate production incompatibility.

## B. Exact Prompt 2 files

All are new; no pre-existing repository file was edited:

- `src/research/__init__.py`
- `src/research/special_ratings.py`
- `src/research/feasibility.py`
- `scripts/evaluation/build_special_research.py`
- `tests/unit/research/test_special_ratings.py`
- `tests/unit/research/test_feasibility.py`
- `data/research/historical-special-ratings-v1/.gitattributes`
- `data/research/historical-special-ratings-v1/README.md`
- `data/research/historical-special-ratings-v1/specification.json`
- `data/research/historical-special-ratings-v1/sources.json`
- `data/research/historical-special-ratings-v1/coverage.json`
- `data/research/historical-special-ratings-v1/manifest.json`
- `data/research/historical-special-ratings-v1/preservation.json`

No frontend files were changed by Prompt 2. Existing Prompt 1 files are listed in section L, separately from this work.

## C. Star Power methodology

The chosen candidate measures the upper end of available squad player impact, balanced across four positions. It does not equate international goals, caps, popularity, or eventual awards with player quality.

Required upstream player metric: regularized adjusted plus-minus (RAPM) from the preceding 730 days. For 11-versus-11 regulation segments, with `m` minutes, `g` home-minus-away goals, and player indicators `X` (+1 home, −1 away), the frozen candidate objective is:

`min Σ (m/90)*(90*g/m - home/competition intercepts - Xβ)^2 + 20*Σβ²`.

Intercepts are unpenalized; red-card and extra-time segments are excluded. Teammate/opponent adjustment comes from the simultaneous player design, not from treating goals as individual contributions. The coefficient fitting stage is **specified but not implemented or trained**, because verified segment/identity coverage is absent. Complete on-pitch identities, substitutions, times, goals, competitions and prior-window membership are prerequisites. Team-specific substitutions often make coefficients weakly identifiable; goalkeeper and defender attribution is especially difficult. The ridge constant 20 is an unvalidated frozen candidate, not a fitted optimum.

The implemented aggregator requires a reconciled pre-match roster, publication-verified availability checked within seven days, and a reference ending no more than 30 days before the cutoff. Every available player requires at least 900 prior-window minutes and a finite impact estimate with lower/upper uncertainty bounds. The available squad must contain at least 11 players. Each role needs at least 30 eligible peers from at least five teams. Reference training cannot extend beyond its observation cutoff. Player IDs must be unique; roster/team/role mismatches fail explicitly.

For player impact `b`, calculate the midrank percentile `100*(#peer<b + .5*#peer=b)/N` within that position. Average the highest one goalkeeper and highest two defenders, midfielders and forwards separately, then average those four role scores with equal weights. Thus the output lies within 0–100. Recompute lower sensitivity bounds using each player's lower value against peers' upper values, and vice versa for upper bounds, including reselection of top players. These are input-interval sensitivity bounds, **not calibrated confidence intervals**. No missing player is assigned 50. A measured tied reference can mathematically yield 50, which is distinct from a missing-value default.

The full reference population, training hash, source revisions and cutoff belong to the evidence hash. Arbitrary caller-provided hashes alone do not certify the upstream model: independent review must reproduce coefficients from rights-cleared source segments. Publication and event time are separate: retrospective estimates can use earlier events only when the observation window is independently established, but this does not prove that the complete input chain was available historically. Outputs explicitly retain that limitation.

Alternatives considered: caps/age measure experience rather than impact; goals/assists favor attackers; eventual awards leak future information; contemporary expert assessments can add useful independent evidence but need dated scales, comparable raters and inter-rater uncertainty. On-ball action-value methods such as [VAEP](https://www.janvanhaaren.be/assets/papers/kdd-2019-vaep.pdf) are reproducible with rich events but do not automatically cover off-ball defense or goalkeeping. [Regression-based player ratings research](https://www.ntnu.no/ojs/index.php/nikt/article/view/5265) motivates the adjusted plus-minus candidate, but does not validate these thresholds or women's historical coverage.

Compatibility with the existing 15% weight is **unestablished**. Equal role weights, elite-player selection and percentile compression are hypotheses requiring separate calibration and construct validation. Nothing maps the candidate into production Star Power automatically.

## D. Clutch methodology

The chosen candidate estimates a narrow contrast: regulation outcome residuals in earlier knockout matches versus earlier group matches. It is not a general psychological trait or a shootout measure. Group matches can also involve pressure; this control is a reproducible context proxy, not a claim that group play is pressure-free.

Predeclared pressure stages are round of 16, quarterfinal, semifinal and final. Controls are group games. Exclude third-place matches, 80-minute 1991 records, extra-time goals and shootouts. The input requires a verified source establishing context before the observation match; retrospective archive stage labels alone are counted for feasibility but do not satisfy this gate. No historical context publication date is invented.

For each prior match, require an independently reconstructed pre-match forecast for that team's win/draw/loss over 90 minutes, using only Offense, Defense, Form and rank. Feature set and horizon are schema-enforced. Training must end by the forecast cutoff, strictly before that match; match/team identities must agree. The baseline model version must remain consistent within the sample, while fold-specific training hashes can differ. Existing recorded-final Poisson fits include some extra time and cannot silently serve as regulation-calibrated baselines. Existing five-input predictions with unknown Star/Clutch would be circular and are prohibited.

Let `y` equal 1 for a regulation win, .5 for a draw and 0 for a loss, and `q=p(win)+.5*p(draw)`. Residual `r=y-q`. Use only observations in `(cutoff−4383 days, cutoff]`, where the caller sets cutoff to the previous calendar day. Require at least six pressure and six group observations, at least two pressure editions, and a pressure observation within 1461 days.

`δ=mean(r_pressure)−mean(r_group)`; `n_eff=1/(1/n_pressure+1/n_group)`; `w=n_eff/(n_eff+12)`.

`Clutch=clip(50+50*w*δ,0,100)`.

The shrinkage reference is a zero residual contrast, not an imputed historical rating. Missing forecasts/context/sample evidence returns null with explicit reasons. With adequate measured evidence, a zero contrast may produce 50. Approximate bounds use `δ ± 1.96*sqrt(s²_pressure/n_pressure+s²_group/n_group)` before scaling. These do not account for clustered tournaments, baseline estimation error or model misspecification and are explicitly **not calibrated confidence intervals**; equal synthetic residuals can produce a zero-width interval without establishing certainty.

The aggregator does not manufacture forecasts or expand the approved pressure corpus. The thresholds, 12-year window and scale are frozen candidates requiring validation; none changes existing production thresholds or the 10% Clutch weight.

## E. Historical source inventory

`sources.json` contains 30 inspected/reused source and methodological reference records, with exact URLs, publisher, coverage, fields, revision/hash, timing, retrieval, rights, quality gaps and required transformations. Research metadata is retained; newly inspected PDFs and StatsBomb event data are not redistributed or imported into the historical evidence registry.

| Editions | Actual candidate sources | Evidential limits |
|---|---|---|
| 1991, 1995, 1999 | FIFA technical reports, two parts per edition, mirrored by the Society for American Soccer History; existing RSSSF edition archives | Reports are retrospective; no verified pre-match full player-impact/availability series. 1991 regulation lasts 80 minutes. |
| 2003, 2007, 2011, 2015 | FIFA technical reports via the same archive; existing RSSSF edition archives | Team/player and tournament information does not establish the preceding 730-day reference or historical availability. |
| 2019 | FIFA technical report, official squad announcement, RSSSF; StatsBomb competition metadata identifies 2019 WWC | Richer modern sources remain incomplete for worldwide club/national-team prior windows and match-day availability. |
| 2023 | FIFA squad PDF, official announcement, Football Australia media guide, RSSSF; StatsBomb competition metadata identifies 2023 WWC | Version timing and rights matter; none supplies a complete verified estimator input chain. |

The [SASH index](https://www.ussoccerhistory.org/resources-2/resources/) supplies actual FIFA-authored report links for the first eight editions. PDF download hashes are pinned in `sources.json`. OCR/text extraction is imperfect in older documents; no claim is made that every desired field or every team is present in each individual report part. Future extraction requires manual validation and an acceptable reuse basis.

The [2019 FIFA announcement](https://inside.fifa.com/tournaments/womens/womensworldcup/france2019/news/final-squad-lists-for-fifa-women-s-world-cup-france-2019tm-announced) is dated 27 May 2019. An announcement date does not authenticate later linked PDF bytes. The [current 2023 squad PDF](https://fdp.fifa.org/assetspublic/ce93/pdf/SquadLists-English.pdf) is stamped **20 August 2023, 12:21 UTC, Version 1**, whereas the [squad announcement](https://vod.fifa.com/tournaments/womens/womensworldcup/australia-new-zealand2023/news/fifa-womens-world-cup-2023-tm-squad-lists-officially-confirmed) is dated 11 July. Current caps/goals cannot be treated as the July version. The Australia guide is official but country-limited, and its June 2024 upload path does not prove pre-match 2023 availability.

[StatsBomb's repository](https://github.com/hudl/open-data) lists 2019/2023 WWC and selected women's club/European competitions, not a continuous 1991–2023 worldwide player archive. The [2023 release notice](https://blogarchive.statsbomb.com/news/statsbomb-release-free-2023-womens-world-cup-data/) is dated 23 August 2023. Earlier fixture events could support retrospective models after identity, cutoff and rights review; post-match lineups from the evaluated game cannot establish a pre-match squad. The pinned [user agreement](https://raw.githubusercontent.com/hudl/open-data/master/LICENSE.pdf), updated 8 September 2023, restricts commercial exploitation and third-party data redistribution and requires logo credit for published analysis. Public access is not blanket product-use permission. No event-derived analysis or product import is included here.

## F. Full 1991–2023 coverage matrix

“Sample-ready” only counts enough earlier retrospective archive results under the candidate sample thresholds. It does not establish context publication, forecasts, or estimator computability. A team-case is one team's appearance at one match cutoff; it is not a unique team.

| Edition | Matches | Teams | Star cases | Clutch cases | Both | Missing team-cases per rating | Sample-ready team-cases | Sample-ready both-team matches | O/D/F before → recovered |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1991 | 26 | 12 | 0 | 0 | 0 | 52 | 0 | 0 | 19 → 20 |
| 1995 | 26 | 12 | 0 | 0 | 0 | 52 | 0 | 0 | 19 → 26 |
| 1999 | 32 | 16 | 0 | 0 | 0 | 64 | 0 | 0 | 26 → 30 |
| 2003 | 32 | 16 | 0 | 0 | 0 | 64 | 3 | 0 | 32 → 32 |
| 2007 | 32 | 16 | 0 | 0 | 0 | 64 | 3 | 0 | 31 → 32 |
| 2011 | 32 | 16 | 0 | 0 | 0 | 64 | 8 | 0 | 29 → 32 |
| 2015 | 52 | 24 | 0 | 0 | 0 | 104 | 15 | 2 | 48 → 52 |
| 2019 | 52 | 24 | 0 | 0 | 0 | 104 | 20 | 2 | 52 → 52 |
| 2023 | 64 | 32 | 0 | 0 | 0 | 128 | 8 | 1 | 64 → 64 |
| Total | **348** | 44 unique overall | **0** | **0** | **0** | **696** | **57** | **5** | **320 → 340** |

Every edition has zero teams with a complete Star or Clutch evidence chain and zero uncertain numeric historical estimates (because there are no numeric estimates). Source limitations are listed per edition in `coverage.json`; all 348 match IDs/keys, both team identities, cutoffs, null estimates, missing reasons, context counts and evidence hashes are retained there. Historical numeric uncertainty is unknown, not zero.

## G. Research estimator results

Direct observations: existing reviewed regulation results and archived stages. The context pool comprises 314 matches (234 group, 80 qualifying knockout), represented from both teams' perspectives; per-case filtering uses only earlier days. Excluded from this pool are all 26 1991 matches and eight later third-place matches. This is an incomplete historical pressure corpus; other international competitions have not been silently added.

Derived historical numeric estimates: **0**. Explicit hypothetical assumptions: **0**. Missing: **696 Star and 696 Clutch team-cases**. Strict production eligibility remains unchanged. No accuracy, calibration, lift or ranking claim follows from the feasibility counts. Hashes record reconstruction inputs; they are not evidence of source truth or construct validity.

## H. Scientific limitations and frozen validation plan

At the unchanged pregame base-strength layer, adding `2k` to Star and subtracting `3k` from Clutch leaves `.15*Star+.10*Clutch` unchanged while both stay in range. Regulation outcome fit alone therefore cannot identify the two constructs separately. Star event penalties and Clutch advancement ratios introduce other behavior, but do not establish separate validity from historical regulation accuracy.

Before Prompt 3 comparisons, independently review the frozen definitions and upstream data. Use chronological training/validation with whole-edition separation, and reconstruct every prior forecast from training available before its own fixture. All 348 outcomes have already been available during dataset work: do not describe a retrospectively selected subset as a pristine untouched test. Reserve a genuinely untouched future cohort or independently held-out data for confirmation; explicitly label earlier rolling-origin comparisons exploratory.

Pre-register primary multiclass log loss and Brier score, calibration curves/slope, paired model comparisons, subgroup coverage, and tournament-cluster uncertainty. Compare an O/D/F/rank baseline, baseline plus Star, baseline plus Clutch, and both on the same complete-case cohort. Report the excluded cohort separately; never impute 50 to obtain coverage. Evaluate a separately predeclared missingness policy only as a different model. Keep advancement/shootout validation separate from regulation validation.

Measure Star correlations with Offense/Defense/Form and Clutch correlations with Form, including partial correlations conditional on opponent strength and sample size. Cross-fit any residualization/calibration within training folds. Examine collinearity, parameter recovery, player coefficient stability, independent expert/position targets, and whether adding each construct yields incremental held-out information. Prediction improvement alone is insufficient to name a latent psychological trait.

Test robustness to source availability, role populations, top-player selection, reference date, uncertainty bounds and pressure definitions. Treat each changed threshold/normalization as a new preregistered candidate version; do not optimize across the full 348 outcomes. Retain full reference populations, freeze training hashes, and report multiple-comparison burden. Percentile spacing has no intrinsic linear relationship to the engine's 15%/10% weights; calibration must be estimated only within training data and independently tested. Sparse, dependent tournament samples, survivorship into knockouts, regional club coverage and changing football eras make causal interpretations inappropriate.

## I. Prompt 1 compatibility

The builder calls the existing content-pinned original and recovery asset validators, preserving all 137 complete rating populations and their source-prefix hashes. Original manifest: `47c947db3f117a14761930da3c0dcfa3b68b50e94b6e12904b9bf7ddc75a0a28`. Recovery manifest: `45593e9139180f48ec931846d6316f62dfc975386c28c58167c0e737f42ce31b`. The merged source hash is retained in the feasibility artifact.

Prompt 1's 69 approved fixtures improve O/D/F availability by 20 matches, from 320 to 340. They do not supply player segments/availability, verified pressure context, regulation-specific goals and independent baseline forecasts as a complete special-rating input. Therefore they add **zero qualifying special observations or computable special-rating cases** in this version. No fixture is imported twice, no population is refitted or reduced to evaluated teams, and no recovery file is modified. The current stored final-score rating model must not be relabeled a 90-minute forecast model. Eight O/D/F gaps remain: match IDs 3, 5, 10, 11, 16, 17, 57 and 65.

## J. Test results

Focused research suite: **34 passed, 0 failed**. New research modules: **99.386503% combined statement/branch coverage** (244 statements, one missed; 82 branches, one partial). Ruff lint, formatting and strict Mypy checks pass (100 source files). `make certify`: **1,867 passed, 0 failed**, in 27 minutes 36 seconds; coverage gate and disposable-resource cleanup **PASS**. That run collected 33 research cases; the final focused run includes the additional edition/date check and final assertions. Its reported combined coverage was **95.052688%**, above the required 95%. Final per-file combined coverage is **95.570638%** (5351/5599), taking unchanged modules from full certification and replacing every research module with its final focused coverage. This avoids mixing coverage line mappings across the small research-only validation change. Full and focused test counts overlap and must not be added. Exact totals, calculation method and final research Python hashes are recorded in `preservation.json`. Interface/inventory checks cover strict historical cutoffs, provenance, missing/invalid evidence, team/player identity, duplicate fixtures, normalization, uncertainty, samples, version/hash reconstruction, all nine editions and absence of production research imports. Synthetic fixtures remain in tests only. Full backend certification includes existing Backtesting and Monte Carlo regressions. Frontend checks are not required because Prompt 2 changes no frontend contract or file.

## K. Database preservation

Read-only canonical before/after counts and complete SHA256 fingerprints are recorded in `preservation.json` and match exactly: matches 348; competitions 9; teams 44; ranking releases 96; ranking observations 16,525; FIFA team mappings 44; rating runs 1; team ratings 44; scenarios 0; predictions 0. Certification provisions its own disposable test services; those writes are isolated from the canonical database. No canonical migrations or data mutations are requested or performed.

## L. Git state

Both repositories remain on `member/wes-v2`. Service HEAD: `396eedbb0107d87c81d466cb860d07c13b1f3334`. App HEAD: `799740f8ec7807d3b6798845879d5506e44d93ae`. No commits, pushes, branch switches, merges, rebases, resets or stashes were performed. Working trees intentionally retain the prior Prompt 1 work and the new Prompt 2 files.

Pre-existing service tracked modifications: `.gitattributes`, `src/schemas/evaluation/request.py`, `src/schemas/evaluation/response.py`, `src/services/evaluation.py`, `tests/integration/routers/test_evaluation_full.py`, `tests/unit/schemas/contract_fingerprints.json`. Pre-existing new service files: `src/football/results_recovery.py`, `src/services/evaluation_recovery.py`, `scripts/evaluation/build_recovery.py`, `tests/unit/services/test_evaluation_recovery.py`, and the existing `data/evaluation/international-results-recovery-v1/` package and sources.

Pre-existing app modifications: `src/features/analytics/domain/backtesting.ts`, its `.test.ts`, `src/features/analytics/components/backtesting-panel.tsx`, its `.test.tsx`, and `tests/e2e/backtesting.normalized.spec.ts`. Byte-for-byte comparison against the start-of-Prompt-2 inventory confirms preservation of all 319 pre-existing service files and 162 app files (tracked and nonignored untracked). The inventory digests and repository HEADs are recorded in `preservation.json`.

## M. Requirements before Prompt 3 model comparison

1. Rights-cleared, dated player rosters and availability plus complete prior-window segments, stable identities, and role reference populations. Independently reproduce and assess the player-impact fit before using its aggregate.
2. Broader reviewed historical pressure/control results where available, explicit regulation horizons, and verified pre-match context evidence. Resolve 1991's 80-minute mismatch separately without changing the current engine in this task.
3. Independent pre-match 90-minute O/D/F/rank forecasts for every prior Clutch observation, with training hashes and a noncircular validation procedure.
4. Independent review and preregistration of construct targets, thresholds, normalization, uncertainty and splits; a genuinely untouched confirmatory cohort; no full-cohort tuning.
5. Explicit, separately validated treatment of the existing 15% and 10% weights and advancement behavior. Resolve remaining O/D/F/source-publication gaps; missing evidence must continue to exclude unsupported cases.

**Answer:** reproducible aggregation interfaces and explicit candidate measurements can be constructed, but the examined sources do not yet support complete defensible pre-match Star Power or Clutch ratings for any of the 348 cases. The role-balanced RAPM aggregate and opponent-adjusted regulation-residual contrast are ready for independent methodological/data-feasibility review. Neither is ready for historical accuracy comparison or production use until its evidence prerequisites and independent validation are satisfied. Clutch has a small existing result-context foothold; Star requires substantially more player data, especially for 1991–1999.
