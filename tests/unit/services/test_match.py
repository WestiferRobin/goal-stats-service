from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from werkzeug.exceptions import NotFound

from infra.repositories.match import MatchProjection
from schemas.match import CatalogMatchQuery
from services import match


def test_match_filters_and_joined_serialization_without_per_row_lookup(service_context):
    row = MatchProjection(
        9,
        date(2023, 7, 20),
        2,
        "Cup",
        "2023",
        1,
        "First",
        2,
        "Second",
        1,
        0,
        "including_extra_time_no_shootout",
        None,
        None,
        None,
    )
    listing = Mock(return_value=[row, row])
    repo = SimpleNamespace(
        list=listing, get_projection=lambda identity: row if identity == 9 else None
    )
    service_context.bind(match, "MatchRepository", repo)
    service = match.MatchService(service_context.database)
    query = CatalogMatchQuery(
        team_id=1, competition_id=2, date_from="2023-07-20", limit=2, offset=3
    )
    result = service.list(query)
    listing.assert_called_once_with(**query.model_dump())
    assert result[0]["match_date"] == "2023-07-20"
    assert result[0]["away_team_name"] == "Second"
    assert result[0]["competition_name"] == "Cup"
    assert result[0] == result[1] == service.get(9)
    with pytest.raises(NotFound):
        service.get(999)
