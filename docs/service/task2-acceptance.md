# Task #2 historical-data acceptance

**TASK #2 COMPLETE — local PostgreSQL certified on 2026-10-08 (America/Los_Angeles).**
**CLOUD RUNTIME: UNVERIFIED.** No cloud import or deployment was attempted.

## Environment and baseline

Branch: `member/wes`. Existing Prompt 1/2 work was preserved; no staging, commit or
push occurred. Database `goal_stats_service_local`, user `goalstats`, Compose project
`goalstats-service-local`, volume `goalstats-service-local_postgres-data` (created
2026-10-07T01:10:20Z). PostgreSQL and Redis were initially stopped and were started
with `make infra` before recording the database baseline. No migration/import ran
before the baseline was captured.

| Table | Before | After import/reimport/restart |
| --- | ---: | ---: |
| `football_teams` | 32 | 32 |
| `football_history` | 16 | 16 |
| `football_snapshots` | 0 | 0 |
| `items` | 0 | 0 |
| `actions` | 0 | 0 |
| `teams` | absent | 32 |
| `competitions` | absent | 1 |
| `matches` | absent | 64 |

Alembic advanced from `d94f81ab2301` to `e3a71c92b406`. SQLAlchemy metadata comparison
reported no differences. Schema inspection confirmed three integer identity primary
keys, three restrictive foreign keys, three unique constraints, 27 check constraints,
and indexes on all match foreign keys plus date. Legacy schemas and sorted full-record
SHA-256 digests remained identical to baseline, including prototype ratings/history.
No prototype record was reclassified as verified history.

`.env.local` checksum before and after:
`fbb6ef1af318e97a4a54de3c12e47592a3bdaeeb01d830b7257ca75f751ab2ba`.
No credential values were printed or added to tracked files. `TODO.md` and Makefile
checksums were unchanged. The Make interface still has seven public commands.

## Source, validation and actual import

