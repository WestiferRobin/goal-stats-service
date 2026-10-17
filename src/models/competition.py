from sqlalchemy import Identity, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, _nonblank


class Competition(Base):
    __tablename__ = "competitions"
    __table_args__ = (
        UniqueConstraint("name_key", "edition_label", "category"),
        *_nonblank("name", "name_key", "edition_label", "category"),
    )
    competition_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    name_key: Mapped[str] = mapped_column(String(160))
    edition_label: Mapped[str] = mapped_column(String(40))
    category: Mapped[str] = mapped_column(String(40))
