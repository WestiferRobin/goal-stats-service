# Historical evaluation protocol — pregame-regulation-v1

`POST /api/v1/evaluations/backtests` performs read-only evaluation, not prediction
persistence. Existing production bearer service authentication applies unchanged.
The Next.js proxy and Analytics placeholder are deliberately unchanged in this phase.

## Approved package and release status

The only HTTP-selectable package is `womens-world-cup-recorded-v1`: the nine approved
Women's World Cup editions, 1991–2023, with 348 records from revision
`1855e313ae8bcd0330426e62c8e4cf15ce45077c` of Mart Jürisoo's international results.
The source SHA-256 is
`de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0`.

**This package has no approved regulation outcome labels or observed historical
Star Power/Clutch evidence. Its historical publication-availability evidence is also
unverified. Consequently it publishes no accuracy, log loss, or Brier score.**
Recorded final scores include extra time and exclude shootout kicks. Neither a
non-draw nor a draw proves what the regulation score was. No tournament-stage or
winner heuristic substitutes for an approved regulation label.

`EvaluationPackage` is a server-owned approval boundary. It binds each approved
regulation score to the source record key, match date, source participant names,
source citation/hash, and explicit regulation definition. Observed special ratings
also require source/hash and an availability date strictly before match day.
Approval of new evidence requires a reviewed package version and dataset identifier;
callers cannot upload observations, labels, source files, or arbitrary model versions.
Synthetic packages are injected by tests only and respond with
`evidence_kind: synthetic`. There is no public synthetic dataset selector.

The dataset hash covers the ordered historical projection, including recorded
scores and source identities, excluding database-generated IDs. The package hash
covers the approved evidence registry and source identity. The manifest hash covers
both hashes, protocol/model versions, request, assumptions, rankings and case results.
Thus source, input, label, ranking or assumption changes alter the replay manifest.
Database IDs identify local records; source record keys identify matches across imports.
An incomplete/oversized/duplicate catalog fails closed instead of silently shrinking
this approved cohort.

## Modes and cutoffs

- `strict_historical`: no caller-supplied strengths. Cases need approved regulation
  labels, historical Star Power/Clutch evidence, and verified historical source
  availability. Missing evidence excludes the case.
- `retrospective_assumptions`: a nonblank `assumption_package_id` and explicit
  per-match/per-team Star Power/Clutch values (finite 0–100, including zero) are
  required. Missing participant assumptions exclude that case. They remain labeled
  hypothetical in both request manifest and per-case provenance. Assumptions never
  establish regulation outcomes and never become observed ratings.

Cutoff is the previous calendar day. The existing
`international-recorded-score-poisson-v1` rating calculator receives only results
on/before that cutoff, excluding the evaluated match, all same-day matches and future
matches. Its existing four-year fit and frozen pre-form baseline remain unchanged.
Only the pinned, checksum-verified source may be loaded, from the repository raw
source or production bootstrap source. No current stored rating cohort is consulted.
Failure to fit or missing per-team ratings is explicit. If earlier evidence gates
fail, `rating_reconstruction: not_attempted` avoids pretending a fit was attempted.

Historical match dates alone do not prove contemporaneous publication availability.
Retrospective mode records this limitation; strict mode requires reviewed evidence.
Experimental ratings are based on recorded-match scores including extra time and are
not calibrated regulation forecasts. Cutoff safety does not establish predictive
quality or historical deployment of this model.

FIFA rank uses the latest release **published strictly before match day**. Missing
releases, mappings or observations remain null with reasons; no current rank or older
observation is silently substituted. Ranking provenance is returned even for excluded
cases. Ranking is optional in the existing prediction contract.

## Prediction inputs and metrics

The unchanged `road-to-the-final-heuristic-v2` pure `predict_state` adapter receives:
minute zero; 0–0 goals; zero shots, cards, corners, saves, blocks, big chances and
modifiers; and a fixed 50%/50% possession convention. These values are pregame
conventions, not observed final statistics. Reconstructed strengths and dated ranks
are explicit. The existing preview input schema validates the values. No scenario or
prediction is inserted, and no database transaction stays open during calculation.

