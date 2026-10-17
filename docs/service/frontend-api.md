# Women's World Cup backend API

Base path: `/api/v1`. Generated OpenAPI: `/swagger/v1/swagger.json`; UI: `/swagger`.
This document describes backend contracts only. Frontend integration has not been certified.

The active API has **15 application operations**, two infrastructure operations and
three optional Swagger route rules. There is no parallel prototype API.

| Method | Path beneath `/api/v1` | Behavior |
|---|---|---|
| GET | `/catalog/teams` | Normalized teams, ordered by name then ID |
| GET | `/catalog/teams/{team_id}` | Team metadata; unknown ratings remain null |
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
`status` (maximum 10 characters, default empty). Preview returns the existing engine
report directly, including probabilities, scorelines, xG, momentum, confidence and
reasoning. It never creates scenarios or predictions. Calculations run after the
identity-validation transaction ends. Probabilities are fractions, while momentum
and confidence are percentages.

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

History is newest first by generation time then prediction ID, with limit 50 by
default, maximum 200, and nonnegative offset. Scenario lists can filter by `team_id`.
A dedicated pair-wide prediction history contract remains an optional extension;
this phase retains the approved per-scenario history and does not invent an alias.

## Historical insights

`GET /catalog/matches/insights?team1_id=1&team2_id=2&limit=50&offset=0`
validates two distinct existing IDs. The response includes `head_to_head`,
`team1_history`, `team2_history`, participant names/IDs, and pagination metadata.
Each list independently applies limit/offset and is ordered by match date then ID,
oldest first. Head-to-head matches either home/away orientation and retains original
orientation, competition, dates and score basis. No meetings returns an empty list.
These are historical result records, not invented observations or recent-form ratings.

## Hypothetical simulation

POST `/competitions/simulate` with `teams`, an ordered array of objects containing
`team_id`, the five required strength assumptions and optional `fifa_rank`.
Supply exactly 4, 8, 16 or 32 distinct IDs. `simulations` defaults to 1,000 and is
bounded to 1,000–2,000, preserving the reference HTTP budget.

Adjacent entries meet in the first knockout round. No group stages, qualification,
official brackets or historic ratings are inferred. The response preserves champion,
semifinal/final distributions and most-common-final output, marks
`kind: hypothetical_knockout`, and declares `probability_unit: percent`.
No simulation records are persisted. Results are stochastic; tests control and
restore random state without adding a production seed API.

## Errors and retired contracts

Validation returns safe Problem Details with 400; absent identities return 404;
integrity conflicts return 409 where documented; unexpected failures return 500.
Infrastructure routes remain `/health` and `/ready`.

Legacy `/teams`, stateless `/predictions`, `/snapshots`, `/history`, `/insights`,
`/backtests`, `/tournaments/simulate` and `/live/refresh` contracts are inactive.
Their supported replacements are listed above. Backtesting and live observations
are deferred pending defensible historical inputs and verified provider policies.
Their reusable calculation/parsing helpers remain; they are not activated by routes.
