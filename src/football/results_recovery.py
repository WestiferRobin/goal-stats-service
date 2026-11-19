"""Reviewed additional results only; original observations and rating formulas stay intact."""

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from football.team_ratings import SOURCE_SHA, Result

RECOVERY_ID = "international-results-recovery-v1"
ROOT = Path(__file__).resolve().parents[2] / "data/evaluation" / RECOVERY_ID
OVERLAY_SHA256 = "8e80eeea6cc3d6bd10ec4b26e966e6cb7376d4037a5ebd6e88155e3e3df23b61"


def content_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def checked_json(path: Path, sha: str) -> dict[str, Any]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError("Recovery checksum mismatch")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Expected recovery object")
    return value


def merge_results(base: list[Result], overlay: dict[str, Any]) -> list[Result]:
    """Reject reverse-orientation duplicates/conflicts; never repair source rows silently."""
    if (
        overlay["package_id"] != RECOVERY_ID
        or type(overlay["version"]) is not int
        or overlay["version"] != 1
        or overlay["original_source_sha256"] != SOURCE_SHA
        or overlay["historical_availability_verified"] is not False
    ):
        raise ValueError("Incompatible recovery package")
    names = {n for r in base for n in (r.home, r.away)}
    index = {(r.day, tuple(sorted((r.home, r.away)))): r for r in base}
    merged = list(base)
    sources = overlay["sources"]
    if (
        not isinstance(sources, dict)
        or not sources
        or not isinstance(overlay["fixtures"], list)
        or not overlay["fixtures"]
    ):
        raise ValueError("Empty or invalid recovery schema")
    for source in sources.values():
        if not all(
            source.get(k) for k in ("url", "publisher", "revision", "retrieved_on", "rights_basis")
        ):
            raise ValueError("Missing recovery source provenance")
        sha = source.get("sha256", "")
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("Missing source checksum")
        date.fromisoformat(source["retrieved_on"])
    for item in overlay["fixtures"]:
        day = date.fromisoformat(item["date"])
        if day.isoformat() != item["date"] or day > date.fromisoformat(overlay["reviewed_on"]):
            raise ValueError("Invalid historical fixture date")
        home, away = item["home"], item["away"]
        if home not in names or away not in names or home == away:
            raise ValueError("Unreviewed team identity")
        if (
            item["status"] != "approved_addition"
            or item["classification"] != "women_senior_national"
            or item["score_basis"] != "including_extra_time_no_shootout"
            or item["availability"] != "unverified"
            or type(item["neutral"]) is not bool
            or not item["source_ids"]
            or any(s not in sources for s in item["source_ids"])
            or not item["source_location"]
            or not item["competition"]
            or not item["venue_country"]
            or not item["score_semantics_review"]
            or item["identity_mapping"] != {"home": home, "away": away}
        ):
            raise ValueError("Unapproved fixture evidence")
        scores = (item["home_score"], item["away_score"])
        if any(type(v) is not int or v < 0 for v in scores):
            raise ValueError("Invalid recovered score")
        row = Result(day, home, away, *scores, item["neutral"])
        key = day, tuple(sorted((home, away)))
        if key in index:
            old = index[key]
            old_scores = (old.goals_home, old.goals_away)
            if old.home != home:
                old_scores = old_scores[::-1]
            if old_scores != scores or old.neutral != row.neutral:
                raise ValueError("Conflicting recovered result")
            raise ValueError("Duplicate recovered result")
        if item["fixture_id"] != content_hash([day.isoformat(), *sorted((home, away))]):
            raise ValueError("Fixture identity hash mismatch")
        index[key] = row
        merged.append(row)
    return sorted(merged, key=lambda r: (r.day, r.home, r.away))


def load_overlay() -> dict[str, Any]:
    overlay = checked_json(ROOT / "overlay.json", OVERLAY_SHA256)
    for source in overlay["sources"].values():
        if "snapshot" in source:
            path = ROOT / source["snapshot"]
            if (
                path.parent != ROOT / "sources"
                or hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]
            ):
                raise ValueError("Recovery source snapshot mismatch")
    return overlay
