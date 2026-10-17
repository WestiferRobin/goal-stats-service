"""Historical team responses with service-owned read transactions."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session
from werkzeug.exceptions import NotFound

from infra.repositories.team import TeamRepository
from infra.resources.db import Database
from schemas.team import CatalogTeamResponse


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
