# Frontend API: historical catalog, scenarios and saved predictions

Base URL for local development: `http://127.0.0.1:5100`.
Interactive documentation: [Swagger](http://127.0.0.1:5100/swagger).
Generated specification: `/swagger/v1/swagger.json`.

`127.0.0.1` means **your own computer**, not Wes's machine or a shared hosted service.
From the backend repository, run `make setup`, then `make run`. For Docker Flask,
stop host Flask with Ctrl-C first, then run `make deploy`. `make stop` stops this
project's Docker services while preserving PostgreSQL data. See [development](development.md).

A fresh setup imports the bundled prototype catalog, **not** the downloaded historical
catalog. Follow the [historical import procedure](football.md#historical-import-operations)
once to load the pinned 2023 dataset; it requires no frontend CSV handling or database
credentials. An empty historical API array can mean the historical import has not run.

Start with your section:

- [Esteban — Teams, Matches and Scenarios](#esteban--teams-matches-and-scenarios)
- [Mehla — Saved Predictions](#mehla--saved-predictions)
- [Nikita — Home](#nikita--home)
- [Frontend proxy integration](#frontend-proxy-integration)

Backend HTTP and database integration are certified; **React screens have not been
certified**. The current frontend proxy needs the changes listed below before it
can forward these new routes. JSON uses `snake_case`, integer IDs, and UTC ISO
timestamps. Lists are arrays, not `{items: ...}` envelopes.


## Esteban — Teams, Matches and Scenarios

### Choose the right catalog

**Historical catalog** (`/api/v1/catalog/*`): verified 2023 FIFA Women's World Cup
identities and results, read from PostgreSQL `teams`, `competitions`, and `matches`.
The selected dataset has 32 teams, one competition, and 64 matches. Requests never
read CSV files. Ratings and rankings that are unavailable remain JSON `null`.

**Prediction catalog** (`GET /api/v1/teams`): existing model-ready prototype teams
from PostgreSQL `football_teams`. Continue passing the names from this endpoint to
`POST /api/v1/predictions` as `team1` and `team2`.

Historical team IDs are not accepted by the stateless prediction endpoint. Each
historical team currently has `prediction_ready: false`, even if a prototype record
has the same name or attributed ratings are later added to the historical record.
Do not automatically map the two catalogs by name or ID. Do not display missing
ratings as zero. Compare historical teams by requesting two team details separately.
Scenario and saved Prediction APIs are documented below. Existing legacy snapshot
endpoints remain available unchanged.

### Endpoints

All endpoints below use **GET**, require no body, and return `application/json`.
Lists are plain JSON arrays, with `[]` when empty; detail endpoints return one
object. IDs are positive PostgreSQL integers (1–2147483647). Obtain IDs from list
responses; example IDs are illustrative and may differ across database imports.

| URL path | Query parameters | Successful response | Order |
| --- | --- | --- | --- |
| `/api/v1/catalog/teams` | None | Array of Team objects | Name, then team ID |
| `/api/v1/catalog/teams/{team_id}` | None | Team object | — |
| `/api/v1/catalog/competitions` | None | Array of Competition objects | Name, edition label, then competition ID |
| `/api/v1/catalog/matches` | Listed below | Array of Match objects | Match date ascending, then match ID |
| `/api/v1/catalog/matches/{match_id}` | None | Match object | — |

Team and competition lists return the complete small catalogs. Only the match list
is paginated. All five endpoints read PostgreSQL and do not write data.

#### Match list filters and pagination

| Parameter | Type / default | Meaning |
| --- | --- | --- |
| `team_id` | Positive integer, optional | Team participates as either home **or** away |
| `competition_id` | Positive integer, optional | Competition ID |
| `date_from` | `YYYY-MM-DD`, optional | Inclusive earliest date |
| `date_to` | `YYYY-MM-DD`, optional | Inclusive latest date |
| `limit` | Integer, default `50`, range `1–200` | Maximum rows on this page |
| `offset` | Integer, default `0`, range `0–9223372036854775807` | Rows to skip after filtering |

Filters combine with AND. A well-formed but nonexistent filter ID returns `[]`.
Invalid calendar dates, timestamps, reversed date ranges, unknown match filters,
malformed IDs and invalid pagination values return 400. Use one value per parameter.
For the full 64-match dataset, request `?limit=200`, or request the default page and
then `?offset=50`. There is no total-count envelope. Continue increasing offset by
limit until a page contains fewer than limit rows (or is empty).

#### Team object

```json
{
  "team_id": 1,
  "name": "New Zealand",
  "category": "women_senior_national",
  "offense": null,
  "defense": null,
  "form": null,
  "star_power": null,
  "clutch": null,
  "fifa_rank": null,
  "ranking_date": null,
  "prediction_ready": false
}
```

`team_id` is an integer; `name` and `category` are strings. The five ratings are
numbers or null; `fifa_rank` is an integer or null. `ranking_date` is an ISO date
string or null. `prediction_ready` is a boolean, currently always false.
The team list wraps these objects in an array: `[{...}, {...}]`.

#### Competition object

```json
{
  "competition_id": 1,
  "name": "FIFA Women's World Cup",
  "edition_label": "2023",
  "category": "women_senior_national"
}
```

`competition_id` is an integer; the other three fields are strings.
The competitions response is an array of these objects.

#### Match object

```json
{
  "match_id": 1,
  "match_date": "2023-07-20",
  "competition_id": 1,
  "competition_name": "FIFA Women's World Cup",
  "edition_label": "2023",
  "home_team_id": 1,
  "home_team_name": "New Zealand",
  "away_team_id": 2,
  "away_team_name": "Norway",
  "home_score": 1,
  "away_score": 0,
  "score_basis": "including_extra_time_no_shootout",
  "neutral": false,
  "city": "Auckland",
  "country": "New Zealand"
}
```

IDs and scores are integers. Date is `YYYY-MM-DD`. Names, edition label and score
basis are strings. `neutral` is boolean or null; `city` and `country` are strings
or null when unavailable. The score basis means scores include extra time when
played but exclude penalty shootout goals; a tied score does not identify the
shootout winner. Home/away describe source participation, not necessarily venue
advantage. The match list contains exactly the same fields as match detail.
Importer provenance and internal keys are not exposed.

### Errors

Successful reads return 200. Missing team/match details return 404. Invalid IDs
and match query parameters return 400. Errors use `application/problem+json`:

```json
{
  "type": "about:blank",
  "title": "Not Found",
  "status": 404,
  "detail": "The requested resource was not found."
}
```

For 400, `title` is `Bad Request` and `detail` is
`The request could not be understood.` Unexpected failures return 500 with a
generic detail, without SQL errors, credentials or stack traces.

### Copyable examples

```bash
curl -sS 'http://127.0.0.1:5100/api/v1/catalog/teams'
curl -sS 'http://127.0.0.1:5100/api/v1/catalog/teams/1'
curl -sS 'http://127.0.0.1:5100/api/v1/catalog/competitions'
curl -sS 'http://127.0.0.1:5100/api/v1/catalog/matches?limit=200'
curl -sS 'http://127.0.0.1:5100/api/v1/catalog/matches/1'
curl -sS 'http://127.0.0.1:5100/api/v1/catalog/matches?team_id=1&competition_id=1&date_from=2023-07-20&date_to=2023-08-20&limit=20&offset=0'
# The existing prediction workflow uses prototype names:
curl -sS 'http://127.0.0.1:5100/api/v1/teams'
curl -sS -X POST 'http://127.0.0.1:5100/api/v1/predictions' \
  -H 'Content-Type: application/json' \
  -d '{"team1":"Spain","team2":"England","minute":0}'
```

### Implementation and verification notes

The existing Flask football router/service/schema modules implement this API.
SQLAlchemy uses the shared transaction/session infrastructure and bound parameters;
match reads join two team aliases and the competition on their foreign keys in one
SELECT. Detail lookups use primary keys. Existing constraints prevent orphaned
references and duplicate source match identities. No migrations or prediction
algorithms change for this API.

Automated tests use owned disposable PostgreSQL schemas. Routine fixtures contain
three teams and three matches; a synthetic importer fixture checks 32/64 counts
and page boundaries. Real-dataset acceptance is separately verified against the
persistent development database using read-only API/SQL comparisons.

Codex AI assisted with this implementation, tests and documentation under the
supplied Prompt 1 requirements. Team review and explanation of the work remain
part of the project submission process.

Validation on October 10, 2026 (America/Los_Angeles): `make test` passed **500 tests**
in 28.26 seconds, including 47 new catalog cases and existing football regressions.
Ruff lint/format and strict mypy (68 source files) passed. Host Flask started with
`make run`; `/health`, `/ready`, Swagger and all five new routes returned 200.
Every one of the 32 real team details and 64 real match details matched independent
SQL projections; the competition list, filters and pagination also matched.
Existing prediction generation, team/history/snapshot reads, insights and backtests
passed runtime checks. Snapshot writes were tested only in disposable databases.
Full-record digests of all nine existing application/migration tables remained
identical before and after startup and runtime checks. Alembic stayed at
`e3a71c92b406`; `TODO.md` and Makefile checksums were unchanged.


### Saved scenarios

A historical Match records a real completed game. A Scenario stores a user's
hypothetical or manually entered game state. Linking a scenario to a historical
match does not change that match or automatically copy its final score.

All scenario data lives in PostgreSQL `scenarios`, including each submitted state
field and both rating snapshots. Team names are joined from the catalog on reads.
The historical match is represented by `match_id`; use catalog match detail to
retrieve its facts. Team IDs, match association, title, creation time and rating
snapshots are immutable through this API. To choose different teams or ratings,
create another scenario.

#### Exact endpoints

| Method | URL | Result |
| --- | --- | --- |
| POST | `/api/v1/scenarios` | 201, full saved Scenario object, `Location` header pointing to its GET URL |
| GET | `/api/v1/scenarios/{scenario_id}` | 200, full Scenario object; 404 if missing |
| GET | `/api/v1/scenarios` | 200, array of full Scenario objects; `[]` if empty |
| PATCH | `/api/v1/scenarios/{scenario_id}` | 200, full updated Scenario object; 404 if missing |

List parameters: `limit` defaults to 50 (1–200); `offset` defaults to 0
(0–9223372036854775807); optional `team_id` matches either side. List order is
creation time descending, then scenario ID descending. Invalid parameters return
400; a valid filter ID without matches returns `[]`. IDs are 1–2147483647.
There is no DELETE endpoint.

To reopen: list scenarios, keep the selected `scenario_id`, then GET its URL.
A browser refresh or backend restart does not lose the saved state.

#### Creation fields and validation

POST requires `Content-Type: application/json` and a JSON object. Use JSON numbers,
not numeric strings or booleans. Unknown fields are rejected. The same constraints
apply when PATCH supplies a state field.

| Fields | Required on POST? | Constraint / meaning |
| --- | --- | --- |
| `team1_id`, `team2_id` | Yes | Existing normalized team IDs; must differ |
| `match_id` | No; defaults to null | Existing historical match with these two participants, in either order |
| `title` | No; defaults to null | Optional label, 1–120 characters |
| `match_minute` | Yes | Integer 0–120 |
| `team1_goals`, `team2_goals` | Yes | Integers 0–1000 |
| `team1_possession`, `team2_possession` | Yes | Finite numbers 0–100; sum must be within 0.01 of 100 |
| Both teams' `shots`, `shots_on_target`, `big_chances`, `defender_blocks`, `goalkeeper_saves`, `corners`, `yellow_cards` | Yes | Integers 0–1000; prefix each with `team1_` or `team2_` |
| `team1_red_cards`, `team2_red_cards` | Yes | Integers 0–11 |
| `team1_modifier_total`, `team2_modifier_total` | No; defaults to 0 | Finite numbers −3000 through 3000 |
| Both teams' `offense`, `defense`, `form`, `star_power`, `clutch` | Yes | Explicit finite rating snapshots 0–100; prefix with `team1_` or `team2_` |
| `team1_fifa_rank`, `team2_fifa_rank` | No; defaults to null | Positive integers up to 2147483647 |

Statistic and minute bounds match the existing prediction request contract.
Modifier totals represent the sum of caller-selected modifiers, not a change to the
engine's calculation. The ±3000 bound matches the existing maximum of 30 modifiers
at ±100 each; the engine's existing event-score cap remains unchanged. Individual
modifier explanations are not stored by this contract. No missing statistics are
silently filled in. Shots are stored exactly as submitted; the existing engine
adapter's shots/on-target normalization remains a prediction-time concern.

#### Prediction readiness and rating provenance

Every accepted scenario has explicit, validated rating snapshots and therefore
returns `prediction_ready: true`. This means **input completeness**, not verified
rating accuracy. Use the saved-prediction endpoint below to generate a result. A historical
team can remain `prediction_ready: false` in the catalog while an explicitly supplied
scenario snapshot is complete. Historical team ratings and rankings remain untouched.

The caller must deliberately supply suitable model inputs. Neither matching names
nor existing prototype ratings cause an automatic copy. Missing/null required
ratings are rejected with 400; there is no incomplete-draft scenario mode in this
contract. The examples below contain clearly labeled **synthetic demonstration
ratings**, not factual assessments of historical teams.

Saved predictions now copy the full effective inputs used at generation time, so
scenario PATCH cannot reinterpret earlier results. `POST /api/v1/predictions` still
accepts its original prototype-name request; it does not accept scenario IDs.

#### POST example

Replace the team IDs with IDs from the historical catalog and supply your own
explicit match state and model inputs. Save the following as `scenario.json`:

```json
{
  "title": "Documentation example \u2014 synthetic inputs",
  "team1_id": 1,
  "team2_id": 2,
  "match_id": null,
  "match_minute": 65,
  "team1_goals": 0,
  "team1_shots": 0,
  "team1_shots_on_target": 0,
  "team1_big_chances": 0,
  "team1_defender_blocks": 0,
  "team1_goalkeeper_saves": 0,
  "team1_corners": 0,
  "team1_yellow_cards": 0,
  "team1_red_cards": 0,
  "team1_possession": 50,
  "team1_offense": 70,
  "team1_defense": 70,
  "team1_form": 70,
  "team1_star_power": 70,
  "team1_clutch": 70,
  "team1_fifa_rank": null,
  "team1_modifier_total": 0,
  "team2_goals": 0,
  "team2_shots": 0,
  "team2_shots_on_target": 0,
  "team2_big_chances": 0,
  "team2_defender_blocks": 0,
  "team2_goalkeeper_saves": 0,
  "team2_corners": 0,
  "team2_yellow_cards": 0,
  "team2_red_cards": 0,
  "team2_possession": 50,
  "team2_offense": 70,
  "team2_defense": 70,
  "team2_form": 70,
  "team2_star_power": 70,
  "team2_clutch": 70,
  "team2_fifa_rank": null,
  "team2_modifier_total": 0
}
```

```bash
curl -i -X POST 'http://127.0.0.1:5100/api/v1/scenarios' \
  -H 'Content-Type: application/json' --data-binary @scenario.json
```

#### GET / POST / PATCH response example

The persisted representation is the same for all three operations. The ID,
creation timestamp and team names below are illustrative. Names are resolved from
the submitted IDs. All state/rating fields below are persisted; `prediction_ready`
is derived from the enforced complete-input contract.

```json
{
  "title": "Documentation example \u2014 synthetic inputs",
  "team1_id": 1,
  "team2_id": 2,
  "match_id": null,
  "match_minute": 65,
  "team1_goals": 0,
  "team1_shots": 0,
  "team1_shots_on_target": 0,
  "team1_big_chances": 0,
  "team1_defender_blocks": 0,
  "team1_goalkeeper_saves": 0,
  "team1_corners": 0,
  "team1_yellow_cards": 0,
  "team1_red_cards": 0,
  "team1_possession": 50,
  "team1_offense": 70,
  "team1_defense": 70,
  "team1_form": 70,
  "team1_star_power": 70,
  "team1_clutch": 70,
  "team1_fifa_rank": null,
  "team1_modifier_total": 0,
  "team2_goals": 0,
  "team2_shots": 0,
  "team2_shots_on_target": 0,
  "team2_big_chances": 0,
  "team2_defender_blocks": 0,
  "team2_goalkeeper_saves": 0,
  "team2_corners": 0,
  "team2_yellow_cards": 0,
  "team2_red_cards": 0,
  "team2_possession": 50,
  "team2_offense": 70,
  "team2_defense": 70,
  "team2_form": 70,
  "team2_star_power": 70,
  "team2_clutch": 70,
  "team2_fifa_rank": null,
  "team2_modifier_total": 0,
  "scenario_id": 1,
  "created_at": "2026-10-10T19:00:00Z",
  "team1_name": "Example Team A",
  "team2_name": "Example Team B",
  "prediction_ready": true
}
```

```bash
curl -sS 'http://127.0.0.1:5100/api/v1/scenarios?limit=20&offset=0'
curl -sS 'http://127.0.0.1:5100/api/v1/scenarios/1'
curl -sS -X PATCH 'http://127.0.0.1:5100/api/v1/scenarios/1' \
  -H 'Content-Type: application/json' \
  -d '{"match_minute":70,"team1_goals":1,"team1_possession":60,"team2_possession":40}'
```

PATCH accepts only `match_minute` and the statistics/modifier totals listed above.
Omitted fields remain unchanged; explicit null, an empty object, and attempts to
change identity/rating fields return 400. The merged state must pass validation:
when changing possession, normally send both percentages together. Each update
locks the row and commits atomically. Sequential writes to the same field use the
last committed value; there is no optimistic version/ETag contract yet.

#### Scenario errors

All errors use the existing `application/problem+json` object (`type`, `title`,
`status`, `detail`). Malformed bodies, missing required fields, invalid ranges,
same-team selection, and mismatched historical participants return 400. Missing
teams, matches or scenarios return 404. A database integrity conflict returns 409
with generic detail `Conflict`; unexpected database failures return 500 with
`An unexpected error occurred.` No partial scenario/update is committed on failure.
Detailed field requirements and examples are in Swagger; error messages do not
include rejected values, SQL or credentials.

#### Prompt 2 validation evidence

Validated October 10, 2026 (America/Los_Angeles). `make test` passed **598 tests in
51.45 seconds**, including 97 new scenario cases and one additional standalone
upgrade-parity case. Ruff lint/format and strict mypy (73 source files) passed.
Tests cover creation/reopening, optional match relationships in both orientations,
strict validation, missing ratings/statistics, pagination, immutable snapshots,
PATCH, injected commit failures/rollback, database constraints, additive migration,
SQL parity, OpenAPI examples and existing API regressions. Provider tests ran only
against ownership-verified disposable PostgreSQL.

The supported `make run` workflow applied `f6b82d14c903` and started host Flask.
PostgreSQL and Redis were healthy; `/health`, `/ready`, Swagger and scenario routes
were exercised through actual HTTP. A deliberately retained test record,
**scenario ID 1**, is titled `Prompt 2 runtime test: explicit prototype snapshots,
not historical ratings`. Its explicit inputs came from the existing Spain/England
prototype records solely for acceptance testing, supplied in the POST body. No
catalog ratings were populated or automatically mapped by the API. It links to
historical match 64, but its manually entered match state remains scenario data.

POST returned 201; GET, PATCH and subsequent GET returned 200. Every persisted
column matched independent SQL readback. After a safe Flask restart through
`make run`, the same ID, timestamp, state and rating snapshots were retrieved.
All eight preexisting application-table full-record digests remained unchanged;
only the new scenario table and Alembic revision were added/advanced. Existing
catalog (32 teams, one competition, 64 matches), prototype prediction, history,
snapshot reads and backtests passed runtime checks. No existing records were
reset/deleted. Prior migrations, `TODO.md`, Makefile and prediction algorithms
were unchanged; no commit or push was performed.


## Mehla — Saved Predictions

Use this workflow to generate from a saved scenario and reopen the result later.
Each generation inserts a new PostgreSQL `predictions` row referencing `scenarios`.
Recalculating is intentionally **not idempotent**: a retry creates another record.
It never overwrites a previous prediction or changes the scenario.

### Exact endpoints

| Method | URL | Request | Success |
| --- | --- | --- | --- |
| POST | `/api/v1/scenarios/{scenario_id}/predictions` | No body or query parameters | 201, saved prediction object; `Location` header points to its GET URL |
| GET | `/api/v1/scenarios/{scenario_id}/predictions` | Optional `limit`, `offset` | 200, array of saved prediction objects |
| GET | `/api/v1/predictions/{prediction_id}` | No body | 200, one saved prediction object |

IDs are integers 1–2147483647. History defaults to `limit=50`, `offset=0`; limit is
1–200 and offset is 0–9223372036854775807. History is ordered by `generated_at`
descending, then `prediction_id` descending. An existing scenario with no results
returns `[]`; a missing scenario returns 404. A missing prediction also returns 404.

The original **`POST /api/v1/predictions` remains stateless**: its existing body,
response shape and prototype-team selection are unchanged. It does not save a new
normalized Prediction row. Legacy `/snapshots` functionality is also unchanged.

### Inputs, readiness and reproducibility

Generation uses the saved scenario's explicit rating snapshots and statistics.
It does not read prototype ratings, replace missing ratings, use historical final
scores as live state, or make external provider requests. Generation revalidates
all scenario inputs; a missing or invalid rating returns 400 with its field name,
for example:

```json
{
  "type": "about:blank",
  "title": "Bad Request",
  "status": 400,
  "detail": "Scenario is not prediction-ready. Missing or invalid inputs: team1_offense."
}
```

The current Scenario creation API/database already rejects incomplete rating
snapshots. Generation's check is an additional safeguard for invalid/legacy inputs.
Historical catalog ratings may still be null: complete explicit scenario snapshots
are what the generation endpoint requires.

Each prediction stores an **immutable effective input snapshot** in JSONB. It
contains the scenario ID, creation time, title, team IDs/names, optional match ID,
all submitted statistics and rating snapshots, plus `adapter_version: "scenario-v1"`,
`extra_minute: 0` and `status: ""`. The current scenario contract has no separate
extra-time/status controls; these are the engine's existing explicit adapter
defaults. Optional FIFA rankings remain null when absent; unused FIFA points/date
retain the engine constructor defaults (null/empty string).

As in the existing prediction adapter, effective `shots` is the larger of submitted
shots and shots on target. This normalized value is stored in the snapshot without
changing the scenario. Modifier totals are passed as one aggregate modifier per
nonzero side, labeled `Saved scenario modifier total`; the engine keeps its original
cap. The snapshot contains the raw aggregate, not just its capped contribution.

One joined SELECT captures a consistent scenario/team-name view. Its transaction
ends before computation begins. The engine calculates from that captured view;
a short second transaction saves the validated result. If PATCH occurs during
calculation, this prediction still represents the captured pre-PATCH inputs. The
next generation captures the updated state. No long-held database lock is needed
throughout computation.

GET reconstructs the report from saved columns, details and input snapshot. It
never recalculates or joins current scenario/team values. Team renames, rating
changes and scenario PATCH therefore cannot alter an earlier saved response.
There are no prediction update/delete routes. Reproducing numerical results requires
the recorded model and adapter versions; the engine implementation remains unchanged.

### Saved response fields

| Field | Meaning |
| --- | --- |
| `prediction_id` | Stable integer ID for reopening this result |
| `scenario_id` | Parent scenario ID; many predictions may share it |
| `generated_at` | Timezone-aware generation/persistence timestamp |
| `model_version` | Existing engine identifier, currently `road-to-the-final-heuristic-v1` |
| `input_snapshot` | Immutable effective inputs described above |
| `output` | Existing canonical prediction report, saved rather than recalculated |

`output` contains `team1`, `team2`, `minute`, `status`, `probabilities`, `advancement`,
`expected_goals_remaining`, `momentum_percent`, `most_likely_score`, `top_scorelines`,
`confidence`, `reasoning`, and `model`.

Win/draw/loss, advancement and scoreline probabilities are fractions (0–1).
Confidence and momentum are percentages (0–100). Win/draw/loss must sum to 1 within
absolute tolerance **1e-9**, enforced before saving and by PostgreSQL. Numeric
outputs must be finite. Expected remaining goals are nonnegative and most-likely
scores are nonnegative integers. Current engine reports provide both; database
columns allow null for future unavailable values, but this engine version never
omits them. No unsupported competitiveness or other output is fabricated.

PostgreSQL stores the core probabilities, expected goals, most-likely scores,
model version, IDs and timestamp in explicit columns. JSONB `details` holds the
remaining variable report fields (advancement, momentum, scorelines, confidence,
reasoning); JSONB `input_snapshot` holds inputs. Core results are not duplicated
inside `details`.

### Copyable workflow

Create a complete scenario using the POST example above, then substitute the
returned scenario ID below. POST generation has **no body** (even `{}` is rejected).

```bash
curl -i -X POST 'http://127.0.0.1:5100/api/v1/scenarios/2/predictions'
curl -sS 'http://127.0.0.1:5100/api/v1/predictions/1'
curl -sS 'http://127.0.0.1:5100/api/v1/scenarios/2/predictions?limit=20&offset=0'
# Change only the scenario, then append another prediction:
curl -sS -X PATCH 'http://127.0.0.1:5100/api/v1/scenarios/2' \
  -H 'Content-Type: application/json' -d '{"match_minute":70,"team1_goals":1}'
curl -i -X POST 'http://127.0.0.1:5100/api/v1/scenarios/2/predictions'
```

Example saved response from the explicitly labeled local acceptance-test scenario
(prototype test inputs, not asserted historical ratings):

```json
{
  "generated_at": "2026-10-11T00:36:39.972937Z",
  "input_snapshot": {
    "adapter_version": "scenario-v1",
    "created_at": "2026-10-11T00:36:39.955086Z",
    "extra_minute": 0,
    "match_id": 64,
    "match_minute": 0,
    "prediction_ready": true,
    "scenario_id": 2,
    "status": "",
    "team1_big_chances": 0,
    "team1_clutch": 92.0,
    "team1_corners": 0,
    "team1_defender_blocks": 0,
    "team1_defense": 91.0,
    "team1_fifa_rank": 1,
    "team1_form": 94.0,
    "team1_goalkeeper_saves": 0,
    "team1_goals": 0,
    "team1_id": 9,
    "team1_modifier_total": 0.0,
    "team1_name": "Spain",
    "team1_offense": 92.0,
    "team1_possession": 50.0,
    "team1_red_cards": 0,
    "team1_shots": 0,
    "team1_shots_on_target": 0,
    "team1_star_power": 93.0,
    "team1_yellow_cards": 0,
    "team2_big_chances": 0,
    "team2_clutch": 91.0,
    "team2_corners": 0,
    "team2_defender_blocks": 0,
    "team2_defense": 91.0,
    "team2_fifa_rank": 2,
    "team2_form": 93.0,
    "team2_goalkeeper_saves": 0,
    "team2_goals": 0,
    "team2_id": 13,
    "team2_modifier_total": 0.0,
    "team2_name": "England",
    "team2_offense": 91.0,
    "team2_possession": 50.0,
    "team2_red_cards": 0,
    "team2_shots": 0,
    "team2_shots_on_target": 0,
    "team2_star_power": 92.0,
    "team2_yellow_cards": 0,
    "title": "Prompt 3 runtime test: explicit prototype snapshots, not historical ratings"
  },
  "model_version": "road-to-the-final-heuristic-v1",
  "output": {
    "advancement": {
      "team1": 0.5034159036642268,
      "team2": 0.49658409633577316
    },
    "confidence": {
      "label": "Low",
      "percent": 0.6737103005351117
    },
    "expected_goals_remaining": {
      "team1": 1.3057512925750225,
      "team2": 1.2942487074249773
    },
    "minute": 0,
    "model": "road-to-the-final-heuristic-v1",
    "momentum_percent": {
      "team1": 50.0,
      "team2": 50.0
    },
    "most_likely_score": [
      1,
      1
    ],
    "probabilities": {
      "draw": 0.26390886112362144,
      "team1": 0.37074041064032975,
      "team2": 0.36535072823604886
    },
    "reasoning": [
      "No major live events yet. The prediction is based on team ratings and the Poisson model."
    ],
    "status": "",
    "team1": "Spain",
    "team2": "England",
    "top_scorelines": [
      {
        "probability": 0.12551992484807034,
        "team1_goals": 1,
        "team2_goals": 1
      },
      {
        "probability": 0.09698284736772378,
        "team1_goals": 1,
        "team2_goals": 0
      },
      {
        "probability": 0.0961285089755012,
        "team1_goals": 0,
        "team2_goals": 1
      },
      {
        "probability": 0.0819489020571438,
        "team1_goals": 2,
        "team2_goals": 1
      },
      {
        "probability": 0.08122700024534767,
        "team1_goals": 1,
        "team2_goals": 2
      }
    ]
  },
  "prediction_id": 1,
  "scenario_id": 2
}
```

History returns a plain JSON array containing these **same complete objects**,
newest first; there is no separate summary/envelope. For a scenario with no saved
predictions, the exact history response is:

```json
[]
```

### Frontend handoff

Esteban can navigate from a selected scenario's ID to its prediction-history URL.
The generate action sends a bodyless POST and uses the returned `prediction_id` or
`Location` header to open the saved result. Mehla can render `output.probabilities`,
`output.expected_goals_remaining`, `output.most_likely_score`,
`output.top_scorelines`, `output.confidence`, and `output.reasoning` using the
existing stateless report shape. Show `input_snapshot` when explaining the state
used for an older result; do not substitute the scenario's latest values.
React integration has not been changed or tested in this prompt.

### Errors and atomicity

Errors use the existing problem-JSON contract. Malformed IDs/pagination, supplied
POST bodies/query overrides and invalid scenario inputs return 400. Missing
resources return 404. A foreign-key conflict (for example, an external concurrent
scenario deletion before insert) returns 409. Engine failures, invalid engine
outputs and unexpected database failures return a generic 500. Failed computation
or writes leave no partial prediction. SQL internals, rejected values, credentials
and stack traces are not returned. Earlier predictions remain unchanged.

### Prompt 3 validation evidence

Validated October 10, 2026 (America/Los_Angeles). Final `make test` passed **651 tests
in 67.81 seconds**, including 52 new saved-prediction cases and one additional
standalone SQL upgrade-parity case. Ruff lint/format and strict mypy (79 source
files) passed. The suite exercised direct engine-output parity, generation outside
an open DB transaction, input validation, engine/invalid-output failures, rollback,
probability/database constraints, multiple results, immutable A/B inputs/outputs,
concurrent scenario edits during calculation, migration preservation, SQL parity,
OpenAPI and previous API regressions. Tests used owned disposable PostgreSQL.

The existing `make run` workflow applied additive migration `a7c93e25d104`, then
started host Flask. PostgreSQL/Redis, health, readiness and Swagger were healthy.
A clearly labeled new **scenario 2** used explicitly supplied Spain/England prototype
snapshots solely as test inputs; historical catalog ratings were not changed.
Bodyless generation created **prediction 1** from minute 0. After PATCH changed
scenario 2 to minute 70 and a 1–0 score, generation created **prediction 2**.
Both were retrieved unchanged through detail/history APIs and matched independent
SQL readback, including every core output column, JSON details and input snapshot.
Prediction 2 recorded effective shots of 4 while the scenario's submitted shots
remained 0, demonstrating normalization without scenario mutation.

After a safe Flask restart through `make run`, both predictions and their original
snapshots/outputs were retrieved unchanged. All preexisting records across nine
application tables retained their full-record digests, including Prompt 2's
scenario 1. Only the explicitly created test scenario/predictions were added;
scenario 2 alone was patched. The catalog remains 32 teams, one competition and
64 matches. Legacy stateless prediction, team/history/snapshot reads and backtests
passed runtime checks. Prior migrations, prediction algorithms, `TODO.md`, Makefile
and the legacy seed were unchanged. No commit, push, volume deletion or unrelated
Docker project operation was performed. React integration remains unverified.

## Nikita — Home

Home may remain static for Phase 1. There is no required new Home endpoint and no
cross-scenario "latest prediction" endpoint. An optional summary can read
`GET /api/v1/scenarios?limit=1` (most recently **created**, not updated or predicted),
then `GET /api/v1/scenarios/{scenario_id}/predictions?limit=1`. This displays only that
scenario's latest saved result. Use the response objects documented above; both calls
return arrays and write nothing. Handle `[]`, 400, 404 and service failures. This is not
a global recent-prediction feed. If the UI already knows a prediction ID, use
`GET /api/v1/predictions/{prediction_id}` directly. No new APIs are needed for static Home.

## Frontend proxy integration

Read-only inspection of `goal-stats-app` on 2026-10-10 found an explicit allowlist in
`src/app/api/football/[...path]/route.ts`. Its current allowlist covers only the legacy
football endpoints; **catalog/scenario/saved-prediction requests currently return 404**.
The frontend repository was not changed. The frontend integration owner needs to:

1. Add the following exact allowlist entries (validate dynamic IDs as positive integers).

   | Proxy suffix after `/api/football/` | Methods | Backend suffix after `/api/v1/` |
   | --- | --- | --- |
   | `catalog/teams` | GET | Same suffix |
   | `catalog/teams/{team_id}` | GET | Same suffix |
   | `catalog/competitions` | GET | Same suffix |
   | `catalog/matches` | GET | Same suffix |
   | `catalog/matches/{match_id}` | GET | Same suffix |
   | `scenarios` | GET, POST | Same suffix |
   | `scenarios/{scenario_id}` | GET, PATCH | Same suffix |
   | `scenarios/{scenario_id}/predictions` | GET, POST | Same suffix |
   | `predictions/{prediction_id}` | GET | Same suffix |

2. Export PATCH from the route; permit PATCH in the method types in both that route
   and `src/lib/api/client.ts`. Parse JSON for scenario POST/PATCH. Preserve the
   existing origin, content-type, object and size checks for those writes, applying
   the origin check to PATCH too.
3. Special-case scenario prediction POST as **bodyless**: the current proxy requires
   JSON for every POST, but the backend rejects even `{}` on this endpoint. Forward
   `body: undefined`, do not call `JSON.parse` on an empty body, and retain the write
   origin check. Preserve legacy prediction POST's JSON contract.
4. Forward query strings unchanged. Rewrite the 201 `Location` headers for scenarios
   and saved predictions to their `/api/football/...` equivalents (currently only
   legacy snapshot Locations are rewritten).
5. Update error wording for missing scenarios/predictions, preserve safe backend
   400/404/409 statuses, and map unavailable/timeout cases deliberately. Existing
   errors mention only teams/snapshots and map some HTTP failures to 502. Do not
   retry prediction POST blindly: every successful call appends a new result.
6. Test the proxy and connect the screens against these documented contracts.

Set **server-only** `FOOTBALL_API_BASE_URL=http://127.0.0.1:5100` in the frontend's
local configuration when Next.js runs on the host. Use the origin only, without
`/api/v1`; the proxy appends that prefix. `SERVICE_API_BASE_URL` is a separate Home
configuration and does not configure the football proxy. A containerized frontend
needs an origin reachable from its container; its own loopback is not the backend.

Browser requests should target same-origin `/api/football/...`; the Next.js server
calls Flask. Flask does not advertise cross-origin browser access, and no CORS change
is needed for this server-side arrangement. Do not put database URLs, passwords or
provider keys in `NEXT_PUBLIC_*` variables or browser code. The frontend needs only
the backend HTTP origin; PostgreSQL remains behind Flask.

## Final backend certification — 2026-10-10

See [the acceptance report](backend-certification.md) for the seven-task matrix,
actual scenario/prediction IDs, host/Docker/restart results, test results, course
alignment, known limits and Discord handoff. Earlier Prompt 1–3 evidence above is
historical; this report describes the final combined state.
