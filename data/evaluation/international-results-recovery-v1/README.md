# Historical results recovery v1 — 1991–2023

## A. Implementation summary

Opt-in recovery improves rating-complete coverage from **320/348 (91.95%) to 340/348 (97.70%)**: 20 recovered cases, eight remaining. All nine editions and all 348 canonical matches and regulation labels are retained. This is rating coverage, not forecasting accuracy. No Star Power/Clutch package was supplied: strict and empty retrospective evaluations remain entirely excluded, with no accuracy result. The 1991 80-minute model restriction remains.

The original 11,650-row source, full evidence package, 2023 pilot, calculator, prediction model and Monte Carlo code are unchanged. The overlay adds 69 unique, reviewed observations (11,719 merged rows). Host-country orientation is normalized explicitly in new records; it never repairs or replaces original rows.

In Analytics select **Full World Cup Evidence — 1991–2023**, then **Historical results → Reviewed recovery additions v1**. Original results remain the default. API selection: `{"dataset_id":"womens-world-cup-full-v1","recovery_package_id":"international-results-recovery-v1","limit":348}`. Unknown packages and recovery on other datasets are rejected. Response echoes selection and gives case-level overlay and population provenance.

## B. Files changed

`.gitattributes` preserves checksum-pinned recovery bytes across platform checkouts.

Service implementation: `src/football/results_recovery.py`, `src/services/evaluation_recovery.py`, `src/services/evaluation.py`, `src/schemas/evaluation/request.py`, `src/schemas/evaluation/response.py`. Offline builder: `scripts/evaluation/build_recovery.py`. Tests: `tests/unit/services/test_evaluation_recovery.py`, `tests/integration/routers/test_evaluation_full.py`, and the intentional OpenAPI fingerprint in `tests/unit/schemas/contract_fingerprints.json`.

New evidence directory: `data/evaluation/international-results-recovery-v1/`: this README, `overlay.json`, `ratings.json`, `coverage.json`, `manifest.json`, and four attributed source snapshots (`sources/brazil.html`, `sources/ecuador.html`, `sources/ghana.html`, `sources/southafrica.html`).

App: `src/features/analytics/domain/backtesting.ts`, `backtesting.test.ts`; `src/features/analytics/components/backtesting-panel.tsx`, `backtesting-panel.test.tsx`; `tests/e2e/backtesting.normalized.spec.ts`.

## C. Approved fixtures

Each row below is one addition, counted once even when it influences many cases. Exact per-fixture status, identity mapping, location, neutral flag, score review, source IDs and orientation decisions are in `overlay.json`. Scores include extra time when recorded, exclude shootouts, and are never added as new World Cup regulation labels. Ghana–Russia on 1994-09-09 is explicitly 2–1 after extra time (1–1 regulation). Other approved rows have no extra-time/shootout annotation.

