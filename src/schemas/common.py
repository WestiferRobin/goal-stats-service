"""Shared input constraints and compatible timestamp serialization."""

from typing import Annotated
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
)


def nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("Name must be nonblank.")
    return value


def nonzero(value: UUID) -> UUID:
    if value.int == 0:
        raise ValueError("A nonempty UUID is required.")
    return value


Name = Annotated[str, Field(strict=True, min_length=1, max_length=200), AfterValidator(nonblank)]
Identity = Annotated[UUID, AfterValidator(nonzero)]
Timestamp = Annotated[
    AwareDatetime,
    PlainSerializer(lambda value: value.isoformat(), return_type=str),
    WithJsonSchema({"type": "string", "format": "date-time"}, mode="serialization"),
]


Count = Annotated[int, Field(ge=0, le=1000)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


def validate_possession(first: float, second: float) -> None:
    if abs(first + second - 100) > 0.01:
        raise ValueError("Possession must total 100")


class HistoryQuery(Contract):
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


CatalogID = Annotated[int, Field(ge=1, le=2147483647)]
