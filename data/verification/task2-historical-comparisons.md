# Task 2 historical comparisons and discrepancy ledger

Review date: **2026-11-13**. Base: `member/wes`,
`27df1e5ab55fa3223a3b9509e6578a94bf0152ad`.
This is new evidence, not a rewrite of `womens-world-cup-coverage.json`.
Human acceptance remains pending. “Verified” below means checked during this
technical review with Codex assistance, not signed off by Wesley or Mehla.

## Method and limits

Bounded selection: the nine finals, plus the previously reviewed Panama–France
2023 fixture. This preserves the five earlier examples and adds one final for
each previously unrepresented edition (1991, 1995, 2007, 2015, 2019).
Read the exact pinned CSV, locate by date and participant pair, then compare the
participant-to-score mapping against the linked record, separately from order,
city and shootout outcome. Observe source conflicts rather than voting by website
count. All ten dates, pairs and recorded scores were corroborated; this is a
purposive sample, not random sampling or proof of accuracy for the other 338.

All URLs below were consulted on the review date. DFB's 1995 page initially loaded
through web access, then timed out on repeated detailed reads; a direct Python
`urllib.request.urlopen(url, timeout=20)` read succeeded and exposed the fixture
header, date, score and Solna venue. No credentials were used. The FIFA 2011 video
page exposed its score in the page title; UEFA's readable match report supplies
the date and extra-time detail. No video-content review is claimed.

| Source | Authority / maintenance | Independence and permitted use |
| --- | --- | --- |
| [Pinned Mart Jürisoo README][upstream] | Dataset author's schema and attribution | Defines source semantics, not independent accuracy. Lists Wikipedia, FIFA, RSSSF and national associations as inputs. |
| FIFA match reports / retrospective articles | Tournament organizer; separately published records | Authoritative corroboration of stated facts; may be an upstream ancestor of the CSV. No proven independent data lineage. |
| DFB, U.S. Soccer, FFF, RFEF | National associations publishing match records/reports | Authoritative institutional records; maintenance is separate, ancestry of individual CSV facts is unknown. |
| UEFA reports | Continental governing body | Authoritative corroboration, not infallible: D08 records a retrospective-table error. |
| [RSSSF 1995][rsssf95] and older references in coverage JSON | Specialist compilation maintained by named contributors | Separately maintained, but expressly a possible upstream input. Useful cross-check; not lineage-independent certification. Only the 1995 final was freshly compared here. |
| [Pinned Hudl open-data directory][hudl] | Separate provider repository cited by earlier audit | Old comparison has no recovered fixture ledger. Web retrieval was restricted; no new Hudl verification or proven independence is claimed. |

The prior all-348 comparison is retained as historical reported evidence only.
No edition is classified **independently complete**. Here **pinned-source verified**
means agreement with manifests, checksum and recorded fingerprints;
**independently corroborated** means the specific facts in the sample were checked
against separately published authoritative records, not proven independent lineage.

## Exact sample observations

CSV line numbers include the header as line 1. “Home–away” is source column order,
not a certification of home advantage. Country and neutral are recorded here for
traceability; their correctness was not exhaustively validated.

