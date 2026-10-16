import pytest

from infra.repositories.competition import CompetitionRepository
from infra.repositories.team import TeamRepository
from schemas.competition.request import TournamentRequest
from services.competition import CompetitionService
from services.team import TeamService


@pytest.mark.postgres
def test_simulation_releases_database_before_engine(small_catalog, import_database, monkeypatch):
    service = CompetitionService(
        repo=CompetitionRepository(import_database),
        team_service=TeamService(repo=TeamRepository(import_database)),
    )
    from models.team import Team

    with import_database.transaction() as session:
        session.add(
            Team(team_id=4, name="Sweden", name_key="sweden", category="women_senior_national")
        )

    def compute(teams, count):
        assert import_database.engine.pool.checkedout() == 0
        assert [t.name for t in teams] == ["Sweden", "Spain", "Japan", "England"]
        return [], "Sweden", count, None

    monkeypatch.setattr("services.competition.simulate_tournament", compute)
    body = TournamentRequest(
        teams=[
            dict(team_id=i, offense=70, defense=70, form=70, star_power=70, clutch=70)
            for i in [4, 3, 2, 1]
        ]
    )
    assert service.simulate(body)["predicted_champion"] == "Sweden"
