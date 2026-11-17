# Women's World Cup backend API

Base path: `/api/v1`. Generated OpenAPI: `/swagger/v1/swagger.json`; UI: `/swagger`.
This document describes backend contracts only. Frontend integration has not been certified.

The active API has **16 application operations**, two infrastructure operations and
three optional Swagger route rules. There is no parallel prototype API.

| Method | Path beneath `/api/v1` | Behavior |
|---|---|---|
| GET | `/catalog/teams` | Normalized teams, ordered by name then ID |
| GET | `/catalog/teams/{team_id}` | Team metadata; unknown ratings remain null |
| GET | `/catalog/teams/{team_id}/summary` | Historical totals across all matching World Cup records |
| GET | `/catalog/competitions` | Historical competition editions |
| GET | `/catalog/matches` | Historical matches; team/competition/date filters |
| GET | `/catalog/matches/{match_id}` | Historical result and score basis |
| GET | `/catalog/matches/insights` | Head-to-head and both teams' histories |
| POST | `/scenarios` | Save explicit scenario state and rating assumptions |
| GET | `/scenarios` | List full saved scenarios |
| GET | `/scenarios/{scenario_id}` | Reopen a scenario |
| PATCH | `/scenarios/{scenario_id}` | Update supplied match-state fields |
| POST | `/scenarios/{scenario_id}/predictions` | Bodyless calculation and append |
| GET | `/scenarios/{scenario_id}/predictions` | Saved prediction history |
| GET | `/predictions/{prediction_id}` | Exact saved result and effective inputs |
| POST | `/predictions/preview` | Calculate without persistence |
| POST | `/competitions/simulate` | Hypothetical caller-ordered knockout bracket |

## Inputs and factual data

Historical catalog records come from the approved 1991–2023 source. The full import
contains 44 teams, nine editions, 348 matches and 1,081 goals. Startup does not seed.
Use returned integer IDs; names are display values, not lookup keys.

The source has no offense, defense, form, star-power or clutch ratings. Callers must
supply these five 0–100 assumptions for each prediction participant. Optional FIFA
rank is a positive integer. Catalog nulls never fall back to prototype values.
`prediction_ready: false` on a catalog team means catalog membership alone does not
provide the complete model inputs; it does not prohibit explicit-input predictions.

Scenario and preview requests use `team1_id`, `team2_id`, `match_minute`, and flattened
`team1_*` / `team2_*` fields. Required state includes goals, shots, shots_on_target,
big_chances, defender_blocks, goalkeeper_saves, corners, yellow_cards, red_cards and
possession. Possessions must total 100. Rating fields are offense, defense, form,
star_power and clutch; fifa_rank is optional. Modifier totals default to zero.
See generated schemas for numeric bounds and complete examples.

Preview accepts the same explicit state/rating fields, without scenario title or
match association. It additionally accepts `extra_minute` (0–30, default 0) and
`status` (maximum 10 characters, default empty). Preview returns the v2 engine
report directly, including probabilities, scorelines, xG, momentum, confidence and
reasoning. It never creates scenarios or predictions. Calculations run after the
identity-validation transaction ends. Probabilities are fractions, while momentum
and confidence are percentages.

## Prediction model and horizon

New previews and generated predictions use `road-to-the-final-heuristic-v2`.
Ratings and match statistics are user-provided hypothetical assumptions; historical
browsing does not automatically supply ratings. Predictions are calculated estimates,
not recorded historical match facts. The report's `reasoning` describes these limits.

| Supplied minute | V2 behavior |
|---|---|
| 0–89 | Predict additional goals through the nominal minute-90 horizon |
| 90 | Zero remaining modeled time; summarize the supplied current score |
| 91–120 | Outside the supported horizon; summarize the supplied current score |

At and beyond minute 90, remaining xG is exactly zero, W/D/L is deterministic from
the supplied score, and the only scoreline has probability one. The supplied minute
is retained. This does not confirm the real final whistle or reconstruct the score
at minute 90. Stoppage time, extra time, and shootouts are not forecast.

Preview `status` and `extra_minute` retain their accepted ranges. Status is uppercased
and echoed; neither field determines completion, a match phase, or a future horizon.
These preview metadata fields are not persisted in saved scenarios. Saving retains
the fixed saved-input defaults below, not a lossless copy of nondefault preview metadata.