| ID / edition / CSV line | Date; pinned home–away; score | Pinned city / country / neutral | Comparator observation and evidence | Finding |
| --- | --- | --- | --- | --- |
| S91 / 1991 / 617 | 1991-11-30; Norway–United States; 1-2 | Guangzhou / China / TRUE | [DFB][dfb91]: same date, Norway 1-2 USA, Tianhe Stadium, Guangzhou | Date, pair, scores agree; USA naming variation. |
| S95 / 1995 / 871 | 1995-06-18; Germany–Norway; 0-2 | Solna / Sweden / TRUE | [DFB][dfb95]: same date, Germany 0-2 Norway, Råsunda Stadion, Solna. [RSSSF][rsssf95], Final: June 18, Norway 2-0 Germany, Stockholm | Scores agree after reversing order; venue terminology requires qualification (D02). |
| S99 / 1999 / 1455 | 1999-07-10; United States–China; 0-0 | Pasadena / United States / FALSE | [FIFA][fifa99], summary: same date, USA 0-0 China PR; shootout 5-4. Summary labels Rose Bowl, Los Angeles; body locates Rose Bowl in Pasadena | Recorded score agrees; D03/D04 address names, venue and missing shootout. |
| S03 / 2003 / 2291 | 2003-10-12; Germany–Sweden; 2-1 | Carson / United States / TRUE | [FIFA][fifa03], summary: same date, Germany 2-1 Sweden, Home Depot Center, Carson; winning goal at 98 minutes | Extra-time-inclusive score agrees; D05/D08. |
| S07 / 2007 / 3289 | 2007-09-30; Germany–Brazil; 2-0 | Shanghai / China / TRUE | [FIFA][fifa07], summary: same date, Germany 2-0 Brazil, Shanghai Hongkou Football Stadium | Date, pair, scores and city agree. |
| S11 / 2011 / 4428 | 2011-07-17; Japan–United States; 2-2 | Frankfurt / Germany / TRUE | [UEFA][uefa11]: same date, Japan 2-2 US after extra time, shootout 3-1, Frankfurt. [FIFA video title][fifa11] agrees on both scores | Draw under recorded-score rule; shootout winner is distinct (D04). |
| S15 / 2015 / 5814 | 2015-07-05; United States–Japan; 5-2 | Vancouver / Canada / TRUE | [U.S. Soccer][uss15], opening paragraph: same date, USA 5-2 Japan, BC Place, Vancouver | Date, pair, scores and city agree. |
| S19 / 2019 / 7590 | 2019-07-07; United States–Netherlands; 2-0 | Décines-Charpieu / France / TRUE | [UEFA][uefa19], Final: July 7, United States 2-0 Netherlands, Lyon. [FIFA][fifa19venue] identifies Stade de Lyon; [UEFA venue profile][lyon] places it in Décines-Charpieu | Scores agree; geographic representation supported (D06). |
| S23F / 2023 / 9481 | 2023-08-20; Spain–England; 1-0 | Sydney / Australia / TRUE | [FIFA PDF][fifa23], page 1: same date, Spain 1-0 England, final match 64, Stadium Australia. [RFEF][rfef23] explicitly associates venue with Sydney | Date, pair, scores and city agree. |
| S23P / 2023 / 9460 | 2023-08-02; Panama–France; 3-6 | Sydney / Australia / TRUE | [FFF match record][fffmatch]: August 2, Panama 3-6 France, Sydney. [FFF article][fffarticle] opening and group schedule agree, but technical sheet says August 23 | Source result corroborated; comparator date error recorded in D09. |

## Edition coverage matrix

Counts and full-row fingerprints freshly checked by the existing source verifier.
Expected match counts come from the pinned manifests, not a new independent census.
Fingerprints below show identifying prefixes; exact 64-character values are in
[the unchanged coverage artifact](womens-world-cup-coverage.json).
“0 errors” means no confirmed defect in pinned facts found; it is not a claim
that every unsampled fact was independently verified.

| Edition | Expected / selected fixtures | Teams | Goals | Duplicate pairs | Fingerprint result (prefix) | Checked fixtures / source | Confirmed differences / unresolved |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| 1991 | 26 / 26 | 12 | 99 | 0 | PASS `8fa9e3354aa9` | 1 / DFB | USA label; 0 errors; legacy scope unknown |
| 1995 | 26 / 26 | 12 | 99 | 0 | PASS `2ba7be5e888c` | 1 / DFB, RSSSF | Reversed order D01; venue D02 unresolved; 0 errors |
| 1999 | 32 / 32 | 16 | 123 | 0 | PASS `ede2c431addc` | 1 / FIFA | Names/venue D03, shootout D04; 0 errors; legacy scope unknown |
| 2003 | 32 / 32 | 16 | 107 | 0 | PASS `6e0a7075c62b` | 1 / FIFA | Missing split D05; comparator error D08; 0 pinned errors |
| 2007 | 32 / 32 | 16 | 111 | 0 | PASS `7019aeed543f` | 1 / FIFA | 0 observed mismatches; legacy scope unknown |
| 2011 | 32 / 32 | 16 | 86 | 0 | PASS `f415846e9e19` | 1 / UEFA, FIFA | Shootout/split D04/D05; 0 errors; legacy scope unknown |
| 2015 | 52 / 52 | 24 | 146 | 0 | PASS `09b8cbb41979` | 1 / U.S. Soccer | USA label; 0 errors; legacy scope unknown |
| 2019 | 52 / 52 | 24 | 146 | 0 | PASS `1b8cb3d6ee73` | 1 / UEFA, FIFA | City representation D06; 0 errors; legacy scope unknown |
| 2023 | 64 / 64 | 32 | 164 | 0 | PASS `1716fb38bdcc` | 2 / FIFA, RFEF, FFF | Comparator date error D09; 0 pinned errors; legacy scope unknown |
| Total | 348 / 348 | 44 distinct | 1,081 | 0 | Full-source checksum PASS | 10 distinct fixtures | No confirmed pinned-data error; D02/D10 remain open |

