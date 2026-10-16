# mypy: disable-error-code="no-untyped-call"
"""Historical competition responses; imports remain separately owned."""

from typing import Any

from football.engine import Team, simulate_tournament
from infra.repositories.competition import CompetitionRepository
from schemas.competition import CatalogCompetitionResponse
from schemas.competition.request import TournamentRequest
from schemas.competition.response import TournamentResponse
from services.team import TeamService


class CompetitionService:
    def __init__(self, *, repo: CompetitionRepository, team_service: TeamService) -> None:
        if repo.database is not team_service.database:
            raise ValueError("Repositories must share the same Database instance")
        self.team_service = team_service
        self.repo = repo

    def list(self) -> list[dict[str, Any]]:
        with self.repo.transaction() as session:
            return [
                CatalogCompetitionResponse.model_validate(row, from_attributes=True).model_dump(
                    mode="json"
                )
                for row in self.repo.list(session)
            ]

    def simulate(self, body: TournamentRequest) -> dict[str, Any]:
        with self.repo.transaction() as session:
            names = self.team_service.capture_names_in_transaction(
                session=session, team_ids=[t.team_id for t in body.teams]
            )
        teams = [
            Team(name=names[t.team_id], **t.model_dump(exclude={"team_id"})) for t in body.teams
        ]
        results, champion, count, final = simulate_tournament(teams, body.simulations)
        return TournamentResponse.model_validate(
            dict(
                results=results,
                predicted_champion=champion,
                simulations=count,
                most_common_final=final,
            )
        ).model_dump(mode="json")
