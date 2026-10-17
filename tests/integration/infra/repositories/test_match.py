from datetime import date

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError

from infra.repositories.match import MatchRepository
from infra.repositories.scenario import ScenarioRepository
from infra.repositories.team import TeamRepository
from tests.fixtures.historical_database import scenario


@pytest.mark.postgres
def test_match_join_is_one_query_and_materialized(database):
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(database.engine, "before_cursor_execute", capture)
    try:
        with database.transaction() as session:
            rows = MatchRepository(database).list(session)
        assert len(statements) == 1
        assert [r.match_id for r in rows] == [10, 20, 30]
        assert (rows[0].home_team_name, rows[0].away_team_name) == ("Alpha", "Zulu")
        assert (rows[0].competition_name, rows[0].edition_label) == ("Cup", "2019")
        assert rows[0].score_basis == "including_extra_time_no_shootout"
        assert rows[0].neutral is None
    finally:
        event.remove(database.engine, "before_cursor_execute", capture)


@pytest.mark.postgres
@pytest.mark.parametrize(
    "filters,expected",
    [
        ({"competition_id": 10}, [10, 20]),
        ({"team_id": 30}, [20, 30]),
        ({"date_from": date(2023, 7, 21)}, [30]),
        ({"date_to": date(2023, 7, 20)}, [10, 20]),
        (
            {
                "team_id": 30,
                "competition_id": 10,
                "date_from": date(2023, 7, 20),
                "date_to": date(2023, 7, 20),
            },
            [20],
        ),
        ({"limit": 1, "offset": 1}, [20]),
        ({"competition_id": 999}, []),
    ],
)
def test_match_filters_and_pagination(database, filters, expected):
    with database.transaction() as session:
        assert [r.match_id for r in MatchRepository(database).list(session, **filters)] == expected


@pytest.mark.postgres
def test_match_detail_and_provenance_are_unchanged(database):
    with database.transaction() as session:
        session.execute(text("SET TRANSACTION READ ONLY"))
        repo = MatchRepository(database)
        assert repo.get_projection(session, 20).home_team_id == 30
        assert repo.get_by_id(session, 20).source_record_key == f"{20:064x}"
        assert repo.get_by_id(session, 20).source_home_team == "original home"
        assert repo.get_projection(session, 999) is None
        assert repo.get_by_id(session, 999) is None


@pytest.mark.postgres
@pytest.mark.parametrize("kind", ["match"])
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


@pytest.mark.postgres
def test_head_to_head_matches_both_orientations_and_has_stable_pagination(database):
    with database.transaction() as session:
        repo = MatchRepository(database)
        for first, second in [(20, 30), (30, 20)]:
            assert [
                r.match_id for r in repo.list(session, team_id=first, opponent_team_id=second)
            ] == [20, 30]
        assert [
            r.match_id
            for r in repo.list(session, team_id=20, opponent_team_id=30, limit=1, offset=1)
        ] == [30]
        assert repo.list(session, team_id=10, opponent_team_id=30) == []