Every edition is pinned-source verified with an authoritative corroborated sample.
Common limitations: small final-heavy sample; no independent full-edition census;
no proof of independent lineage; no blanket venue/neutral or missing-field
certification. D07 is source-wide; D10 cannot be assigned to particular editions
or counted as a known number of conflicting fixtures.

## Discrepancy ledger

### D01 — score-preserving reversal (representation)

- **Fixture:** S95, 1995-06-18, Germany / Norway, CSV line 871.
- **Pinned value:** home Germany 0; away Norway 2.
- **Comparison:** [RSSSF 1995, Final][rsssf95] lists Norway 2-0 Germany;
  [DFB][dfb95] lists Germany 0-2 Norway.
- **Difference:** participant order is reversed in RSSSF, with scores reversed too.
- **Statistical impact:** none: Germany GF 0 / GA 2 / loss, Norway GF 2 / GA 0 / win;
  one appearance each. A score-only swap would be wrong, but is not observed.
- **Resolution / reviewer:** representation verified; retain source order proposed,
  human acceptance pending. Does not resolve unidentified older ordering claims.

### D02 — Solna / Stockholm (unresolved venue representation)

- **Fixture:** S95, 1995-06-18, Germany / Norway, CSV line 871.
- **Pinned value:** city `Solna`, country `Sweden`; no stadium field.
- **Comparison:** [DFB][dfb95] says Råsunda Stadion, Solna, Sweden;
  [RSSSF][rsssf95] says Stockholm and does not name a stadium.
- **Difference:** city label differs. DFB directly supports the pinned city;
  RSSSF's intended geographic granularity is not established by its final entry.
- **Classification / impact:** unresolved representation, not a confirmed source error;
  no effect on current W/D/L, goals, identities or appearances (none uses venue).
- **Resolution / reviewer:** defer exact cross-source venue equivalence; approval
  pending to exclude venue certification from basic-statistics acceptance. Do not
  claim all city mismatches refer to the same physical venue.
- **Evidence required for closure:** an attributable fixture-level source or
  clarification identifying the stadium intended by RSSSF’s Stockholm entry and
  linking it to the Råsunda venue in Solna. Until then, the proposed disposition is
  deferred, with venue certification excluded from basic-results acceptance;
  final disposition requires Wesley and Mehla approval.

### D03 — Pasadena / Los Angeles and team labels (representation)

- **Fixture:** S99, 1999-07-10, United States / China, CSV line 1455.
- **Pinned value:** `United States`, `China`, 0-0, city `Pasadena`.
- **Comparison:** [FIFA][fifa99] summary uses USA, China PR, 0-0, Rose Bowl,
  Los Angeles; the same article's body explicitly identifies Rose Bowl in Pasadena.
- **Difference:** abbreviated/official team names and metro versus municipality.
- **Impact:** no score, identity or appearance change for this identified fixture.
- **Resolution / reviewer:** same venue supported for this fixture; preserve pinned
  labels proposed, human acceptance pending. No runtime alias registration or global
  city mapping is authorized by this observation. China remains distinct from Taiwan.

### D04 — shootout information absent (missing field)

- **Fixtures:** S99 (1999-07-10 USA / China, line 1455) and S11
  (2011-07-17 Japan / USA, line 4428).
- **Pinned values:** 0-0 and 2-2 respectively; no shootout score/winner columns.
- **Comparisons:** [FIFA 1999][fifa99] reports USA winning the shootout 5-4;
  [UEFA 2011][uefa11] and [FIFA title][fifa11] report Japan winning it 3-1.
- **Difference:** extra outcome information exists in comparators but not the CSV.
- **Impact:** each fixture is a draw for both teams under the proposed recorded-score
  contract; ordinary goals are 0-0 and 2-2. Winner-based W/L would differ. Appearances
  and identities are unchanged. Never add shootout tallies to GF/GA.
- **Resolution / reviewer:** missing field verified; exclusion from current contract
  proposed / human acceptance pending. No shootout winner inferred from a tied score.