Source: Mart Jürisoo, [Women's International Football Results](https://github.com/martj42/womens-international-results).
Pinned revision: `1855e313ae8bcd0330426e62c8e4cf15ce45077c`.
Full `results.csv` SHA-256:
`de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0`.
The [manifest](../../data/manifests/womens-world-cup-2023.json) supplies selection,
competition mapping, attribution and expected counts. The CSV remains ignored at
`.host-sessions/task2-acceptance/input/results.csv`, outside tracked data packaging.

The adapter read 11,650 rows, selected 64 and filtered out 11,586. Selection is
`FIFA World Cup`, inclusive 2023-07-20 through 2023-08-20, explicitly mapped to
`FIFA Women's World Cup`, edition `2023`, category `women_senior_national`.
There were zero rejected records, duplicate input identities or conflicts.
All 64 stored records were compared field-by-field against typed source records,
including scores, venue flags, original labels, row numbers and provenance.
All historical model ratings, FIFA ranks and ranking metadata remain NULL.

| Run | Teams inserted/proposed | Competitions | Matches | Unchanged | Committed |
| --- | ---: | ---: | ---: | ---: | --- |
| Dry-run | 32 proposed | 1 proposed | 64 proposed | 0 | false |
| First import | 32 | 1 | 64 | 0 | true |
| Repeat import | 0 | 0 | 0 | 64 | true |

Dry-run left full table/schema snapshots identical. The first import committed one
SQLAlchemy transaction. Reimport preserved every primary key, timestamp, fact and
provenance field. SHA-256 identity excludes scores, file versions/checksums and row
order. Conflicting facts abort instead of overwriting; failed writes roll back.

## Relational SQL evidence

The [read-only SQL script](../../sql/verify_historical_import.sql) returned all 64
matches joined to home/away teams and competition, with zero duplicate identity
groups and zero orphaned foreign keys. Example observed rows:

| Match ID | Date | Home | Away | Score |
| ---: | --- | --- | --- | --- |
| 1 | 2023-07-20 | New Zealand | Norway | 1–0 |
| 64 | 2023-08-20 | Spain | England | 1–0 |

Scores use `including_extra_time_no_shootout`; shootout goals are not ordinary
match goals. The source-specific SQL digest was unchanged across reimport/restart:
`fb1d44d3c2278cf02c2ef27a976e9bc8` (verification digest, not the source checksum).

## Existing API and automated checks

Host Flask was started with `make run`. Actual HTTP requests returned 200 for
`/health`, `/ready`, `/swagger`, `/api/v1/teams`, `/api/v1/backtests`,
`/api/v1/history`, and `/api/v1/snapshots?team1=Spain&team2=England`.
Readiness was `Healthy`; the team list contained 32 prototype teams, backtests
reported 13 evaluations, and the snapshot list remained empty. An initial snapshot
request without required team filters correctly returned 400; the corrected request
passed. Snapshot creation/retrieval compatibility is additionally covered in the
disposable-database suite; no acceptance snapshot was added to development data.

`POST /api/v1/predictions` with Spain, England and minute 0 returned 200 with valid
probabilities: Spain 0.37074041064032975, draw 0.26390886112362144, England
0.36535072823604886 (sum 1 within tolerance). Prediction algorithms were unchanged.
These APIs still use prototype structures; normalized-catalog REST endpoints are
not implemented.

`make test` passed **453 tests in 25.36 seconds**, plus Ruff lint/format and strict
mypy (68 source files). It used its owned disposable PostgreSQL/Redis providers,
separate from development. One targeted safety change removed `--volumes` from
`scripts/test.sh` cleanup; test storage is tmpfs. No volume deletion is needed or
performed. No importer or prediction defect required changes during acceptance.

## Stop/restart and resource safety

Host Flask was stopped with Ctrl-C, followed by `make stop` and `make infra`.
The original PostgreSQL volume retained the same name, creation metadata and mount
identity. All table schemas and full-record digests matched the post-import snapshot;
representative match IDs 1, 32 and 64 were unchanged. SQL verification passed again.
The unrelated containers' IDs, states and start timestamps matched their initial
snapshot; no unrelated Docker resource was stopped or altered.

Final running Goal Stats containers: `goalstats-service-local-postgres-1` and
`goalstats-service-local-redis-1`, both healthy. Host Flask is stopped. Disposable
test containers were removed without deleting Docker volumes.

## Manual verification and recovery

From the repository root, with the existing infrastructure healthy:

```bash
gs_compose() {
  docker compose --env-file .env.local -p goalstats-service-local \
    -f docker/compose.local.yml "$@"
}

historical_import() {
  gs_compose run --rm --no-deps -T \
    -v "$PWD/.host-sessions/task2-acceptance/input:/input:ro" app \
    flask --app 'main:create_app()' import-football \
    --dataset womens-world-cup-2023 --directory /input \
    --target local --expect-host postgres \
    --expect-database goal_stats_service_local "$@"
}

historical_import --dry-run
# Optional authorized repeat write: expects zero inserts and 64 unchanged matches.
historical_import

gs_compose exec -T postgres psql -X -v ON_ERROR_STOP=1 \
  -U goalstats -d goal_stats_service_local < sql/verify_historical_import.sql
```

The [operator procedure](football.md#historical-import-operations) documents fresh
input acquisition, target preflight and separate migrations. Stop on any error.
Checksum failure requires the exact pinned file; conflicts require explicit review.
Never reset tables, change the pinned checksum to accept unknown input, or delete
volumes to recover. Repeat the dry-run after fixing the demonstrated cause.

Cloud jobs use the same image with deployment-injected secrets, explicit cloud and
expected-host/database flags, production confirmation, verified TLS and separate
migrations. Configuration, redaction and authorization tests passed; no cloud runtime
or provider-specific certificate deployment was tested. `.env.local` is not a cloud
credential source. Historical import is never automatic in Flask workers.

## CS 514 technical summary and AI assistance

Goal Stats now stores a verified real-world women's international tournament in
PostgreSQL. Teams and competition information are normalized and referenced by match
foreign keys; identity, uniqueness, nonblank, score-range and attribution constraints
protect integrity. The deterministic source key makes imports repeatable while
preserving source lineage. Unicode/whitespace normalization, explicit mappings and
strict CSV/checksum validation precede an atomic database transaction. SQL joins
retrieve complete historical fixtures without repeating team/competition identities.
Local acceptance demonstrated 32 teams, one competition, 64 matches, unchanged
reimport, restart persistence, preserved legacy functionality and passing regressions.
Scenarios, Predictions and frontend-facing normalized APIs remain subsequent work.

Codex AI assisted with schema/importer implementation, tests, acceptance execution,
SQL verification and this documentation under the user's supplied requirements.
This evidence is not a claim of independent human authorship or completed human
review. Team members should review and be prepared to explain the design and their
contributions before submission. Google Drive documents were read only; none were
edited automatically.
