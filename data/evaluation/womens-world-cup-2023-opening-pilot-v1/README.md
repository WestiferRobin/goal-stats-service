# 2023 Retrospective Evaluation Pilot

Classification: **Retrospective assumption-based evaluation**. Two matches cannot
support meaningful model accuracy conclusions. No prospective forecasting claim.

The reviewed `manifest.json` binds two official 1–0 regulation labels to existing
source keys. Local catalog IDs 285 and 286 are review references, not selection
keys: imports may assign different database IDs. The package validates the entire
348-match catalog projection before selecting the two identities. It never imports
or changes historical records.

Both FIFA post-match reports identify completed group matches on 20 July 2023.
Their cover pages establish identity and result; page 2 supplies scoring events and
timelines ending at FT. Article 37.7 of the 2023 regulations establishes 90-minute
regulation; articles 14.1–14.2 concern extra time and shootouts in knockout matches.
The labels include second-half stoppage time and exclude extra time/shootout kicks.

## Evidence integrity and source access

The original FIFA report bytes were retrieved on 2026-11-15 and SHA-256 verified:

- New Zealand–Norway: `764b3aadec407d3eb63b54c9c0c31e533b9a5f1b5c210731c4d54bf2a98f1b7c`.
- Australia–Republic of Ireland: `ec9fc573a1b6dd6b3b700d2fdb481553e2e9497e45246b01b0ad50d62442797b`.

The FFF-hosted regulations were verified through browser PDF text. Direct binary
retrieval returned HTTP 403. `regulations-evidence.json` therefore records reviewed
facts, locations and that limitation. **Its checksum identifies the evidence
record, not the original regulations PDF.** The original PDF hash is explicitly
null; no unavailable checksum is invented.

The loader pins the manifest checksum in code, verifies both referenced local
artifact checksums, and includes all provenance in the package hash. Runtime
requests perform no remote downloads. Original PDFs are linked, not redistributed;
the package conveys no general permission to redistribute third-party publications.
Any source correction requires review and a new package version, not a silent edit.

## Inputs and reproducibility

`rating-reconstruction.json` is a verification artifact, never a runtime replacement
for the existing calculator. It records the pinned result source, model, previous-day
cutoff, source row count, numerical ratings, coverage and reconstruction hash. No
current stored rating cohort is used. Historical rankings are resolved from the
database's latest release strictly before the match and included in case provenance.

There are deliberately **no Star Power or Clutch values** in this package. Strict
mode remains excluded for missing historical observations and unverified historical
publication availability. Retrospective mode requires a caller-named assumption
package; absent participant assumptions exclude the affected match. Zero is valid;
missing, nonfinite and out-of-range ratings never acquire defaults.

Test-only assumptions appear only in automated tests. Their scores do not constitute
a user-approved pilot result or observations of historical team strengths.
