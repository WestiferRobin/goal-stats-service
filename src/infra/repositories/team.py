"""Historical team reads using the caller's transaction."""

from collections.abc import Sequence
from contextlib import AbstractContextManager

from sqlalchemy import select
from sqlalchemy.orm import Session

from infra.resources.db import Database
from models.team import Team


class TeamRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def transaction(self) -> AbstractContextManager[Session]:
        """Provide a context whose boundary is chosen by the calling service."""
        return self.database.transaction()

    def get_by_id(self, session: Session, team_id: int) -> Team | None:
        return session.get(Team, team_id)

    def get_participants(
        self, session: Session, team_ids: Sequence[int], *, for_key_share: bool = False
    ) -> list[Team]:
        statement = select(Team).where(Team.team_id.in_(team_ids)).order_by(Team.team_id)
        if for_key_share:
            statement = statement.with_for_update(read=True, key_share=True)
        return list(session.scalars(statement))

    def list(self, session: Session) -> list[Team]:
        return list(session.scalars(select(Team).order_by(Team.name, Team.team_id)))
