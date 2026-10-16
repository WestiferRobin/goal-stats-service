import pytest

from infra.repositories.match import MatchRepository
from infra.repositories.team import TeamRepository
from schemas.match.request import HistoricalComparison
from services.match import MatchService
from services.team import TeamService


@pytest.mark.postgres
def test_comparison_returns_materialized_historical_results(small_catalog, import_database):
    service = MatchService(
        repo=MatchRepository(import_database),
        team_service=TeamService(repo=TeamRepository(import_database)),
    )
    result = service.insights(HistoricalComparison(team1_id=3, team2_id=1))
    assert import_database.engine.pool.checkedout() == 0
    assert result["head_to_head"][0]["competition_name"] == "FIFA Women's World Cup"
    assert result["head_to_head"][0]["home_team_name"] == "Spain"
