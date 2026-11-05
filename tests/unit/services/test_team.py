from types import SimpleNamespace

import pytest
from werkzeug.exceptions import NotFound

from models.team import Team
from services import team


def test_team_responses_preserve_order_nulls_and_no_rating_fallback(service_context):
    rows = [
        Team(team_id=2, name="Alpha", name_key="alpha", category="women"),
        Team(team_id=1, name="Zulu", name_key="zulu", category="women"),
    ]
    service_context.repository(
        "TeamRepository",
        SimpleNamespace(
            list=lambda: rows,
            get_by_id=lambda identity: next((r for r in rows if r.team_id == identity), None),
        ),
    )
    service = team.TeamService(repo=service_context.repositories["TeamRepository"])
    result = service.list()
    assert [r["team_id"] for r in result] == [2, 1]
    assert result[0]["offense"] is None and result[0]["fifa_rank"] is None
    assert result[0]["prediction_ready"] is False
    assert service.get(2) == result[0]
    with pytest.raises(NotFound):
        service.get(999)
    assert service_context.events == ["begin", "commit", "begin", "commit", "begin", "rollback"]


@pytest.mark.parametrize("count", [0, 1, 2])
def test_participant_validation_borrows_session_and_locks(count):
    from unittest.mock import Mock

    session = object()
    repo = SimpleNamespace(
        database=object(),
        get_participants=Mock(return_value=[object() for _ in range(count)]),
    )
    service = team.TeamService(repo=repo)
    original = vars(service).copy()
    if count == 2:
        assert service.require_participants_in_transaction(session=session, team_ids=(1, 2)) is None
    else:
        with pytest.raises(NotFound):
            service.require_participants_in_transaction(session=session, team_ids=(1, 2))
    repo.get_participants.assert_called_once_with(session, (1, 2), for_key_share=True)
    assert vars(service) == original
    assert service.database is repo.database


def test_capture_names_rejects_missing_identity():
    from unittest.mock import Mock

    session = object()
    row = SimpleNamespace(team_id=4, name="Spain")
    repo = SimpleNamespace(database=object(), get_participants=Mock(return_value=[row]))
    service = team.TeamService(repo=repo)
    assert service.capture_names_in_transaction(session=session, team_ids=[4]) == {4: "Spain"}
    with pytest.raises(NotFound):
        service.capture_names_in_transaction(session=session, team_ids=[4, 9])


@pytest.fixture
def summary_service():
    from contextlib import nullcontext
    from unittest.mock import Mock

    from infra.repositories.team import TeamSummaryProjection

    session = object()
    repo = SimpleNamespace(
        transaction=Mock(return_value=nullcontext(session)),
        get_by_id=Mock(return_value=SimpleNamespace(team_id=4, name="Spain")),
        summary=Mock(return_value=TeamSummaryProjection(4, 2, 1, 1, 7, 4, 3, 2, 0)),
    )
    return team.TeamService(repo=repo), repo, session


def test_summary_filters_and_same_session(summary_service):
    from datetime import date

    from schemas.team.request import TeamSummaryQuery

    service, repo, session = summary_service
    query = TeamSummaryQuery(competition_id=2, date_from="2023-07-01", date_to="2023-08-01")
    result = service.summary(4, query)
    repo.transaction.assert_called_once_with()
    repo.get_by_id.assert_called_once_with(session, 4)
    repo.summary.assert_called_once_with(
        session, team_id=4, competition_id=2, date_from=date(2023, 7, 1), date_to=date(2023, 8, 1)
    )
    assert result == dict(
        team_id=4,
        name="Spain",
        matches_played=4,
        wins=2,
        draws=1,
        losses=1,
        goals_for=7,
        goals_against=4,
        goal_difference=3,
        tournament_appearances=2,
        filters={"competition_id": 2, "date_from": "2023-07-01", "date_to": "2023-08-01"},
        score_basis="including_extra_time_no_shootout",
        result_definition="recorded_final_score",
        coverage_status="available_records_only",
    )


def test_summary_empty(summary_service):
    from infra.repositories.team import TeamSummaryProjection
    from schemas.team.request import TeamSummaryQuery

    service, repo, session = summary_service
    repo.summary.return_value = TeamSummaryProjection(*([0] * 9))
    result = service.summary(4, TeamSummaryQuery())
    assert result["coverage_status"] == "no_matching_records"
    assert result["score_basis"] is None
    assert result["filters"] == {"competition_id": None, "date_from": None, "date_to": None}
    for field in (
        "matches_played",
        "wins",
        "draws",
        "losses",
        "goals_for",
        "goals_against",
        "goal_difference",
        "tournament_appearances",
    ):
        assert result[field] == 0
    repo.summary.assert_called_once_with(
        session, team_id=4, competition_id=None, date_from=None, date_to=None
    )


def test_summary_unknown_skips_aggregation(summary_service):
    from schemas.team.request import TeamSummaryQuery

    service, repo, _ = summary_service
    repo.get_by_id.return_value = None
    with pytest.raises(NotFound):
        service.summary(999, TeamSummaryQuery())
    repo.summary.assert_not_called()


def test_summary_unsupported_is_internal_error(summary_service):
    from dataclasses import replace

    from schemas.team.request import TeamSummaryQuery

    service, repo, _ = summary_service
    repo.summary.return_value = replace(repo.summary.return_value, unsupported_score_basis_count=1)
    with pytest.raises(RuntimeError):
        service.summary(4, TeamSummaryQuery())


@pytest.mark.parametrize("operation", ["get_by_id", "summary"])
def test_summary_database_error_propagates(summary_service, operation):
    from sqlalchemy.exc import OperationalError

    from schemas.team.request import TeamSummaryQuery

    service, repo, _ = summary_service
    failure = OperationalError("private sql", {}, RuntimeError("private database"))
    getattr(repo, operation).side_effect = failure
    with pytest.raises(OperationalError) as error:
        service.summary(4, TeamSummaryQuery())
    assert error.value is failure
    if operation == "get_by_id":
        repo.summary.assert_not_called()


def test_summary_response_invariants_enforced(summary_service):
    from dataclasses import replace

    from pydantic import ValidationError

    from schemas.team.request import TeamSummaryQuery

    service, repo, _ = summary_service
    repo.summary.return_value = replace(repo.summary.return_value, wins=99)
    with pytest.raises(ValidationError):
        service.summary(4, TeamSummaryQuery())
