from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from werkzeug.exceptions import BadRequest, NotFound

from infra.repositories.scenario import ScenarioProjection
from schemas.scenario import ScenarioCreate, ScenarioPatch, ScenarioQuery
from services import scenario


def repositories(context, projection):
    rows = {7: projection}

    def add(row):
        row.scenario_id = 7
        row.created_at = projection.scenario.created_at
        rows[7] = ScenarioProjection(row, "First", "Second")

    repo = SimpleNamespace(
        add=Mock(side_effect=add),
        flush=Mock(),
        get_projection=lambda identity: rows.get(identity),
        get_by_id=Mock(return_value=projection.scenario),
        list=Mock(return_value=[projection]),
        exists=lambda identity: identity in rows,
    )
    context.repository("ScenarioRepository", repo)
    teams = SimpleNamespace(require_participants_in_transaction=Mock())
    matches = SimpleNamespace(require_match_participants_in_transaction=Mock())
    context.service("TeamService", teams)
    context.service("MatchService", matches)
    return repo, teams, matches


def test_scenario_create_shared_session_ratings_and_match_locks(
    service_context, scenario_projection, scenario_body
):
    repo, teams, matches = repositories(service_context, scenario_projection)
    order = []
    teams.require_participants_in_transaction.side_effect = lambda **kw: order.append("team")
    matches.require_match_participants_in_transaction.side_effect = lambda **kw: order.append(
        "match"
    )
    original_add = repo.add.side_effect

    def add(row):
        order.append("insert")
        original_add(row)

    repo.add.side_effect = add
    body = ScenarioCreate(**{**scenario_body, "match_id": 4, "team1_offense": 83})
    result = scenario.ScenarioService(
        repo=service_context.repositories["ScenarioRepository"],
        team_service=service_context.services["TeamService"],
        match_service=service_context.services["MatchService"],
    ).create(body)
    assert result["team1_offense"] == 83 and result["team2_offense"] == 70
    assert result["team1_name"] == "First" and result["match_id"] == 4
    teams.require_participants_in_transaction.assert_called_once_with(team_ids=(1, 2))
    matches.require_match_participants_in_transaction.assert_called_once_with(
        match_id=4, team_ids=(1, 2)
    )
    assert service_context.events == ["begin", "commit"]
    assert repo.add.call_count == 1
    assert order == ["team", "match", "insert"]


@pytest.mark.parametrize(
    "failure,error", [("team", NotFound), ("match", NotFound), ("mismatch", BadRequest)]
)
def test_scenario_invalid_references_rollback_without_insert(
    service_context, scenario_projection, scenario_body, failure, error
):
    repo, teams, matches = repositories(service_context, scenario_projection)
    if failure == "team":
        teams.require_participants_in_transaction.side_effect = NotFound
    elif failure == "match":
        matches.require_match_participants_in_transaction.side_effect = NotFound
    else:
        matches.require_match_participants_in_transaction.side_effect = BadRequest
    with pytest.raises(error):
        scenario.ScenarioService(
            repo=service_context.repositories["ScenarioRepository"],
            team_service=service_context.services["TeamService"],
            match_service=service_context.services["MatchService"],
        ).create(ScenarioCreate(**{**scenario_body, "match_id": 4}))
    assert not repo.add.called
    assert service_context.events == ["begin", "rollback"]


def test_scenario_contract_rejects_same_team(scenario_body):
    with pytest.raises(ValidationError):
        ScenarioCreate(**{**scenario_body, "team2_id": 1})


def test_scenario_patch_validates_combined_state_before_mutation(
    service_context, scenario_projection
):
    repo, _, _ = repositories(service_context, scenario_projection)
    service = scenario.ScenarioService(
        repo=service_context.repositories["ScenarioRepository"],
        team_service=service_context.services["TeamService"],
        match_service=service_context.services["MatchService"],
    )
    with pytest.raises(BadRequest):
        service.update(7, ScenarioPatch(team1_possession=60))
    assert scenario_projection.scenario.team1_possession == 50
    assert not repo.flush.called
    assert service_context.events == ["begin", "rollback"]
    result = service.update(7, ScenarioPatch(team1_possession=60, team2_possession=40))
    assert (result["team1_possession"], result["team2_possession"]) == (60, 40)
    assert result["team1_offense"] == 70
    repo.get_by_id.assert_called_with(7, for_update=True)
    assert repo.flush.call_count == 1


def test_scenario_get_list_and_missing(service_context, scenario_projection):
    repo, _, _ = repositories(service_context, scenario_projection)
    service = scenario.ScenarioService(
        repo=service_context.repositories["ScenarioRepository"],
        team_service=service_context.services["TeamService"],
        match_service=service_context.services["MatchService"],
    )
    query = ScenarioQuery(team_id=2, limit=3, offset=1)
    assert service.list(query) == [service.get(7)]
    repo.list.assert_called_once_with(team_id=2, limit=3, offset=1)
    with pytest.raises(NotFound):
        service.get(999)


@pytest.mark.parametrize("mismatched", ["team", "match"])
def test_scenario_rejects_mismatched_database_dependencies(mismatched):
    database = object()
    repo = SimpleNamespace(database=database)
    team_service = SimpleNamespace(database=object() if mismatched == "team" else database)
    match_service = SimpleNamespace(database=object() if mismatched == "match" else database)
    with pytest.raises(ValueError, match="same Database"):
        scenario.ScenarioService(repo=repo, team_service=team_service, match_service=match_service)


def test_snapshot_and_existence_borrow_session_without_validation(scenario_projection):
    from datetime import datetime

    session, database = object(), object()
    repo = SimpleNamespace(
        database=database,
        get_projection=Mock(return_value=scenario_projection),
        exists=Mock(return_value=True),
    )
    service = scenario.ScenarioService(
        repo=repo,
        team_service=SimpleNamespace(database=database),
        match_service=SimpleNamespace(database=database),
    )
    original = vars(service).copy()
    scenario_projection.scenario.team1_offense = None
    captured = service.capture_state_in_transaction(session=session, scenario_id=7)
    expected = {
        column.name: getattr(scenario_projection.scenario, column.name)
        for column in scenario_projection.scenario.__table__.columns
    }
    expected.update(team1_name="First", team2_name="Second")
    assert dict(captured) == expected
    assert captured["team1_offense"] is None
    assert all(
        value is None or isinstance(value, (str, int, float, bool, datetime))
        for value in captured.values()
    )
    with pytest.raises(TypeError):
        captured["team1_offense"] = 99
    scenario_projection.scenario.team1_offense = 80
    assert captured["team1_offense"] is None
    assert service.require_exists_in_transaction(session=session, scenario_id=7) is None
    repo.get_projection.assert_called_once_with(session, 7)
    repo.exists.assert_called_once_with(session, 7)
    repo.get_projection.return_value = None
    repo.exists.return_value = False
    with pytest.raises(NotFound):
        service.capture_state_in_transaction(session=session, scenario_id=999)
    with pytest.raises(NotFound):
        service.require_exists_in_transaction(session=session, scenario_id=999)
    assert vars(service) == original
    assert service.database is database