### D05 — regulation-time and extra-time splits absent (missing field)

- **Fixtures:** S03 (2003-10-12 Germany / Sweden, line 2291) and S11
  (2011-07-17 Japan / USA, line 4428).
- **Pinned values:** final scores 2-1 and 2-2; no regulation-time split or ET flag.
- **Comparisons:** [FIFA 2003][fifa03] gives a 1-1 tie before a 98th-minute winner;
  [UEFA 2011][uefa11] describes regulation equalization followed by one goal each in ET.
- **Difference:** final scores agree, but component scores cannot be recovered from
  the CSV alone. The comparator narrative supports 1-1 at regulation for both examples.
- **Impact:** Germany's 2003 result would be a draw at regulation, a win in this
  contract; excluding ET would also reduce goals. No change to editions/identities.
- **Resolution / reviewer:** limitation verified; ET-inclusive definitions proposed,
  acceptance pending. Do not backfill schema fields from these examples.

### D06 — Décines-Charpieu / Lyon (representation)

- **Fixture:** S19, 2019-07-07, United States / Netherlands, CSV line 7590.
- **Pinned value:** city `Décines-Charpieu`, France, score 2-0.
- **Comparison:** [UEFA final listing][uefa19] uses Lyon; [FIFA final notice][fifa19venue]
  names Stade de Lyon; [UEFA stadium profile][lyon] locates that stadium in
  Décines-Charpieu, east of central Lyon.
- **Difference / impact:** municipality versus event-city label; no effect on
  score, W/D/L, goals, identities or appearances.
- **Resolution / reviewer:** geographic equivalence supported for this fixture;
  retaining pinned city proposed, acceptance pending. No global venue certification.

### D07 — README row count (confirmed documentation error)

- **Identity:** source-wide pinned revision, not a single fixture/edition.
- **Pinned value:** actual CSV has 11,650 data rows (header excluded), checksum
  `de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0`.
- **Comparison:** [README at the same revision][upstream] says 11,020 results.
- **Difference:** documentation understates actual rows by 630.
- **Impact:** none on the explicitly selected 348 fixtures or calculated statistics;
  README count cannot be used as the byte-level acceptance criterion.
- **Resolution / reviewer:** stale metadata verified; report measured count, retain
  pinned bytes. No upstream correction made; human acceptance of evidence pending.

### D08 — 2003 final score in UEFA retrospective (confirmed comparator error)

