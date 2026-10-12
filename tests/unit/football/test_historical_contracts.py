"""Prepared contracts are tested without the ignored downloaded source or a database."""

import hashlib
import json
from copy import deepcopy

import pytest
from verify_historical_contracts import (
    ROOT,
    SPECS,
    expected_manifest,
    fixture_digest,
    load_contracts,
    validate_contract,
    verify_selection,
    verify_source,
)

from football.historical_dataset import load_manifest


def test_all_nine_contracts_and_deterministic_evidence():
    contracts = load_contracts()
    assert len(contracts) == 9
    assert sum(e["matches"] for _, e in contracts) == 348
    assert sum(e["total_goals"] for _, e in contracts) == 1081
    assert len({p for _, e in contracts for p in e["participants"]}) == 44
    paths = [ROOT / "data/verification/womens-world-cup-coverage.json"]
    paths.extend(ROOT / f"data/womens-world-cup/{m['dataset_id']}.json" for m, _ in contracts[:-1])
    for path in paths:
        contents = path.read_text(encoding="utf-8")
        assert contents == json.dumps(json.loads(contents), ensure_ascii=False, indent=2) + "\n"
    for manifest, _ in contracts:
        loaded = load_manifest(manifest["dataset_id"])
        assert loaded.model_dump(mode="json", exclude={"approval"}) == manifest


@pytest.mark.parametrize("year", SPECS)
def test_pinned_contract_rejects_changes(year):
    _, evidence = next(
        (m, e) for m, e in load_contracts() if m["competition"]["edition_label"] == year
    )
    manifest = expected_manifest(year)
    mutations = [
        ("sha256", "0" * 64),
        ("upstream_revision", "0" * 40),
        ("dataset_id", "womens-world-cup-2099"),
        ("source", "other"),
        ("author", "unknown"),
        ("required_columns", []),
        ("reviewed_team_aliases", {"China": "Taiwan"}),
        ("selection", {**manifest["selection"], "tournament": "Friendly"}),
        ("selection", {**manifest["selection"], "date_to": f"{year}-12-31"}),
        ("expected_counts", {"matches": 1, "teams": 2, "competitions": 1}),
        ("unexpected", True),
    ]
    for field, value in mutations:
        changed = deepcopy(manifest)
        changed[field] = value
        with pytest.raises(ValueError, match="pinned contract"):
            validate_contract(changed, evidence)


@pytest.mark.parametrize(
    "field,value",
    [
        ("approval_status", "pending"),
        ("identity_policy", "v2"),
        ("home_away_policy", "reorder"),
        ("score_basis", "regulation"),
        ("total_goals", 100),
        ("runtime_supported", True),
        ("participants", ["China", "Taiwan"]),
        ("fixture_sha256", "bad"),
    ],
)
def test_unapproved_or_changed_evidence_rejected(field, value):
    manifest, evidence = load_contracts()[0]
    evidence[field] = value
    with pytest.raises(ValueError):
        validate_contract(manifest, evidence)


def test_unknown_edition_rejected():
    manifest, evidence = load_contracts()[0]
    manifest["competition"]["edition_label"] = "2027"
    with pytest.raises(ValueError, match="Unknown edition"):
        validate_contract(manifest, evidence)


@pytest.fixture
def sample():
    row = {
        "date": "1991-11-16",
        "home_team": "China",
        "away_team": "Taiwan",
        "home_score": "1",
        "away_score": "0",
        "tournament": "FIFA World Cup",
        "city": "",
        "country": "China",
        "neutral": "FALSE",
    }
    second = {**row, "date": "1991-11-30", "home_team": "England", "away_team": "Scotland"}
    rows = [row, second]
    selection = expected_manifest("1991")["selection"]
    evidence = {
        "matches": 2,
        "participants": ["China", "England", "Scotland", "Taiwan"],
        "participant_count": 4,
        "total_goals": 2,
        "fixture_sha256": fixture_digest(rows),
    }
    return rows, selection, evidence


def test_exact_selection_boundaries_and_order_independent_evidence(sample):
    rows, selection, evidence = sample
    filtered = [
        {**rows[0], "date": "1991-11-15"},
        {**rows[0], "date": "1991-12-01"},
        {**rows[0], "tournament": "Friendly"},
    ]
    assert verify_selection(rows + filtered, selection, evidence) == rows
    assert verify_selection(list(reversed(rows)), selection, evidence) == list(reversed(rows))
    assert fixture_digest(rows) == fixture_digest(list(reversed(rows)))


@pytest.mark.parametrize(
    "field,value",
    [
        ("date", "1991-02-30"),
        ("date", "1991-1-1"),
        ("date", ""),
        ("home_score", "-1"),
        ("away_score", "1.5"),
        ("home_score", "NaN"),
        ("home_score", "inf"),
        ("home_score", "32768"),
        ("home_score", ""),
        ("home_team", ""),
        ("home_team", " Taiwan "),
        ("tournament", ""),
        ("neutral", "maybe"),
    ],
)
def test_invalid_source_rows_rejected(sample, field, value):
    rows, selection, evidence = sample
    rows[0][field] = value
    with pytest.raises(ValueError, match="Source row 2"):
        verify_selection(rows, selection, evidence)


@pytest.mark.parametrize(
    "change", [{}, {"home_score": "2"}, {"home_team": "Taiwan", "away_team": "China"}]
)
def test_duplicate_and_contradictory_identities_rejected(sample, change):
    rows, selection, evidence = sample
    rows.append({**rows[0], **change})
    with pytest.raises(ValueError, match="Duplicate|Contradictory"):
        verify_selection(rows, selection, evidence)


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"home_team": "Japan"}, "participant"),
        ({"home_score": "2"}, "Goal"),
        ({"city": "Different"}, "digest"),
        ({"date": "1991-11-17"}, "digest"),
        ({"date": "1991-12-01"}, "Match count"),
        ({"home_team": "Taiwan", "away_team": "China"}, "digest"),
    ],
)
def test_counts_alone_cannot_approve_changed_fixtures(sample, change, reason):
    rows, selection, evidence = sample
    rows[0].update(change)
    with pytest.raises(ValueError, match=reason):
        verify_selection(rows, selection, evidence)


def test_source_checksum_rejected_before_parsing(tmp_path):
    source = tmp_path / "results.csv"
    source.write_bytes(b"not a CSV")
    with pytest.raises(ValueError, match="STOP: source checksum"):
        verify_source(source)


def test_existing_2023_manifest_bytes_preserved():
    path = ROOT / "data/womens-world-cup/womens-world-cup-2023.json"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "59dbd16bf7d49dfe820abe00ef20ef28f30206f6efca25f6ca17068ae17428b0"
    )
