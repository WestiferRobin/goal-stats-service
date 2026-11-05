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


# Synthetic expectations are independent of the repository calculation.
@pytest.fixture
def summary_database(import_database):
    from datetime import date

    from models.competition import Competition
    from models.team import Team

    with import_database.transaction() as session:
        session.add_all(
            [
                Team(
                    team_id=i,
                    name=f"Team {i}",
                    name_key=f"team {i}",
                    category="women_senior_national",
                )
                for i in (1, 2, 3, 4)
            ]
        )
        session.add_all(
            [
                Competition(
                    competition_id=i,
                    name=name,
                    name_key=key,
                    edition_label=edition,
                    category=category,
                )
                for i, name, key, edition, category in [
                    (1, "World Cup", "fifa women's world cup", "2019", "women_senior_national"),
                    (2, "World Cup", "fifa women's world cup", "2023", "women_senior_national"),
                    (3, "Other Cup", "other cup", "2023", "women_senior_national"),
                    (4, "World Cup", "fifa women's world cup", "2023", "women_youth"),
                ]
            ]
        )
        session.flush()
        session.add_all(
            [
                summary_match(1, 1, 1, 2, 3, 1, date(2019, 6, 1)),
                summary_match(2, 1, 2, 1, 0, 2, date(2019, 6, 2)),
                # Extra time is already included; no shootout winner is inferred.
                summary_match(3, 2, 1, 2, 1, 1, date(2023, 7, 1)),
                summary_match(4, 2, 2, 1, 2, 1, date(2023, 7, 2)),
                summary_match(5, 3, 1, 2, 99, 0, date(2023, 7, 1)),
                summary_match(6, 4, 1, 2, 99, 0, date(2023, 7, 1)),
                summary_match(7, 2, 2, 3, 99, 0, date(2023, 7, 1)),
            ]
        )
    return import_database


def summary_match(
    identity,
    competition,
    home,
    away,
    home_score,
    away_score,
    day,
    basis="including_extra_time_no_shootout",
):
    from models.match import Match

    return Match(
        match_id=identity,
        competition_id=competition,
        home_team_id=home,
        away_team_id=away,
        home_score=home_score,
        away_score=away_score,
        match_date=day,
        score_basis=basis,
        source="summary_fixture",
        source_record_key=f"{identity:064x}",
        source_version="synthetic",
        source_file_sha256="a" * 64,
        source_row=identity,
        source_url="fixture://summary",
        source_home_team=f"Team {home}",
        source_away_team=f"Team {away}",
        source_tournament="synthetic",
    )


@pytest.mark.postgres
@pytest.mark.parametrize(
    "filters,expected",
    [
        ({}, (4, 2, 1, 1, 7, 4, 3, 2, 0)),
        ({"competition_id": 1}, (2, 2, 0, 0, 5, 1, 4, 1, 0)),
        ({"competition_id": 2}, (2, 0, 1, 1, 2, 3, -1, 1, 0)),
        ({"date_from": "2023-07-01", "date_to": "2023-07-01"}, (1, 0, 1, 0, 1, 1, 0, 1, 0)),
        ({"date_from": "2019-06-02", "date_to": "2023-07-01"}, (2, 1, 1, 0, 3, 1, 2, 2, 0)),
        (
            {"competition_id": 2, "date_from": "2023-07-02", "date_to": "2023-07-02"},
            (1, 0, 0, 1, 1, 2, -1, 1, 0),
        ),
        ({"date_from": "2023-07-02"}, (1, 0, 0, 1, 1, 2, -1, 1, 0)),
        ({"date_to": "2019-06-01"}, (1, 1, 0, 0, 3, 1, 2, 1, 0)),
        ({"competition_id": 3}, (0,) * 9),
        ({"competition_id": 4}, (0,) * 9),
        ({"competition_id": 999}, (0,) * 9),
        ({"date_from": "2024-01-01"}, (0,) * 9),
        ({"competition_id": 1, "date_from": "2023-01-01"}, (0,) * 9),
    ],
)
def test_summary_totals_filters_and_scope(summary_database, filters, expected):
    from dataclasses import astuple
    from datetime import date

    filters = {
        key: date.fromisoformat(value) if key.startswith("date_") else value
        for key, value in filters.items()
    }
    repo = TeamRepository(summary_database)
    with repo.transaction() as session:
        assert astuple(repo.summary(session, team_id=1, **filters)) == expected


@pytest.mark.postgres
@pytest.mark.parametrize(
    "team_id,expected",
    [
        (2, (5, 2, 1, 2, 103, 7, 96, 2, 0)),
        (4, (0,) * 9),
        (999, (0,) * 9),
    ],
)
def test_summary_other_participants_and_empty(summary_database, team_id, expected):
    from dataclasses import astuple

    repo = TeamRepository(summary_database)
    with repo.transaction() as session:
        assert astuple(repo.summary(session, team_id=team_id)) == expected


@pytest.mark.postgres
@pytest.mark.parametrize("mixed", [False, True])
def test_summary_flags_unsupported_without_excluding_rows(summary_database, mixed):
    from dataclasses import astuple

    from sqlalchemy import update

    from models.match import Match

    with summary_database.transaction() as session:
        statement = update(Match).where(Match.match_id.in_([1] if mixed else [1, 2, 3, 4]))
        session.execute(statement.values(score_basis="unsupported_fixture"))
    repo = TeamRepository(summary_database)
    with repo.transaction() as session:
        assert astuple(repo.summary(session, team_id=1)) == (
            4,
            2,
            1,
            1,
            7,
            4,
            3,
            2,
            1 if mixed else 4,
        )
        assert repo.summary(session, team_id=1, competition_id=2).unsupported_score_basis_count == (
            0 if mixed else 2
        )


@pytest.mark.postgres
def test_summary_over_200_records_one_select_no_writes(summary_database):
    from dataclasses import astuple
    from datetime import date

    from sqlalchemy import event

    with summary_database.transaction() as session:
        session.add_all(
            [
                summary_match(
                    i,
                    2,
                    4 if i % 2 else 3,
                    3 if i % 2 else 4,
                    2 if i % 2 else 1,
                    1 if i % 2 else 2,
                    date(2023, 7, 3),
                )
                for i in range(100, 301)
            ]
        )
    statements = []

    def track(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(summary_database.engine, "before_cursor_execute", track)
    try:
        repo = TeamRepository(summary_database)
        with repo.transaction() as session:
            assert astuple(repo.summary(session, team_id=4)) == (
                201,
                201,
                0,
                0,
                402,
                201,
                201,
                1,
                0,
            )
        assert len(statements) == 1
        sql = statements[0].upper()
        assert sql.lstrip().startswith("SELECT")
        assert all(token not in sql for token in ("LIMIT", "OFFSET", "GROUP BY"))
    finally:
        event.remove(summary_database.engine, "before_cursor_execute", track)
