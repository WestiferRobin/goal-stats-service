# Goal Stats backend certification — October 10, 2026

Migration-history note: dated revision-chain evidence below predates consolidation
into `a7c93e25d104_init_models.py`. The head ID and schema are preserved; see
[the current migration workflow](development.md#schema-changes).

Certification date uses America/Los_Angeles; recorded API timestamps use UTC.
Scope: Wes's October 12 backend milestone, Prompts 1–4. This certifies backend
HTTP/database integration, not connected React screens or a hosted deployment.

## A. Final verdict

**READY FOR TEAM HANDOFF**

Wes's backend responsibilities for the October 12 milestone are ready for team
handoff. The frontend team must extend its existing proxy and connect/test the
screens. These are explicitly documented frontend integration steps, not a claim
that the current frontend already consumes the new endpoints.

## B. Seven-task completion matrix

| Task | Result | Evidence |
| --- | --- | --- |
| 1. Setup | PASS | Existing environment and clean source export both passed `make setup`; infra, host, Docker, stop, help and isolated tests exercised |
| 2. Real data | PASS | 32 teams, one competition, 64 matches; every stored match compared with the pinned CSV; repeat import inserted zero rows |
| 3. Persistence | PASS | Current migration head; keys, constraints, indexes, saved scenarios and immutable prediction snapshots verified; complete restart retained data |
| 4. Frontend APIs | PASS | Catalog, scenarios and saved predictions work over HTTP; proxy changes documented; static Home needs no new API |
| 5. Complete backend flow | PASS | Scenario 3 → predictions 3 and 4 → saved retrieval → host/Docker/restart retrieval |
| 6. Engine compatibility | PASS | Existing stateless API, prototype catalog, history, insights and backtests pass; engine unchanged |
| 7. Documentation | PASS | Responsibility-based API reference, exact proxy requirements, request/response examples, errors, persistence and limits |

## C. Git branch / status

Branch remained `member/wes`. Existing modified/untracked work from the previous
prompts was preserved. Prompt 4 changed only `docs/service/frontend-api.md` and
added this report. Nothing staged, committed or pushed. Full baseline file hashes
were recorded before certification; existing migrations, algorithms, TODO and all
other preexisting files remained unchanged during Prompt 4.

## D. Database schema certification

Actual migration chain:

```text
b7f42e9c1a60 → d94f81ab2301 → e3a71c92b406 → f6b82d14c903 → a7c93e25d104 (head)
```

Live PostgreSQL reported the same head. Migration tests cover upgrades and model
parity. New forward migrations add tables; they do not drop/reset legacy data.
Downgrade definitions were not invoked against development data.

| Table | Primary key | Foreign keys | CHECK constraints | Inspected indexes* |
| --- | --- | --- | ---: | ---: |
| teams | team_id | — | 11 | 1 |
| competitions | competition_id | — | 4 | 1 |
| matches | match_id | competition_id; home_team_id; away_team_id | 12 | 5 |
| scenarios | scenario_id | team1_id; team2_id; optional match_id | 37 | 4 |
| predictions | prediction_id | scenario_id | 11 | 2 |

*SQLAlchemy inspector counts include unique-constraint backing indexes and exclude
primary-key indexes. Foreign keys use RESTRICT. Checks cover nonblank identities,
distinct teams, valid scores/state/rating ranges, possession totals, finite results,
probability ranges/sum and JSONB object types. Historical source/key uniqueness
prevents duplicate imports. Scenario history uses scenario/time/ID indexes; no
uniqueness constraint prevents multiple predictions for one scenario.

Legacy items, actions, football_teams, football_history and football_snapshots
remain intact. Scenarios reference normalized teams; their optional historical
match must contain the same participants. Rating snapshots are explicit inputs.
Predictions reference the scenario and preserve effective inputs independently.
Append-only behavior is enforced by the API surface, not a database trigger that
prevents a privileged database operator from editing rows.

## E. Historical data verification

Source: Mart Jürisoo's women's international results, pinned revision
`1855e313ae8bcd0330426e62c8e4cf15ce45077c`.
Full CSV SHA-256:
`de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0`.
See [manifest](../../data/womens-world-cup/womens-world-cup-2023.json) and
[historical catalog documentation](historical-catalog.md).

Independently selected the original CSV row using each stored `source_row` and
compared dates, both team identities, scores, city, country, neutrality, source
labels, revision, URL, checksum, score basis and competition edition. All 64 passed.
Competition is FIFA Women's World Cup, edition 2023; dates July 20–August 20.
Scores include extra time and exclude shootout goals.

Dry-run and actual authorized repeat import read 11,650 source rows, selected 64,
reported 64 unchanged, zero inserts, zero conflicts and zero rejected records.
No unrelated data was acquired. All historical ratings/ranks remain NULL. Prototype
inputs remain separately labeled; they are not historical observations.

## F. Teams / Matches API results

All 32 team details and all 64 match details matched independent SQL joins.
Competition listing, default 50-row page plus offset page, team participation,
competition and inclusive date filters passed. Invalid ID/date/offset produced
400; missing detail produced 404. Lists are JSON arrays; no CSV access occurs in
request handlers. Existing `GET /api/v1/teams` still returns 32 prototype teams.

Exact catalog routes: GET `/api/v1/catalog/teams`,
`/api/v1/catalog/teams/{team_id}`, `/api/v1/catalog/competitions`,
`/api/v1/catalog/matches`, `/api/v1/catalog/matches/{match_id}`.

## G. Scenario API results

POST `/api/v1/scenarios` returned 201 and scenario ID **3**. GET collection/detail
and PATCH returned 200. Scenario 3 explicitly selects Spain and England and links
to historical match **64**. Its title labels acceptance inputs as prototype
snapshots, not historical ratings. The caller deliberately selected these existing
prototype test values and submitted them; the API never inferred ratings by name.

Initial minute/score: 0 / 0–0. PATCH saved minute 70, team1 goals 1, shots on target 4.
Raw team1 shots remained 0. SQL readback matched every stored scenario field.
Empty/identity-changing/out-of-range/null/boolean/inconsistent-possession PATCH
requests returned 400 and left the row unchanged. Missing scenario returned 404.
Optional-null historical match creation and relationship validation are also covered
by isolated integration tests.

## H. Prediction API results

POST `/api/v1/scenarios/3/predictions` returned 201 twice. GET
`/api/v1/predictions/3` and `/api/v1/predictions/4` returned stored results, and GET
`/api/v1/scenarios/3/predictions` returned `[B, A]`. Pagination returned A alone.

These are exact projections of actual responses, not complete response objects:

```json
[
  {
    "prediction_id": 3,
    "scenario_id": 3,
    "generated_at": "2026-10-11T00:43:29.676685Z",
    "model_version": "road-to-the-final-heuristic-v1",
    "output": {
      "probabilities": {"team1": 0.37074041064032975, "draw": 0.26390886112362144, "team2": 0.36535072823604886},
      "most_likely_score": [1, 1]
    }
  },
  {
    "prediction_id": 4,
    "scenario_id": 3,
    "generated_at": "2026-10-11T00:43:29.714589Z",
    "model_version": "road-to-the-final-heuristic-v1",
    "output": {
      "probabilities": {"team1": 0.8305061813391272, "draw": 0.1490566247899871, "team2": 0.020437193870885682},
      "most_likely_score": [1, 0]
    }
  }
]
```

A retains minute 0 / 0–0; B retains minute 70 / 1–0. B's effective shots are 4,
consistent with the unchanged engine adapter; the scenario still stores raw shots 0.
Both complete responses, snapshots and output columns matched SQL and remained
byte-for-value equivalent after retrieval and restarts. Probabilities sum to 1.
Body `{}` and unknown query parameters on generation return 400; absent resources
return 404. Generation is a bodyless POST and each success appends one record.

Full local acceptance receipts are in ignored `.host-sessions/prompt4/runtime.json`;
the portable response contract and a complete example are in [frontend-api.md](frontend-api.md).

## I. Full backend workflow

Verified dataset → relational SQL → catalog JSON → selected teams → scenario INSERT
→ GET → state UPDATE → engine → prediction INSERT → saved GET/history → restart →
same saved records. No frontend CSV parsing or direct PostgreSQL access is required.
Only one clearly labeled acceptance scenario and two predictions were added.

## J. Host runtime verification

`make setup`, `make infra` and `make run` succeeded. Host Flask listened on
127.0.0.1:5100 with Docker providers. Health/readiness/Swagger and the complete
catalog/scenario/prediction checks passed. Host Flask was stopped before Docker mode.

Clean-start setup was also exercised in a temporary export of the current tracked
and untracked source, initially without `.env.local` or `.venv`. `make setup`
created both, installed pinned Python 3.12 dependencies, checked them, built images
and pulled providers without starting services. This validates the pending source
state's fresh setup, not an upstream clone containing still-uncommitted work.

## K. Docker runtime verification

`make deploy` succeeded with Flask, PostgreSQL and Redis in Docker. The same scenario
and predictions remained accessible at 127.0.0.1:5100. Docker and host were never
serving simultaneously. Both used the same database and PostgreSQL volume.

## L. Persistence after restart

Executed `make stop` followed by `make deploy`. Rechecked complete saved responses,
SQL parity, historical source comparison and previous-record hashes. All passed.
`goalstats-service-local_postgres-data` retained identical inspect metadata and
mount identity. No volume deletion or database reset occurred.

## M. Prediction engine regression

Engine calculations were not edited. Stateless POST `/api/v1/predictions` works;
prototype teams count 32, history count 16, insights head-to-head query and backtests
(13 evaluated matches) pass. Existing snapshots remain usable. Saved generation
uses the same report engine with explicit complete inputs. Tests cover engine
parity, no implicit prototype lookup, validation/rollback, concurrent updates and
immutable saved responses. No historical prediction accuracy claim is made.

## N. Frontend proxy compatibility

Read-only inspected `goal-stats-app`'s football catch-all route and server HTTP client.
Current allowlist rejects the new paths; PATCH is not exported/typed; all POSTs
currently require JSON, conflicting with bodyless saved-generation POST. Location
rewriting handles only snapshots, and error messages/status mappings need updating.

[Exact frontend changes](frontend-api.md#frontend-proxy-integration) are documented.
Use server-only `FOOTBALL_API_BASE_URL=http://127.0.0.1:5100` on a host-running frontend;
the proxy appends `/api/v1`. `SERVICE_API_BASE_URL` configures a separate Home client.
Browser calls remain same-origin. Flask does not advertise permissive CORS, and
server-to-server forwarding does not need it. No backend secrets belong in browser
configuration. Frontend repository unchanged; React/proxy execution not certified.

## O. OpenAPI / Swagger

`/swagger` returns the local Swagger UI and `/swagger/v1/swagger.json` returns
OpenAPI 3.1. Runtime route inspection exactly matched **25 paths / 36 operations**,
with no collisions or advertised nonexistent routes. All existing routes remain.
Scenario and saved-prediction responses validated against their Pydantic response
models; integration tests check schemas, examples, status codes and error contracts.
Saved generation correctly advertises no request body. Errors use problem+json.

## P. Automated test results

Final `make test`: **651 passed**. Ruff lint passed, **174 files** passed formatting,
and strict mypy passed **79 source files**. Includes unit/integration, migrations,
catalog, scenarios, prediction persistence and existing football regressions.

Owned disposable project: `goal-stats-service-test-003a6b0011c4`; PostgreSQL and Redis
use ephemeral storage and ownership verification. Development database record hashes
were unchanged except the earlier intentional acceptance records. Scoped cleanup
removed the test containers/network without deleting persistent volumes. Final test
log: `/tmp/goalstats-prompt4-tests.log` (local evidence, not required frontend setup).

## Q. Database integrity

Final records: teams 32, competitions 1, matches 64, scenarios 3, predictions 4;
football_teams 32, football_history 16, football_snapshots 0, items 0, actions 0.
All foreign keys checked by anti-join: zero orphans. Zero duplicate historical source
identities. Full-record hashes of all preexisting rows match the starting baseline.
No accidental deletion; predictions 1/2 and scenarios 1/2 remain intact.

## R. CS 514 rubric alignment

Demonstrated normalized identities/relationships, primary/foreign keys, SELECT,
INSERT, scenario UPDATE, relational joins, constraints, transactions, SQLAlchemy
programming, Alembic migrations, persistent application records and REST integration.
Snapshots deliberately preserve historical inputs without conflating them with
current team values. PostgreSQL is supported by the course's DBMS choices.

Read Product Decisions, Draft Database Product Document, course final-v2 rubric,
and Links/Reference from Drive. Searches did not locate separate files named
Draft Database Product Overview & Instructions or Team Tasks: 10/2/2026–10/12/2026.
The user's explicit seven-task assignment governed this certification. Product
Decisions describes Project as the overview/instructions page. No Drive edits made.

Recommended exact technical-document corrections:

- Replace the opening with: “Goal Stats uses PostgreSQL to persist teams,
  competitions, historical matches, user-created scenarios, and generated predictions.
  Flask REST APIs provide the application workflow; verified CSV data is imported
  through a separate operator command.”
- Replace the integration arrow with: “Goal Stats frontend → server-side HTTP proxy
  → Flask REST API → existing RoadToTheFinal engine → PostgreSQL.”
- Replace `INT UNSIGNED AUTO_INCREMENT` with `INTEGER GENERATED BY DEFAULT AS IDENTITY`.
  PostgreSQL has no unsigned integer type; use CHECK constraints for domain ranges.
  Replace `DOUBLE` with `DOUBLE PRECISION` and `DATETIME(6)` with
  `TIMESTAMP WITH TIME ZONE`. Actual FIFA ranks are nullable INTEGER with positive checks.
- Use `UNIQUE(name_key, category)` for teams, and
  `UNIQUE(name_key, edition_label, category)` for competitions. Edition is required.
  Document ratings/ranking attribution, source provenance and `score_basis VARCHAR(64)`.
- Add scenario title, shots, corners and yellow cards; all required model inputs
  must be supplied explicitly. Historical team ratings can remain NULL.
- Add required prediction `input_snapshot JSONB` and `details JSONB`, and document
  probability sum/range checks. Generation appends a result; GET retrieves saved
  values without recalculating or joining current scenario state.
- Replace other implementation references to MySQL with PostgreSQL. Do not claim
  StatsBomb, 2027 fixtures, live feeds or historical ratings were imported.

Remaining course work is team-owned: frontend connection/demo, screenshots, human
review and contribution narrative, overview/instructions, technical PDF updates,
presentation and individual peer evaluations. Load/scale benchmarking, calibration
and future analytics are not certified here. The course does not require every
possible database feature; this work does not claim stored procedures/triggers.

AI disclosure: Codex AI assisted with implementation in Prompts 1–3 and integration
verification, test execution and documentation in Prompt 4. This is not a claim of
independent human authorship or completed human review. Team members must accurately
identify AI assistance, describe their own review/modifications and be prepared to
explain and defend the submitted work.

## S. Documentation updated

[Frontend API reference](frontend-api.md) now groups work by teammate, explains
first-run historical import, corrects outdated historical-ID wording, and documents
precise proxy/body/method/error/Location requirements. This report records final
combined evidence. Earlier task acceptance documents remain historical evidence.

## T. Frontend handoff reference

Use [frontend-api.md](frontend-api.md) for request bodies, all response fields,
validation/error behavior, persisted values, examples and limits. Esteban owns
catalog/scenario integration; Mehla uses generation, saved detail and history;
Nikita can keep Home static. A recent summary is optional and not a global feed.

## U. Discord handoff message

> Wes's October 12 backend work is ready for handoff. Run `make setup`, then
> `make run` in goal-stats-service (or stop host Flask and use `make deploy`).
> API: http://127.0.0.1:5100 — Swagger: http://127.0.0.1:5100/swagger.
> 127.0.0.1 is each developer's own machine, not a shared hosted server.
> Esteban: GET `/api/v1/catalog/teams`, team detail, competitions, matches/detail;
> POST/GET `/api/v1/scenarios`; GET/PATCH `/api/v1/scenarios/{id}`.
> Mehla: bodyless POST `/api/v1/scenarios/{id}/predictions`, GET that path for history,
> and GET `/api/v1/predictions/{id}` for saved results.
> Nikita: Home can stay static; saved-result summaries are optional.
> Catalog/scenarios/predictions, host/Docker persistence and 651 tests pass.
> Historical ratings remain null; scenarios require explicit model inputs.
> Fresh databases need the documented historical import. Repeated generation saves
> a new result. The current frontend proxy needs allowlist/PATCH/bodyless-POST changes;
> React integration has not been certified. Full instructions and examples:
> `docs/service/frontend-api.md` in the backend repo.

This message is prepared for the user to paste; it was not sent.

## V. Files modified / added

Prompt 4 only: updated `docs/service/frontend-api.md`; added
`docs/service/backend-certification.md`. Ignored local evidence lives under
`.host-sessions/prompt4`; temporary setup/test logs remain local. Prior prompt changes
remain in models, services, routers, schemas, migration/SQL exports, importer,
settings/readiness, tests and documentation. No prior implementation was replaced.

## W. TODO.md status

Unchanged and unstaged. Baseline hash verified, along with all existing non-documentation
files. No changes were made to the frontend repository.

## X. Remaining issues

No blocking backend defects found. Frontend proxy/screen integration remains with
teammates. Missing planning documents and Drive wording corrections need team review.
No cloud deployment, browser UI, load benchmark or authoritative historical rating
source is claimed. Current API does not support incomplete scenario drafts, deletion,
or a global latest-prediction feed. No authentication is included in this local
prototype. These are scope limits, not new features introduced during certification.

## Y. Exact manual verification commands

Run from `goal-stats-service`, in order. Do not run host and Docker Flask together.

```bash
git branch --show-current
make help
make setup
make run
# In another terminal, while host Flask runs:
curl -fsS http://127.0.0.1:5100/health
curl -fsS http://127.0.0.1:5100/ready
curl -fsS http://127.0.0.1:5100/swagger/v1/swagger.json
curl -fsS http://127.0.0.1:5100/api/v1/catalog/teams
curl -fsS 'http://127.0.0.1:5100/api/v1/catalog/matches?limit=200'
# These IDs are the retained acceptance records on this database only:
curl -fsS http://127.0.0.1:5100/api/v1/scenarios/3
curl -fsS http://127.0.0.1:5100/api/v1/predictions/3
curl -fsS http://127.0.0.1:5100/api/v1/predictions/4
curl -fsS 'http://127.0.0.1:5100/api/v1/scenarios/3/predictions?limit=2'
# Stop host Flask with Ctrl-C in its terminal before switching:
make deploy
curl -fsS http://127.0.0.1:5100/api/v1/predictions/3
make stop
make deploy
curl -fsS http://127.0.0.1:5100/api/v1/predictions/3
make test
docker compose --env-file .env.local -p goalstats-service-local \
  -f docker/compose.local.yml exec -T postgres \
  psql -X -v ON_ERROR_STOP=1 -U goalstats -d goal_stats_service_local \
  < sql/verify_historical_import.sql
git status --short
```

On a fresh database, first run the [historical import](football.md#historical-import-operations),
then use the [scenario POST example](frontend-api.md) and returned IDs. Example IDs
are not portable. New prediction POSTs intentionally add records. For read-only
rechecking of this machine's complete saved acceptance responses:

```bash
PYTHONPATH=src .venv/bin/python .host-sessions/prompt4/verify.py --restart
PYTHONPATH=src .venv/bin/python .host-sessions/prompt4/source.py
PYTHONPATH=src .venv/bin/python .host-sessions/prompt4/catalog.py
```

## Z. Final commit readiness

Implementation and certification are ready for review and a user-controlled commit.
Nothing has been staged/committed/pushed. Review the entire accumulated diff and
include new migration/model/API/test/docs files deliberately; do not stage local
configuration, datasets, environments or TODO. `.env.local`, `.venv` and downloaded
CSV evidence are ignored; no credential values were added to tracked files.

Left running, all healthy: `goalstats-service-local-app-1`,
`goalstats-service-local-postgres-1`, `goalstats-service-local-redis-1`.
Host Flask is stopped. Unrelated containers retained their IDs/status/start times.
