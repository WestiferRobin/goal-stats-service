"""Historical match filtering and response validation."""

from typing import Any

from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, NotFound

from infra.repositories.match import MatchRepository
from infra.resources.db import Database
from schemas.match import CatalogMatchQuery, CatalogMatchResponse
from schemas.match.request import HistoricalComparison
from schemas.match.response import HistoricalInsights
from services.team import TeamService


class MatchService:
    def __init__(self, *, repo: MatchRepository, team_service: TeamService) -> None:
        if repo.database is not team_service.database:
            raise ValueError("Repositories must share the same Database instance")
        self.team_service = team_service
        self.repo = repo

    @property
    def database(self) -> Database:
        """Application resource identity; no operation session is retained."""
        return self.repo.database

    def list(self, query: CatalogMatchQuery) -> list[dict[str, Any]]:
        with self.repo.transaction() as session:
            rows = self.repo.list(session, **query.model_dump())
            return [
                CatalogMatchResponse.model_validate(row, from_attributes=True).model_dump(
                    mode="json"
                )
                for row in rows
            ]

    def get(self, match_id: int) -> dict[str, Any]:
        with self.repo.transaction() as session:
            row = self.repo.get_projection(session, match_id)
            if row is None:
                raise NotFound()
            return CatalogMatchResponse.model_validate(row, from_attributes=True).model_dump(
                mode="json"
            )

    def require_match_participants_in_transaction(
        self, *, session: Session, match_id: int, team_ids: tuple[int, int]
    ) -> None:
        """Validate the historical match while borrowing the caller's session."""
        match = self.repo.get_by_id(session, match_id, for_share=True)
        if match is None:
            raise NotFound()
        if {match.home_team_id, match.away_team_id} != set(team_ids):
            raise BadRequest()

    def insights(self, query: HistoricalComparison) -> dict[str, Any]:
        with self.repo.transaction() as session:
            names = self.team_service.capture_names_in_transaction(
                session=session, team_ids=(query.team1_id, query.team2_id)
            )

            def read(
                team_id: int, opponent_team_id: int | None = None
            ) -> list[CatalogMatchResponse]:
                return [
                    CatalogMatchResponse.model_validate(row, from_attributes=True)
                    for row in self.repo.list(
                        session,
                        team_id=team_id,
                        opponent_team_id=opponent_team_id,
                        limit=query.limit,
                        offset=query.offset,
                    )
                ]

            return HistoricalInsights(
                team1_id=query.team1_id,
                team2_id=query.team2_id,
                team1_name=names[query.team1_id],
                team2_name=names[query.team2_id],
                head_to_head=read(query.team1_id, query.team2_id),
                team1_history=read(query.team1_id),
                team2_history=read(query.team2_id),
                limit=query.limit,
                offset=query.offset,
            ).model_dump(mode="json")
