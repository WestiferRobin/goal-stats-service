"""Repository contracts on the existing ownership-verified disposable PostgreSQL fixture."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError

from infra.repositories.competition import CompetitionRepository
from infra.repositories.match import MatchRepository
from infra.repositories.prediction import PredictionRepository
from infra.repositories.scenario import ScenarioRepository
from infra.repositories.team import TeamRepository
from models.competition import Competition
from models.hold.football import FootballTeam
from models.match import Match
from models.prediction import Prediction
from models.scenario import Scenario
from models.team import Team
from tests.integration.football import conftest as football_fixtures

import_database = football_fixtures.import_database

pytestmark = pytest.mark.postgres
STAMP = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def database(import_database):
    with import_database.transaction() as session:
        session.add_all(
            [
                Team(team_id=i, name=n, name_key=n.lower(), category=c)
                for i, n, c in [(30, "Alpha", "b"), (20, "Zulu", "a"), (10, "Alpha", "a")]
            ]
        )
        session.add(FootballTeam(name="Prototype Only", ratings={"name": "Prototype Only"}))
        session.add_all(
            [
                Competition(
                    competition_id=i, name="Cup", name_key="cup", edition_label=y, category=c
                )
                for i, y, c in [(30, "2023", "b"), (20, "2023", "a"), (10, "2019", "a")]
            ]
        )
        session.flush()
        session.add_all(
            [
                Match(
                    match_id=i,
                    competition_id=c,
                    home_team_id=h,
                    away_team_id=a,
                    match_date=date(2023, 7, day),
                    home_score=1,
                    away_score=0,
                    score_basis="including_extra_time_no_shootout",
                    source="synthetic",
                    source_record_key=f"{i:064x}",
                    source_version="fixture",
                    source_file_sha256="a" * 64,
                    source_row=i,
                    source_url="fixture://test",
                    source_home_team="original home",
                    source_away_team="original away",
                    source_tournament="Cup",
                )
                for i, c, h, a, day in [
                    (30, 20, 20, 30, 21),
                    (20, 10, 30, 20, 20),
                    (10, 10, 10, 20, 20),
                ]
            ]
        )
    return import_database


def scenario(body, **changes):
    return Scenario(**{**body, "team1_id": 10, "team2_id": 20, "created_at": STAMP, **changes})


def prediction(scenario_id, **changes):
    return Prediction(
        **{
            "scenario_id": scenario_id,
            "generated_at": STAMP,
            "model_version": "fixture-v1",
            "team1_win_probability": 0.5,
            "draw_probability": 0.25,
            "team2_win_probability": 0.25,
            "input_snapshot": {"team1_name": "captured", "ratings": {"offense": 70}},
            "details": {"reasoning": ["synthetic"]},
            **changes,
        }
    )


def test_team_reads_order_identity_and_no_prototype_fallback(database):
    with database.transaction() as session:
        repo = TeamRepository(session)
        assert repo.session is session
        assert [r.team_id for r in repo.list()] == [10, 30, 20]
        assert repo.get_by_id(20).name == "Zulu"
        assert repo.get_by_id(999) is None
        assert [r.team_id for r in repo.get_participants([30, 10, 30, 999])] == [10, 30]
        assert repo.get_participants([]) == []
        assert all(r.name != "Prototype Only" for r in repo.list())
        assert repo.get_by_id(10).offense is None


def test_competition_reads_order_and_missing_identity(database):
    with database.transaction() as session:
        session.execute(text("SET TRANSACTION READ ONLY"))
        repo = CompetitionRepository(session)
        assert [r.competition_id for r in repo.list()] == [10, 20, 30]
        assert repo.get_by_id(10).edition_label == "2019"
        assert repo.get_by_id(999) is None


def test_match_join_is_one_query_and_materialized(database):
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(database.engine, "before_cursor_execute", capture)
    try:
        with database.transaction() as session:
            rows = MatchRepository(session).list()
        assert len(statements) == 1
        assert [r.match_id for r in rows] == [10, 20, 30]
        assert (rows[0].home_team_name, rows[0].away_team_name) == ("Alpha", "Zulu")
        assert (rows[0].competition_name, rows[0].edition_label) == ("Cup", "2019")
        assert rows[0].score_basis == "including_extra_time_no_shootout"
        assert rows[0].neutral is None
    finally:
        event.remove(database.engine, "before_cursor_execute", capture)


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
        assert [r.match_id for r in MatchRepository(session).list(**filters)] == expected


def test_match_detail_and_provenance_are_unchanged(database):
    with database.transaction() as session:
        session.execute(text("SET TRANSACTION READ ONLY"))
        repo = MatchRepository(session)
        assert repo.get_projection(20).home_team_id == 30
        assert repo.get_by_id(20).source_record_key == f"{20:064x}"
        assert repo.get_by_id(20).source_home_team == "original home"
        assert repo.get_projection(999) is None
        assert repo.get_by_id(999) is None


def test_scenario_insert_projection_update_and_missing(database, scenario_body):
    with database.transaction() as session:
        repo = ScenarioRepository(session)
        row = scenario(scenario_body, match_id=10)
        repo.add(row)
        identity = row.scenario_id
        assert identity is not None
        assert repo.exists(identity)
        assert repo.get_by_id(identity) is row
        projected = repo.get_projection(identity)
        assert projected.scenario is row
        assert (projected.team1_name, projected.team2_name) == ("Alpha", "Zulu")
        row.match_minute = 70  # Caller-validated state, repository only flushes.
        repo.flush()
        assert not repo.exists(999)
        assert repo.get_by_id(999) is None
        assert repo.get_projection(999) is None
    with database.transaction() as session:
        assert ScenarioRepository(session).get_by_id(identity).match_minute == 70


def test_scenario_order_filter_and_shared_projection(database, scenario_body):
    with database.transaction() as session:
        repo = ScenarioRepository(session)
        rows = [
            scenario(scenario_body),
            scenario(scenario_body, team1_id=30),
            scenario(scenario_body, created_at=datetime(2025, 1, 1, tzinfo=UTC)),
        ]
        for row in rows:
            repo.add(row)
        ids = [r.scenario_id for r in rows]
    with database.transaction() as session:
        repo = ScenarioRepository(session)
        assert [r.scenario.scenario_id for r in repo.list()] == [ids[1], ids[0], ids[2]]
        assert [r.scenario.scenario_id for r in repo.list(team_id=30)] == [ids[1]]
        assert len(repo.list(team_id=20)) == 3  # Away participant also matches.
        assert repo.list(team_id=999) == []
        page = repo.list(limit=1, offset=1)
        assert page[0].scenario.scenario_id == ids[0]
    assert page[0].team1_name == "Alpha"
    assert page[0].scenario.match_minute == scenario_body["match_minute"]


def test_prediction_append_history_and_snapshot_preservation(database, scenario_body):
    with database.transaction() as session:
        parent, other = scenario(scenario_body), scenario(scenario_body)
        ScenarioRepository(session).add(parent)
        ScenarioRepository(session).add(other)
        repo = PredictionRepository(session)
        rows = [
            prediction(parent.scenario_id),
            prediction(parent.scenario_id),
            prediction(parent.scenario_id, generated_at=datetime(2025, 1, 1, tzinfo=UTC)),
            prediction(other.scenario_id),
        ]
        for row in rows:
            repo.add(row)
        ids = [r.prediction_id for r in rows]
        parent_id = parent.scenario_id
        assert all(ids)
        parent.team1_offense = 99
    with database.transaction() as session:
        repo = PredictionRepository(session)
        history = repo.history(parent_id)
        assert [r.prediction_id for r in history] == [ids[1], ids[0], ids[2]]
        assert [r.prediction_id for r in repo.history(parent_id, limit=1, offset=1)] == [ids[0]]
        assert repo.history(999) == []
        assert repo.get_by_id(999) is None
        saved = repo.get_by_id(ids[0])
        assert saved.input_snapshot == {"team1_name": "captured", "ratings": {"offense": 70}}
        assert saved.model_version == "fixture-v1"
        assert saved.details == {"reasoning": ["synthetic"]}
        assert not hasattr(repo, "update") and not hasattr(repo, "delete")
    assert saved.input_snapshot["team1_name"] == "captured"


def test_shared_session_caller_rollback_undoes_all_writes(database, scenario_body, monkeypatch):
    with database.sessions() as session:
        repositories = [
            cls(session)
            for cls in (
                TeamRepository,
                CompetitionRepository,
                MatchRepository,
                ScenarioRepository,
                PredictionRepository,
            )
        ]
        assert all(repo.session is session for repo in repositories)

        def forbidden():
            pytest.fail("Repository attempted independent transaction control")

        with monkeypatch.context() as patch:
            patch.setattr(session, "commit", forbidden)
            patch.setattr(session, "rollback", forbidden)
            assert len(repositories[0].get_participants([10, 20], for_key_share=True)) == 2
            assert repositories[1].get_by_id(10) is not None
            assert repositories[2].get_by_id(10, for_share=True) is not None
            row = scenario(scenario_body)
            repositories[3].add(row)
            result = prediction(row.scenario_id)
            repositories[4].add(result)
            identity, prediction_id = row.scenario_id, result.prediction_id
            with database.sessions() as observer:
                assert ScenarioRepository(observer).get_by_id(identity) is None
                assert PredictionRepository(observer).get_by_id(prediction_id) is None
        session.rollback()
    with database.transaction() as session:
        assert ScenarioRepository(session).get_by_id(identity) is None
        assert PredictionRepository(session).get_by_id(prediction_id) is None


@pytest.mark.parametrize("kind", ["team", "match", "scenario"])
def test_postgresql_locks_conflict_until_caller_releases(database, scenario_body, kind):
    with database.transaction() as session:
        row = scenario(scenario_body)
        ScenarioRepository(session).add(row)
        scenario_id = row.scenario_id
    table, key, identity = {
        "team": ("teams", "team_id", 10),
        "match": ("matches", "match_id", 10),
        "scenario": ("scenarios", "scenario_id", scenario_id),
    }[kind]
    with database.sessions() as holder:
        if kind == "team":
            TeamRepository(holder).get_participants([10], for_key_share=True)
        elif kind == "match":
            MatchRepository(holder).get_by_id(10, for_share=True)
        else:
            ScenarioRepository(holder).get_by_id(scenario_id, for_update=True)
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
