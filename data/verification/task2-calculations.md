# Task 2 independent source calculations

Verified 2026-11-13 against `member/wes` at
`27df1e5ab55fa3223a3b9509e6578a94bf0152ad`.
These are CSV-derived totals, **not live database observations**. No application
repository, importer or summary implementation is called by this calculation.

[task2-team-calculations.csv](task2-team-calculations.csv) contains all 126
selection contributions, including deliberately repeated fixtures in overlapping
examples. Each row records the edition, physical CSV line (header is line 1), date,
original participants and scores, queried team, oriented GF/GA and W/D/L.
Do not sum across selections. The source file is pinned and ignored; this evidence
file is not an import dataset or replacement regression baseline.

| Selection | M | W | D | L | GF | GA | GD | Editions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| United States, all nine editions | 54 | 41 | 9 | 4 | 142 | 39 | 103 | 9 |
| Germany, all nine editions | 47 | 31 | 6 | 10 | 129 | 42 | 87 | 9 |
| Spain, all nine editions | 14 | 7 | 2 | 5 | 24 | 15 | 9 | 3 |
| Japan, 2011 | 6 | 4 | 1 | 1 | 12 | 6 | 6 | 1 |
| Panama, all nine editions | 3 | 0 | 0 | 3 | 3 | 11 | -8 | 1 |
| United States, 1999-07-10 final | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| Germany, 2003-10-12 final | 1 | 1 | 0 | 0 | 2 | 1 | 1 | 1 |

Japan's six 2011 contributions are 2-1 New Zealand, 4-0 Mexico, 0-2 England,
1-0 Germany, 3-1 Sweden, 2-2 United States. Panama's 2023 contributions are
0-4 Brazil, 0-1 Jamaica, 3-6 France. These are all oriented to the queried team.
USA's 1999 final is a draw in the recorded-score contract; Germany's 2003 final
is a win including the extra-time goal. External corroboration for those finals
is in the [comparison ledger](task2-historical-comparisons.md).

## Reproduce and check every evidence row

Run from the repository root with Python 3. This reads only local files, checks
the checksum first, selects using each manifest's tournament and inclusive bounds,
and checks the evidence CSV exactly. Editions correspond one-to-one to the
manifest competition editions; no year is inferred for an out-of-scope record.
The comparison uses integer scores, sums goals and counts distinct matching
editions. Assertions cover each example independently of `TeamRepository.summary`.

```python
import csv
import hashlib
import json
from pathlib import Path

root = Path(".")
source = root / "data/raw/martj42-womens-results/1855e313ae8bcd0330426e62c8e4cf15ce45077c/results.csv"
assert hashlib.sha256(source.read_bytes()).hexdigest() == "de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0"
with source.open(encoding="utf-8", newline="") as handle:
    raw = list(csv.DictReader(handle))
assert len(raw) == 11650
selected = []
for path in sorted((root / "data/womens-world-cup").glob("*.json")):
    manifest = json.loads(path.read_text())
    selection = manifest["selection"]
    edition = manifest["competition"]["edition_label"]
    for line, row in enumerate(raw, 2):
        if (row["tournament"] == selection["tournament"]
                and selection["date_from"] <= row["date"] <= selection["date_to"]):
            selected.append((edition, line, row))
assert len(selected) == 348
assert len({team for _, _, r in selected for team in (r["home_team"], r["away_team"])}) == 44
assert sum(int(r["home_score"]) + int(r["away_score"]) for _, _, r in selected) == 1081
assert len({(r["date"], tuple(sorted((r["home_team"], r["away_team"])))) for _, _, r in selected}) == 348
queries = [
    ("United States", "United States", None, None, [54,41,9,4,142,39,103,9]),
    ("Germany", "Germany", None, None, [47,31,6,10,129,42,87,9]),
    ("Spain", "Spain", None, None, [14,7,2,5,24,15,9,3]),
    ("Japan 2011", "Japan", "2011", None, [6,4,1,1,12,6,6,1]),
    ("Panama", "Panama", None, None, [3,0,0,3,3,11,-8,1]),
    ("USA 1999 final", "United States", "1999", "1999-07-10", [1,0,1,0,0,0,0,1]),
    ("Germany 2003 final", "Germany", "2003", "2003-10-12", [1,1,0,0,2,1,1,1]),
]
evidence = []
for label, team, year, day, expected in queries:
    group = []
    for edition, line, row in selected:
        if team not in (row["home_team"], row["away_team"]):
            continue
        if (year and edition != year) or (day and row["date"] != day):
            continue
        home, away = int(row["home_score"]), int(row["away_score"])
        gf, ga = (home, away) if team == row["home_team"] else (away, home)
        result = "W" if gf > ga else "D" if gf == ga else "L"
        group.append(dict(selection=label, edition=edition, csv_line=str(line),
            **{k: row[k] for k in ("date", "home_team", "away_team", "home_score", "away_score")},
            team=team, goals_for=str(gf), goals_against=str(ga), result=result))
    gf = sum(int(r["goals_for"]) for r in group)
    ga = sum(int(r["goals_against"]) for r in group)
    totals = [len(group), *[sum(r["result"] == v for r in group) for v in "WDL"],
              gf, ga, gf - ga, len({r["edition"] for r in group})]
    assert totals == expected, (label, totals)
    evidence.extend(group)
    print(label, totals)
with (root / "data/verification/task2-team-calculations.csv").open(newline="") as handle:
    assert list(csv.DictReader(handle)) == evidence
print("PASS: seven totals and all 126 contribution rows")
```
