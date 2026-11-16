# Women's World Cup 1991–2023 evidence registry

Classification: **Retrospective assumption-based evaluation**, when the caller
supplies explicit hypothetical inputs. No prospective forecasting claim.
All 348 catalog identities are represented. No canonical database rows are imported
or changed. The original recorded package and the official two-match pilot remain
available separately.

## Contents and approval boundary

- `registry.json`: 348 unique source-key mappings, original catalog IDs (reference
  only), orientation, stage, duration, regulation/final/extra-time/shootout scores,
  completion, verification, discrepancies and attributed source locations.
  `extra_time_score` is the cumulative score at the end of extra time, not just
  goals scored during extra time; `shootout_score` contains shootout kicks only.
- `sources/*.html`: nine byte-preserved RSSSF snapshots. Each page expressly permits
  copying with acknowledgement. Attribution and the original permission footer are
  retained. These are archival evidence, not newly acquired official FIFA reports.
- `rules.json`: separate 80/90-minute protocols, golden-goal handling, the 1999
  third-place exception, reviewed rule sources and explicit original-regulations gaps.
  Its hash identifies the reviewed facts, not the original third-party documents.
- `ratings.json`: outputs of the unchanged calculator at all 137 previous-day
  cutoffs, including EVERY calculated reference team, coverage, source-row hashes,
  full-population hashes and model/source identity. The source file is checksum
  verified, and evaluated-day/future results are excluded. The runtime verifies the
  full input-population hash before scoring; no current stored ratings are used.
- `manifest.json`: hashes of the registry, ratings and rules; catalog/model identity.
  Its checksum is pinned in `src/services/evaluation_full.py`. Source HTML checksums
  are checked by the loader. Any correction requires review and a new package.
- `coverage.json`: read-only local evidence audit, including exact per-case
  exclusions and ranking provenance. It contains no user assumption values or
  prediction metrics. It is a report, not an eligibility authority.

Official pilot labels retain priority over the matching archive labels. Archives
must agree with their scores. The entire 348-row catalog projection is fingerprinted
before edition selection or pagination; numeric IDs are never selection keys.

## Attribution and limitations

RSSSF authors: David Shannon (1991, 1995, 1999); Lars Aarhus and Sturmius Burkert
(2003); Roberto Di Maggio (2007, 2011, 2019, 2023); Karel Stokkermans (2015).
URLs, snapshot hashes and reuse permission are in `registry.json`. The canonical
recorded-score source is Mart Jürisoo's Women's International Football Results,
revision `1855e313ae8bcd0330426e62c8e4cf15ce45077c`, under the existing approved
catalog attribution/license policy. martj42 lists RSSSF among its sources: agreement
is reconciliation, not proof of two independent observations.

Nineteen extra-time matches use individually reviewed regulation scores, checked
against the archived scorer timelines. A goal's numeric minute alone is NOT used
to distinguish stoppage time from extra time. Shootout kicks are always separate.
The 1999 and 2003 golden-goal winners are regulation draws; minute discrepancies
(104/105 and 97/98 respectively) are retained explicitly. Zero-goal matches are
accounted for, not inferred to be missing event files.

Original regulations for 1991–2019 were not acquired. Reviewed historical duration
and observed knockout procedures are recorded, with unverified extra-time maxima
left null. The 2023 regulations PDF's binary checksum remains unavailable (HTTP
403); the pilot's reviewed facts and limitation are preserved. The 80-minute 1991
model is unvalidated and cannot score, even if every rating is provided.

Historical source publication availability and observational Star Power/Clutch
remain unverified. Strict eligibility is therefore zero. Caller assumptions must
be explicitly named/versioned, finite and 0–100 for each participant/source key;
there are no defaults or supplied production examples. Missing values exclude a
match. Rankings are optional under the existing model, and gaps remain visible.

## Reproduction

Export existing catalog Match records as JSON using a read-only database session.
Then run from the service repository, with the pinned CSV available:

```sh
PYTHONPATH=src .venv/bin/python -B scripts/evaluation/build_full.py /path/to/catalog.json
```

The offline builder makes no network calls or database writes. It rejects incomplete,
duplicate, ambiguous and conflicting archive joins. It regenerates all reference
populations with the existing calculator; review the resulting manifest checksum
before updating the loader's pin. Do not overwrite a released version in place.

Runtime API: `POST /api/v1/evaluations/backtests`, dataset
`womens-world-cup-full-v1`, optional numeric `edition`, `offset`, and `limit` up to
348. `edition: null` selects all nine. The frontend proxy uses the same contract.
Full-package request bodies are bounded at 128 KiB; older packages retain 32 KiB
and 16-case limits. Summary counts cover the requested cohort/page, and explicit
catalog totals are separate. Top-level numerical metrics are 90-minute only;
80-minute summary metrics remain null. No incompatible horizons are averaged.
