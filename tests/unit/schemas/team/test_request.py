import pytest
from pydantic import ValidationError

from schemas.team import CatalogTeamPath


@pytest.mark.parametrize("value", [0, -1, 2147483648])
def test_team_path_bounds(value):
    with pytest.raises(ValidationError):
        CatalogTeamPath(team_id=value)
