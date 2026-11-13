# Task 1 — Database ownership design and migration plan

**Prompt 1 design status: PROPOSED — NOT YET IMPLEMENTED OR FORMALLY APPROVED**

**Prompt 2 implementation update — 2026-11-13:** The user subsequently authorized
the minimal schema implementation. Revision `e42b7c19a603` now extends
`d91e6a4b208f`, with the two-column users table, nullable scenario owner FK/index,
guarded downgrade, projection compatibility, readiness registration and SQL parity.
The original design below is retained as the implementation contract and historical
Prompt 1 record; its future-tense statements describe that stage. Formal team
acceptance and persistent deployment are not implied. No account workflows or
private-record enforcement have been activated.

Design date: 2026-11-13. Original task owner: Mehla. Requested implementation
owner: Wesley. This is Prompt 1 of 4: design, documentation and verification only.
Technical verdict: **DESIGN READY FOR IMPLEMENTATION**, subject to review of this
proposal and a later implementation instruction. This is not production deployment
authorization or formal team acceptance. No migration was generated or executed.

## 1. Requirements and scope

The [Engineering Backlog](https://docs.google.com/document/d/1nsJYQbk84yOqcpXeAhxrXTRAZtPNignpOJSuN26Wlg0/edit)
requires schema, relationship, constraint, index and migration review, preservation
of existing records, and preparation for accounts and ownership. The
[Weekly Team Tasks](https://docs.google.com/document/d/1D_mUhoDmvOqDpT08I0w_yk_jOd5jw2wTEj-nAtbDf0I/edit)
requires Mehla/Wes coordination on database contracts and historical statistics.
Both were reread; the [team folder](https://drive.google.com/drive/folders/1YmdKkVIK2x2nm_Ht--Uz8ajjnD5_pvaq)
returned those documents. The weekly title extends through November 16; its body
still states October 28–November 4. No approval is inferred from the title.

The user's Prompt 1 resolves the scope question: implement database preparation
in a subsequent stage, while deferring accounts and authorization. Zero users is
a supported initial and ongoing state. This proposal does not require an email,
password, identity provider, seeded account, login endpoint or authenticated request.

Only this design document changes in Prompt 1. Current models, migrations, SQL,
services, tests, CI, data and other documentation remain unchanged.

## 2. Verified baseline and invariants

| Item | Baseline |
| --- | --- |
| Repository | `WestiferRobin/goal-stats-service` |
| Branch / HEAD | `member/wes` / `4c0d851e9805174322c04c05bbc5fa177d3ea2bf` |
| Initial tree / conflicts | Clean / none |
| Local and remote master | `677cb5256243cd142ce4ea86d4ea9277e98ed042` |
| Local and remote mehla-data | `2d78595b19fe977a9a0645fba8f70b88b13e0c89` |
| Local and remote member/wes | Match HEAD |
| Migration graph | `a7c93e25d104 → c8d42f19e630 → d91e6a4b208f` |
| Active application tables | `teams`, `competitions`, `matches`, `scenarios`, `predictions` |

Remote references were read without fetching. Metadata and revision inspection
used Python imports and Alembic ScriptDirectory without a database connection.
The empty `src/models/__init__.py` does not register models. Explicit imports in
[Alembic](../../alembic/env.py) and [database resources](../../src/infra/resources/db.py)
register the five active mappings. `User` is absent from both.

| Table / model | Identity and relationships | Invariants to preserve |
| --- | --- | --- |
| [teams](../../src/models/team.py) | Integer identity `team_id`; unique `(name_key, category)` | 11 checks; nullable unknown ratings; rating/ranking attribution |
| [competitions](../../src/models/competition.py) | Integer identity `competition_id`; unique `(name_key, edition_label, category)` | Four nonblank checks; separate editions/categories |
| [matches](../../src/models/match.py) | Integer identity `match_id`; competition and two team FKs | 12 checks; nonnegative scores; distinct teams; unique source/record key; full provenance |
| [scenarios](../../src/models/scenario.py) | Integer identity `scenario_id`; two team FKs, optional match FK | 37 checks; explicit rating snapshots; bounded state; possession sum; current timestamps and ordering |
| [predictions](../../src/models/prediction.py) | Integer identity `prediction_id`; required scenario FK | 11 checks; bounded probabilities; JSON objects; saved model/input/output and timestamps |

All seven current FKs use `ON DELETE RESTRICT`. Existing indexes include match
references/date, scenario references and `(created_at, scenario_id)`, and prediction
`(scenario_id, generated_at, prediction_id)` plus `(generated_at, prediction_id)`.
Keep every current constraint, index, column, ID and identity sequence intact.

Services own transaction boundaries; repositories flush but do not independently
commit. Scenario PATCH locks its row. Prediction generation captures inputs,
computes outside the transaction, then appends a result. Reads do not recalculate.
Append-only behavior is an application contract, not a privileged-SQL write ban.
Historical imports affect catalog tables only and remain idempotent/conflict-aware.

The user states there are currently no registered users. No persistent database
was inspected to independently establish its contents. No equivalent Task 1 design
document was found. Current [architecture](architecture.md), [API](frontend-api.md),
[retirement](football.md), [deployment](render.md) and [testing](../testing/overview.md)
documentation were inspected. `development.md` still names `c8d42f19e630` as current
head: correct that separately during implementation documentation, not this stage.

## 3. Minimal provider-neutral users table

Proposed final fields, and no others:

| Field | PostgreSQL definition | Purpose |
| --- | --- | --- |
| `user_id` | `INTEGER GENERATED BY DEFAULT AS IDENTITY NOT NULL` | Stable surrogate identity; `pk_users` primary key |
| `created_at` | `TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()` | Database-created identity timestamp |

This follows current SQLAlchemy `Identity()` and timestamp conventions. The PK
provides uniqueness and its backing index. No additional users index or uniqueness
constraint is justified before a login/contact identity exists. Zero rows is valid;
creation of this table must not insert a record or consume an identity value.

The dormant [User draft](../../src/models/user.py) has required email, case-sensitive
email uniqueness and a trim-based nonblank check. Retain its `user_id` and
`created_at`; omit its email field/check/unique constraint from the activated model.
This changes an unmigrated draft, not an existing active users column. A target
already containing an unexpected users table is a schema collision: stop and
inspect, never drop/adopt/overwrite it automatically.

| Identity question | Proposed decision and consequence |
| --- | --- |
| Local versus external authentication | Assume neither. Task 13 decides and extends the schema additively. |
| Required email | No email column now; zero email requirements. An account identity is not defined by a contact address. |
| Email as login or contact | Undecided for Task 13; neither role is encoded now. |
| Normalized email uniqueness | Deferred with email. Before email login, agree normalization/verification and enforce canonical uniqueness in the database. |
| Provider identifiers | Deferred; a later provider mapping should uniquely identify provider/issuer and subject, rather than treating email as a provider identity. |
| Password fields | Deferred with credential storage and hashing to Task 13. |
| Account status/deactivation | Deferred. An unused boolean would not enforce anything. Define lifecycle states with Tasks 13/14 before account release. |
| Future schema evolution | Add identity attributes/mappings against stable `user_id`; validate/backfill before imposing future required fields. |

This is an identity anchor for future registration, not a usable login system.
No account CRUD repository, router, session table or ORM relationship collection
is necessary in this stage's subsequent schema implementation.

## 4. Scenario and prediction ownership

Add only `scenarios.owner_user_id INTEGER NULL`, with no default and no backfill.
Use `fk_scenarios_owner_user_id_users` referencing `users.user_id`,
`ON DELETE RESTRICT`, default `ON UPDATE NO ACTION`, nondeferrable. This follows
the current restrictive relationship policy; user IDs are stable, not reassigned.

Add the nonunique B-tree index `ix_scenarios_owner_user_id` on
`(owner_user_id, created_at, scenario_id)` in ascending order. This supports the
future predicate `owner_user_id = :authenticated_id` followed by the current
`created_at DESC, scenario_id DESC` order using a backward scan. It also indexes
the referencing owner key. Do not add a redundant owner-only index; retain the
existing global ordering index for current shared lists. Planner selection remains
data-dependent; this is an access-pattern justification, not a benchmark claim.
See [PostgreSQL index ordering](https://www.postgresql.org/docs/17/indexes-ordering.html).

A prediction inherits ownership through its required `scenario_id`. Do not add
`predictions.owner_user_id`, change prediction indexes, or put ownership in saved
prediction JSON. A duplicate owner would create an unnecessary consistency rule.
Future prediction detail/history authorization must join/check the parent scenario.
Changing a scenario's owner would change access to all its predictions, which is
why no ownership transfer workflow is introduced without a separate policy.

## 5. Legacy records and shared API behavior

Existing scenarios receive NULL ownership. Their existing fields, IDs and
timestamps are unchanged. Predictions retain their original scenario references,
IDs, model versions, timestamps, input snapshots and output JSON. No default user,
automatic claim, update/backfill, record deletion or prediction recalculation occurs.

Current shared create/list/read/PATCH and prediction workflows remain shared.
Anonymous-in-the-current-application-context scenario creation still stores NULL.
Production's existing service-token mutation checks remain exactly as configured.
Task 1 does not add filtering, identity assignment, row-level security or private APIs.

Future private-user routes must exclude unowned records by default and prevent
cross-user reads/writes on every scenario and prediction path. They must not leave
an alternate shared route exposing private rows. Claiming, bulk assignment, owner
transfer, account erasure/anonymization and retention require explicit policy.
Do not assign legacy records to the first user or silently set owners to NULL on
account deletion. `RESTRICT` blocks deletion of referenced users; deleting an
unreferenced user is mechanically possible but is not an account-deletion product
workflow. Account deactivation and any retention period remain deferred decisions.

**Private-account release is blocked until Tasks 13 and 14 are implemented and
cross-user isolation is verified. Schema preparation alone creates no privacy.**

## 6. Required compatibility adaptations for Prompt 2

An ORM-column-only change would break existing behavior. These narrow adaptations
are required implementation work, not authorization features:

1. In [ScenarioService](../../src/services/scenario.py), `_response` and
   `capture_state_in_transaction` currently enumerate every mapped scenario column.
   Both would include `owner_user_id`. `ScenarioResponse` and inherited
   `PredictionInputs` forbid extra fields: a no-database validation probe confirmed
   `owner_user_id` yields `extra_forbidden`. Exclude the new internal field from
   both projections (prefer one shared projection definition/helper). Keep names,
   defaults, state validation and effective input capture unchanged. Do not loosen
   `extra="forbid"`, expose owner IDs, or add ownership to request/response schemas.
2. Explicitly import `User` in `alembic/env.py` and `infra/resources/db.py` and
   include it in readiness's table probes. A SELECT returning zero rows is healthy.
   Preserve lazy startup, transaction handling and exact-head checks. Verify any
   direct metadata entry points see all six mappings without package-wide magic.
3. [Bootstrap](../../src/football/bootstrap.py) derives allowed tables from
   `Base.metadata`; correct registration admits users without disabling unrelated
   table checks. Its historical emptiness test intentionally examines catalog,
   scenarios and predictions, not user count. Retain that behavior and verify
   both zero users and existing users survive bootstrap unchanged.
4. [Historical verification SQL](../../sql/verify_historical_import.sql) hardcodes
   `d91e6a4b208f`. Update only the expected head when the actual revision is chosen;
   do not change approved historical facts, selection, score rules or evidence.
   Its scenario digest hashes the whole row, so adding a NULL field changes that
   digest even when old values are identical. Migration tests must compare the
   original column projection (or post-upgrade JSON minus `owner_user_id`) against
   the pre-upgrade baseline and separately assert NULL owners. Do not weaken the
   verifier's normal full-row preservation checks. Establish a new post-migration
   baseline after proving preservation; old and new shape digests are not directly
   comparable. Add explicit users preservation checks in migration/bootstrap tests.
5. Update only schema-dependent table/head expectations in current tests. Preserve
   API/schema fingerprints, datasets, Task 2 acceptance evidence and algorithm
   expectations. Keep the existing shared fixtures and test organization.

These service/readiness/verifier adjustments must be included in Prompt 2's
implementation scope. If a later instruction forbids them, report that concrete
scope conflict instead of shipping a model-only change that breaks workflows.

## 7. One forward migration

Choose a unique revision ID during implementation, with
`down_revision = "d91e6a4b208f"`. There must remain exactly one head. Do not rewrite
any of the three existing revisions or manually stamp a target past a failure.

Upgrade, in one normal Alembic PostgreSQL DDL transaction:

1. Create `users` with the two fields and named primary key above.
2. Add nullable `scenarios.owner_user_id` without a default.
3. Add the named, fully validated restrictive foreign key.
4. Create the ordinary composite index above.
5. Let Alembic advance the revision after successful DDL; commit at the existing
   caller-owned transaction boundary.

No application-data DML, `CASCADE`, autonomous commit, savepoint bypass, seed user,
or ownership trigger is needed. Ordinary Alembic repeated `upgrade head` is a
no-op at the recorded head; do not disguise unexpected schema collisions with
`IF NOT EXISTS`. Fresh installation traverses the existing guarded retirements
then this revision. Earlier supported revisions retain all existing guard behavior.
Removed intermediate revisions still require the appropriate previous checkout;
populated legacy tables still block retirement pending separate preservation work.

## 8. Production compatibility, locking and deployment

The repository pins PostgreSQL 17 for local/test infrastructure. Production server
version, row counts, relation sizes, long transactions, backups and lock traffic
must be checked for the actual authorized deployment; none were observed here.

Adding the nullable column without a default avoids a row rewrite, but ALTER TABLE
still requires locks. Plan for ACCESS EXCLUSIVE on scenarios during the additive
transaction; other reads/writes may wait until commit. FK creation can scan rows
and locks its participating tables. A short DDL statement is not proof of a short
deployment. See [PostgreSQL ALTER TABLE](https://www.postgresql.org/docs/17/sql-altertable.html).

The ordinary index build can block writes and adds work proportional to table size.
Do not use `CREATE INDEX CONCURRENTLY` inside this transaction: it is not allowed
there. If measurement shows the maintenance window is unacceptable, revise the
one-transaction plan explicitly rather than introducing an unreviewed autocommit
path. See [PostgreSQL CREATE INDEX](https://www.postgresql.org/docs/17/sql-createindex.html).

The existing database engine sets a 3,000 ms statement timeout. Retain it by default;
use a migration-session `lock_timeout` below it (proposed 1,000 ms) during the
authorized rollout, without changing application defaults. A lock or statement
timeout must abort and roll back, not be swallowed. Longer bounded migration
timeouts require measured rehearsal and target-specific approval; never silently
disable them. See [PostgreSQL timeouts](https://www.postgresql.org/docs/17/runtime-config-client.html).

| Application / database combination | Compatibility |
| --- | --- |
| Old code / old schema | Existing supported baseline |
| Old code / new schema | Ordinary explicit-column CRUD is structurally compatible; operationally unsupported: old readiness rejects the new head, old historical verifier expects the old head, and old bootstrap rejects unknown users metadata |
| New code / old schema | Unsupported: ORM reads expect the owner column/users; readiness rejects the old head |
| New code / new schema | Required supported target, including zero users and NULL-owned legacy scenarios |

Deployment sequence, for a later separately authorized target:

1. Verify target identity/TLS, exact supported revision, expected schema, no
   unexpected users/owner objects, legacy guards, table sizes and active sessions.
   Take a consistent backup including schema, data and identity sequences and
   verify restoration in an isolated environment. Record original-column digests.
2. Rehearse the same artifact/migration on owned disposable infrastructure with
   representative existing rows; measure duration and lock/timeout behavior.
3. Use a coordinated maintenance window; drain serving traffic and writers. Run
   only one migration/bootstrap actor. The existing bootstrap transaction can
   encompass migration, catalog verification and imports, extending lock duration.
4. Run the approved new release's migration/startup path with existing identity and
   source safeguards. Do not run the old bootstrap after upgrading the schema.
5. Start the new application only after success; check exact head, all six tables,
   zero-user readiness, preserved original data and shared workflows before
   restoring traffic. Reestablish verifier preservation baselines only after proof.
6. On failure, stop rollout and verify transaction rollback/revision. Use old code
   only with its supported old schema; never bypass readiness to force a rollback.

This is not a zero-downtime design. No duration or production-size assumption is
made. A persistent upgrade is not authorized by this document.

## 9. Guarded downgrade and data preservation

Recommend permitting reversal to `d91e6a4b208f` only when **users has no rows and
every scenario owner is NULL**. Existing unowned scenarios/predictions may remain.

In the same transaction, acquire exclusive locks on scenarios then users before
checking emptiness, preventing concurrent ownership/user writes between guard and
drop. Use an online/offline-compatible SQL `DO` guard as in existing retirements.
If either condition fails, raise an error without changing data or revision. Check
both conditions explicitly even though a healthy FK relates them. Never delete
users, clear owners, or offer a force flag to make the guard pass.

After a successful guard, drop the owner index, owner FK, owner column, then users
without CASCADE; let Alembic record the parent. Unexpected dependencies abort the
transaction. Verify the guards and final schema in disposable downgrade tests.

Populated identity/ownership requires a separately approved archival/restoration
plan and preferably a forward repair. A backup alone does not bypass the downgrade
guard. Reversal of an empty users table can discard its sequence state; a complete
backup retains that state if restoration is necessary. Do not downgrade to `base`
as a rollback procedure: the original baseline downgrade drops application tables.

## 10. Standalone SQL parity

[export_football_sql.py](../../scripts/database/export_football_sql.py) runs Alembic
offline through head and writes normalized SQL to
[001_fresh_database.sql](../../sql/001_fresh_database.sql). It is not a hand-written
independent schema. Regenerate it after the new migration is reviewed; retain all
existing historical migration output and append the new revision output. Final
schema: six application tables plus `alembic_version`, zero inserted users.

Future offline regeneration command (not run in Prompt 1):

```bash
APP_ENV=test DATABASE_URL=postgresql+psycopg://offline:offline@127.0.0.1/goalstats_test_export \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B \
  scripts/database/export_football_sql.py --mode schema
```

Future Prompt 3 offline parity check:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider \
  tests/unit/test_sql_exports.py
```

`test_schema_exports_match_without_reading_prototype` compares generated bytes
against the tracked file and forbids database connection. Real installation parity
is `tests/integration/infra/resources/test_db.py::test_standalone_schema_path`:
execute the export in its owned disposable schema, check the new head and compare
metadata. Retain/extend explicit FK, index, check and default inspection where
autogeneration comparison alone cannot prove all invariants.

## 11. Prompt 3 regression plan

Extend the existing modules below; proposed new cases are acceptance requirements,
not claims that those cases already exist. Do not rewrite the test framework.

| Exact module | Required acceptance cases |
| --- | --- |
| `tests/integration/infra/resources/test_db.py` | Fresh upgrade yields six tables and one head, zero users healthy; SQL installation parity; missing users/owner column or old revision fails readiness; lock-timeout and failed-DDL rollback leaves pre-upgrade schema/data/revision; populated Item and Action retirement each refuses with row/revision preservation; downgrade empty succeeds, populated users (even unreferenced) or owned scenarios refuses; dependency failure rolls back drops |
| `tests/integration/infra/repositories/test_scenario.py` | NULL and valid owner succeed; missing user fails and rolls back; referenced user delete/key update fails; named FK/index and column nullability/default inspected; no redundant owner index; current scenario create/list/read/PATCH remains compatible |
| `tests/integration/infra/repositories/test_prediction.py` | Extend supported upgrade paths through new head; fixture at old head includes catalog, scenario and v1/v2 saved predictions; compare old columns, IDs, timestamps, model/version and JSON semantically; owners all NULL and users empty; repeated upgrade no-op; parent relationship/history unchanged; all writes still roll back together |
| `tests/integration/infra/repositories/test_team.py` | Duplicate canonical team key/category rejected; allowed distinct category retained; existing full-history summary/order/locks tests pass |
| `tests/integration/infra/repositories/test_competition.py` | Duplicate key/edition/category rejected; distinct editions/categories accepted; rows unchanged after failure |
| `tests/integration/infra/repositories/test_match.py` | Duplicate source/record key, missing competition/home/away FK, negative score and same-team match rejected; existing query/provenance/lock tests pass |
| `tests/unit/services/test_scenario.py` | Internal owner excluded from both response and captured inputs, for NULL and non-NULL owner; strict schemas unchanged; PATCH cannot alter owner |
| `tests/unit/services/test_prediction.py` | Capture/generation accepts unchanged input contract; owner never enters new snapshots; frozen snapshots still load without owner |
| `tests/integration/services/test_scenario.py` | Existing concurrent transactions and composed creation locks unchanged |
| `tests/integration/services/test_prediction.py` | Preview/generation/history, concurrent capture, v1/v2 preservation and application reopen tests unchanged |
| `tests/integration/routers/test_scenario.py` | Zero-user HTTP create/list/detail/PATCH; supplied owner field rejected; response keys unchanged; test-seeded owner remains unchanged after PATCH |
| `tests/integration/routers/test_prediction.py` | Zero-user preview/generate/detail/history; old saved JSON preserved; no owner field exposed |
| `tests/integration/routers/test_openapi.py` | Existing route inventory and API contracts/fingerprints unchanged |
| `tests/integration/football/test_historical_import.py` | Nine-edition/repeated/conflicting imports and SQL verifier pass at new head; existing users, scenarios and predictions preserved; migrate-aware projection comparison rather than comparing incompatible row-shape digests |
| `tests/integration/football/test_bootstrap.py` | Fresh zero-user bootstrap; existing complete catalog with zero/nonzero users accepted without alteration; unrelated tables still rejected; import/final-verification failure rolls back new DDL and retains prior records |
| `tests/integration/test_production.py` | Existing missing/invalid/valid service bearer behavior unchanged; shared reads unchanged; no login/ownership enforcement added |
| `tests/unit/test_sql_exports.py` | Offline export byte parity; no database/source-file side effects; historical facts unchanged |

Use valid otherwise-complete fixtures for negative cases so each rejection proves
the intended constraint. For an Action guard case, preserve its required Item too;
also test the Item-only case. For migration failure, inject a late failure in a
disposable transaction and assert original schema, data and version survive.
SQLSTATE/constraint-name assertions should distinguish intended failures from
unrelated setup errors. Lock tests must own both connections and use bounded waits.

Old-head fixtures must use old-compatible explicit SQL/projections: the new ORM
cannot query an owner column before it exists. Compare JSONB semantically or via
canonical representation; do not assert preservation of an original JSON text
serialization PostgreSQL does not retain. Compare old columns exactly and new
ownership separately. Include read-back of unchanged frozen predictions without
calling the engine. Test live ownership FK inheritance by joining the parent;
do not mistake that relation test for Task 14 authorization coverage.

Run `make test` in Prompt 3 only after the existing harness verifies owned disposable
PostgreSQL/Redis. It includes the integration modules and SQL parity test above.
`make certify`, if required by the later prompt, additionally requires the existing
read-only pinned-source setup; ordinary CI excludes that certification case.
Never point these tests at development/production or remove unrelated Docker
resources. Application reopen tests do not prove a PostgreSQL server restart;
any separately required server-restart test must own its disposable provider.

## 12. Implementation scope, decisions and acceptance

| Task | Work |
| --- | --- |
| Task 1 | Minimal users table; nullable owner FK/index; one additive guarded migration; registration/readiness; narrow serialization compatibility fix; SQL parity and verifier-head maintenance; preservation/constraint tests; accurate docs |
| Task 13 | Registration/login/logout; email/provider identity and credential policies; passwords/providers/sessions; frontend accounts; account lifecycle schema as needed |
| Task 14 | Trusted request identity; owner assignment; scoped reads/writes; direct prediction access checks; cross-user denial; legacy visibility/claiming/transfer; shared-write containment and release security |

Expected Prompt 2 code files: `src/models/user.py`, `src/models/scenario.py`,
`alembic/env.py`, one new file under `alembic/versions/`,
`src/infra/resources/db.py`, `src/services/scenario.py`,
`sql/001_fresh_database.sql`, and the expected-head expression in
`sql/verify_historical_import.sql`. Existing prediction model/repository/service,
catalog implementation, algorithms, data and API schemas need no behavior change.
Bootstrap should require only tests if explicit registration works as designed.
Test changes follow section 11. Update current schema/head documentation during
implementation without rewriting dated evidence or Task 2 acceptance facts.

Proposed reviewer: Mehla with Wesley; Tasks 13/14 owners review identity/security
handoff. No reviewer approval has been received or invented.

| Open decision | Timing / consequence |
| --- | --- |
| Accept this minimal two-column identity anchor and guarded downgrade | Review with the implementation instruction; no authentication strategy must be chosen to build it |
| Email/provider/credential strategy and lifecycle states | Before Task 13 implementation/account release; safely deferred by this design |
| Legacy claiming, retention, account erasure and owner transfer | Before those Task 14 capabilities; default remains no claim/transfer and no automatic private visibility |
| Production target, backup, window and measured timeout budget | Before any persistent deployment; no production readiness claim until rehearsal/preflight |
| Private-account release acceptance | Tasks 13/14 owners must prove every access path is isolated, including any formerly shared route |

No unresolved product choice forces a different minimal schema now. The proposed
schema is technically ready to implement, but its proposal label remains until
formal review. An unapproved future email or provider policy must not be smuggled
into Prompt 2 as a required column or default account.

Implementation acceptance criteria:

1. Exactly one forward revision after `d91e6a4b208f`; old migration bytes unchanged.
2. Exactly six registered application tables and SQL parity; zero users valid.
3. Only the approved identity fields, nullable owner reference and justified index
   added; old checks/FKs/indexes remain intact.
4. Every original row field, ID, timestamp and saved prediction survives supported
   upgrades; all legacy owners NULL; no users seeded; historical facts unchanged.
5. Current requests/responses and prediction inputs remain identical in shape;
   shared flows work without users; ownership injection is rejected.
6. Invalid ownership and referenced-user deletion fail safely; rollback refuses
   populated identities/ownership and unexpected dependencies without data loss.
7. Bootstrap, readiness, verifier head and maintenance commands agree with the new
   schema; old/new deployment incompatibilities are documented and tested.
8. Section 11 checks and canonical suite pass in owned infrastructure; no baseline
   relaxation, new auth features or algorithm changes.
9. Current documentation reflects the six-table head and preserves task boundaries;
   team acceptance is recorded separately from technical test success.

## 13. Prompt 1 verification record

Verified current graph, five-table metadata registration, source paths, service
projections, strict extra-field rejection, SQL exporter/test contract, bootstrap
table policy, verifier head/digest behavior and exact-head readiness. Consulted
PostgreSQL 17 documentation matching the repository's local/test major version.
No database connections, Docker-backed tests, schema implementation, dependency
installation, staging, commits or pushes were performed.

Prompt 1 completion checks passed: this new file was inspected independently,
all 18 relative links resolved, whitespace/code-fence checks passed, and
`git diff --check` passed. `git status --short` showed only this untracked design
document. SHA-256 comparison found all 256 previously tracked files unchanged;
HEAD, master and mehla-data remained at their recorded revisions. These
documentation checks do not replace future migration/production acceptance tests.

## 14. Prompt 3 verification and acceptance preparation — 2026-11-13

**TECHNICALLY READY FOR FINAL AUDIT. Formal human acceptance remains pending.**
The Prompt 1 proposal and Prompt 2 implementation record above are preserved.
Current implemented head is `e42b7c19a603`; six registered tables include the
two-column users identity table. No persistent database was accessed or migrated.

Prompt 3 independently reviewed the complete Task 1 diff and added missing
regression coverage. No runtime/schema defect was demonstrated and no runtime
implementation or migration was changed in this stage. The earlier five-table
startup assertion was already corrected in Prompt 2; the full rerun now passes.

Verification commands and observed results:

| Command / check | Result |
| --- | --- |
| `make test` | **1,636 passed, 1 deselected**, 258.19 seconds; zero failures/setup errors |
| Harness Ruff lint and format | PASS; 214 Python files already formatted |
| Harness strict mypy | PASS; 81 source files |
| Harness cleanup/preservation | `Canonical test workflow: PASS (tests and cleanup)` |
| `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B scripts/database/verify_historical_contracts.py` | PASS: nine editions, 348 matches, 44 participants, 1,081 goals, 11,650 source rows |
| Source SHA-256 | `de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0`, unchanged |
| Graph / metadata inspection | One base `a7c93e25d104`, one head `e42b7c19a603`; six mappings |
| Historical migration comparison | All three previously committed migrations byte-identical to HEAD |
| `git diff --check` / relative documentation links | PASS |

The canonical run used owned disposable PostgreSQL 17/Redis, project
`goal-stats-service-test-4afe592d58286c3fcc0c0e8e`. The harness verified provider
ownership and unrelated-resource preservation and removed its containers/network.
No external cleanup interference was observed. The one deselected case is the
existing pinned-source certification test; `make certify` and production rehearsal
were not run. The separate historical-contract verifier did validate the pinned
source/evidence. This does not assert persistent database seeding or formal Task 2
acceptance.

New or strengthened PostgreSQL evidence in this stage:

- `tests/integration/infra/repositories/test_team.py::test_team_constraints_reject_invalid_write_without_changes`
  covers duplicate canonical identity, blank identity fields and invalid ratings/rank.
- `tests/integration/infra/repositories/test_competition.py::test_competition_constraints_reject_invalid_write_without_changes`
  covers duplicate edition identity and blank identity values.
- `tests/integration/infra/repositories/test_match.py::test_match_constraints_reject_invalid_write_without_changes`
  covers all three missing references, negative scores, same-team fixtures and
  duplicate source identity. All catalog failures assert SQLSTATE and unchanged
  full database row snapshots after rollback.
- `tests/integration/infra/repositories/test_prediction.py::test_previous_schema_seeded_history_survives_ownership_upgrade`
  inserts catalog, scenario and frozen v1 prediction rows directly into the old
  reflected schema, upgrades twice, checks every original field/JSON and NULL owner,
  and reopens the saved output with calculation forbidden. Existing v1/v2 coexistence,
  history/reopen and supported-revision preservation tests also pass.
- `tests/integration/infra/resources/test_db.py::test_standalone_schema_path`
  now compares reflected columns/types/nullability/defaults/identity, primary keys,
  foreign keys/delete options, unique/check constraints and indexes against the
  Alembic-installed schema, in addition to model parity and offline export equality.
- The same resource module adds `test_populated_item_action_retirement_preserves_all_records`,
  `test_ownership_migration_lock_timeout_preserves_state` and
  `test_ownership_downgrade_dependency_failure_is_atomic`. Item-only and Item/Action
  cases preserve all legacy/normalized rows and the original revision. Lock failures
  cover upgrade and downgrade; dependency refusal restores dropped index/FK work.
- `tests/integration/football/test_bootstrap.py::test_fresh_then_complete_skips_import`
  now verifies both zero-user bootstrap and repeated bootstrap with an existing
  user, preserving all records without reimporting.

Existing Prompt 2 ownership tests pass: user insertion, duplicate/null identity
rejection, NULL/valid/invalid owners, referenced-user deletion refusal, unchanged
shared create/list/read/PATCH, rejected client owner assignment, inherited prediction
owner, guarded downgrade and atomic failed upgrade. Public schemas/fingerprints,
frozen outputs and service-token behavior were not relaxed. The full suite also
passes catalog/history/import, full-history summary, preview/generate/history,
Analytics-facing saved output, seeded simulation and production-token regressions.

Current documentation corrections in Prompt 3 are limited to this evidence section,
`README.md` and `docs/service/football.md`: the latter two still described the
retirement revision as head. They now distinguish that historical revision from
the six-table ownership head. Prompt 2's current architecture, development,
historical-catalog and deployment guidance was verified and retained. Dated
historical reports and Task 2 acceptance evidence were not rewritten.

| Technical acceptance requirement | Evidence | Result | Remaining |
| --- | --- | --- | --- |
| Active users / zero-user support | Metadata, fresh upgrade, readiness and API tests | PASS | None for Task 1 |
| Nullable scenario ownership | FK/index inspection and valid/invalid/NULL tests | PASS | None for Task 1 |
| Prediction inheritance / preservation | Parent join, frozen v1/v2, exact stored-value comparisons | PASS | Task 14 enforcement deferred |
| Correct constraints and indexes | PostgreSQL rejection tests and reflection | PASS | None for Task 1 |
| Additive migration / supported upgrades | One-head graph, unchanged history, populated old-schema upgrade | PASS | Target-specific deployment preflight |
| Existing-record preservation | Full-row and original-column comparisons; no seeds/backfills | PASS | None for tested paths |
| Downgrade protection | Populated refusal, empty reversal, dependency and lock failures | PASS | No force rollback permitted |
| Standalone SQL parity | Offline byte equality, reflected schema and model comparisons | PASS | None |
| Existing API compatibility | Full suite, zero-user flows, unchanged public schemas | PASS | Shared behavior remains intentional |
| Historical compatibility | Import/summary tests plus pinned-contract verifier | PASS | Task 2 human acceptance separate |
| Full backend regression | 1,636 passed, cleanup PASS | PASS | Prompt 4 final review |
| Current docs / task boundaries | Correct head, deployment order and deferred identity/security policy | PASS | None for technical scope |
| Formal team acceptance | No approval evidence supplied | APPROVAL PENDING | Human review |

Production remains a separate operational gate. Normal `start.sh` serves without
migration; explicit `--migrate` or `--bootstrap --confirm-production` completes
migration before Gunicorn and exits on failure. Old readiness rejects the new head,
and new ORM code requires the new schema. Rehearse and coordinate migration/app
deployment with verified backups and a maintenance window; locks/timeouts can
interrupt traffic. No production blocker was reproduced, but target performance,
restore rehearsal and actual deployment are NOT VERIFIED here. Private accounts
remain blocked on Tasks 13/14; ownership preparation does not make records private.

Committed HEAD and master/mehla-data references remain unchanged. No files were
staged, committed or pushed. Prompt 4 should perform final acceptance review and
any separately authorized commit/push; no confirmed Task 1 runtime defect remains.

## 15. Prompt 4 final technical acceptance — 2026-11-13

The current Weekly Team Tasks and Engineering Backlog were reread through Google
Docs, and the team folder was checked. Implementation, migration history, metadata,
SQL, tests and deployment instructions were independently reviewed. No material
Task 1 design decision remains unresolved. Formal team acceptance remains pending;
the user's implementation and conditional commit/push authorization is separate.

Fresh `make test`: **1,636 passed, 1 deselected in 268.94 seconds**, zero failures
or setup errors. Ruff lint passed, all 214 Python files were already formatted,
and strict mypy passed for 81 source files. The ownership-verified disposable
PostgreSQL 17/Redis project `goal-stats-service-test-3397f821f4f3ea185ef6f29d`
finished with `Canonical test workflow: PASS (tests and cleanup)`.
The deselected case is the existing pinned-source certification case; separate
`make certify` was not run. The fresh historical-contract verifier passed for nine
editions, 348 matches, 44 participants, 1,081 goals and 11,650 source rows, with the
unchanged source SHA-256 recorded above.

This matrix was completed before staging or committing. Test references below
refer to the executed integration suite under `tests/integration/`, with detailed
test names in section 14.

| Requirement | Implementation evidence | Test evidence | Result |
| --- | --- | --- | --- |
| Existing schema preserved | Original columns, constraints and indexes retained; old migrations unchanged | Original-column and full-row snapshots across upgrades | PASS |
| Users table active | Explicit metadata/readiness imports; identity PK and timestamp default | User insertion, duplicate/null rejection, six-table reflection | PASS |
| Zero users supported | No seed, backfill or login requirement | Fresh migration, readiness, bootstrap and scenario creation | PASS |
| Scenario ownership nullable | Nullable owner FK without default | NULL/valid/invalid owners; PATCH preserves owner | PASS |
| Prediction ownership inherited | Required scenario FK; no duplicate owner field | Parent join, saved snapshot and history/reopen regressions | PASS |
| Foreign keys and indexes | RESTRICT owner FK and owner/time/ID index; prior indexes retained | PostgreSQL reflection and referenced-user deletion refusal | PASS |
| Fresh migration | Single base/head; additive revision after d91e6a4b208f | Empty install, repeat upgrade and zero-user assertions | PASS |
| Supported upgrade preservation | Prior revisions retained; no existing-row DML | Old-schema seeded catalog/scenario/v1 prediction; supported revision matrix | PASS |
| Downgrade safety | Locks and data guard; no CASCADE | Empty reversal; populated-user/owner refusal; lock/dependency atomicity | PASS |
| Standalone SQL parity | Export includes new revision and exact head | Offline export equality; reflected columns/defaults/keys/checks/indexes and model comparison | PASS |
| Catalog constraints | Existing identity, reference and score constraints unchanged | Duplicate identities, invalid references/scores, rollback snapshots | PASS |
| Legacy retirement guards | Earlier guarded revisions byte-identical | Populated Item/Action refusal and prototype dependency/ownership guards | PASS |
| Existing API compatibility | Internal owner excluded from public projections; contracts unchanged | Full API/service suite, rejected owner input, preview/history/simulator regressions | PASS |
| Historical-data compatibility | Importer, source data and Task 2 evidence unchanged | Repeat/conflicting/concurrent import regressions and fresh contract verifier | PASS |
| Production migration sequence | Drain, backup/rehearse, migrate, then matching application; fail-fast startup | Startup regressions and disposable failed-DDL/lock-timeout tests; script review | PASS |
| Documentation current | Six-table architecture, current head, deployment/downgrade and scope guidance | Current docs/API/Task 2 evidence reviewed against code and executed checks | PASS |
| Full regression suite | Canonical isolated harness unchanged | 1,636 passed; lint, format, strict mypy and cleanup passed | PASS |
| Task 13/14 scope preserved | No authentication, owner assignment/filtering or privacy claim | Zero-user/shared API and unchanged token/contract regressions | PASS |

All technical precommit criteria pass. Production execution, target-specific lock
timing and backup restoration rehearsal remain deployment work, not completed
operations. Human approval remains pending. Task 9 may continue against the shared
API contract; private-account release still requires Tasks 13/14.

The authorized next operations are one Task 1 commit on `member/wes`, with parent
`4c0d851e9805174322c04c05bbc5fa177d3ea2bf`, a normal push after rechecking remote
references, and exact-commit hosted CI verification. Commit/push/CI outcomes are
reported after those operations; this precommit record does not claim them.
