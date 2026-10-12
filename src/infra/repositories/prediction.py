"""Append and read saved predictions within a caller-owned transaction."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.prediction import Prediction


class PredictionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, prediction: Prediction) -> None:
        self.session.add(prediction)
        self.session.flush()

    def get_by_id(self, prediction_id: int) -> Prediction | None:
        return self.session.get(Prediction, prediction_id)

    def history(self, scenario_id: int, *, limit: int = 50, offset: int = 0) -> list[Prediction]:
        return list(
            self.session.scalars(
                select(Prediction)
                .where(Prediction.scenario_id == scenario_id)
                .order_by(Prediction.generated_at.desc(), Prediction.prediction_id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