| Date | Home | Away | Final | Venue country | Source IDs |
|---|---|---|---|---|---|
| 1991-04-02 | Bulgaria | United States | 0–3 | Bulgaria | usa |
| 1991-04-03 | United States | Hungary | 6–0 | Bulgaria | usa |
| 1991-04-05 | United States | France | 2–0 | Bulgaria | usa |
| 1991-04-07 | United States | Russia | 5–0 | Bulgaria | usa |
| 1991-05-18 | France | United States | 0–4 | France | usa |
| 1991-05-25 | United States | England | 3–1 | France | usa |
| 1991-05-28 | Netherlands | United States | 4–3 | Netherlands | usa |
| 1991-05-30 | Germany | United States | 2–4 | Germany | usa |
| 1991-06-05 | Denmark | United States | 1–0 | Denmark | usa |
| 1991-08-04 | China | United States | 2–1 | China | usa |
| 1991-08-08 | China | United States | 2–2 | China | usa |
| 1991-08-10 | China | United States | 0–3 | China | usa |
| 1991-08-30 | United States | Norway | 0–1 | United States | usa |
| 1991-09-01 | United States | Norway | 1–2 | United States | usa |
| 1991-10-04 | United States | China | 1–2 | United States | usa |
| 1991-10-12 | United States | China | 2–0 | United States | usa |
| 1993-05-30 | South Africa | Eswatini | 14–0 | South Africa | southafrica |
| 1993-10-23 | Zimbabwe | South Africa | 1–2 | Zimbabwe | southafrica |
| 1993-10-24 | Zimbabwe | South Africa | 0–8 | Zimbabwe | southafrica |
| 1994-04-20 | Australia | Russia | 1–2 | Australia | australia.pdf |
| 1994-04-23 | Australia | Russia | 1–1 | Australia | australia.pdf |
| 1994-08-12 | Russia | Australia | 0–3 | Russia | australia.pdf |
| 1994-08-27 | Russia | Ghana | 2–1 | India | ghana |
| 1994-08-31 | Ghana | New Zealand | 3–0 | India | ghana |
| 1994-09-04 | Ghana | Bulgaria | 5–1 | India | ghana |
| 1994-09-06 | Ghana | Hungary | 4–1 | India | ghana |
| 1994-09-09 | Ghana | Russia | 2–1 | India | ghana |
| 1994-09-27 | Japan | Australia | 2–2 | Japan | australia.pdf |
| 1995-03-17 | Australia | New Zealand | 4–0 | Australia | australia.pdf |
| 1995-03-19 | Australia | New Zealand | 2–0 | Australia | australia.pdf |
| 1995-04-10 | Australia | Argentina | 7–0 | Brazil | australia.pdf |
| 1995-04-11 | Brazil | Argentina | 4–1 | Brazil | brazil |
| 1995-05-11 | Canada | Australia | 3–0 | Canada | australia.pdf |
| 1995-05-12 | United States | Brazil | 3–0 | United States | usa, brazil |
| 1995-05-13 | Canada | Australia | 0–3 | Canada | australia.pdf |
| 1995-05-14 | United States | Brazil | 4–1 | United States | usa, brazil |
| 1995-05-18 | Scotland | Australia | 0–0 | Scotland | australia.pdf |
| 1995-05-19 | United States | Canada | 9–1 | United States | canada, usa |
| 1995-05-27 | Sweden | Australia | 5–0 | Sweden | australia.pdf |
| 1998-10-10 | Ghana | Egypt | 4–0 | Ghana | ghana |
| 1999-02-14 | Turkey | Germany | 1–12 | Turkey | dfb1999 |
| 1999-03-06 | China | Ghana | 2–1 | China | ghana |
| 1999-03-09 | China | Ghana | 2–1 | China | ghana |
| 1999-03-25 | Germany | China | 0–3 | Germany | dfb1999 |
| 1999-03-28 | Germany | China | 4–1 | Germany | dfb1999 |
| 1999-04-22 | Germany | Denmark | 3–1 | Germany | dfb1999 |
| 1999-05-15 | Nigeria | Ghana | 2–1 | Nigeria | ghana |
| 1999-05-26 | Germany | Switzerland | 2–0 | Germany | dfb1999 |
| 1999-05-30 | Germany | France | 4–1 | Germany | dfb1999 |
| 1999-06-03 | Germany | Netherlands | 2–0 | Germany | dfb1999 |
| 2007-07-19 | Australia | New Zealand | 3–0 | Australia | australia.pdf |
| 2007-07-22 | Australia | New Zealand | 1–0 | Australia | australia.pdf |
| 2010-09-15 | Germany | Canada | 5–0 | Germany | dfb2011 |
| 2010-10-28 | Germany | Australia | 2–1 | Germany | dfb2011 |
| 2010-11-25 | Germany | Nigeria | 8–0 | Germany | dfb2011 |
| 2011-05-21 | Germany | North Korea | 2–0 | Germany | dfb2011 |
| 2011-06-03 | Germany | Italy | 5–0 | Germany | dfb2011 |
| 2011-06-07 | Germany | Netherlands | 5–0 | Germany | dfb2011 |
| 2011-06-16 | Germany | Norway | 3–0 | Germany | dfb2011 |
| 2014-09-11 | Ecuador | Peru | 1–0 | Ecuador | ecuador |
| 2014-09-13 | Ecuador | Venezuela | 1–0 | Ecuador | ecuador |
| 2014-09-17 | Ecuador | Colombia | 0–1 | Ecuador | ecuador |
| 2014-09-19 | Ecuador | Uruguay | 1–2 | Ecuador | ecuador |
| 2014-09-24 | Ecuador | Brazil | 0–4 | Ecuador | ecuador |
| 2014-09-26 | Ecuador | Colombia | 1–2 | Ecuador | ecuador |
| 2014-09-28 | Ecuador | Argentina | 3–2 | Ecuador | ecuador |
| 2014-11-08 | Ecuador | Trinidad and Tobago | 0–0 | Ecuador | ecuador |
| 2014-12-02 | Trinidad and Tobago | Ecuador | 0–1 | Trinidad and Tobago | ecuador |
| 2015-03-03 | Spain | New Zealand | 2–2 | Spain | rfef2015 |

