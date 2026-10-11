"""Scenario API and persistence tests use only ownership-verified disposable PostgreSQL."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from models.base import Base
from models.catalog import Match, Team
from models.scenario import Scenario
from schemas.scenarios import ScenarioState

pytestmark = pytest.mark.postgres
URL = "/api/v1/scenarios"


@pytest.fixture
def scenario_body():
    body = {
        "title": "Synthetic scenario fixture",
        "team1_id": 1,
        "team2_id": 2,
        "match_id": None,
        "match_minute": 65,
    }
    for side in (1, 2):
        for field in (
            "goals",
            "shots",
            "shots_on_target",
            "big_chances",
            "defender_blocks",
            "goalkeeper_saves",
            "corners",
            "yellow_cards",
            "red_cards",
        ):
            body[f"team{side}_{field}"] = 0
        body[f"team{side}_possession"] = 50
        for field in ("offense", "defense", "form", "star_power", "clutch"):
            body[f"team{side}_{field}"] = 70
    return body


@pytest.fixture
def scenario_client(import_database, app_factory, postgres_config, monkeypatch):
    with import_database.transaction() as session:
        session.add_all(
            [
                Team(team_id=i, name=name, name_key=name.lower(), category="test")
                for i, name in [(1, "First"), (2, "Second"), (3, "Third")]
            ]
        )
        session.execute(
            text(
                "INSERT INTO competitions (competition_id,name,name_key,edition_label,category) "
                "VALUES (1,'Test','test','2023','test')"
            )
        )
        session.flush()
        session.add(
            Match(
                match_id=1,
                competition_id=1,
                home_team_id=1,
                away_team_id=2,
                match_date=datetime(2023, 8, 20).date(),
                home_score=1,
                away_score=0,
                score_basis="including_extra_time_no_shootout",
                source="test",
                source_record_key="a" * 64,
                source_file_sha256="b" * 64,
                source_row=1,
                source_version="test",
                source_url="https://example.com/test",
                source_home_team="First",
                source_away_team="Second",
                source_tournament="Test",
            )
        )
    monkeypatch.setattr("main.Database", lambda _: import_database)
    return app_factory(postgres_config).test_client()


def create(client, body):
    response = client.post(URL, json=body)
    assert response.status_code == 201, response.json
    return response


def test_create_reopen_update_and_new_app(
    scenario_client, scenario_body, import_database, app_factory, postgres_config
):
    client = scenario_client
    assert client.get(URL).json == []
    response = create(client, scenario_body)
    saved = response.json
    assert response.headers["Location"] == f"{URL}/{saved['scenario_id']}"
    assert datetime.fromisoformat(saved["created_at"]).tzinfo is not None
    assert saved["team1_name"] == "First" and saved["team2_name"] == "Second"
    assert saved["prediction_ready"] is True
    assert saved["match_id"] is saved["team1_fifa_rank"] is saved["team2_fifa_rank"] is None
    assert saved["team1_modifier_total"] == saved["team2_modifier_total"] == 0
    assert client.get(response.headers["Location"]).json == saved
    with import_database.transaction() as session:
        row = session.get(Scenario, saved["scenario_id"])
        assert row.team1_id == 1 and row.team2_id == 2
        assert row.match_minute == 65 and row.team1_offense == 70
        # Catalog changes must never rewrite the stored input snapshot.
        session.get(Team, 1).offense = 90
        session.get(Team, 1).ratings_source = "test"
    patch = {
        "match_minute": 70,
        "team1_goals": 1,
        "team1_possession": 60,
        "team2_possession": 40,
        "team1_modifier_total": -3,
    }
    updated = client.patch(response.headers["Location"], json=patch)
    assert updated.status_code == 200
    assert updated.json == {**saved, **patch}
    # Dispose pooled connections and reopen through an independent application instance.
    import_database.dispose()
    second = app_factory(postgres_config).test_client()
    assert second.get(response.headers["Location"]).json == updated.json
    with import_database.transaction() as session:
        row = session.get(Scenario, saved["scenario_id"])
        assert row.match_minute == 70 and row.team1_goals == 1 and row.team1_offense == 70


@pytest.mark.parametrize("reverse", [False, True])
def test_optional_match_agreement(scenario_client, scenario_body, reverse):
    body = {**scenario_body, "match_id": 1, "team1_fifa_rank": 1}
    if reverse:
        body["team1_id"], body["team2_id"] = body["team2_id"], body["team1_id"]
    result = create(scenario_client, body).json
    assert result["match_id"] == 1 and result["team1_fifa_rank"] == 1
    assert result["team1_id"] == body["team1_id"]


@pytest.mark.parametrize(
    ("changes", "status"),
    [
        ({"team1_id": 999}, 404),
        ({"team2_id": 999}, 404),
        ({"match_id": 999}, 404),
        ({"team1_id": 2}, 400),
        ({"match_id": 1, "team2_id": 3}, 400),
        ({"team1_id": 0}, 400),
        ({"team1_id": "1"}, 400),
        ({"team1_id": True}, 400),
        ({"match_minute": 121}, 400),
        ({"match_minute": -1}, 400),
        ({"team1_goals": -1}, 400),
        ({"team1_goals": 1.5}, 400),
        ({"team1_goals": True}, 400),
        ({"team1_goals": "1"}, 400),
        ({"team1_shots_on_target": 1001}, 400),
        ({"team1_red_cards": 12}, 400),
        ({"team1_possession": 101}, 400),
        ({"team1_possession": 40}, 400),
        ({"team1_possession": float("nan")}, 400),
        ({"team1_possession": float("inf")}, 400),
        ({"team1_offense": None}, 400),
        ({"team1_offense": -1}, 400),
        ({"team2_defense": 101}, 400),
        ({"team1_offense": float("nan")}, 400),
        ({"team1_offense": float("inf")}, 400),
        ({"team1_fifa_rank": 0}, 400),
        ({"team1_fifa_rank": 1.5}, 400),
        ({"team1_modifier_total": float("inf")}, 400),
        ({"team1_modifier_total": 3001}, 400),
        ({"prediction_ready": True}, 400),
        ({"unexpected": 1}, 400),
    ],
)
def test_invalid_create_is_atomic(scenario_client, scenario_body, import_database, changes, status):
    response = scenario_client.post(URL, json={**scenario_body, **changes})
    assert response.status_code == status
    assert response.mimetype == "application/problem+json"
    with import_database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(Scenario)) == 0


@pytest.mark.parametrize(
    "missing",
    [
        "team1_id",
        "match_minute",
        "team1_goals",
        "team1_possession",
        "team2_shots_on_target",
        "team1_offense",
        "team2_clutch",
    ],
)
def test_missing_inputs_are_never_invented(scenario_client, scenario_body, missing):
    del scenario_body[missing]
    assert scenario_client.post(URL, json=scenario_body).status_code == 400
    assert scenario_client.get(URL).json == []


@pytest.mark.parametrize(
    "patch",
    [
        {},
        {"team1_id": 3},
        {"team2_id": 3},
        {"match_id": 1},
        {"team1_offense": 90},
        {"team2_fifa_rank": 2},
        {"created_at": "2020-01-01"},
        {"scenario_id": 2},
        {"match_minute": None},
        {"match_minute": 121},
        {"team1_possession": 20},
        {"team1_goals": -1},
        {"team1_modifier_total": float("nan")},
        {"team1_goals": 2, "team1_possession": 60},
    ],
)
def test_invalid_patch_preserves_entire_row(scenario_client, scenario_body, patch):
    response = create(scenario_client, scenario_body)
    location = response.headers["Location"]
    failed = scenario_client.patch(location, json=patch)
    assert failed.status_code == 400
    assert failed.mimetype == "application/problem+json"
    assert scenario_client.get(location).json == response.json


def test_pagination_filter_and_order(scenario_client, scenario_body, import_database):
    saved = [
        create(scenario_client, {**scenario_body, "team2_id": second}).json for second in (2, 3, 2)
    ]
    with import_database.transaction() as session:
        session.execute(text("UPDATE scenarios SET created_at = '2026-01-01T00:00:00Z'"))
    all_rows = scenario_client.get(URL).json
    assert [r["scenario_id"] for r in all_rows] == [r["scenario_id"] for r in saved[::-1]]
    assert scenario_client.get(URL + "?limit=1&offset=1").json == all_rows[1:2]
    assert len(scenario_client.get(URL + "?team_id=1").json) == 3
    assert len(scenario_client.get(URL + "?team_id=2").json) == 2
    assert scenario_client.get(URL + "?team_id=999").json == []
    assert scenario_client.get(URL + "?offset=999").json == []


@pytest.mark.parametrize(
    "suffix",
    [
        "?limit=0",
        "?limit=201",
        "?offset=-1",
        "?team_id=0",
        "?offset=9223372036854775808",
        "?unknown=1",
        "/abc",
        "/0",
    ],
)
def test_invalid_paths_and_queries(scenario_client, suffix):
    assert scenario_client.get(URL + suffix).status_code == 400


def test_missing_scenario(scenario_client):
    assert scenario_client.get(URL + "/999").status_code == 404
    assert scenario_client.patch(URL + "/999", json={"match_minute": 1}).status_code == 404


@pytest.mark.parametrize("method", ["post", "patch"])
@pytest.mark.parametrize("body", [[], None, "text", 42])
def test_nonobject_body(scenario_client, method, body):
    path = URL if method == "post" else URL + "/1"
    response = getattr(scenario_client, method)(
        path, data=json.dumps(body), content_type="application/json"
    )
    assert response.status_code == 400


def test_failures_roll_back_without_leaking_details(scenario_client, scenario_body, monkeypatch):
    saved = create(scenario_client, scenario_body)

    def fail(session):
        raise OperationalError("private sql and credential", {}, Exception("secret"))

    event.listen(Session, "before_commit", fail)
    try:
        for method, path, body in [
            ("post", URL, scenario_body),
            ("patch", saved.headers["Location"], {"team1_goals": 4}),
        ]:
            response = getattr(scenario_client, method)(path, json=body)
            assert response.status_code == 500
            assert response.json["detail"] == "An unexpected error occurred."
            assert "secret" not in response.text and "credential" not in response.text
    finally:
        event.remove(Session, "before_commit", fail)
    assert scenario_client.get(URL).json == [saved.json]


def test_conflict_rolls_back(scenario_client, scenario_body, monkeypatch):
    def fail(session):
        raise IntegrityError("private sql", {}, Exception("secret"))

    event.listen(Session, "before_commit", fail)
    try:
        response = scenario_client.post(URL, json=scenario_body)
        assert response.status_code == 409
        assert "private" not in response.text and "secret" not in response.text
    finally:
        event.remove(Session, "before_commit", fail)
    assert scenario_client.get(URL).json == []


def test_schema_migration_preserves_existing_data(scenario_client, scenario_body, import_database):
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    with import_database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "e3a71c92b406")  # Disposable schema only.
        tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
        before = {
            table: connection.execute(
                text(f'SELECT row_to_json(t)::text FROM "{table}" t ORDER BY row_to_json(t)::text')
            ).all()
            for table in tables
        }
        command.upgrade(config, "head")
        for table in tables:
            assert (
                connection.execute(
                    text(
                        f'SELECT row_to_json(t)::text FROM "{table}" t '
                        "ORDER BY row_to_json(t)::text"
                    )
                ).all()
                == before[table]
            )
        inspector = inspect(connection)
        assert set(inspector.get_table_names()) == tables | {
            "alembic_version",
            "scenarios",
            "predictions",
        }
        assert inspector.get_pk_constraint("scenarios")["constrained_columns"] == ["scenario_id"]
        assert next(c for c in inspector.get_columns("scenarios") if c["name"] == "scenario_id")[
            "identity"
        ]
        keys = inspector.get_foreign_keys("scenarios")
        assert {tuple(k["constrained_columns"]) for k in keys} == {
            ("team1_id",),
            ("team2_id",),
            ("match_id",),
        }
        assert all(k["options"]["ondelete"] == "RESTRICT" for k in keys)
        assert {tuple(i["column_names"]) for i in inspector.get_indexes("scenarios")} == {
            ("team1_id",),
            ("team2_id",),
            ("match_id",),
            ("created_at", "scenario_id"),
        }
        context = MigrationContext.configure(connection, opts={"compare_server_default": True})
        assert compare_metadata(context, Base.metadata) == []
    assert create(scenario_client, scenario_body).status_code == 201


@pytest.mark.parametrize(
    "changes",
    [
        {"team1_id": 2},
        {"team1_id": 999},
        {"match_id": 999},
        {"match_minute": -1},
        {"match_minute": 121},
        {"team1_goals": -1},
        {"team2_red_cards": 12},
        {"team1_possession": 101},
        {"team1_possession": 60},
        {"team1_possession": float("nan")},
        {"team1_offense": None},
        {"team1_offense": float("nan")},
        {"team1_offense": float("inf")},
        {"team1_defense": -1},
        {"team2_clutch": 101},
        {"team1_modifier_total": float("nan")},
        {"team1_modifier_total": float("inf")},
        {"team1_modifier_total": float("-inf")},
        {"team2_fifa_rank": 0},
    ],
)
def test_database_rejects_invalid_values(scenario_client, scenario_body, import_database, changes):
    saved = create(scenario_client, scenario_body).json
    with pytest.raises(IntegrityError):
        with import_database.transaction() as session:
            session.execute(
                Scenario.__table__.update()
                .where(Scenario.scenario_id == saved["scenario_id"])
                .values(**changes)
            )
    assert scenario_client.get(f"{URL}/{saved['scenario_id']}").json == saved


def test_restrictive_foreign_keys(scenario_client, scenario_body, import_database):
    create(scenario_client, {**scenario_body, "match_id": 1})
    for model, key in [(Team, Team.team_id), (Match, Match.match_id)]:
        with pytest.raises(IntegrityError):
            with import_database.transaction() as session:
                session.execute(model.__table__.delete().where(key == 1))


def test_openapi_scenario_contract(scenario_client):
    spec = scenario_client.get("/swagger/v1/swagger.json").json
    assert set(spec["paths"][URL]) == {"get", "post"}
    assert set(spec["paths"][URL + "/{scenario_id}"]) == {"get", "patch"}
    assert "201" in spec["paths"][URL]["post"]["responses"]
    assert "Location" in spec["paths"][URL]["post"]["responses"]["201"]["headers"]
    schemas = spec["components"]["schemas"]
    for path, method in [(URL, "post"), (URL + "/{scenario_id}", "patch")]:
        assert spec["paths"][path][method]["requestBody"]["content"]["application/json"]["example"]
    for path, method, status in [(URL, "post", "201"), (URL + "/{scenario_id}", "get", "200")]:
        assert spec["paths"][path][method]["responses"][status]["content"]["application/json"][
            "example"
        ]
    assert "team1_offense" in schemas["ScenarioCreate"]["required"]
    assert "team1_id" not in schemas["ScenarioPatch"]["properties"]
    assert set(ScenarioState.model_fields) == set(schemas["ScenarioPatch"]["properties"])
