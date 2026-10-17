"""Competition identities; historical insertion belongs to the importer."""

from contextlib import AbstractContextManager

from sqlalchemy import select
from sqlalchemy.orm import Session

from infra.resources.db import Database
from models.competition import Competition


class CompetitionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def transaction(self) -> AbstractContextManager[Session]:
        """Provide a context whose boundary is chosen by the calling service."""
        return self.database.transaction()

    def list(self, session: Session) -> list[Competition]:
        return list(
            session.scalars(
                select(Competition).order_by(
                    Competition.name, Competition.edition_label, Competition.competition_id
                )
            )
        )

    def get_by_id(self, session: Session, competition_id: int) -> Competition | None:
        return session.get(Competition, competition_id)
