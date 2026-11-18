import pytest
from pydantic import ValidationError

from schemas.problem import ProblemDetailSchema


def test_problem_contract_is_exact_frozen_and_required():
    payload = dict(type="about:blank", title="Bad Request", status=400, detail="Safe detail")
    problem = ProblemDetailSchema(**payload)
    assert problem.model_dump(mode="json", exclude_none=True) == payload
    for key in payload:
        with pytest.raises(ValidationError):
            ProblemDetailSchema.model_validate({k: v for k, v in payload.items() if k != key})
    with pytest.raises(ValidationError):
        ProblemDetailSchema.model_validate({**payload, "private": "secret"})
    with pytest.raises(ValidationError):
        problem.detail = "changed"