## D. Rejected or unresolved evidence

- Brazil-Australia April 1995: Unresolved dates: official Australia guide April 15/17 vs RSSSF Brasil April 13/16; exclude both matches.
- USA-Australia January 1995: Official guide lists January 20/23; USA archive has no January 1995 matches. Classification/date corroboration unresolved; exclude.
- Egypt-Ghana September 1998: Approximate date (~26 September), not an exact cutoff-safe observation.
- USA-Yugoslavia 1991-04-01: Historical federation identity not approved against modern successor labels; excluded pending identity review.
- Nigeria-China 1999-06-12: Search lead reports 4-3; venue/classification and authoritative evidence not verified, excluded.
- Brazil 1991: All eight pre-World-Cup senior A results already in original; club/state/unofficial selections not accepted.
- Nigeria 1991: No verified pre-November-1990 senior results recovered; frozen baseline remains a cold start.
- Canada PDF: Requested PDF returned 404; replaced with official match 432 and corroborating USA archive.

Brazil’s eight approved pre-1991-World-Cup internationals were already present; exhibitions against clubs or regional selections cannot fill the Form gap. Nigeria’s pre-1991 reference population remains absent. The 1993 South African results establish reference membership for Nigeria’s 1995 opponents, without lowering eligibility requirements. Historical Swaziland maps explicitly to the original source’s Eswatini identity. No other original identity was rewritten. The unresolved Nigeria–China 1999 lead is not an approved observation; search results alone do not establish venue and classification.

## E. Coverage across all editions

| Edition | Matches | Complete before | Complete after | Newly complete | Remaining |
|---|---:|---:|---:|---:|---:|
| 1991 | 26 | 19 | 20 | 1 | 6 |
| 1995 | 26 | 19 | 26 | 7 | 0 |
| 1999 | 32 | 26 | 30 | 4 | 2 |
| 2003 | 32 | 32 | 32 | 0 | 0 |
| 2007 | 32 | 31 | 32 | 1 | 0 |
| 2011 | 32 | 29 | 32 | 3 | 0 |
| 2015 | 52 | 48 | 52 | 4 | 0 |
| 2019 | 52 | 52 | 52 | 0 | 0 |
| 2023 | 64 | 64 | 64 | 0 | 0 |
| **Total** | **348** | **320** | **340** | **20** | **8** |

All editions retain the publication-availability warning. Disputed April 1995 Brazil–Australia dates remain excluded. The existing original regulation-label discrepancies remain recorded in the unchanged full evidence package. A recovered team can change the fitted reference population and percentiles for already complete teams; there is no claim that only incomplete participants change.

## F. All 28 original gaps and remaining failures

M = matches in `(cutoff − 1461 days, cutoff]`; F = observations in `(cutoff − 365 days, cutoff]` whose **both** teams exist in the fit frozen at `cutoff − 365 days`. O/D requires M ≥ 8 and last match within 730 days; Form additionally requires F ≥ 3. Both reference fits require at least 20 global observations. Fitting, shrinkage and percentile normalization are unchanged.

