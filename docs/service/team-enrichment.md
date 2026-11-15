# Teams enrichment

Enrichment is separate from `make seed`. It never updates `teams`, `matches`,
`competitions`, scenarios, users or saved predictions. Five new tables retain
official ranking releases/observations, FIFA identity mappings, rating runs and
per-team snapshots. Catalog reads project enrichment without copying it into
prediction inputs. Star Power and Clutch remain unchanged everywhere in the
backend.

## Reproduce locally

Use the existing Python 3.12 virtual environment. Apply the reviewed additive
Alembic migration with the repository's normal target verification first.
Acquisition requires network access; replay/import uses only the saved package
and the committed results CSV. Choose a fresh acquisition directory:

```sh
PYTHONPATH=src .venv/bin/python -B -m football.enrichment acquire \
  --directory .host-sessions/fifa-rankings-YYYYMMDD
PYTHONPATH=src .venv/bin/python -B -m football.enrichment import \
  --directory .host-sessions/fifa-rankings-YYYYMMDD \
  --target local --expect-host 127.0.0.1 \
  --expect-database goal_stats_service_local --report .host-sessions/dry-run.json
```

The default import is a PostgreSQL read-only transaction. Add `--apply` to the
same command after reviewing its report. All releases, mappings and the cohort
commit atomically. An advisory transaction lock serializes CLI writers. Identical
imports insert nothing; changed publication dates, response bytes, mappings or
stored observations fail rather than overwrite. No migrations run inside import.
Cloud imports additionally require the existing verified TLS/production target
authorization. Import error exceptions cause transaction rollback.

Keep acquisition packages for replay. `manifest.json` records response URLs,
SHA-256 checksums, row counts and retrieval time. The index HTML binds opaque FIFA
schedule IDs to explicit publication dates. Do not parse dates from schedule IDs.
The current interface exposes all rows in one response; any continuation token
or hash causes rejection rather than partial import. HTTP acquisition is bounded
and uses four workers. A failed acquisition can be retried with a fresh directory.

The latest dated official release is selected for all catalog teams. Positive
rank/status-zero observations are ranked; other statuses and missing teams are
unranked, without carrying forward an older rank. Raw observations retain source
status, names, IDs and original values. PostgreSQL numeric retains published
points; display values are JSON numbers. The latest eligible rating run is chosen
once per response, and every team carries the same run/cutoff identity. Team
profile ratings remain explicitly experimental.

Source permissions: the FIFA website/API is not an unrestricted redistribution
license. Retain attribution and establish permission for the intended deployment
under https://inside.fifa.com/terms-of-service before public/commercial release.
Downloaded packages are ignored local artifacts, not committed public datasets.

## Rating specification: international-recorded-score-poisson-v1

Input: existing approved results.csv, revision
`1855e313ae8bcd0330426e62c8e4cf15ce45077c`, SHA-256
`de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0`.
All international matches in the file are eligible for this separate calculation;
the approved nine World Cup manifests/imports are unchanged. The cutoff defaults
to the source's latest date, 2026-06-10, and can be explicitly reduced.

For matches in (cutoff - 1461 days, cutoff], weight each by
`2 ** (-age_days / 730)`. Fit independent Poisson recorded goals with:

```
log(home_mean) = intercept + attack[home] + concede[away] + home_advantage
log(away_mean) = intercept + attack[away] + concede[home]
```

Home advantage is omitted at neutral venues. Maximize weighted log likelihood
minus `4 * sum(coefficient ** 2)` for attack, concede and home coefficients;
the intercept is unpenalized. Block Newton updates use fixed damping 0.5 and a
maximum absolute step 0.25, stopping below 1e-7 or after 400 iterations. No random
initialization, future results, FIFA rankings or scenario values are involved.

Offense is the midrank percentile of attack. Defense is the midrank percentile
of negative concede. Eligibility: at least eight matches in the window and a
latest match within 730 days. Reference population: every eligible national team
in the source, including opponents outside the 44-team UI catalog.

Form is descriptive recent performance against frozen expectations. Fit the
same model at cutoff - 365 days, before every form observation. For matches in
the following year, compute `(goal_difference - expected_difference) /
sqrt(home_mean + away_mean)`, with opposite signs for the opponents. Weight by
half-life 180 days, sum and divide by `5 + sum(weights)` to shrink sparse results.
Only matches between teams represented in the frozen model qualify. Require at
least three form matches plus attack/defense eligibility. Convert to midrank
percentiles among eligible form teams. Missing evidence returns null, never 50.
Ratings are rounded to two decimals; tied reference values receive equal ranks.

These are scores per recorded match, INCLUDING extra-time goals and EXCLUDING
shootout goals, not per-90 xG or official ratings. Coverage, tournament selection,
source omissions and sparse opponents limit interpretation. There are no
validated uncertainty intervals. All thresholds/hyperparameters are explicit
versioned design choices, not empirically proven universal constants.

## Validation and publication limits

Two disjoint 180-day holdouts end at cutoff - 365 days and cutoff. Each model is
fitted only through the preceding boundary. Report mean joint Poisson negative
log likelihood against a training-only global-goal-mean baseline. An additional
diagnostic applies pre-holdout form as opposing log-rate adjustments. No parameter
is chosen from holdout results. The diagnostic is NOT used by the prediction
engine or to replace Offense/Defense.

At the initial cutoff, opponent adjustment improves both held-out scores, but
adding Form worsens both. Therefore Form is displayed as descriptive recent
performance, not as proven incremental predictive information. Existing
prediction formulas, five explicit strength inputs and Monte Carlo semantics are
unchanged. Numerical range/repeatability are not claims of predictive calibration.

Reports include per-team counts, latest match, missing-data reasons and holdout
losses. The run ID hashes model version, cutoff, source checksum, ratings and
validation report. Refresh creates a new immutable cohort. If an import fails,
the old cohort remains intact. Cutoff/source dates are shown on Teams, so June
ratings are not represented as November evidence. Public deployment still needs
source permission and an explicit decision to publish experimental metrics.

Rollback must retain the new tables and data. A rollback application build must
remain compatible with the new Alembic head: an unmodified old build checks the
old head and will fail readiness. The migration downgrade locks and refuses
populated enrichment tables. Never delete history or prediction records to roll
back enrichment.
