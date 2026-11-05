import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from schemas.team import CatalogTeamResponse, CatalogTeamsResponse
from schemas.team.response import TeamSummaryResponse


def test_historical_team_nulls_and_readiness():
    values = dict(
        team_id=1,
        name="Historical",
        category="women",
        offense=None,
        defense=None,
        form=None,
        star_power=None,
        clutch=None,
        fifa_rank=None,
        ranking_date=None,
    )
    row = CatalogTeamResponse(**values)
    assert CatalogTeamsResponse([row]).model_dump(mode="json") == [
        {**values, "prediction_ready": False}
    ]
    with pytest.raises(ValidationError):
        CatalogTeamResponse(**values, prediction_ready=True)
    del values["offense"]
    with pytest.raises(ValidationError):
        CatalogTeamResponse(**values)


@pytest.fixture
def summary_values():
    return dict(
        team_id=1,
        name="Historical",
        matches_played=4,
        wins=1,
        draws=1,
        losses=2,
        goals_for=3,
        goals_against=5,
        goal_difference=-2,
        tournament_appearances=2,
        filters={},
        score_basis="including_extra_time_no_shootout",
        result_definition="recorded_final_score",
        coverage_status="available_records_only",
    )


def test_summary_serialization_and_negative_difference(summary_values):
    row = TeamSummaryResponse(**summary_values)
    expected = {
        **summary_values,
        "filters": {
            "competition_id": None,
            "date_from": None,
            "date_to": None,
        },
    }
    assert json.loads(row.model_dump_json()) == expected
    assert row.model_dump(mode="json") == expected
    summary_values["filters"] = {"competition_id": 2, "date_from": "2024-02-29"}
    assert TeamSummaryResponse(**summary_values).model_dump(mode="json")["filters"] == {
        "competition_id": 2,
        "date_from": "2024-02-29",
        "date_to": None,
    }


@pytest.fixture
def empty_summary(summary_values):
    return {
        **summary_values,
        **dict.fromkeys(
            [
                "matches_played",
                "wins",
                "draws",
                "losses",
                "goals_for",
                "goals_against",
                "goal_difference",
                "tournament_appearances",
            ],
            0,
        ),
        "score_basis": None,
        "coverage_status": "no_matching_records",
    }


def test_summary_empty(empty_summary):
    result = TeamSummaryResponse(**empty_summary).model_dump(mode="json")
    assert result["matches_played"] == 0
    assert result["score_basis"] is None
    assert result["coverage_status"] == "no_matching_records"


@pytest.mark.parametrize(
    "field",
    [
        "matches_played",
        "wins",
        "draws",
        "losses",
        "goals_for",
        "goals_against",
        "goal_difference",
        "tournament_appearances",
    ],
)
@pytest.mark.parametrize("value", [True, False, 1.5, 1.0, "1"])
def test_summary_strict_integers(summary_values, field, value):
    with pytest.raises(ValidationError) as error:
        TeamSummaryResponse(**{**summary_values, field: value})
    assert any(e["loc"] == (field,) and e["type"] == "int_type" for e in error.value.errors())


@pytest.mark.parametrize(
    "field",
    [
        "matches_played",
        "wins",
        "draws",
        "losses",
        "goals_for",
        "goals_against",
        "tournament_appearances",
    ],
)
def test_summary_nonnegative_counts(summary_values, field):
    with pytest.raises(ValidationError):
        TeamSummaryResponse(**{**summary_values, field: -1})


def test_summary_large_totals(summary_values):
    row = TeamSummaryResponse(
        **{
            **summary_values,
            "matches_played": 4000,
            "wins": 1500,
            "draws": 1200,
            "losses": 1300,
            "goals_for": 9000,
            "goals_against": 7000,
            "goal_difference": 2000,
            "tournament_appearances": 1001,
        }
    )
    assert row.matches_played == 4000
    assert row.goal_difference == 2000


@pytest.mark.parametrize(
    "changes",
    [
        {"wins": 2},
        {"goal_difference": 0},
        {"tournament_appearances": 5},
        {"tournament_appearances": 0},
        {"score_basis": None},
        {"score_basis": "regulation_only"},
        {"coverage_status": "no_matching_records"},
        {"coverage_status": "complete"},
        {"result_definition": "shootout_winner"},
        {"name": ""},
        {"team_id": 0},
        {"team_id": -1},
        {"team_id": 2147483648},
        {"category": "women"},
        {"filters": {"limit": 50}},
    ],
)
def test_summary_invalid_populated_response(summary_values, changes):
    with pytest.raises(ValidationError):
        TeamSummaryResponse(**{**summary_values, **changes})


@pytest.mark.parametrize(
    "changes",
    [
        {"wins": 1},
        {"draws": 1},
        {"losses": 1},
        {"tournament_appearances": 1},
        {"goals_for": 1, "goals_against": 1},
        {"goal_difference": 1},
        {"score_basis": "including_extra_time_no_shootout"},
        {"coverage_status": "available_records_only"},
    ],
)
def test_summary_invalid_empty_response(empty_summary, changes):
    with pytest.raises(ValidationError):
        TeamSummaryResponse(**{**empty_summary, **changes})


@pytest.mark.parametrize("field", list(TeamSummaryResponse.model_fields))
def test_summary_all_fields_required(summary_values, field):
    del summary_values[field]
    with pytest.raises(ValidationError) as error:
        TeamSummaryResponse(**summary_values)
    assert any(e["loc"] == (field,) and e["type"] == "missing" for e in error.value.errors())


def test_existing_catalog_schema_fingerprints_unchanged():
    baseline = json.loads((Path(__file__).parents[1] / "contract_fingerprints.json").read_text())
    for model in (CatalogTeamResponse, CatalogTeamsResponse):
        for mode in ("validation", "serialization"):
            payload = json.dumps(
                model.model_json_schema(mode=mode), sort_keys=True, separators=(",", ":")
            )
            assert (
                hashlib.sha256(payload.encode()).hexdigest()
                == baseline["schemas"][model.__name__][mode]
            )