| Match ID | Edition / cutoff | Originally deficient team | M before→after | F before→after | Remaining failure |
|---|---|---|---|---|---|
| 3 | 1991 / 1991-11-16 | Brazil | 8→8 | 0→0 | fewer_than_three_qualifying_form_matches |
| 4 | 1991 / 1991-11-16 | United States | 18→34 | 1→16 | None |
| 5 | 1991 / 1991-11-16 | Nigeria | 6→6 | 0→0 | fewer_than_eight_matches, fewer_than_three_qualifying_form_matches |
| 10 | 1991 / 1991-11-18 | Brazil | 9→9 | 1→1 | fewer_than_three_qualifying_form_matches |
| 10 | 1991 / 1991-11-18 | United States | 19→35 | 2→17 | None |
| 11 | 1991 / 1991-11-18 | Nigeria | 7→7 | 0→0 | fewer_than_eight_matches, fewer_than_three_qualifying_form_matches |
| 16 | 1991 / 1991-11-20 | Brazil | 10→10 | 2→2 | fewer_than_three_qualifying_form_matches |
| 17 | 1991 / 1991-11-20 | Nigeria | 8→8 | 0→0 | fewer_than_three_qualifying_form_matches |
| 28 | 1995 / 1995-06-04 | Brazil | 8→11 | 1→3 | None |
| 29 | 1995 / 1995-06-05 | Nigeria | 11→11 | 2→4 | None |
| 30 | 1995 / 1995-06-05 | Canada | 7→10 | 4→7 | None |
| 32 | 1995 / 1995-06-05 | Australia | 4→15 | 4→12 | None |
| 34 | 1995 / 1995-06-06 | Brazil | 9→12 | 2→4 | None |
| 38 | 1995 / 1995-06-07 | Australia | 5→16 | 5→13 | None |
| 43 | 1995 / 1995-06-09 | Australia | 6→17 | 6→14 | None |
| 57 | 1999 / 1999-06-19 | Nigeria | 5→6 | 2→3 | fewer_than_eight_matches |
| 58 | 1999 / 1999-06-19 | Germany | 24→31 | 2→9 | None |
| 60 | 1999 / 1999-06-19 | Ghana | 6→10 | 2→6 | None |
| 64 | 1999 / 1999-06-22 | Ghana | 7→11 | 3→7 | None |
| 65 | 1999 / 1999-06-23 | Nigeria | 6→7 | 3→4 | fewer_than_eight_matches |
| 73 | 1999 / 1999-06-26 | Nigeria | 7→8 | 4→5 | None |
| 123 | 2007 / 2007-09-11 | New Zealand | 8→10 | 2→4 | None |
| 150 | 2011 / 2011-06-25 | Germany | 36→43 | 0→7 | None |
| 158 | 2011 / 2011-06-29 | Germany | 37→44 | 1→8 | None |
| 165 | 2011 / 2011-07-04 | Germany | 38→45 | 2→9 | None |
| 185 | 2015 / 2015-06-07 | Ecuador | 0→9 | 0→9 | None |
| 189 | 2015 / 2015-06-08 | Spain | 26→27 | 2→3 | None |
| 197 | 2015 / 2015-06-11 | Ecuador | 1→10 | 1→10 | None |
| 209 | 2015 / 2015-06-15 | Ecuador | 2→11 | 2→11 | None |

Remaining IDs: **3, 5, 10, 11, 16, 17, 57, 65**. Brazil (3, 10, 16) still lacks three qualifying Form matches; Chile/Venezuela are missing from the frozen reference. Nigeria (5, 11, 17) has no frozen-baseline team membership; its first two cases also have fewer than eight matches. Nigeria (57, 65) has qualifying Form after the Ghana recovery but only six/seven matches in the four-year window.

`coverage.json` provides every one of the 348 cases, both participants, exact M/F counts, previous and recovered ratings, frozen dates, missing reference-team names, excluded Form fixtures, threshold reasons, and changes for previously complete participants. Original-gap investigation is therefore inspectable even when a team becomes complete.

## G. Reconstruction and hashes

All **137 complete populations** were rebuilt with the existing calculator. **112** population rating hashes changed; 25 remained identical. **200** previously complete cases have at least one changed participant rating/evidence record. The exact dates, IDs and before/after values are in `coverage.json`. `ratings.json` contains every team, including ineligible teams, not just World Cup participants.

All source rows are merged and sorted by date/home/away using the original ordering semantics. Unordered date/team identities reject reversed duplicates and conflicting scores or neutrality. Fits receive only rows at or before the previous-day cutoff. `recovered_fixture_ids` lists additions in the union of the main and frozen-reference windows (last 1826 days); the source population hash includes **all** prior source rows as in the original pipeline.

Rebuild offline (no network/database access): `PYTHONPATH=src .venv/bin/python -B scripts/evaluation/build_recovery.py`. Review hashes before changing the runtime approval pin. Runtime validates the original package, overlay, attributed snapshots, merged source and every cutoff population.

| Artifact | SHA-256 |
|---|---|
| overlay.json | `8e80eeea6cc3d6bd10ec4b26e966e6cb7376d4037a5ebd6e88155e3e3df23b61` |
| ratings.json | `5034b17ff458be1495da893f5f95be875ca25f9b7cc8598a84121973dd0490fa` |
| coverage.json | `5bb5658f21aa91b40921d88dbe10377c0977968783ef9fd176586f3029be2ae4` |
| manifest.json | `45593e9139180f48ec931846d6316f62dfc975386c28c58167c0e737f42ce31b` |
| Merged Result records (canonical JSON) | `22259e986df3cbf5970eea96a4ea4a884dad06ca5846d904da73f1d65237df85` |
| Original source (unchanged) | `de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0` |

## H. Source provenance and rights

