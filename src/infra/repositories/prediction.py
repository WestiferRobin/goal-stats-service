"""Append and read saved predictions within a caller-owned transaction."""

from contextlib import AbstractContextManager

from sqlalchemy import select
from sqlalchemy.orm import Session

from infra.resources.db import Database
from models.prediction import Prediction


class PredictionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def transaction(self) -> AbstractContextManager[Session]:
        """Provide a context whose boundary is chosen by the calling service."""
        return self.database.transaction()

    def add(self, session: Session, prediction: Prediction) -> None:
        session.add(prediction)
        session.flush()

    def get_by_id(self, session: Session, prediction_id: int) -> Prediction | None:
        return session.get(Prediction, prediction_id)

    def history(
        self, session: Session, scenario_id: int, *, limit: int = 50, offset: int = 0
    ) -> list[Prediction]:
        return list(
            session.scalars(
                select(Prediction)
                .where(Prediction.scenario_id == scenario_id)
                .order_by(Prediction.generated_at.desc(), Prediction.prediction_id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
