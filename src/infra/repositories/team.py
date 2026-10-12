"""Historical team reads using the caller's transaction."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.team import Team


class TeamRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, team_id: int) -> Team | None:
        return self.session.get(Team, team_id)

    def get_participants(
        self, team_ids: Sequence[int], *, for_key_share: bool = False
    ) -> list[Team]:
        statement = select(Team).where(Team.team_id.in_(team_ids)).order_by(Team.team_id)
        if for_key_share:
            statement = statement.with_for_update(read=True, key_share=True)
        return list(self.session.scalars(statement))

    def list(self) -> list[Team]:
        return list(self.session.scalars(select(Team).order_by(Team.name, Team.team_id)))
