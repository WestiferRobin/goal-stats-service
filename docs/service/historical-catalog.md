# Historical catalog

Current architecture: five domain tables plus users identity preparation, independent
domain routers and no prototype data fallback. See [API contracts](frontend-api.md), [import/retirement
safeguards](football.md) and [source integrity](../../data/README.md).

The approved 1991–2023 selection contains 44 teams, nine editions, 348 matches and
1,081 goals. The importer retains exact source checksum, date/participant selection,
provenance, stable identities, conflict rejection and per-edition transactions.
Historical inputs populate teams, competitions and matches only. Unavailable
strength ratings remain null; scenarios require explicit assumptions.

Catalog and insights reads use normalized repositories. Comparisons preserve dates,
home/away orientation, competition identity and score basis. They never invent
in-play statistics. Scenario/prediction records survive repeated historical imports.

Fresh startup does not seed. Runtime readiness requires six application tables at head
`e42b7c19a603`; an empty users table is valid. The retirement migration blocks
populated prototype tables pending external preservation and coordinated archival. No persistent migration/import was
performed in Prompt 1. `make test` runs ordinary Unit + Integration tests, excluding
the pinned-source test. `make certify` includes actual pinned-source verification
and requires at least 95% combined statement and branch coverage. Synthetic fixtures
are not source proof.

Both commands run locally through `.venv`; Docker supplies disposable PostgreSQL
and Redis. Certification checksum-verifies the approved source and mounts it on a
read-only filesystem. It fails if mandatory historical-source verification cannot
execute. No prototype CSV fallback exists.

## Task 2 acceptance

**DONE — Historical data definitions and bounded validation complete for the current
implementation scope.** The project owner accepts the implemented definitions and
recorded limitations. This does not assert Mehla's personal sign-off, instructor
approval, independent verification of every fixture, or production certification.

[Source provenance and distribution](../../data/README.md) records Mart Jürisoo's
source, attribution and revision `1855e313ae8bcd0330426e62c8e4cf15ce45077c`.
The committed `results.csv` has SHA-256
`de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0`.
A fresh clone includes it; local seeding mounts that repository source read-only.
The verifier checks 11,650 source rows and all nine approved selections: 348 matches,
44 teams and 1,081 goals. Source agreement is reproducibility evidence, not proof
that all upstream facts are correct.

[Accepted API definitions](frontend-api.md#historical-team-summary) count W/D/L
from recorded final scores, including extra-time goals but excluding shootout kicks.
Tied recorded scores remain draws. Appearances count distinct matching editions;
date bounds are inclusive. Empty selections do not prove historical nonparticipation.
No historical prediction ratings are inferred.

[Independent calculations](../../data/verification/task2-calculations.md) preserve
seven examples and 126 contribution rows, including overlapping selections. USA's
all-edition example is 54 matches, 41 wins, nine draws, four losses, 142 GF, 39 GA,
103 GD and nine appearances. These are source calculations, not live database totals.
The [comparison ledger](../../data/verification/task2-historical-comparisons.md)
corroborates ten fixtures (all nine finals plus Panama–France), not all 348.
Separate publications do not establish independent data lineage. D02's Solna versus
Stockholm venue issue and D10's missing original comparison ledger remain unresolved;
venue certification and the unauditable all-fixture claim are excluded from this
accepted scope. No source bytes were changed to hide these limitations.

Concise evidence recovered from the deleted Phase 2 report at `f6e690e^`:
on 2026-11-13 the source verifier passed, focused checks reported **266 passed in
0.36s**, and calculation reproduction matched all seven totals/126 contributions.
That review did not run PostgreSQL or a completed fresh full regression; it cited
prior CI's 1,607 passed / one deselected separately. These are dated receipts,
not claims about the current run. Maintained verifier, calculations, coverage JSON,
comparison ledger and integration tests retain the reproducible evidence.

## Historical 2023 acceptance

This concise record preserves unique evidence from the deleted 2026-10-08 report
from Git revision `f6e690e^`; it is not current database state.
The local import selected 64 of 11,650 rows and created 32 teams, one competition
and 64 matches. Dry-run wrote nothing; repeat import inserted nothing and reported
64 unchanged matches. Full source-field comparisons and relational checks passed.
Legacy table schemas and full-record digests were preserved; reimport and local
stop/restart retained IDs, timestamps, provenance and the original PostgreSQL volume.
The source-specific SQL digest was `fb1d44d3c2278cf02c2ef27a976e9bc8`.
The then-current suite reported **453 passed in 25.36s**, Ruff lint/format and strict
mypy (68 files). Those APIs and migration layout predate the current architecture.
The source was externally supplied then; it is committed now. No cloud runtime or
cloud deployment was verified. Neither this receipt nor source coverage establishes
what any current persistent database contains.
