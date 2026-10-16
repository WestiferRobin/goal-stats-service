# Backend certification

Prompt 2 includes the actual approved Women's World Cup source in canonical host
certification. Prompt 1's five application tables and 15 application operations remain
unchanged. This phase does not seed development data or provide Prompt 3's independent
final certification.

Run `make certify` from the repository root with Docker Desktop/Compose and the
repository Python 3.12 `.venv`. Run `make setup` to prepare a missing environment.
Testing verifies all pinned dependencies and `pip check`; it never installs packages.
The shared `scripts/testing/test.sh` accepts zero arguments for test mode or exactly
`certify`. Extra arguments and inherited provider/pytest/coverage overrides fail closed.

## Execution and selection

All Python executes on the host: Ruff lint, Ruff formatting, strict mypy, Alembic,
pytest and coverage reporting. Docker starts only pinned PostgreSQL and Redis images,
with tmpfs storage and dynamically allocated `127.0.0.1` ports. Each run generates a
unique project, session, PostgreSQL user/password and independent Redis password.
There is no Python runner image build, runner container or Flask container.

The complete `tests/unit` and `tests/integration` selection runs together exactly once
under coverage. GNU Make-dependent cases run on hosts with GNU Make available.
The `pinned_source` case is mandatory in this invocation; no marker filter excludes it.
`make test` alone excludes it explicitly. The runner validates the ignored pinned CSV,
creates and verifies an invocation-owned macOS read-only image, and exposes it only to
this execution. Missing source, invalid manifests/checksum or mount failures fail closed.
See [testing](overview.md#pinned-historical-source-certification) for source location,
checksum, ownership checks and lifecycle.

## Measurement and reports

The unchanged `.coveragerc` measures all executable `src/` modules, including
unexecuted modules, with branches enabled. Only the existing type-only guard/import
exclusion remains. Tests and infrastructure scripts are outside production coverage.
The existing reporting helper evaluates exact integer counts before display rounding:

```text
100 * (covered statements + covered branches)
    >= 95 * (total statements + total branches)
```

The host runner uses a fresh absolute `COVERAGE_FILE` in a private unique
`.host-sessions/certify-<project>.<suffix>/` directory. It prints missing lines and
branches and retains `coverage.json`, `coverage.xml` and pytest `tests.xml`, including on threshold
failure. Reports never overwrite prior runs. No Docker report mount is used.
Only this invocation's raw `.coverage` is removed after writers have terminated.
Early failures may produce no reports; report generation or raw cleanup failure
prevents PASS. Coverage from separate runs or application processes is never merged.
Subprocess coverage is not implicitly enabled; in-process Flask CLI tests contribute.

## Ownership, failure and cleanup

A version-3 receipt in a private owned session directory binds full container IDs,
project/session labels, isolated network, tmpfs storage, actual loopback mappings,
credentials and exact targets. Live Docker metadata is rechecked before owned commands
and fixture activation. PostgreSQL identity and Redis authentication are verified
before running Alembic or pytest. `.env.local` is never loaded for tests.

The supervisor owns each child process group, relays SIGINT/SIGTERM and waits before
provider cleanup. Cleanup removes only the invocation's Compose resources, never
persistent volumes or unrelated containers. Baseline resource identities and running
containers must remain present. The original execution failure takes precedence over
secondary cleanup failures, which are reported separately. Source cleanup verifies the
session token, directory owner/inode, exact image path/owner and device before detaching.
It confirms detachment before removing the private image and copied CSV. If ownership
or detach verification fails, the session remains for recovery and PASS is prohibited.

A failing full suite can still produce diagnostic reports. They do not certify tests.
Final PASS appears only after tests, reports, the 95% gate, cleanup and preservation
checks succeed. `make test` retains the same quality and safety checks without coverage.

## Prompt 2 real-source results — 2026-10-15

`make certify` passed: **1,143 tests (813 Unit, 330 Integration), zero skipped or
deselected**, including `test_pinned_source_import_repeat_and_application_restart`.
`make test` passed: **1,142 tests, one intentional pinned-source deselection, zero skips**,
with successful disposable-resource cleanup.
Host Ruff lint/format and strict mypy passed. The historical test verified 44 teams,
nine editions, 348 matches and 1,081 goals in disposable PostgreSQL, source-row parity,
normalized APIs, scenario/prediction persistence, repeat imports and application restart.

| Coverage | Covered / total | Percentage |
| --- | ---: | ---: |
| Statements | 2,680 / 2,711 | 98.856511% |
| Branches | 532 / 556 | 95.683453% |
| Combined | 3,212 / 3,267 | **98.316498%** |

Retained local artifacts:
`.host-sessions/certify-goal-stats-service-test-6d1f434ea795595918cce721.EvY3Js/`
contains validated `coverage.json`, `coverage.xml` and `tests.xml`. The pytest XML records
the pinned-source test passing. Raw `.coverage`, the owned source image/mount/session,
and owned Docker providers/network were removed. The unrelated mounted-image inventory
was unchanged; Docker preservation checks passed. Focused safety/import tests: 247 passed.

Production source, historical manifests/CSV, migrations, dependencies, `.env.local`
and persistent resources were not changed. Prompt 3 remains independent final certification.

## Historical container-runner evidence

The dated records below describe the earlier container implementation. Their counts,
coverage results and artifact behavior are historical, not host certification evidence.

## Phase 2 measured baseline (2026-10-14)

The disposable certification run passed all 11 preliminary integration cases and then 873 ordinary
cases, with eight existing Make-dependent container skips and one pinned-source
case deselected. The complete source measurement was:

| Metric | Result |
| --- | --- |
| Statements | 2,579 / 2,850 — 90.491228% |
| Branches | 455 / 600 — 75.833333% |
| Combined | 3,034 / 3,450 — 87.942029% |
| Missing | 271 statements and 145 branches |

The coverage gate correctly failed at the unchanged 95% threshold; JSON/XML reports
survived cleanup. This is infrastructure verification, not a passing certification.
Prompt 3 should prioritize `football/live.py`, `football/import_data.py`, provider
failure handling and remaining engine branches, using the report's exact missing
lines and arcs. An earlier diagnostic report showing zero coverage is invalid and
is explicitly marked as such in its retained artifact directory; reporting self-tests
now run in child processes to preserve the measured process's coverage state.

## Phase 3 coverage closure (2026-10-14)

A fresh baseline certification reproduced 87.942029% combined coverage: 2,579/2,850
statements and 455/600 branches, with 271 missing statements and 145 missing branches.
The historical preliminary subset passed (11 cases); the full suite passed 873 cases with eight existing host-Make
skips and one pinned-source deselection. The expected threshold failure cleaned its
owned resources and retained JSON/XML reports.

After 104 additional unit cases, `make certify` passed its preliminary, full-suite, reporting,
coverage and cleanup gates. Collection is 655 Unit + 330 ordinary Integration cases,
plus the separate opt-in historical-source case. The full run executed 977 passing
cases, skipped the eight existing Make-dependent cases in the tooling container, and
deselected the pinned-source case. The eight Make-dependent cases also passed separately
on the host. Focused validation passed 292 tests; Ruff, formatting, strict mypy and
`git diff --check` passed.

| Metric | Final result |
| --- | --- |
| Statements | 2,810 / 2,850 — 98.596491% |
| Branches | 571 / 600 — 95.166667% |
| Combined | 3,381 / 3,450 — **98.000000%** |
| Missing | 40 statements and 29 branches |

The measured source denominator, branch policy and 95% threshold are unchanged.
Only the two previously justified type-only lines remain excluded. The historical preliminary execution
is not added to coverage, and no subprocess execution is assumed to contribute.

The additions exercise provider URL/header/timeout/size contracts and failure handling;
live fixture selection, reversed teams, statistics, cards and timelines; in-process
import entry-point argument handling and cleanup; historical snapshot parsing;
deterministic engine labels, tiebreaks, byes and stage accounting; connection identity
and TLS rejection; strict settings; and malformed-provider fallback without persistence.
No production changes or new production defects were required to achieve the result.

Review artifacts:

- [Baseline gap inventory](coverage-gap-baseline.csv): every module initially below 95%,
  behavior classification, and exact missing statements/arcs.
- [Before/after module comparison](coverage-gap-results.csv): remaining gaps are retained,
  including CLI/parser error paths and direct application bootstrap paths.
- [Addition inventory](coverage-additions.csv): every new node ID, behavior, source-function
  spans, expected assertions and passing result. Function spans identify the code under
  test; exact aggregate execution and missing arcs are in the generated coverage JSON.

The final reports are in the ignored run directory
`.host-sessions/certify-goal-stats-service-test-d6a0f0f35b692992b86a0d30.MnkHVI/`.
Its `coverage.json`, `coverage.xml` and raw data survived container, network and image
cleanup. The fresh baseline reports remain separately under
`.host-sessions/certify-goal-stats-service-test-f94252f236bfa60fba357561.x2Apsj/`.

All existing test/helper definitions and 881 ordinary baseline node IDs were preserved.
Production files, authoritative schema/router baselines, SQL, Alembic, coverage
configuration and runner policy retain their pre-phase hashes. Exactly one root
conftest and the existing eight shared fixture modules remain. Independent Phase 4
certification can repeat `make certify` using this unchanged pipeline.

The engine's zero-momentum and zero-probability defensive fallbacks remain measured
but uncovered: valid teams have a positive momentum floor, and valid probability
calculations retain positive mass. Tests do not monkeypatch these invariants solely
to execute defensive lines. The benchmark is combined source coverage, not a claim
that every module individually exceeds 95% or that every possible input is validated.


## Final ownership remediation

Meaningful unit suites now own exception handlers, football CLI dispatch, historical
import fact helpers, scenario prediction adaptation, infrastructure readiness, Match
responses and Scenario responses in their matching `tests/unit/` paths. Existing HTTP,
PostgreSQL and service tests remain intact. There is still exactly one root
`tests/conftest.py`; no new fixture framework or test category is introduced. The gate
remains at least 95% combined statement-and-branch coverage across all `src/` files.
Earlier Phase 2/3 records describe the artifact retention behavior at that time; current
runs retain JSON/XML and remove their temporary raw database.

## Host execution migration — 2026-10-15

Implementation verification ran on branch `member/wes`, HEAD
`663cc6a20aefb8b7044421009b4bd816b46fa69f`, using repository Python 3.12.0.
Both final `make test` and `make certify` runs passed **1,107 tests**, with no skips
and the single opt-in pinned-source case deselected. Collection is 777 Unit and
330 ordinary Integration cases, plus that one opt-in case. The 43 additional Unit
cases exercise host execution, receipt/port safety, configuration isolation and
process lifecycle. The eight GNU Make-dependent cases now execute on the host.
All nine former special-marker integration files retain their exact test bodies.

Both commands passed host Ruff lint/format and strict mypy (81 source files).
Each created only its two disposable provider containers, using authenticated
Docker-allocated loopback ports, and passed owned-resource absence and preexisting
resource-preservation checks after cleanup. No Python runner container was used.

| Metric | Fresh host result |
| --- | --- |
| Statements | 2,815 / 2,850 — 98.771930% |
| Branches | 572 / 600 — 95.333333% |
| Combined | 3,387 / 3,450 — **98.173913%** |
| Missing | 35 statements and 28 branches |

The final host reports are retained in
`.host-sessions/certify-goal-stats-service-test-e80f58e78598001b6e758efc.CVEokX/`.
JSON/XML validity, complete source inclusion, private directory permissions and
raw `.coverage` removal were checked after completion. Earlier reports were preserved.
Production source, migrations, SQL, data, dependency pins, coverage policy/helper,
Makefile and Dockerfile retain their pre-migration contents. The 42 schema fingerprints
and OpenAPI fingerprint
`a04648f363bd50e42e69561b1998779ca770a0918ee57d9b2b127fa0e7b6eb17`
remain unchanged and their contract tests passed.

Failure-path tests cover missing/invalid host environments, unsafe receipts and ports,
provider/command/report failures, original exit-code precedence, raw cleanup failure,
and SIGINT/SIGTERM. Real process tests also verify stubborn descendants through nested
supervisors are terminated before cleanup returns. The opt-in actual-source integration
case was not executed in this phase; its host fixture rejects missing source, writable
filesystems and chmod-only protection. Independent Phase 2 certification remains a
separate review of this implementation evidence.