V2 removes artificial time/xG floors and uses adaptive independent Poisson tails
with omitted joint mass bounded by `1e-12`. Default/legacy engine callers and
tournament simulation retain their existing behavior. This is a numerical correction,
not calibration or measured accuracy.

Confidence remains a percentage heuristic derived from the margin between the two
leading W/D/L probabilities. Advancement remains a fraction using hypothetical
clutch-weighted tiebreak shares for draws (equal shares when both clutch values are
zero). It is not an observed shootout result or a forecast of extra-time play.

Preview and generation preserve `effective_shots = max(shots, shots_on_target)`.
Only copied calculation inputs are normalized; the saved scenario remains unchanged.
Saved prediction input snapshots record those effective shots. No stricter validation
is introduced.

## Saved workflow

Create a scenario, retain its integer ID, then POST with **no body or query** to its
`/predictions` resource. Each successful generation creates a new prediction.
Creation and generation are two transactions: a generation failure leaves the
scenario available. Retain its ID, inspect the error, reopen it to check inputs,
and reload prediction history before retrying after an uncertain network failure.
Retries are not idempotent and may append another result.

Saved responses include `prediction_id`, `scenario_id`, timestamp, model version,
immutable `input_snapshot`, and `output`. Reads never recalculate. Scenario edits do
not change old predictions. Existing `scenario-v1` snapshots remain compatible:
extra minute is zero, status empty and modifiers represented by totals. This phase
does not add new persistent state fields or claim lossless legacy snapshot conversion.

New saved records have `model_version == output.model == "road-to-the-final-heuristic-v2"`.
Existing v1 records retain their original model identifier, inputs, and numerical
outputs. Reads and history do not execute either model. V1 and v2 can coexist in
the same history; no records are rewritten and no migration is required.

History is newest first by generation time then prediction ID, with limit 50 by
default, maximum 200, and nonnegative offset. Scenario lists can filter by `team_id`.
A dedicated pair-wide prediction history contract remains an optional extension;
this phase retains the approved per-scenario history and does not invent an alias.

### Frontend handoff — Nikita

The existing parsers accept both model identifiers with the same fields and units.
Frontend presentation has not been updated by this backend change. Label the fixed
90-minute horizon; distinguish minute 90–120 supplied-score summaries from forecasts
and avoid presenting their confidence as measured certainty about an actual result.
Explain heuristic confidence and hypothetical advancement. Align the Matches
shots-on-target submit check with backend normalization. Distinguish legacy v1
snapshots from corrected v2 outputs without rewriting their historical descriptions.

## Historical insights

`GET /catalog/matches/insights?team1_id=1&team2_id=2&limit=50&offset=0`
validates two distinct existing IDs. The response includes `head_to_head`,
`team1_history`, `team2_history`, participant names/IDs, and pagination metadata.
Each list independently applies limit/offset and is ordered by match date then ID,
oldest first. Head-to-head matches either home/away orientation and retains original
orientation, competition, dates and score basis. No meetings returns an empty list.
These are historical result records, not invented observations or recent-form ratings.

## Historical team summary

`GET /api/v1/catalog/teams/{team_id}/summary` reads existing database records without
changing them. These definitions are **accepted project behavior for the current
implementation scope**, as accepted by the project owner. This does not claim
Mehla’s personal sign-off or instructor/course approval. Existing catalog and
match-history response shapes are unchanged. Source-validation limits and unresolved
D02/D10 evidence remain in the [discrepancy ledger](../../data/verification/task2-historical-comparisons.md).

The required path `team_id` and optional query `competition_id` are positive integer
IDs, bounded to 2,147,483,647. Optional `date_from` and `date_to` must be valid calendar
dates in exact `YYYY-MM-DD` form. Both boundaries are inclusive; reversed ranges are
rejected. Unknown query fields, including `limit`, `offset`, and query-string
`team_id`, are rejected. Summary totals are never paginated.

Matches must involve the selected team and belong to competitions with
`name_key = "fifa women's world cup"` and `category = "women_senior_national"`.
Competition and date filters combine with this scope. A valid but nonexistent or
out-of-scope competition ID produces no matching records, not an unknown-team error.

Every response includes all of these fields:

