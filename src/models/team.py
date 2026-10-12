from datetime import date

from sqlalchemy import CheckConstraint, Double, Identity, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, _nonblank


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("name_key", "category"),
        *_nonblank("name", "name_key", "category"),
        *(
            CheckConstraint(f"{name} BETWEEN 0 AND 100", name=f"{name}_range")
            for name in ("offense", "defense", "form", "star_power", "clutch")
        ),
        CheckConstraint("fifa_rank > 0", name="fifa_rank_positive"),
        CheckConstraint(
            "(offense IS NULL AND defense IS NULL AND form IS NULL AND star_power IS NULL "
            "AND clutch IS NULL) OR "
            "(ratings_source IS NOT NULL AND ratings_source ~ '[^[:space:]]')",
            name="ratings_attribution",
        ),
        CheckConstraint(
            "(fifa_rank IS NULL AND ranking_date IS NULL) OR "
            "(ranking_source IS NOT NULL AND ranking_source ~ '[^[:space:]]')",
            name="ranking_attribution",
        ),
    )
    team_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))
    offense: Mapped[float | None] = mapped_column(Double)
    defense: Mapped[float | None] = mapped_column(Double)
    form: Mapped[float | None] = mapped_column(Double)
    star_power: Mapped[float | None] = mapped_column(Double)
    clutch: Mapped[float | None] = mapped_column(Double)
    fifa_rank: Mapped[int | None]
    ratings_source: Mapped[str | None] = mapped_column(Text)
    ranking_source: Mapped[str | None] = mapped_column(Text)
    ranking_date: Mapped[date | None]
