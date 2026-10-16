"""Joined historical response validation and JSON representation."""

from datetime import date

import pytest
from pydantic import ValidationError

from schemas.match.response import CatalogMatchesResponse, CatalogMatchResponse


@pytest.fixture
def match_response_data():
    return dict(
        match_id=1,
        match_date="2023-07-20",
        competition_id=3,
        competition_name="Women's World Cup",
        edition_label="2023",
        home_team_id=10,
        home_team_name="Alpha",
        away_team_id=20,
        away_team_name="Beta",
        home_score=2,
        away_score=0,
        score_basis="including_extra_time_no_shootout",
        neutral=None,
        city=None,
        country=None,
    )


def test_joined_response_and_list_serialize_dates_and_nullable_fields(match_response_data):
    model = CatalogMatchResponse(**match_response_data)
    assert model.match_date == date(2023, 7, 20)
    assert model.model_dump(mode="json") == match_response_data
    wrapper = CatalogMatchesResponse([model])
    assert wrapper.model_dump(mode="json") == [match_response_data]
    assert CatalogMatchesResponse.model_validate_json(wrapper.model_dump_json()) == wrapper


@pytest.mark.parametrize(
    "missing",
    ["match_id", "match_date", "home_team_name", "competition_name", "home_score", "neutral"],
)
def test_required_fields_cannot_be_omitted(match_response_data, missing):
    del match_response_data[missing]
    with pytest.raises(ValidationError) as caught:
        CatalogMatchResponse(**match_response_data)
    assert any(e["loc"] == (missing,) and e["type"] == "missing" for e in caught.value.errors())


@pytest.mark.parametrize(
    "field,value",
    [
        ("match_date", "not-a-date"),
        ("home_score", 1.5),
        ("home_score", None),
        ("home_team_name", None),
        ("extra", 1),
    ],
)
def test_malformed_or_unknown_response_fields_fail(match_response_data, field, value):
    with pytest.raises(ValidationError):
        CatalogMatchResponse(**{**match_response_data, field: value})


def test_score_coercion_matches_actual_unconstrained_integer_contract(match_response_data):
    # Response scores have int typing, not request-side range/strict constraints.
    model = CatalogMatchResponse(**{**match_response_data, "home_score": "2", "away_score": -1})
    assert model.home_score == 2 and model.away_score == -1
