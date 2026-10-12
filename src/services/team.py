"""Historical team responses with service-owned read transactions."""

from typing import Any

from werkzeug.exceptions import NotFound

from infra.repositories.team import TeamRepository
from infra.resources.db import Database
from schemas.team import CatalogTeamResponse


class TeamService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list(self) -> list[dict[str, Any]]:
        with self.database.transaction() as session:
            return [
                CatalogTeamResponse.model_validate(row, from_attributes=True).model_dump(
                    mode="json"
                )
                for row in TeamRepository(session).list()
            ]

    def get(self, team_id: int) -> dict[str, Any]:
        with self.database.transaction() as session:
            row = TeamRepository(session).get_by_id(team_id)
            if row is None:
                raise NotFound()
            return CatalogTeamResponse.model_validate(row, from_attributes=True).model_dump(
                mode="json"
            )
