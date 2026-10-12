"""Competition identities; historical insertion belongs to the importer."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.competition import Competition


class CompetitionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[Competition]:
        return list(
            self.session.scalars(
                select(Competition).order_by(
                    Competition.name, Competition.edition_label, Competition.competition_id
                )
            )
        )

    def get_by_id(self, competition_id: int) -> Competition | None:
        return self.session.get(Competition, competition_id)
