from types import SimpleNamespace

from models.competition import Competition
from services import competition


def test_competition_preserves_repository_order_and_identity(service_context):
    rows = [
        Competition(competition_id=i, name="Cup", edition_label=year, category="women")
        for i, year in [(8, "1991"), (2, "2023")]
    ]
    service_context.repository("CompetitionRepository", SimpleNamespace(list=lambda: rows))
    result = competition.CompetitionService(
        repo=service_context.repositories["CompetitionRepository"],
        team_service=SimpleNamespace(
            database=service_context.repositories["CompetitionRepository"].database
        ),
    ).list()
    assert result == [
        {"competition_id": i, "name": "Cup", "edition_label": y, "category": "women"}
        for i, y in [(8, "1991"), (2, "2023")]
    ]
    assert service_context.events == ["begin", "commit"]


def test_simulation_preserves_order_and_calculates_after_transaction(service_context, monkeypatch):
    from schemas.competition.request import TournamentRequest

    def team(identity):
        return dict(team_id=identity, offense=70, defense=70, form=70, star_power=70, clutch=70)

    from types import SimpleNamespace

    service_context.repository("CompetitionRepository", SimpleNamespace())
    repo = service_context.repositories["CompetitionRepository"]

    def names(*, session, team_ids):
        assert service_context.state.active
        assert team_ids == [4, 3, 2, 1]
        return {i: str(i) for i in team_ids}

    service = competition.CompetitionService(
        repo=repo,
        team_service=SimpleNamespace(database=repo.database, capture_names_in_transaction=names),
    )

    def simulate(teams, count):
        assert not service_context.state.active
        assert [t.name for t in teams] == ["4", "3", "2", "1"]
        return [], "4", count, None

    monkeypatch.setattr(competition, "simulate_tournament", simulate)
    result = service.simulate(TournamentRequest(teams=[team(i) for i in [4, 3, 2, 1]]))
    assert result["kind"] == "hypothetical_knockout"
    assert service_context.events == ["begin", "commit"]
