"""Pure record extraction and fact comparison, without database sessions."""

from datetime import date
from types import SimpleNamespace

import pytest

from football.historical_dataset import load_manifest, parse_selected_record
from football.historical_import import _match_values, _same_facts


@pytest.fixture
def historical_record(historical_csv):
    row = {**historical_csv.rows[0], "city": "", "country": "", "neutral": ""}
    return parse_selected_record(row, source_row=1, manifest=load_manifest())


def test_match_values_extract_scalar_fields_and_preserve_provenance(historical_record):
    values = _match_values(historical_record, 10, 20, 30)
    assert {k: values[k] for k in ("home_team_id", "away_team_id", "competition_id")} == {
        "home_team_id": 10,
        "away_team_id": 20,
        "competition_id": 30,
    }
    assert not {"home_team", "away_team", "competition"} & values.keys()
    assert values["match_date"] == date(2023, 7, 20)
    assert values["home_score"] == 0 and values["away_score"] == 0
    assert values["city"] is values["country"] is values["neutral"] is None
    assert values["source_record_key"] == historical_record.source_record_key
    assert values["source_row"] == 1
    assert values["source_file_sha256"] == historical_record.source_file_sha256


def test_equivalent_facts_ignore_source_identity_and_provenance(historical_record):
    stored = SimpleNamespace(**_match_values(historical_record, 1, 2, 3))
    other = historical_record.model_copy(
        update={
            "source_record_key": "a" * 64,
            "source_version": "other-version",
            "source_file_sha256": "b" * 64,
            "source_row": 99,
            "source_url": "other-url",
        }
    )
    assert _same_facts(stored, historical_record, 1, 2, 3)
    # Identity selection belongs to the caller; this helper compares only match facts.
    assert _same_facts(stored, other, 1, 2, 3)


@pytest.mark.parametrize(
    "field,value",
    [
        ("home_team_id", 4),
        ("away_team_id", 4),
        ("competition_id", 4),
        ("match_date", date(2023, 7, 21)),
        ("home_score", 1),
        ("away_score", 1),
        ("score_basis", "different"),
        ("neutral", False),
        ("city", "Sydney"),
        ("country", "Australia"),
    ],
)
def test_each_meaningful_fact_difference_is_detected(historical_record, field, value):
    values = _match_values(historical_record, 1, 2, 3)
    values[field] = value
    assert not _same_facts(SimpleNamespace(**values), historical_record, 1, 2, 3)


@pytest.mark.parametrize("identities", [(None, 2, 3), (1, None, 3), (1, 2, None)])
def test_unresolved_foreign_identity_is_not_equivalent(historical_record, identities):
    stored = SimpleNamespace(**_match_values(historical_record, 1, 2, 3))
    assert not _same_facts(stored, historical_record, *identities)