Modern retrieval does not prove historical pre-match publication. Every addition retains `availability: unverified`; the package retains `historical_availability_verified: false`. Event date, current retrieval (2026-11-16), archive revision, and known publication date are separate. Compilation dates not documented are explicitly null. RFEF’s 2015-03-03 publication is recorded, but no package-wide availability inference is made. Official source documents and SASH prose/media are not redistributed; only structured result facts and checksums are included. Four RSSSF snapshots are retained under their explicit attributed-copying notices. These archives are not claimed to be independent of the original source’s upstream feeds.

- **dfb2011**: [German Football Association](https://datencenter.dfb.de/competitions/laenderspiel-1066/seasons/2010-2011). Revision: 2010/11 season; publication date unknown. Original downloaded bytes SHA-256: `3510bcba7444c16e990c795b0a221673ad187b40b63859d9f684e535fdbae850`.
- **dfb1999**: [German Football Association](https://datencenter.dfb.de/competitions/laenderspiel-1066/seasons/1998-1999). Revision: 1998/99 season; publication date unknown. Original downloaded bytes SHA-256: `46c85cce4931990c3fae4b2eb57496e3b1a5de0e4ed9bb2cfdf11944f6f97c24`.
- **rfef2015**: [Royal Spanish Football Federation](https://rfef.es/es/noticias/cronica-tablas-primer-amistoso-frente-nueva-zelanda-2-2). Revision: 2015-03-03. Original downloaded bytes SHA-256: `4b5ebc972a8f794ad0fd377e19e4397c66e01c24b06e70b111c1a8a6140f7a92`.
- **canada**: [Canada Soccer](https://canadasoccer.com/match/432/). Revision: Match 432; publication date unknown. Original downloaded bytes SHA-256: `c893ab8d1d2aaf57d64988370fe80b44387d346362bb6e4167f5d1989e1a13ee`.
- **australia.pdf**: [Football Australia](https://matildas.com.au/sites/default/files/2024-06/CommBank%20Matildas%20-%20Official%20Media%20Guide%20FWWC2023%20%281%29.pdf). Revision: FWWC2023 media guide; June 2024 upload path. Original downloaded bytes SHA-256: `91bed8554201631a2ec0ccea9e4132eb6fae9d0aa8d7ca4202206447fd60d64c`.
- **ecuador**: [RSSSF / Roberto Di Maggio](https://www.rsssf.org/tabless/sam-women2014.html). Revision: 2024-08-29. Original downloaded bytes SHA-256: `d8b27fac4ad966909d12b12dc75210315e24bc7bcf255b56b314ab4235fa1417`.
- **brazil**: [RSSSF Brasil / Marcelo Leme de Arruda](https://rsssfbrasil.com/sel/brazilaw.htm). Revision: 2026-10-13. Original downloaded bytes SHA-256: `681dbf3bed49e77bd5552406ff129b33bb05447b6763ea5b0008cd2122173c50`.
- **ghana**: [RSSSF / Martin Neu](https://www.rsssf.org/tablesg/gha-wom-intres.html). Revision: 2024-02-20. Original downloaded bytes SHA-256: `c105242625c5f10e2e48e121b744849ade2002f3f5fa09b0fdaba388d4014c80`.
- **usa**: [Society for American Soccer History / David Litterer](https://www.ussoccerhistory.org/ASHA/ASHA/usawomen.html). Revision: All-time archive through 2014; publication date unknown. Original downloaded bytes SHA-256: `92e797d5a373dfa77aafac32fd96dca667654eeb50a93e13716eb80a1956803d`.
- **southafrica**: [RSSSF / Sebastien Duret](https://www.rsssf.org/tablesz/zaf-wom-intres.html). Revision: 2003-11-05. Original downloaded bytes SHA-256: `2884bda11ed2887018fa1dfe25805382b05927c3d75acb31bc208994219dcf04`.

## I. Verification

`make certify`: **1,834 passed, 0 failed**. Combined coverage **95.334724%** (required 95%); statements 96.386974%, branches 91.181989%. Ruff, formatting (245 files), strict Mypy (97 source files), and owned resource cleanup passed. The full suite independently recalculated all 137 recovered populations, verified every cutoff/source hash, exercised strict/retrospective separation and the existing Monte Carlo regressions, and checked read-only HTTP evaluation against a disposable full catalog. A separate targeted run passed 65 tests; these are included in the certification count.

Final isolated frontend workflow (`python3 scripts/test-normalized.py`): **435 unit/component tests passed**, **35 normalized browser tests passed**, **9 Home/Demo browser tests passed**, **0 failures**. TypeScript, production build and cleanup passed. ESLint had zero errors and three pre-existing warnings in unchanged About/Project/Home files. The recovery browser test checked all 348 real cases, 340 complete ratings, zero strict eligibility, no accuracy, deterministic replay, empty retrospective exclusions and invalidation when switching sources. Initial new UI fixture tests were corrected to use the existing one-case fixture with a one-case request; all final tests passed.

## J. Database preservation

Canonical database baseline was captured read-only before implementation. No canonical database migrations or writes were performed. Disposable test imports are confined to owned test databases. The following before/after counts and SHA-256 fingerprints are identical. Fingerprint method: SHA-256 of JSON-encoded, lexicographically sorted `row_to_json(t)::text` result tuples, queried in a read-only transaction.

| Table | Count before = after | Content SHA-256 before = after |
|---|---:|---|
| matches | 348 | `5bbe9c69d840f15e425080ea8c9168eb09070a450c145a49864821824065bba5` |
| competitions | 9 | `e5644f1fa058ac1d2a05dca4fd5a3ffeeb86cb8ae9936536883d7d3f7908ac73` |
| teams | 44 | `8dec28a6f861bca1afdd2309b2168801eae87822f5dd99c83f4ca46eaf541530` |
| ranking_releases | 96 | `537be0c5774d58e6ecb98f496bb9523ac3833e18c7a32d7a5b3c0638c1770c1e` |
| ranking_observations | 16525 | `9bd708d2dbd142c7f1f5c5d1a230d0ec7a5e8de48c659a4022b4bb919edaf7e9` |
| fifa_team_mappings | 44 | `f2fe7036c527193cfce0f149d7c880054f9541b741a15d98d1ef4c0fc17de07e` |
| rating_runs | 1 | `50504dcc4f4e5649182b538f38b44b0a8344e794f69523db8699dcf36af0ec6d` |
| team_ratings | 44 | `f687088ef79e9265f90f11bb242f1949311ba623403dc69b72f18a41aba84cbd` |
| scenarios | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| predictions | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

## K. Git state

Both repositories remain on `member/wes-v2`. Service HEAD: `396eedbb0107d87c81d466cb860d07c13b1f3334`. App HEAD: `799740f8ec7807d3b6798845879d5506e44d93ae`. Changes intentionally remain uncommitted; no branch switching, reset, stash, merge, rebase, commit or push. Local and remote branch heads were rechecked against these baselines. Both working trees contain only the intended uncommitted implementation. Temporary research downloads, test reports, caches and browser artifacts are outside the intended Git change set.

## L. Remaining blockers

Eight rating gaps remain evidence-limited. Resolving disputed or unidentified fixtures requires better source evidence, not threshold relaxation. All strict historical forecasts still lack sufficient Star Power/Clutch and source-publication evidence. No caller-supplied retrospective assumption package exists. The 1991 80-minute model remains unvalidated. This work does not establish predictive accuracy or calibration.


### Service: exact changed/untracked file inventory

- `.gitattributes`
- `data/evaluation/international-results-recovery-v1/README.md`
- `data/evaluation/international-results-recovery-v1/coverage.json`
- `data/evaluation/international-results-recovery-v1/manifest.json`
- `data/evaluation/international-results-recovery-v1/overlay.json`
- `data/evaluation/international-results-recovery-v1/ratings.json`
- `data/evaluation/international-results-recovery-v1/sources/brazil.html`
- `data/evaluation/international-results-recovery-v1/sources/ecuador.html`
- `data/evaluation/international-results-recovery-v1/sources/ghana.html`
- `data/evaluation/international-results-recovery-v1/sources/southafrica.html`
- `scripts/evaluation/build_recovery.py`
- `src/football/results_recovery.py`
- `src/schemas/evaluation/request.py`
- `src/schemas/evaluation/response.py`
- `src/services/evaluation.py`
- `src/services/evaluation_recovery.py`
- `tests/integration/routers/test_evaluation_full.py`
- `tests/unit/schemas/contract_fingerprints.json`
- `tests/unit/services/test_evaluation_recovery.py`

### App: exact changed/untracked file inventory

- `src/features/analytics/components/backtesting-panel.test.tsx`
- `src/features/analytics/components/backtesting-panel.tsx`
- `src/features/analytics/domain/backtesting.test.ts`
- `src/features/analytics/domain/backtesting.ts`
- `tests/e2e/backtesting.normalized.spec.ts`
