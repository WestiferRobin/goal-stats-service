from pydantic import BaseModel, ConfigDict


class ProblemDetailSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: str
    title: str
    status: int
    detail: str
    reason: str | None = None
    field_errors: dict[str, str] | None = None