Class order is `[home_win, draw, away_win]`. Metrics use regulation labels only:

- Accuracy is a fraction in [0,1], using three-class argmax; exact ties select the
  first class in the declared order.
- Confusion matrix rows are actual classes and columns predicted classes.
- Each probability must be finite, numeric, nonnegative and at most one. Sums must
  be within 1e-9 of one; only this floating-point residual is normalized away.
- Log loss is mean negative natural log of the true-class probability, clipped
  below at 1e-15 solely for that logarithm.
- Brier score is the mean **sum** of all three squared probability errors, not
  divided by three: range [0,2]. No clipping is used for Brier or argmax.
- Invalid probabilities or incompatible prediction versions cannot produce metrics.
- Zero eligible cases return null for all metrics, including the confusion matrix.
  Exclusion reasons count cases, not missing fields; reasons may overlap.
- Calibration is not implemented: the approved evidence currently yields no sample.

## Bounded API and examples

Body limit: 32 KiB. `offset` is 0–347; `limit` is 1–16 (default 16). At most 16
historical cutoffs can be fitted per request, each using the existing bounded fitting
algorithm. At most 32 assumption entries are accepted, with unique match/team keys
belonging to the selected page. The catalog query caps at 349 to detect overflow.

```json
{"dataset_id":"womens-world-cup-recorded-v1","mode":"strict_historical","offset":0,"limit":1}
```

On the complete current catalog, the response includes `dataset_match_count: 348`,
`total_candidate_matches: 1`, `eligible_matches: 0`, `excluded_matches: 1`,
`status: unavailable`, null metrics and the case's actual source key and cutoff.
Its exclusions are `regulation_outcome_evidence_missing`,
`historical_star_power_clutch_evidence_missing` and
`historical_source_availability_unverified`. This is an unavailable result, not 0%
accuracy. All candidate cases remain discoverable by pagination.

The following is **synthetic request syntax**, not a genuine historical observation;
replace the key and IDs with those returned for the selected page:

```json
{
  "dataset_id":"womens-world-cup-recorded-v1",
  "mode":"retrospective_assumptions",
  "limit":1,
  "assumption_package_id":"explicit-user-experiment-v1",
  "assumptions":[
    {"match_key":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","team_id":1,"star_power":0,"clutch":25},
    {"match_key":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","team_id":2,"star_power":60,"clutch":40}
  ]
}
```

Unknown datasets/modes, extra fields, invalid bounds, duplicate assumptions and
assumptions outside the page are rejected. Errors follow existing safe Problem
Details handling; internal paths and exception messages are not returned.

Counts and metrics describe the selected page; `dataset_match_count` describes the
whole approved catalog. Traverse with a stable `dataset_hash` and `package_hash`;
restart if either changes. Do not average page averages unweighted. Combine scored
cases (or eligible-count-weighted losses/accuracy and summed confusion matrices).
For eventual expensive eligible cohorts, clients should start with `limit: 1`.

## Verification and next phase

Pure tests use independent known values for all metrics, exact ties and clipping.
Synthetic service tests use both controlled rating fixtures and the unchanged real
rating calculator plus unchanged prediction adapter. PostgreSQL/API tests use
ownership-verified disposable databases and verify read-only transaction settings,
ranking release boundaries, no persistence, auth, strict schemas and safe failures.

The prototype functions `backtest_matches`, `historical_backtest_matches`, and
`print_backtest_summary` in
[RoadToTheFinal/main.py](https://github.com/Estebansito1/RoadToTheFinal/blob/main/main.py)
were consulted only for separating labels from inputs and aggregating results.
Winner-only scoring, CSV defaults, terminal rendering and mutable prototype state
were not copied.

Prompt 4 can implement the Next.js proxy allowance, typed client, eligibility and
provenance display, explicit assumption entry, page handling and unavailable states.
Browser E2E must use isolated data. Real historical metrics remain blocked until
reviewed regulation labels and compatible historical input evidence exist; frontend
integration must not weaken those gates.
