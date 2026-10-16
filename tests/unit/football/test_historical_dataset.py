import hashlib
import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from football.historical_dataset import (
    APPROVED_DATASETS,
    REQUIRED_COLUMNS,
    DatasetManifest,
    HistoricalTeamRecord,
    identity_issues,
    load_manifest,
    name_key,
    normalize_label,
    parse_selected_record,
    source_record_key,
    validate_checksum,
    validate_headers,
)


def test_pinned_manifest(manifest):
    assert manifest.upstream_revision == "1855e313ae8bcd0330426e62c8e4cf15ce45077c"
    assert manifest.sha256 == "de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0"
    assert manifest.expected_counts.model_dump() == {"matches": 64, "teams": 32, "competitions": 1}
    assert manifest.required_columns == REQUIRED_COLUMNS
    assert manifest.competition.name == "FIFA Women's World Cup"
    assert (
        manifest.competition.source_tournament == manifest.selection.tournament == "FIFA World Cup"
    )
    assert manifest.competition.edition_label == "2023"
    assert manifest.team_category == "women_senior_national"
    assert manifest.score_basis == "including_extra_time_no_shootout"
    assert manifest.reviewed_team_aliases == {}
    assert manifest.attribution_reference.endswith("/README.md")
    assert manifest.license_reference.startswith("https://")


@pytest.fixture
def manifest():
    return load_manifest()


@pytest.mark.parametrize(
    "field,value",
    [
        ("upstream_revision", "main"),
        ("sha256", "a" * 64),
        ("required_columns", ["date"]),
        ("source_url", "https://example.org/results.csv"),
        ("team_category", "men"),
        ("score_basis", "including_shootout"),
        ("extra", True),
        ("expected_counts", {"matches": 63, "teams": 32, "competitions": 1}),
        (
            "selection",
            {"tournament": "FIFA World Cup", "date_from": "2023-01-01", "date_to": "2023-08-20"},
        ),
    ],
)
def test_manifest_rejects_drift(manifest, field, value):
    with pytest.raises(ValidationError):
        DatasetManifest.model_validate({**manifest.model_dump(), field: value})


def test_canonical_identity_and_score_corrections(manifest, row):
    original = parse_selected_record(row, source_row=2, manifest=manifest)
    reordered = parse_selected_record(row, source_row=66, manifest=manifest)
    corrected = parse_selected_record({**row, "home_score": "2"}, source_row=9, manifest=manifest)
    canonical = [
        "martj42_womens_results",
        "women_senior_national",
        "fifa women's world cup",
        "2023",
        "2023-08-20",
        "spain",
        "england",
    ]
    expected = hashlib.sha256(json.dumps(canonical, separators=(",", ":")).encode()).hexdigest()
    assert original.source_record_key == reordered.source_record_key == corrected.source_record_key
    assert original.source_record_key == expected
    issues = identity_issues([original, reordered, corrected])
    assert [i.kind for i in issues] == ["duplicate", "conflict"]
    assert [i.source_row for i in issues] == [66, 9]
    assert all(i.first_row == 2 for i in issues)


@pytest.fixture
def row():
    return dict(
        zip(
            REQUIRED_COLUMNS,
            [
                "2023-08-20",
                "Spain",
                "England",
                "1",
                "0",
                "FIFA World Cup",
                "Sydney",
                "Australia",
                "TRUE",
            ],
            strict=True,
        )
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("source", "another"),
        ("category", "another"),
        ("competition_key", "another"),
        ("edition", "2027"),
        ("match_date", date(2023, 8, 19)),
        ("source_home_team", "France"),
        ("source_away_team", "Germany"),
    ],
)
def test_different_identity_changes_key(field, value):
    values = dict(
        source="martj42_womens_results",
        category="women_senior_national",
        competition_key="fifa women's world cup",
        edition="2023",
        match_date=date(2023, 8, 20),
        source_home_team="Spain",
        source_away_team="England",
    )
    assert source_record_key(**values) != source_record_key(**{**values, field: value})


