import pytest
from pydantic import ValidationError

from schemas.competition.request import TournamentRequest


def team(identity):
    return dict(team_id=identity, offense=70, defense=70, form=70, star_power=70, clutch=70)


@pytest.mark.parametrize("count", [4, 8, 16, 32])
def test_ordered_bracket(count):
    entries = [team(i) for i in range(count, 0, -1)]
    assert [t.team_id for t in TournamentRequest(teams=entries).teams] == list(range(count, 0, -1))


@pytest.mark.parametrize(
    "kind", ["duplicate", "missing", "range", "count", "simulations", "string_id"]
)
def test_invalid_bracket(kind):
    entries = [team(i) for i in range(1, 5)]
    body = dict(teams=entries)
    if kind == "duplicate":
        entries[-1] = entries[0]
    if kind == "missing":
        del entries[0]["offense"]
    if kind == "range":
        entries[0]["offense"] = 101
    if kind == "count":
        entries.pop()
    if kind == "simulations":
        body["simulations"] = 999
    if kind == "string_id":
        entries[0]["team_id"] = "1"
    with pytest.raises(ValidationError):
        TournamentRequest(**body)
