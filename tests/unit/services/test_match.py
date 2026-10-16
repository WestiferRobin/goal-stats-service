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
    service_context.repository("MatchRepository", repo)
    service = match.MatchService(
        repo=service_context.repositories["MatchRepository"],
        team_service=SimpleNamespace(
            database=service_context.repositories["MatchRepository"].database
        ),
    )
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


@pytest.mark.parametrize("participants", [(1, 2), (2, 1), (1, 3), None])
def test_match_validation_borrows_session_and_locks(participants):
    from werkzeug.exceptions import BadRequest

    session = object()
    row = (
        SimpleNamespace(home_team_id=participants[0], away_team_id=participants[1])
        if participants
        else None
    )
    repo = SimpleNamespace(database=object(), get_by_id=Mock(return_value=row))
    service = match.MatchService(repo=repo, team_service=SimpleNamespace(database=repo.database))
    original = vars(service).copy()
    if participants in [(1, 2), (2, 1)]:
        assert (
            service.require_match_participants_in_transaction(
                session=session, match_id=4, team_ids=(1, 2)
            )
            is None
        )
    else:
        with pytest.raises(NotFound if participants is None else BadRequest):
            service.require_match_participants_in_transaction(
                session=session, match_id=4, team_ids=(1, 2)
            )
    repo.get_by_id.assert_called_once_with(session, 4, for_share=True)
    assert vars(service) == original
    assert service.database is repo.database


def test_insights_validates_ids_and_uses_one_caller_transaction(service_context):
    from schemas.match.request import HistoricalComparison

    calls = []

    def listing(**kw):
        calls.append(kw)
        return []

    service_context.repository("MatchRepository", SimpleNamespace(list=listing))
    repo = service_context.repositories["MatchRepository"]

    def names(*, session, team_ids):
        assert service_context.state.active and team_ids == (1, 2)
        return {1: "Spain", 2: "England"}

    service = match.MatchService(
        repo=repo,
        team_service=SimpleNamespace(database=repo.database, capture_names_in_transaction=names),
    )
    result = service.insights(HistoricalComparison(team1_id=1, team2_id=2, limit=3, offset=4))
    assert result["head_to_head"] == result["team1_history"] == result["team2_history"] == []
    assert [c["opponent_team_id"] for c in calls] == [2, None, None]
    assert all(c["limit"] == 3 and c["offset"] == 4 for c in calls)
    assert service_context.events == ["begin", "commit"]
