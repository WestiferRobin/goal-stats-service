import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from infra.repositories.match import MatchRepository
from infra.repositories.scenario import ScenarioRepository
from infra.repositories.team import TeamRepository
from tests.fixtures.historical_database import scenario


@pytest.mark.postgres
def test_team_reads_order_identity_and_no_prototype_fallback(database):
    repo = TeamRepository(database)
    with repo.transaction() as session:
        assert vars(repo) == {"database": database}
        assert [r.team_id for r in repo.list(session)] == [10, 30, 20]
        assert repo.get_by_id(session, 20).name == "Zulu"
        assert repo.get_by_id(session, 999) is None
        assert [r.team_id for r in repo.get_participants(session, [30, 10, 30, 999])] == [10, 30]
        assert repo.get_participants(session, []) == []
        assert all(r.name != "Prototype Only" for r in repo.list(session))
        assert repo.get_by_id(session, 10).offense is None


@pytest.mark.postgres
@pytest.mark.parametrize("kind", ["team"])
def test_postgresql_locks_conflict_until_caller_releases(database, scenario_body, kind):
    with database.transaction() as session:
        row = scenario(scenario_body)
        ScenarioRepository(database).add(session, row)
        scenario_id = row.scenario_id
    table, key, identity = {
        "team": ("teams", "team_id", 10),
        "match": ("matches", "match_id", 10),
        "scenario": ("scenarios", "scenario_id", scenario_id),
    }[kind]
    with database.sessions() as holder:
        if kind == "team":
            TeamRepository(database).get_participants(holder, [10], for_key_share=True)
        elif kind == "match":
            MatchRepository(database).get_by_id(holder, 10, for_share=True)
        else:
            ScenarioRepository(database).get_by_id(holder, scenario_id, for_update=True)
        with database.sessions() as contender:
            with pytest.raises(OperationalError) as error:
                contender.execute(
                    text(f"SELECT * FROM {table} WHERE {key}=:id FOR UPDATE NOWAIT"),
                    {"id": identity},
                )
            assert error.value.orig.sqlstate == "55P03"
        if kind == "team":
            # KEY SHARE permits an ordinary non-key update; FOR SHARE would block it.
            with database.transaction() as updater:
                updater.execute(text("SET LOCAL lock_timeout = '100ms'"))
                updater.execute(
                    text("UPDATE teams SET offense=70, ratings_source='fixture' WHERE team_id=10")
                )
        holder.rollback()
    with database.transaction() as session:
        session.execute(
            text(f"SELECT * FROM {table} WHERE {key}=:id FOR UPDATE NOWAIT"), {"id": identity}
        )
