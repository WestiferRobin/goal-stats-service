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
    service_context.bind(
        team,
        "TeamRepository",
        SimpleNamespace(
            list=lambda: rows,
            get_by_id=lambda identity: next((r for r in rows if r.team_id == identity), None),
        ),
    )
    service = team.TeamService(service_context.database)
    result = service.list()
    assert [r["team_id"] for r in result] == [2, 1]
    assert result[0]["offense"] is None and result[0]["fifa_rank"] is None
    assert result[0]["prediction_ready"] is False
    assert service.get(2) == result[0]
    with pytest.raises(NotFound):
        service.get(999)
    assert service_context.events == ["begin", "commit", "begin", "commit", "begin", "rollback"]
