"""Historical competition responses; imports remain separately owned."""

from typing import Any

from infra.repositories.competition import CompetitionRepository
from infra.resources.db import Database
from schemas.competition import CatalogCompetitionResponse


class CompetitionService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list(self) -> list[dict[str, Any]]:
        with self.database.transaction() as session:
            return [
                CatalogCompetitionResponse.model_validate(row, from_attributes=True).model_dump(
                    mode="json"
                )
                for row in CompetitionRepository(session).list()
            ]
