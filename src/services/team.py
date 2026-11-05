"""Historical team responses with service-owned read transactions."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session
from werkzeug.exceptions import NotFound

from infra.repositories.team import TeamRepository
from infra.resources.db import Database
from schemas.team import CatalogTeamResponse
from schemas.team.request import TeamSummaryQuery
from schemas.team.response import TeamSummaryResponse


class TeamService:
    def __init__(self, *, repo: TeamRepository) -> None:
        self.repo = repo

    @property
    def database(self) -> Database:
        """Application resource identity; no operation session is retained."""
        return self.repo.database

    def list(self) -> list[dict[str, Any]]:
        with self.repo.transaction() as session:
            return [
                CatalogTeamResponse.model_validate(row, from_attributes=True).model_dump(
                    mode="json"
                )
                for row in self.repo.list(session)
            ]

    def get(self, team_id: int) -> dict[str, Any]:
        with self.repo.transaction() as session:
            row = self.repo.get_by_id(session, team_id)
            if row is None:
                raise NotFound()
            return CatalogTeamResponse.model_validate(row, from_attributes=True).model_dump(
                mode="json"
            )

    def summary(self, team_id: int, query: TeamSummaryQuery) -> dict[str, Any]:
        """Read available records using provisional recorded-final-score semantics."""
        with self.repo.transaction() as session:
            row = self.repo.get_by_id(session, team_id)
            if row is None:
                raise NotFound()
            totals = self.repo.summary(session, team_id=team_id, **query.model_dump())
            if totals.unsupported_score_basis_count:
                raise RuntimeError("Historical summary has unsupported score semantics")
            return TeamSummaryResponse(
                team_id=row.team_id,
                name=row.name,
                matches_played=totals.matches_played,
                wins=totals.wins,
                draws=totals.draws,
                losses=totals.losses,
                goals_for=totals.goals_for,
                goals_against=totals.goals_against,
                goal_difference=totals.goal_difference,
                tournament_appearances=totals.tournament_appearances,
                filters=query,
                score_basis="including_extra_time_no_shootout" if totals.matches_played else None,
                result_definition="recorded_final_score",
                coverage_status=(
                    "available_records_only" if totals.matches_played else "no_matching_records"
                ),
            ).model_dump(mode="json")

    def require_participants_in_transaction(
        self, *, session: Session, team_ids: tuple[int, int]
    ) -> None:
        """Validate participants and hold key-share locks in the caller's transaction."""
        teams = self.repo.get_participants(session, team_ids, for_key_share=True)
        if len(teams) != 2:
            raise NotFound()

    def capture_names_in_transaction(
        self, *, session: Session, team_ids: Sequence[int]
    ) -> dict[int, str]:
        """Copy normalized identities; callers own the transaction and supply ratings."""
        rows = self.repo.get_participants(session, team_ids, for_key_share=True)
        if len(rows) != len(set(team_ids)):
            raise NotFound()
        return {row.team_id: row.name for row in rows}
