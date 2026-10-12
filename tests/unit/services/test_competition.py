from types import SimpleNamespace

from models.competition import Competition
from services import competition


def test_competition_preserves_repository_order_and_identity(service_context):
    rows = [
        Competition(competition_id=i, name="Cup", edition_label=year, category="women")
        for i, year in [(8, "1991"), (2, "2023")]
    ]
    service_context.bind(competition, "CompetitionRepository", SimpleNamespace(list=lambda: rows))
    result = competition.CompetitionService(service_context.database).list()
    assert result == [
        {"competition_id": i, "name": "Cup", "edition_label": y, "category": "women"}
        for i, y in [(8, "1991"), (2, "2023")]
    ]
    assert service_context.events == ["begin", "commit"]
