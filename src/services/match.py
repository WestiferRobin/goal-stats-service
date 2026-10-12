"""Historical match filtering and response validation."""

from typing import Any

from werkzeug.exceptions import NotFound

from infra.repositories.match import MatchRepository
from infra.resources.db import Database
from schemas.match import CatalogMatchQuery, CatalogMatchResponse


class MatchService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list(self, query: CatalogMatchQuery) -> list[dict[str, Any]]:
        with self.database.transaction() as session:
            rows = MatchRepository(session).list(**query.model_dump())
            return [
                CatalogMatchResponse.model_validate(row, from_attributes=True).model_dump(
                    mode="json"
                )
                for row in rows
            ]

    def get(self, match_id: int) -> dict[str, Any]:
        with self.database.transaction() as session:
            row = MatchRepository(session).get_projection(match_id)
            if row is None:
                raise NotFound()
            return CatalogMatchResponse.model_validate(row, from_attributes=True).model_dump(
                mode="json"
            )
