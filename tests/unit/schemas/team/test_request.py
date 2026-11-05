from datetime import date

import pytest
from pydantic import ValidationError

from schemas.team import CatalogTeamPath
from schemas.team.request import TeamSummaryQuery


@pytest.mark.parametrize("value", [0, -1, 2147483648])
def test_team_path_bounds(value):
    with pytest.raises(ValidationError):
        CatalogTeamPath(team_id=value)


@pytest.mark.parametrize("value", [1, 2147483647, "42"])
def test_summary_competition_ids(value):
    assert TeamSummaryQuery(competition_id=value).competition_id == int(value)


@pytest.mark.parametrize("value", [0, -1, 2147483648, "abc", 1.5])
def test_summary_invalid_competition_ids(value):
    with pytest.raises(ValidationError):
        TeamSummaryQuery(competition_id=value)


def test_summary_optional_filters_and_inclusive_equal_dates():
    assert TeamSummaryQuery().model_dump(mode="json") == {
        "competition_id": None,
        "date_from": None,
        "date_to": None,
    }
    query = TeamSummaryQuery(date_from="2024-02-29", date_to="2024-02-29")
    assert query.date_from == query.date_to == date(2024, 2, 29)
    assert TeamSummaryQuery(date_from=date(2000, 2, 29)).date_to is None
    assert TeamSummaryQuery(date_to="2023-12-31").date_from is None


@pytest.mark.parametrize("field", ["date_from", "date_to"])
@pytest.mark.parametrize(
    "value",
    [
        "2023-02-29",
        "1900-02-29",
        "2024-04-31",
        "2024-13-01",
        "2024-2-01",
        "2024-02-1",
        "2024-02-29T00:00:00",
        " 2024-02-29",
        "2024-02-29\n",
        "1709164800",
    ],
)
def test_summary_invalid_dates(field, value):
    with pytest.raises(ValidationError):
        TeamSummaryQuery(**{field: value})


def test_summary_reversed_dates():
    with pytest.raises(ValidationError):
        TeamSummaryQuery(date_from="2024-03-01", date_to="2024-02-29")


@pytest.mark.parametrize("field", ["limit", "offset", "team_id", "unknown"])
def test_summary_rejects_unknown_and_pagination_fields(field):
    with pytest.raises(ValidationError) as error:
        TeamSummaryQuery(**{field: 1})
    assert error.value.errors()[0]["type"] == "extra_forbidden"
