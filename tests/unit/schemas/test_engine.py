import pytest
from pydantic import ValidationError

from schemas.engine import Modifier, TeamStats


def test_engine_defaults_are_independent_and_prototype_request_compatible():
    first, second = TeamStats(), TeamStats()
    first.modifiers.append(Modifier(reason="fixture", value=10))
    assert second.modifiers == []


@pytest.mark.parametrize(
    "values", [{"shots": -1}, {"red_cards": 12}, {"possession": 101}, {"extra": 1}]
)
def test_engine_stats_rejections(values):
    with pytest.raises(ValidationError):
        TeamStats(**values)
