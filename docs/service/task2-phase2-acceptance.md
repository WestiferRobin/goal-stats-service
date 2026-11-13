# Task 2 Phase 2 historical-data acceptance

**Canonical review for P1 definitions and P2 validation — 2026-11-13.**
Original owner: Mehla. Implementation: Wesley's requested completion work, with
Codex assistance. **Task 2 is not marked DONE.**

**TECHNICALLY COMPLETE — HUMAN ACCEPTANCE PENDING** for the proposed bounded
basic-results scope. Publishing this evidence does not approve the definitions
or close the unresolved limitations.

**Technical verdict: TECHNICALLY READY FOR ACCEPTANCE of the bounded pinned
basic-results / recorded-score statistics scope described here.** Human acceptance
is pending. This is not certification of every historical fact, venue or independent
data lineage. Broader claims require additional validation.

## A. Task scope and requirements

The [Engineering Backlog](https://docs.google.com/document/d/1nsJYQbk84yOqcpXeAhxrXTRAZtPNignpOJSuN26Wlg0/edit)
defines Task 2 as P1 definitions and P2 accuracy, completeness, consistency and
provenance validation using existing Women's World Cup records. Task 7 needs
history, W/D/L, goals, appearances, pagination and missing-data states.
The [Weekly Team Tasks](https://docs.google.com/document/d/1D_mUhoDmvOqDpT08I0w_yk_jOd5jw2wTEj-nAtbDf0I/edit)
requires Mehla/Wes coordination on definitions and summary queries, example
calculations and documented gaps. Both were reread on the review date; the
[team folder](https://drive.google.com/drive/folders/1YmdKkVIK2x2nm_Ht--Uz8ajjnD5_pvaq)
returned those two documents. The weekly document title extends to November 16,
while its body retains October 28–November 4; no extra completion commitment or
human definition approval is inferred from that title.

This change adds evidence and acceptance documentation only. The
[2026-10-08 acceptance report](task2-acceptance.md) is preserved as the older
2023-only local import report; its historical completion statement does not
establish Phase 2 acceptance across nine editions.

## B. Source inventory and Git baseline

| Item | Verified value |
| --- | --- |
| Branch / HEAD | `member/wes` / `27df1e5ab55fa3223a3b9509e6578a94bf0152ad` |
| Initial tree | Clean; no modified/untracked files or unresolved index entries |
| Source | Mart Jürisoo, Women's International Football Results |
| Revision | `1855e313ae8bcd0330426e62c8e4cf15ce45077c` |
| Full CSV SHA-256 | `de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0` |
| Full source | 11,650 data rows, excluding header |
| Selected scope | Nine editions: 1991, 1995, 1999, 2003, 2007, 2011, 2015, 2019, 2023 |
| Selected totals | 348 matches; 44 distinct participants; 1,081 goals |
| Integrity | Zero duplicate date/unordered-participant pairs; zero blank cells among the nine supplied columns in selected rows |

Existing inventory before edits: nine `data/womens-world-cup/*.json` manifests,
`data/verification/README.md`, `data/verification/womens-world-cup-coverage.json`,
`docs/service/task2-acceptance.md`, `docs/service/historical-catalog.md`,
`docs/service/frontend-api.md`, `data/README.md`, the existing verifier and
historical/summary tests. The ignored raw CSV is at
`data/raw/martj42-womens-results/1855e313ae8bcd0330426e62c8e4cf15ce45077c/results.csv`.

Protected implementations were present and inspected: Task 7's repository,
service, router and response contracts; Task 9's resource/repository/service
architecture; Task 10's time-aware prediction calculations and Task 11's seeded
tournament simulation / conditional draw handling in `src/football/engine.py`.
The consolidated Alembic history and `.github/workflows/ci.yml` remain present.
This is a preservation check, not a new full acceptance audit of Tasks 7/9/10/11.

Before editing, SHA-256 hashes of all tracked files were recorded outside the
repository for final comparison. Prompt 1 changed two tracked
documentation entry points; its final comparison checked 252 tracked files with
250 unchanged. Prompt 3 additionally updates `data/README.md`, qualifies the two
README database observations and expands proposed decisions and D02/D10 closure
requirements. The combined inventory is three modified tracked documents and four
new evidence/documents, listed in section K. The source remains checksum-pinned.
Prompts 1–3 performed no branch operation, fetch, merge, commit, push, database
access, Docker command, frontend edit or dependency change. Prompt 4 authorizes
only final verification and a documentation/evidence commit and normal push to
`member/wes`; it does not grant formal human acceptance.

## C. Provenance and reproducibility

Each manifest selects `FIFA World Cup` using inclusive date bounds and maps it
explicitly to `FIFA Women's World Cup`, `women_senior_national`, and an edition.
The source's full-file checksum is validated before selection. The source adapter
normalizes Unicode NFKC and whitespace for identities, uses casefolded keys, and
applies only reviewed aliases. No aliases are registered for the 44 current labels.
Original labels, original home/away ordering and provenance remain available.
China/Taiwan and England/Scotland remain separate.

`source-record-key-v1` hashes source, category, competition key, edition, date and
normalized original home/away names. It excludes scores, CSV row numbers, source
revision and checksum, allowing corrections to be detected as conflicts rather
than disguised as new fixtures. Imports are atomic per edition and idempotent;
conflicting facts abort instead of overwriting. No import was run in this review.

The existing verifier compares exact participant sets, edition counts, goals,
dates, duplicate/reversed identities and full-row fixture digests. Each digest
covers sorted full row dictionaries, including venue and neutral fields. Passing
the digest proves reproducibility against pinned evidence, not factual truth
independent of the source. Historical runtime flags and regression baselines in
the original coverage artifact are intentionally unchanged.

## D. Verification results and calculations

Fresh source verification: **PASS**, nine editions, 348 matches, 44 participants,
1,081 goals, 11,650 source rows; expected checksum and all fixture fingerprints
agree. A separate standard-library CSV calculation also checked the selection,
unique pairs and all seven requested examples without invoking application code.

| Source-derived selection | M | W | D | L | GF | GA | GD | Editions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| United States | 54 | 41 | 9 | 4 | 142 | 39 | 103 | 9 |
| Germany | 47 | 31 | 6 | 10 | 129 | 42 | 87 | 9 |
| Spain | 14 | 7 | 2 | 5 | 24 | 15 | 9 | 3 |
| Japan, 2011 | 6 | 4 | 1 | 1 | 12 | 6 | 6 | 1 |
| Panama | 3 | 0 | 0 | 3 | 3 | 11 | -8 | 1 |
| USA, 1999 final | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| Germany, 2003 final | 1 | 1 | 0 | 0 | 2 | 1 | 1 | 1 |

The [calculation method and executable reproduction](../../data/verification/task2-calculations.md)
and [126 contribution rows](../../data/verification/task2-team-calculations.csv)
provide every date, participant pair, source score and team-oriented result.
All totals were recalculated, not copied as observations. They agree with the
recorded-score contract. They are **not live database totals**.

Prompt 3 cleanup verification (2026-11-13): source verifier **PASS**; focused tests
**266 passed in 0.36s**, zero failures. The embedded calculation
reproduction passed all seven totals and 126 contribution rows. `git diff --check`,
new-file whitespace checks and relative documentation-link checks passed:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  .venv/bin/python -B scripts/database/verify_historical_contracts.py

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider \
  tests/unit/test_verify_historical_contracts.py \
  tests/unit/football/test_historical_dataset.py \
  tests/unit/football/test_historical_import.py \
  tests/unit/services/test_team.py \
  tests/unit/schemas/team/test_request.py \
  tests/unit/schemas/team/test_response.py

git diff --check
```

These tests cover source contracts/rejection paths, historical parsing/import
logic, summary service and request/response semantics. They do not execute a new
PostgreSQL summary query. Existing repository/API integration tests cover filtered
SQL totals, more than 200 records in one aggregate, safe errors and empty states;
they were inspected but not rerun here. The earlier verified
[CI run at this HEAD](https://github.com/WestiferRobin/goal-stats-service/actions/runs/43421001038)
reported 1,607 passed / 1 deselected; that is prior evidence, not a fresh run.
The separate pinned-source integration marker is not implied by the ordinary CI
count. No Docker/PostgreSQL infrastructure was started. The earlier interrupted
local full-suite attempt is not represented as passing evidence.

## E. Independent historical evidence

The [comparison evidence](../../data/verification/task2-historical-comparisons.md)
contains the exact ten-fixture sample, edition matrix, URLs and source-assessment
table. It covers every final plus Panama–France in 2023. FIFA, DFB, U.S. Soccer,
UEFA, RFEF and FFF corroborate the selected dates, pairs and recorded scores.
RSSSF also supplies a concrete reversed-order comparison for the 1995 final.

All nine editions are **pinned-source verified**, each with an **authoritatively
corroborated sample**. None is **independently complete**. The source author lists
FIFA, RSSSF and national associations among upstream inputs, so separate websites
do not prove independent data lineage. The earlier all-348 comparison is not
reproduced or promoted to independently complete evidence. Hudl could not be
freshly retrieved by web access and contributes no new verification claim.

## F. Discrepancy disposition

See the [fixture-level ledger](../../data/verification/task2-historical-comparisons.md#discrepancy-ledger)
for exact source/comparator values, statistical effects, evidence and reviewer
status. No confirmed pinned-data error was found and no protected correction is
required by the observed evidence.

| Finding | Technical disposition | Human status |
| --- | --- | --- |
| D01 reversed 1995 final order | Team-score association verified; source order retained | Proposed acceptance |
| D02 Solna / Stockholm | DFB supports pinned Solna; exact RSSSF venue equivalence remains unresolved | Accept exclusion of venue certification or investigate further |
| D03 1999 names and Pasadena / Los Angeles | Same identified fixture/venue; no alias or city rewrite | Proposed acceptance |
| D04 shootouts; D05 regulation splits | Missing fields, not score defects; proposed definitions account for them | Definition approval pending |
| D06 Décines-Charpieu / Lyon | Named stadium location supports representation difference | Proposed acceptance |
| D07 upstream README count | Stale 11,020 versus measured 11,650; report actual bytes | Evidence acceptance pending |
| D08 UEFA 2003 retrospective score | Comparator says 1-0; match-specific FIFA supports pinned 2-1 | Retain 2-1 proposed |
| D09 FFF Panama article date | Technical sheet says August 23; separate match record and other sections support August 2 | Retain August 2 proposed |
| D10 original comparison ledger absent | Exact older disputed fixtures/values unknown; cannot mark resolved | Recover evidence or explicitly exclude unauditable claim |

No decision in this table is attributed to a human without explicit acceptance.
“Retained” describes the unchanged source, not an approved team policy.

## G. Statistics definitions

**PROPOSED FOR ACCEPTANCE — WESLEY AND MEHLA APPROVAL PENDING**

1. **W/D/L:** compare each team's recorded final score, including extra time.
   Penalty-shootout goals are excluded. Equal scores are draws even if a shootout
   subsequently determines advancement.
   `result_definition = recorded_final_score`.
2. **Goals:** orient home/away scores to the queried team, include extra-time
   goals, exclude shootout kicks. `GD = GF - GA`;
   `score_basis = including_extra_time_no_shootout` for nonempty results.
3. **Appearances:** count distinct World Cup competition editions represented
   by at least one matching record after all filters. Date filters can reduce
   the count; an edition with zero matching rows contributes zero.
4. **Scope/filters:** Women's senior national World Cup records only; apply optional
   competition and inclusive `date_from` / `date_to` consistently to all totals.
   Summary totals use all matching rows, independent of history-page pagination.
5. **Coverage:** nonempty results say `available_records_only`, never “complete
   history”. Empty filtered results say `no_matching_records`, return zero totals
   and null score basis. They do not establish that the team never participated.
6. **Invalid semantics:** unsupported score bases must fail safely, not be silently
   omitted or combined. Unknown teams are 404, distinct from known teams with no
   matching history.

## H. Task 7 compatibility

[`TeamRepository.summary`](../../src/infra/repositories/team.py) already orients
scores using SQL `case`, aggregates W/D/L and goals over all matching rows, uses
`count(distinct competition_id)` after filters and applies inclusive date bounds.
It restricts competition name/category and has no limit/offset. Venue, neutral
status and shootout winner are not inputs to these aggregates.

[`TeamService.summary`](../../src/services/team.py) checks team existence, rejects
unsupported score semantics and labels empty/nonempty coverage. The
[`TeamSummaryResponse`](../../src/schemas/team/response.py) validates W+D+L=M,
GD=GF-GA and consistency of coverage, score basis and appearances. The existing
[API documentation](frontend-api.md) already calls these rules provisional.
The observed implementation therefore satisfies the proposed definitions without
code or contract changes. Source arithmetic agreement is not a claim that all
348 records currently exist in any particular running database.

## I. Known limitations

- The CSV has no match stage, stadium, regulation-time/ET score splits, ET flag,
  shootout score/winner, rankings or model ratings. These are absent schema facts,
  not blanks in required supplied fields. No values were invented.
- Only ten fixtures were authoritatively corroborated here. Counts and hashes
  verify source consistency; they cannot prove all 348 matches historically correct.
- Full venue/neutral certification is excluded from the proposed scope. D02 is
  unresolved; D10's unknown fixture population cannot be quantified or assigned
  to editions. No assertion of universal harmlessness is made.
- Source lineage independence is unproven. Official comparator pages can contain
  errors, as the ledger demonstrates. URLs may change; observations and locators
  are recorded, but no complete external-page archive is packaged.
- No fresh database import, persistence test, full suite or cloud deployment ran.
  The original 2023 runtime observations remain dated evidence only.

## J. Acceptance decisions

**PROPOSED FOR ACCEPTANCE — WESLEY AND MEHLA APPROVAL PENDING**

The current basic-results feature is validated against its pinned historical source,
supported by representative authoritative fixture comparisons and explicit source
limitations. This is the proposed acceptance boundary, not a formally approved scope.
The source contains nine editions, 348 matches, 44 participants and 1,081 goals;
checksum, fixture inventory and duplicate checks pass. Ten fixtures across all nine
editions are corroborated, and representative team totals are independently recalculated.
Full independent historical accuracy has not been established for every fixture.
Separate websites do not establish independent lineage. Regulation-time splits and
shootout information are outside the current dataset. Historical validation does not
establish current development or production database contents.

| Decision | Current implemented behavior | Supporting evidence | Proposed outcome | Approval status | Impact on Task 7 |
| --- | --- | --- | --- | --- | --- |
| Recorded-score W/D/L | Compare oriented final scores; tied scores are draws | Section G; `TeamRepository.summary`; calculation examples | Accept | Wesley PENDING; Mehla PENDING | Preserve calculations |
| Extra-time goals | Included in recorded scores | Source schema; ledger D05; Germany 2003 example | Include | Wesley PENDING; Mehla PENDING | Preserve score basis |
| Penalty shootouts | Excluded from scores and W/D/L; no winner inferred | Ledger D04; USA 1999 and Japan 2011 examples | Exclude | Wesley PENDING; Mehla PENDING | Preserve draw semantics |
| Tournament appearances | Count distinct matching competition editions | Repository aggregate; section G | Count each matching edition once | Wesley PENDING; Mehla PENDING | Preserve filtered count |
| Competition/date filters | Apply World Cup scope, competition and inclusive dates to every aggregate | Repository filters; API documentation | Apply consistently to all aggregates | Wesley PENDING; Mehla PENDING | Preserve query contract |
| Missing-data coverage | `available_records_only` / `no_matching_records`; empty results do not prove nonparticipation | Service and response schema; section H | Preserve conservative labels | Wesley PENDING; Mehla PENDING | Preserve response semantics |
| Historical validation | Pinned-source verification plus bounded comparisons; API aggregates available imported records | Sections D/E; edition matrix; calculation evidence | Accept bounded source-backed scope above | Wesley PENDING; Mehla PENDING | No completeness claim or code change |
| D02/D10 | Venue is not an aggregate input; unknown older disputes cannot be evaluated | Ledger D02/D10, including required closure evidence | Defer; retain explicitly unresolved limitations pending disposition | Wesley PENDING; Mehla PENDING | No demonstrated correction; reassess only if new evidence affects statistics |

D02 venue certification is proposed for exclusion from basic-results acceptance.
For D10, reviewers must recover the original evidence or explicitly exclude the
unauditable old comparison claim from acceptance. Deferral does not resolve either
finding. Shared acceptance of this table also records the required Task 7 coordination.

Wesley's instruction explicitly authorizes this local implementation and verification
and requires preserving the dataset/API. That authorization is not acceptance of
the definitions or waiver of validation gaps. No explicit Mehla approval was found
in the reviewed requirements. Do not infer approval from `approved_pinned_basic_results`
in the old regression artifact; that flag has an earlier, narrower contract scope.

## K. Deliverables and remaining work

Modified tracked documentation (combined Prompts 1–3):

- `data/verification/README.md`: links current evidence and canonical report;
  distinguishes the dated 2023 import observation from uninspected current databases.
- `data/README.md`: similarly qualifies historical database state and environment differences.
- `docs/service/task2-acceptance.md`: explicitly labels preserved 2023-only report.

New local files:

- `docs/service/task2-phase2-acceptance.md`: this canonical report.
- `data/verification/task2-historical-comparisons.md`: ten-fixture comparison,
  nine-edition matrix, source assessment and discrepancy ledger.
- `data/verification/task2-calculations.md`: method, totals and read-only reproduction.
- `data/verification/task2-team-calculations.csv`: 126 traced example contributions.

Remaining acceptance work is the explicit decisions in section J. If the reviewers
require historical completeness independent of the pinned source or certified
venues, scope and execute that additional validation; the current sample cannot
substitute for it. Do not manufacture an old ledger or mark D02/D10 resolved to
obtain completion. No backend rewrite, reimport or baseline regeneration is
justified by this review. No additional test code is needed for a documentation-only
change; existing tests plus the separate CSV calculation cover the demonstrated work.

## L. Final technical verdict

**TECHNICALLY READY FOR ACCEPTANCE — bounded basic-results scope; human approval
pending.** P1 is fully specified as proposed; P2 now has reproducible source checks,
all-edition sampling, traceable comparisons, discrepancy dispositions and independent
arithmetic. Unknown older discrepancies remain visible and are not certified away.
Task 2 remains open until reviewers explicitly accept the documented scope and
limitations or request the additional validation required for a broader claim.