def test_normalization_optional_fields_and_no_invented_ratings(manifest, row):
    raw = {**row, "home_team": " Ｓｐａｉｎ\u00a0 ", "city": " \t", "country": "", "neutral": ""}
    record = parse_selected_record(raw, source_row=2, manifest=manifest)
    assert record.source_home_team == raw["home_team"]
    assert record.home_team.name == "Spain"
    assert record.city is record.country is record.neutral is None
    assert record.home_team.offense is record.home_team.fifa_rank is None
    assert normalize_label("  Côte\u00a0  d’Ivoire ") == "Côte d’Ivoire"
    assert name_key("E\u0301QUIPE") == name_key("équipe")
    with pytest.raises(ValidationError):
        HistoricalTeamRecord(name="Spain", name_key="spain", offense=50)
    assert (
        record.source_record_key
        == parse_selected_record(row, source_row=3, manifest=manifest).source_record_key
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("date", "2023-02-30"),
        ("date", "20230820"),
        ("date", "2023-08-21"),
        ("date", "2023-07-19"),
        ("date", ""),
        ("home_team", " \t"),
        ("away_team", None),
        ("away_team", " SPAIN "),
        ("home_score", "-1"),
        ("home_score", "1.5"),
        ("home_score", "1.0"),
        ("away_score", "NaN"),
        ("away_score", "32768"),
        ("away_score", ""),
        ("neutral", "maybe"),
        ("tournament", "UEFA Euro"),
    ],
)
def test_invalid_source_values_rejected(manifest, row, field, value):
    with pytest.raises(ValueError):
        parse_selected_record({**row, field: value}, source_row=2, manifest=manifest)


@pytest.mark.parametrize("played", ["2023-07-20", "2023-08-20"])
def test_inclusive_selection(manifest, row, played):
    assert parse_selected_record({**row, "date": played}, source_row=2, manifest=manifest)


def test_headers_checksum_and_row_number(manifest, row):
    validate_headers(REQUIRED_COLUMNS, manifest)
    for headers in [None, REQUIRED_COLUMNS[:-1], (*REQUIRED_COLUMNS, "date")]:
        with pytest.raises(ValueError):
            validate_headers(headers, manifest)
    with pytest.raises(ValueError, match="checksum"):
        validate_checksum(b"not the pinned dataset", manifest)
    with pytest.raises(ValueError):
        parse_selected_record(row, source_row=0, manifest=manifest)


def test_reviewed_aliases_only(manifest, row):
    mapped = DatasetManifest.model_validate(
        {**manifest.model_dump(), "reviewed_team_aliases": {"spain": "España"}}
    )
    original = parse_selected_record(row, source_row=2, manifest=manifest)
    aliased = parse_selected_record(row, source_row=2, manifest=mapped)
    assert aliased.home_team.name == "España"
    assert aliased.source_record_key == original.source_record_key
    assert original.home_team.name == "Spain"


@pytest.mark.parametrize("dataset", APPROVED_DATASETS)
def test_supported_edition_schema(dataset):
    manifest = load_manifest(dataset)
    assert manifest.dataset_id == dataset
    assert manifest.competition.edition_label == dataset.rsplit("-", 1)[1]
    assert len(manifest.approval.participants) == manifest.expected_counts.teams
    assert manifest.approval.identity_policy == "source-record-key-v1"


@pytest.mark.parametrize(
    "dataset",
    [
        "womens-world-cup-2027",
        "../2023.json",
        Path("data/womens-world-cup/womens-world-cup-2023.json"),
        "all-approved",
        "",
    ],
)
def test_unknown_dataset_and_arbitrary_path_rejected(dataset):
    with pytest.raises(ValueError, match="Unknown historical dataset"):
        load_manifest(dataset)


@pytest.mark.parametrize(
    "section,field,value",
    [
        (None, "sha256", "0" * 64),
        (None, "upstream_revision", "0" * 40),
        (None, "source", "other"),
        (None, "dataset_id", "womens-world-cup-1991"),
        (None, "unexpected", True),
        ("competition", "edition_label", "2027"),
        ("competition", "edition_label", "1991"),
        ("selection", "tournament", "Friendly"),
        ("selection", "date_from", "2023-07-19"),
        ("expected_counts", "matches", 52),
        ("expected_counts", "teams", 16),
        ("approval", "total_goals", 163),
        ("approval", "approval_status", "pending"),
        ("approval", "identity_policy", "v2"),
        ("approval", "participants", ["Spain", "England"]),
    ],
)
def test_invalid_runtime_contract(section, field, value):
    data = load_manifest().model_dump()
    target = data if section is None else data[section]
    target[field] = value
    with pytest.raises(ValueError):
        DatasetManifest.model_validate(data)


def test_2011_rejects_32_participants():
    data = load_manifest("womens-world-cup-2011").model_dump()
    data["expected_counts"]["teams"] = 32
    with pytest.raises(ValueError, match="must agree"):
        DatasetManifest.model_validate(data)