- **Fixture:** S03, 2003-10-12, Germany / Sweden, CSV line 2291.
- **Pinned value:** Germany 2-1 Sweden.
- **Comparison:** [UEFA 2019 article][uefa19], “ROLL OF HONOUR”, lists the 2003 final
  as Germany 1-0 Sweden; [FIFA's match-specific record][fifa03] gives 2-1 and all
  three scoring events (41, 46 and 98 minutes).
- **Difference:** retrospective comparator omits one goal from each team.
- **Impact:** adopting 1-0 would reduce GF and GA by one for both teams, although
  W/L, GD and appearances would stay the same.
- **Resolution / reviewer:** retain pinned 2-1, supported by match-specific FIFA
  evidence; comparator error verified. No source correction needed; no external
  edit made. Human acceptance pending. This limits trust in unqualified table matching.

### D09 — Panama–France date within FFF article (confirmed comparator error)

- **Fixture:** S23P, 2023-08-02, Panama / France, CSV line 9460.
- **Pinned value:** date `2023-08-02`, score 3-6, Sydney.
- **Comparison:** [FFF article][fffarticle] technical sheet says “23 août 2023”;
  its publication date, opening paragraph and group schedule say August 2.
  The separate [FFF match record][fffmatch] explicitly gives August 2, 2023, 3-6.
- **Difference:** contradictory day-of-month inside one comparator article.
- **Impact:** copying August 23 would corrupt inclusive date-filter membership
  and edition selection. Full-edition W/D/L and goals only stay intact if retained
  in the same edition; this cannot be treated as universally harmless metadata.
- **Resolution / reviewer:** retain pinned August 2 supported by match record and
  article's consistent sections; comparator error verified, acceptance pending.
  No external correction or dataset change made.

### D10 — unrecovered earlier comparisons (unresolved evidence)

- **Fixture identity / pinned values:** unknown; no dates, participant pairs,
  exact conflicting values or source-record IDs were preserved with the claims.
- **Comparison:** `secondary_evidence` and `limitations` in
  [coverage JSON](womens-world-cup-coverage.json); RSSSF edition links and pinned
  [Hudl directory][hudl] are collection-level references only.
- **Investigation:** searched current `data/verification`, related service docs,
  local `.host-sessions` text/JSON/Markdown, and Git history for the verification
  directory. History has the consolidated evidence commit `2f0ce04`; no detailed
  ledger was recovered. This is not a claim that no external/private record exists.
- **Difference / classification:** exact mismatches cannot be identified;
  unresolved. The old claim of 348 score/date/pair matches is not freshly reproduced.
- **Impact:** unknown for unidentified records. Current source checks and the ten
  concrete samples find no confirmed statistical defect, but do not eliminate
  unknown historical errors. Do not assign a fabricated count of disputed matches.
- **Resolution / reviewer:** unresolved, human decision pending: recover original
  ledger or explicitly exclude that unauditable claim from acceptance and accept
  the bounded evidence here. Fresh D01–D09 observations are not asserted to be
  the same fixtures that prompted the older claims.
- **Evidence required for closure:** recover dates, participant identities, exact
  pinned/comparator values and attributable source records for each older claim,
  then reproduce the comparison with scores oriented to their participants.
  Statistical impact on W/D/L, goals, identities and appearances remains unknown
  for those unidentified records. Proposed disposition: deferred, excluding the
  unauditable claim from acceptance if approved by Wesley and Mehla. Exclusion or
  deferral is not resolution of the underlying unknown discrepancies.

## Scope decision

Propose acceptance of pinned basic results for recorded-score team summaries,
with these exact validation limits. No dataset correction is demonstrated.
Venue/neutral certification, regulation-only results and shootout winners remain
outside this contract. D02 and D10 must remain visible until an explicit scope
decision or additional evidence closes them; this report does not grant approval.

[upstream]: https://raw.githubusercontent.com/martj42/womens-international-results/1855e313ae8bcd0330426e62c8e4cf15ce45077c/README.md
[dfb91]: https://datencenter.dfb.de/en/data-center/fifa-women-s-world-cup/1991-in-china/final/norway-usa-377641
[dfb95]: https://datencenter.dfb.de/en/data-center/fifa-women-s-world-cup/1995-sweden/final/germany-norway-377615
[rsssf95]: https://www.rsssf.org/tablesw/wwc95f.html
[fifa99]: https://inside.fifa.com/tournaments/womens/womensworldcup/usa1999/news/mo-3003-usa-v-chn-1999-wwc-3069388
[fifa03]: https://inside.fifa.com/en/tournaments/womens/womensworldcup/usa2003/news/worldcupathome-germany-sweden-usa-2003-3070050
[fifa07]: https://inside.fifa.com/tournaments/womens/womensworldcup/china2007/news/world-cup-at-home-germany-brazil-2007-3070895
[uefa11]: https://www.uefa.com/news-media/news/01f3-0e12400bb1ef-de625f00c64c-1000--japan-stun-us-from-the-spot-to-take-global-title/
[fifa11]: https://inside.fifa.com/tournaments/womens/womensworldcup/germany2011/watch/2011-women-s-world-cup-final-japan-2-2-usa-3-1-pso
[uss15]: https://www.ussoccer.com/stories/2015/07/world-champions-usa-wins-2015-fifa-womens-world-cup
[uefa19]: https://www.uefa.com/news-media/news/0253-0e17839efb6a-1725295bbac7-1000--us-beat-netherlands-in-women-s-world-cup-final/
[fifa19venue]: https://inside.fifa.com/tournaments/womens/womensworldcup/france2019/news/360-fanpic-final-wwc
[lyon]: https://www.uefa.com/uefaeuro/history/news/0253-0d7ef3821712-9cfbcd7801c4-1000--stade-de-lyon/
[fifa23]: https://www.fifatrainingcentre.com/media/native/tournaments/womens-world-cup/2023/report_134412.pdf
[rfef23]: https://rfef.es/en/noticias/match-report-spain-wins-the-womens-world-cup
[fffarticle]: https://www.fff.fr/article/10722-decoiffante-face-au-panama.html
[fffmatch]: https://www.fff.fr/selection/matchs/3166-panama-france.html
[hudl]: https://github.com/hudl/open-data/tree/4b73468fc5b0f1950f9f66fada70ad3a4f9327cb/data/matches/72
