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
    )
    context.bind(scenario, "ScenarioRepository", repo)
    teams = SimpleNamespace(get_participants=Mock(return_value=[object(), object()]))
    matches = SimpleNamespace(
        get_by_id=Mock(return_value=SimpleNamespace(home_team_id=1, away_team_id=2))
    )
    context.bind(scenario, "TeamRepository", teams)
    context.bind(scenario, "MatchRepository", matches)
    return repo, teams, matches


def test_scenario_create_shared_session_ratings_and_match_locks(
    service_context, scenario_projection, scenario_body
):
    repo, teams, matches = repositories(service_context, scenario_projection)
    body = ScenarioCreate(**{**scenario_body, "match_id": 4, "team1_offense": 83})
    result = scenario.ScenarioService(service_context.database).create(body)
    assert result["team1_offense"] == 83 and result["team2_offense"] == 70
    assert result["team1_name"] == "First" and result["match_id"] == 4
    teams.get_participants.assert_called_once_with([1, 2], for_key_share=True)
    matches.get_by_id.assert_called_once_with(4, for_share=True)
    assert service_context.events == ["begin", "commit"]
    assert repo.add.call_count == 1


@pytest.mark.parametrize(
    "failure,error", [("team", NotFound), ("match", NotFound), ("mismatch", BadRequest)]
)
def test_scenario_invalid_references_rollback_without_insert(
    service_context, scenario_projection, scenario_body, failure, error
):
    repo, teams, matches = repositories(service_context, scenario_projection)
    if failure == "team":
        teams.get_participants.return_value = [object()]
    elif failure == "match":
        matches.get_by_id.return_value = None
    else:
        matches.get_by_id.return_value = SimpleNamespace(home_team_id=1, away_team_id=3)
    with pytest.raises(error):
        scenario.ScenarioService(service_context.database).create(
            ScenarioCreate(**{**scenario_body, "match_id": 4})
        )
    assert not repo.add.called
    assert service_context.events == ["begin", "rollback"]


def test_scenario_contract_rejects_same_team(scenario_body):
    with pytest.raises(ValidationError):
        ScenarioCreate(**{**scenario_body, "team2_id": 1})


def test_scenario_patch_validates_combined_state_before_mutation(
    service_context, scenario_projection
):
    repo, _, _ = repositories(service_context, scenario_projection)
    service = scenario.ScenarioService(service_context.database)
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
    service = scenario.ScenarioService(service_context.database)
    query = ScenarioQuery(team_id=2, limit=3, offset=1)
    assert service.list(query) == [service.get(7)]
    repo.list.assert_called_once_with(team_id=2, limit=3, offset=1)
    with pytest.raises(NotFound):
        service.get(999)
