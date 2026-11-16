"""Reconcile attributed archive snapshots to existing catalog identities, without writes."""

import html
import re
from collections import Counter
from typing import Any

EDITION_COUNTS = {
    1991: 26,
    1995: 26,
    1999: 32,
    2003: 32,
    2007: 32,
    2011: 32,
    2015: 52,
    2019: 52,
    2023: 64,
}
ALIASES = {"United States": "USA", "Republic of Ireland": "Ireland"}
MONTHS = dict(Jun=6, Jul=7, Aug=8, Sep=9, Oct=10, Nov=11)


def reconcile(raw: bytes, edition: int, catalog: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Require a unique date/team/orientation join and an exact final-score reconciliation."""
    text = html.unescape(re.sub("<[^>]+>", "", raw.decode("cp1252")))
    if "You are free to copy this document" not in text or "acknowledgement" not in text:
        raise ValueError("Archive reuse permission missing")
    stage = "group"
    output = {}
    for index, line in enumerate(text.splitlines(), 1):
        for heading, value in [
            ("Round of 16", "round_of_16"),
            ("Second Round", "round_of_16"),
            ("Quarterfinal", "quarterfinal"),
            ("Semifinal", "semifinal"),
            ("Third Place", "third_place"),
            ("Third place", "third_place"),
            ("Final", "final"),
        ]:
            if line.strip().startswith(heading) and not line.strip().startswith("Final Tournament"):
                stage = value
        match = re.match(
            r"\s*(\d{1,2}) (Jun|Jul|Aug|Sep|Oct|Nov)\s+(.+?)\s+(\d+)[–-](\d+)\s+(.+)", line
        )
        if not match:
            continue
        day, month, left, home, away, right = match.groups()
        match_date = f"{edition}-{MONTHS[month]:02d}-{int(day):02d}"
        identities = []
        for case in catalog:
            if case["match_date"] != match_date:
                continue
            for reverse in (False, True):
                h, a = (
                    (case["source_away_team"], case["source_home_team"])
                    if reverse
                    else (case["source_home_team"], case["source_away_team"])
                )
                if any(left.endswith(n) for n in (h, ALIASES.get(h, h))) and any(
                    right == n or right.startswith(n + " ") for n in (a, ALIASES.get(a, a))
                ):
                    identities.append((case, reverse))
        if len(identities) != 1:
            raise ValueError("Missing or ambiguous archive identity")
        case, reverse = identities[0]
        score = [int(away), int(home)] if reverse else [int(home), int(away)]
        if score != [case["home_score"], case["away_score"]]:
            raise ValueError("Archive/catalog score conflict")
        key = case["source_record_key"]
        if key in output:
            raise ValueError("Duplicate archive match")
        pen = re.search(r"(\d+)-(\d+) pen", right)
        shootout = (
            ([int(pen[2]), int(pen[1])] if reverse else [int(pen[1]), int(pen[2])]) if pen else None
        )
        output[key] = dict(
            stage=stage,
            archive_line=index,
            archive_fixture=line.strip(),
            archive_orientation_reversed=reverse,
            final_score=score,
            extra_time_played="aet" in right or "asdet" in right,
            golden_goal_rule="asdet" in right,
            shootout_score=shootout,
        )
    if len(output) != EDITION_COUNTS[edition]:
        raise ValueError("Incomplete edition archive")
    return output


def validate_inventory(records: list[dict[str, Any]]) -> None:
    if len(records) != 348 or len({r["match_key"] for r in records}) != 348:
        raise ValueError("Expected 348 unique matches")
    if Counter(r["edition"] for r in records) != EDITION_COUNTS:
        raise ValueError("Invalid edition inventory")
