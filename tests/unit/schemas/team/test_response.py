import pytest
from pydantic import ValidationError

from schemas.team import CatalogTeamResponse, CatalogTeamsResponse


def test_historical_team_nulls_and_readiness():
    values = dict(
        team_id=1,
        name="Historical",
        category="women",
        offense=None,
        defense=None,
        form=None,
        star_power=None,
        clutch=None,
        fifa_rank=None,
        ranking_date=None,
    )
    row = CatalogTeamResponse(**values)
    assert CatalogTeamsResponse([row]).model_dump(mode="json") == [
        {**values, "prediction_ready": False}
    ]
    with pytest.raises(ValidationError):
        CatalogTeamResponse(**values, prediction_ready=True)
    del values["offense"]
    with pytest.raises(ValidationError):
        CatalogTeamResponse(**values)
