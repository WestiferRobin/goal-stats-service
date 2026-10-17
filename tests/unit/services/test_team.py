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