| Field | Meaning/type |
|---|---|
| `team_id`, `name` | Requested team's integer identity and nonempty display name |
| `matches_played` | Nonnegative integer count of all matching stored matches |
| `wins`, `draws`, `losses` | Nonnegative integer result counts from the team's perspective |
| `goals_for`, `goals_against` | Nonnegative integer sums, correctly oriented for home/away matches |
| `goal_difference` | Signed integer: `goals_for - goals_against` |
| `tournament_appearances` | Nonnegative integer count of distinct World Cup editions represented after filtering |
| `filters` | Applied `competition_id`, `date_from`, and `date_to`; all three keys remain present, with null for omitted values |
| `score_basis` | `including_extra_time_no_shootout`, or null when no records match |
| `result_definition` | `recorded_final_score` |
| `coverage_status` | `available_records_only` or `no_matching_records` |

Wins/losses compare recorded final scores; equal scores count as draws, including
matches whose shootout winner is unavailable. Recorded scores already include
extra-time goals where applicable; shootout goals are excluded. Totals include all
matching rows, regardless of the match-history page being displayed. Rankings and
ratings are not inferred or fabricated.

The response enforces `wins + draws + losses == matches_played`,
`goal_difference == goals_for - goals_against`, and
`tournament_appearances <= matches_played`.

`available_records_only` describes matching imported records; it does not certify
complete historical coverage or independent verification of every match.
`no_matching_records` means the requested team exists but the stored selection is
empty. All statistics are then zero and `score_basis` is null. This does not prove
that the team never participated or that all historical records have been imported.

| Status | Meaning |
|---|---|
| 200 | Valid summary, including labeled empty results |
| 400 | Invalid IDs, dates, reversed ranges, or unsupported query parameters |
| 404 | Requested team does not exist |
| 500 | Unexpected database failure or any matching record with an unsupported score basis |

Unsupported or mixed score bases fail safely instead of silently dropping records
or returning misleading totals. Errors use the existing Problem Details responses;
database details and unsupported stored values are not exposed.

## Hypothetical simulation

POST `/competitions/simulate` with `teams`, an ordered array of objects containing
`team_id`, the five required strength assumptions and optional `fifa_rank`.
Supply exactly 4, 8, 16 or 32 distinct IDs. `simulations` defaults to 1,000 and is
bounded to 1,000–2,000, preserving the reference HTTP budget.

Adjacent entries meet in the first knockout round. No group stages, qualification,
official brackets or historic ratings are inferred. The response preserves champion,
semifinal/final distributions and most-common-final output, marks
`kind: hypothetical_knockout`, and declares `probability_unit: percent`.
No simulation records are persisted. Requests accept an optional integer `seed`
from 0 through 4,294,967,295. Omitted or null seeds generate a seed; the response
returns the actual `seed` used. The engine constructs a request-local random
number generator; it neither consumes nor restores global random state.
Reproduction requires the same ordered participants, assumptions, simulation count
and seed under the same implementation. Names are display values, not identity.
`results[].team_id`, `predicted_champion_id`, and
`most_common_final.team1_id` / `team2_id` identify participants even when names
are duplicated; `most_common_final` is nullable.

A sampled tied score is resolved with the conditional share
`team1.clutch / (team1.clutch + team2.clutch)`, or 0.5 when both are zero.
The overall advancement probability is win probability plus draw probability
times that share; it is not reused as the conditional draw probability.

**Task 11: DONE — Monte Carlo backend implementation and documentation complete.**
Existing engine tests cover bracket progression, seeded reproducibility, participant
identity and four independent Poisson comparisons (20,000 samples per case,
six-standard-error tolerance). Router tests repeat a seeded request and verify no
persisted changes; isolated simulation tests check concurrent requests, unchanged
global random state, seed boundaries and duplicate display names. These checks establish the implemented mathematical contract,
not predictive calibration. Tournament UI execution and live UI acceptance remain
separate frontend scope.

## Errors and retired contracts

Validation returns safe Problem Details with 400; absent identities return 404;
integrity conflicts return 409 where documented; unexpected failures return 500.
Infrastructure routes remain `/health` and `/ready`.

Legacy `/teams`, stateless `/predictions`, `/snapshots`, `/history`, `/insights`,
`/backtests`, `/tournaments/simulate` and `/live/refresh` contracts are inactive.
Their supported replacements are listed above. Backtesting and live observations
are deferred pending defensible historical inputs and verified provider policies.
Their reusable calculation/parsing helpers remain; they are not activated by routes.
