"""Saved prediction history and failures against owned disposable PostgreSQL."""

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

from football.engine import Match as EngineMatch
from football.engine import Team as EngineTeam
from models.base import Base
from models.prediction import Prediction
from models.scenario import Scenario
from models.team import Team
from services.football import report
from services.prediction import PredictionService

pytestmark = pytest.mark.postgres


@pytest.fixture
def saved_scenario(scenario_client, scenario_body):
    scenario_body.update(team1_shots_on_target=4, team1_modifier_total=-7)
    response = scenario_client.post("/api/v1/scenarios", json=scenario_body)
    assert response.status_code == 201
    return response.json


def history_url(saved):
    return f"/api/v1/scenarios/{saved['scenario_id']}/predictions"


def generate(client, saved):
    response = client.post(history_url(saved))
    assert response.status_code == 201, response.json
    return response


def count(database):
    with database.transaction() as session:
        return session.scalar(select(func.count()).select_from(Prediction))


def test_engine_parity_effective_inputs_and_no_transaction_during_compute(
    scenario_client, saved_scenario, import_database, monkeypatch
):
    expected_teams = []
    for side in (1, 2):
        prefix = f"team{side}_"
        team = EngineTeam(
            saved_scenario[prefix + "name"],
            **{
                field: saved_scenario[prefix + field]
                for field in ["offense", "defense", "form", "star_power", "clutch", "fifa_rank"]
            },
        )
        for field in [
            "goals",
            "possession",
            "shots",
            "shots_on_target",
            "big_chances",
            "defender_blocks",
            "goalkeeper_saves",
            "corners",
            "yellow_cards",
            "red_cards",
        ]:
            setattr(team, field, saved_scenario[prefix + field])
        team.shots = max(team.shots, team.shots_on_target)
        total = saved_scenario[prefix + "modifier_total"]
        if total:
            team.add_modifier("Saved scenario modifier total", total)
        expected_teams.append(team)
    expected = report(EngineMatch(*expected_teams, match_minute=saved_scenario["match_minute"]))
    calls = []

    def wrapped(match):
        assert import_database.engine.pool.checkedout() == 0
        calls.append(match)
        return report(match)

    monkeypatch.setattr("football.scenario_prediction.report", wrapped)

    def forbidden(*args, **kwargs):
        raise AssertionError("No prototype lookup or network requests allowed")

    monkeypatch.setattr("services.football.FootballService.team", forbidden)
    monkeypatch.setattr("football.provider.api_get", forbidden)
    response = generate(scenario_client, saved_scenario)
    saved = response.json
    assert len(calls) == 1 and saved["output"] == expected
    assert saved["model_version"] == expected["model"] == "road-to-the-final-heuristic-v1"
    assert datetime.fromisoformat(saved["generated_at"]).tzinfo is not None
    assert saved["input_snapshot"]["team1_shots"] == 4
    assert saved["input_snapshot"]["team1_modifier_total"] == -7
    assert saved["input_snapshot"]["extra_minute"] == 0
    assert saved["input_snapshot"]["status"] == ""
    assert (
        scenario_client.get(f"/api/v1/scenarios/{saved_scenario['scenario_id']}").json
        == saved_scenario
    )
    assert scenario_client.get(response.headers["Location"]).json == saved
    with import_database.transaction() as session:
        row = session.get(Prediction, saved["prediction_id"])
        assert row.input_snapshot == saved["input_snapshot"]
        assert row.team1_win_probability == expected["probabilities"]["team1"]
        assert row.draw_probability == expected["probabilities"]["draw"]
        assert row.team2_win_probability == expected["probabilities"]["team2"]
        assert row.team1_expected_remaining_goals == expected["expected_goals_remaining"]["team1"]
        assert row.most_likely_team1_score == expected["most_likely_score"][0]
        assert row.details["reasoning"] == expected["reasoning"]
        assert "probabilities" not in row.details


def test_recalculation_preserves_A_and_B_and_reopens_after_restart(
    scenario_client, saved_scenario, import_database, app_factory, postgres_config, monkeypatch
):
    first = generate(scenario_client, saved_scenario).json
    path = f"/api/v1/scenarios/{saved_scenario['scenario_id']}"
    assert (
        scenario_client.patch(path, json={"match_minute": 80, "team2_goals": 2}).status_code == 200
    )
    with import_database.transaction() as session:
        team = session.get(Team, saved_scenario["team1_id"])
        team.name = "Renamed team"
        team.offense, team.ratings_source = 99, "test"
    second = generate(scenario_client, saved_scenario).json
    third = generate(scenario_client, saved_scenario).json
    assert len({r["prediction_id"] for r in [first, second, third]}) == 3
    assert first["scenario_id"] == second["scenario_id"]
    assert first["input_snapshot"]["match_minute"] == 65
    assert second["input_snapshot"]["match_minute"] == 80
    assert first["input_snapshot"]["team2_goals"] == 0
    assert second["input_snapshot"]["team2_goals"] == 2
    assert second["input_snapshot"]["team1_offense"] == first["input_snapshot"]["team1_offense"]
    assert first["output"]["team1"] == "First" and second["output"]["team1"] == "Renamed team"
    assert first["output"] != second["output"]

    def forbidden(*args):
        raise AssertionError("Retrieval must not compute")

    monkeypatch.setattr("services.prediction.predict_inputs", forbidden)
    import_database.dispose()
    reopened = app_factory(postgres_config).test_client()
    for row in [first, second, third]:
        assert reopened.get(f"/api/v1/predictions/{row['prediction_id']}").json == row
    assert reopened.get(history_url(saved_scenario)).json == [third, second, first]


def test_concurrent_scenario_edit_after_capture_keeps_original_inputs(
    scenario_client, saved_scenario, monkeypatch
):
    from football.scenario_prediction import predict_inputs

    def edit_then_compute(inputs):
        patch = scenario_client.patch(
            f"/api/v1/scenarios/{saved_scenario['scenario_id']}", json={"match_minute": 90}
        )
        assert patch.status_code == 200
        return predict_inputs(inputs)

    monkeypatch.setattr("services.prediction.predict_inputs", edit_then_compute)
    saved = generate(scenario_client, saved_scenario).json
    assert saved["input_snapshot"]["match_minute"] == saved["output"]["minute"] == 65
    assert (
        scenario_client.get(f"/api/v1/scenarios/{saved_scenario['scenario_id']}").json[
            "match_minute"
        ]
        == 90
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"team1_offense": None},
        {"team2_clutch": None},
        {"team1_defense": float("nan")},
        {"team1_form": 101},
        {"team2_possession": 100},
    ],
)
def test_unready_inputs_are_identified_without_writes(
    scenario_client, saved_scenario, import_database, monkeypatch, changes
):
    # Current DB constraints forbid these states. Simulate legacy/corrupt loader input
    # without weakening the schema or touching persistent development records.
    load = PredictionService._load_scenario

    def invalid(self, scenario_id):
        return {**load(self, scenario_id), **changes}

    monkeypatch.setattr(PredictionService, "_load_scenario", invalid)
    response = scenario_client.post(history_url(saved_scenario))
    assert response.status_code == 400
    assert "not prediction-ready" in response.json["detail"]
    if "team2_possession" not in changes:
        assert next(iter(changes)) in response.json["detail"]
    assert count(import_database) == 0
    assert (
        scenario_client.get(f"/api/v1/scenarios/{saved_scenario['scenario_id']}").json
        == saved_scenario
    )


def test_missing_rating_field_is_identified(
    scenario_client, saved_scenario, monkeypatch, import_database
):
    load = PredictionService._load_scenario

    def missing(self, scenario_id):
        data = load(self, scenario_id)
        del data["team1_offense"]
        return data

    monkeypatch.setattr(PredictionService, "_load_scenario", missing)
    response = scenario_client.post(history_url(saved_scenario))
    assert response.status_code == 400 and "team1_offense" in response.json["detail"]
    assert count(import_database) == 0


@pytest.mark.parametrize(
    "change",
    [
        {"probabilities": {"team1": 0.5, "draw": 0.5, "team2": 0.5}},
        {"probabilities": {"team1": -1, "draw": 1, "team2": 1}},
        {"probabilities": {"team1": float("nan"), "draw": 0, "team2": 1}},
        {"expected_goals_remaining": {"team1": -1, "team2": 1}},
        {"expected_goals_remaining": {"team1": float("inf"), "team2": 1}},
        {"most_likely_score": [-1, 0]},
        {"most_likely_score": [0]},
        {"top_scorelines": [{"team1_goals": 0, "team2_goals": 0, "probability": 2}]},
        {"confidence": {"percent": float("nan"), "label": "invalid"}},
        {"team1": "wrong team"},
        {"model": " "},
    ],
)
def test_invalid_output_never_persists(
    scenario_client, saved_scenario, import_database, monkeypatch, change
):
    from football.scenario_prediction import predict_inputs

    monkeypatch.setattr(
        "services.prediction.predict_inputs", lambda inputs: {**predict_inputs(inputs), **change}
    )
    response = scenario_client.post(history_url(saved_scenario))
    assert response.status_code == 500
    assert response.json["detail"] == "An unexpected error occurred."
    assert count(import_database) == 0


def test_engine_failure_never_persists(
    scenario_client, saved_scenario, import_database, monkeypatch
):
    def fail(inputs):
        raise RuntimeError("secret provider credentials")

    monkeypatch.setattr("services.prediction.predict_inputs", fail)
    response = scenario_client.post(history_url(saved_scenario))
    assert response.status_code == 500 and "secret" not in response.text
    assert count(import_database) == 0


def test_database_failure_rolls_back(scenario_client, saved_scenario, import_database):
    def fail(session):
        if any(isinstance(obj, Prediction) for obj in session.identity_map.values()):
            raise OperationalError("secret SQL", {}, Exception("private"))

    event.listen(Session, "before_commit", fail)
    try:
        response = scenario_client.post(history_url(saved_scenario))
        assert response.status_code == 500 and "secret" not in response.text
    finally:
        event.remove(Session, "before_commit", fail)
    assert count(import_database) == 0


def test_history_empty_order_pagination_and_missing(
    scenario_client, saved_scenario, import_database
):
    url = history_url(saved_scenario)
    assert scenario_client.get(url).json == []
    rows = [generate(scenario_client, saved_scenario).json for _ in range(3)]
    with import_database.transaction() as session:
        session.execute(text("UPDATE predictions SET generated_at='2026-01-01T00:00:00Z'"))
    all_rows = scenario_client.get(url).json
    assert [r["prediction_id"] for r in all_rows] == [r["prediction_id"] for r in rows[::-1]]
    assert scenario_client.get(url + "?limit=1&offset=1").json == all_rows[1:2]
    assert scenario_client.get(url + "?offset=10").json == []
    assert scenario_client.get("/api/v1/scenarios/2147483647/predictions").status_code == 404
    assert scenario_client.post("/api/v1/scenarios/2147483647/predictions").status_code == 404
    assert scenario_client.get("/api/v1/predictions/2147483647").status_code == 404


@pytest.mark.parametrize(
    "suffix",
    [
        "?limit=0",
        "?limit=201",
        "?offset=-1",
        "?offset=x",
        "?offset=9223372036854775808",
        "?unknown=1",
    ],
)
def test_invalid_pagination(scenario_client, saved_scenario, suffix):
    assert scenario_client.get(history_url(saved_scenario) + suffix).status_code == 400


@pytest.mark.parametrize("identifier", ["0", "-1", "no", "1.5", "2147483648"])
def test_invalid_ids(scenario_client, identifier):
    for method, path in [
        ("get", f"/api/v1/predictions/{identifier}"),
        ("get", f"/api/v1/scenarios/{identifier}/predictions"),
        ("post", f"/api/v1/scenarios/{identifier}/predictions"),
    ]:
        assert getattr(scenario_client, method)(path).status_code == 400


def test_generation_rejects_body_and_query_overrides(scenario_client, saved_scenario):
    url = history_url(saved_scenario)
    assert scenario_client.post(url, json={}).status_code == 400
    assert scenario_client.post(url, json={"team1_offense": 99}).status_code == 400
    assert scenario_client.post(url + "?minute=0").status_code == 400


@pytest.mark.parametrize(
    "changes",
    [
        {"team1_win_probability": -1},
        {"team2_win_probability": 2},
        {"draw_probability": float("nan")},
        {"draw_probability": float("inf")},
        {"team1_win_probability": 1, "draw_probability": 1},
        {"team1_expected_remaining_goals": -1},
        {"team2_expected_remaining_goals": float("inf")},
        {"team1_expected_remaining_goals": float("nan")},
        {"most_likely_team1_score": -1},
        {"model_version": " "},
        {"model_version": ""},
        {"scenario_id": 2147483647},
        {"input_snapshot": []},
        {"details": []},
        {"generated_at": None},
    ],
)
def test_database_constraints(scenario_client, saved_scenario, import_database, changes):
    saved = generate(scenario_client, saved_scenario).json
    with pytest.raises(IntegrityError):
        with import_database.transaction() as session:
            session.execute(
                Prediction.__table__.update()
                .where(Prediction.prediction_id == saved["prediction_id"])
                .values(**changes)
            )
    assert scenario_client.get(f"/api/v1/predictions/{saved['prediction_id']}").json == saved


def test_repeated_upgrade_preserves_data_and_relationship(
    scenario_client, saved_scenario, import_database
):
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    with import_database.engine.begin() as connection:
        config.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
        before = {
            name: connection.execute(
                text(f'SELECT row_to_json(t)::text FROM "{name}" t ORDER BY row_to_json(t)::text')
            ).all()
            for name in tables
        }
        command.upgrade(config, "head")
        assert set(inspect(connection).get_table_names()) == tables | {
            "predictions",
            "alembic_version",
        }
        for name in tables:
            assert (
                connection.execute(
                    text(
                        f'SELECT row_to_json(t)::text FROM "{name}" t ORDER BY row_to_json(t)::text'
                    )
                ).all()
                == before[name]
            )
        inspector = inspect(connection)
        assert inspector.get_pk_constraint("predictions")["constrained_columns"] == [
            "prediction_id"
        ]
        fk = inspector.get_foreign_keys("predictions")
        assert (
            len(fk) == 1
            and fk[0]["referred_table"] == "scenarios"
            and fk[0]["options"]["ondelete"] == "RESTRICT"
        )
        assert inspector.get_unique_constraints("predictions") == []
        assert (
            compare_metadata(
                MigrationContext.configure(connection, opts={"compare_server_default": True}),
                Base.metadata,
            )
            == []
        )
    for _ in range(2):
        generate(scenario_client, saved_scenario)
    with pytest.raises(IntegrityError):
        with import_database.transaction() as session:
            session.execute(
                Scenario.__table__.delete().where(
                    Scenario.scenario_id == saved_scenario["scenario_id"]
                )
            )


def test_openapi_saved_predictions(scenario_client):
    spec = scenario_client.get("/swagger/v1/swagger.json").json
    assert set(spec["paths"]["/api/v1/predictions"]) == {"post"}
    assert set(spec["paths"]["/api/v1/predictions/{prediction_id}"]) == {"get"}
    op = spec["paths"]["/api/v1/scenarios/{scenario_id}/predictions"]
    assert set(op) == {"post", "get"}
    assert "requestBody" not in op["post"]
    assert "Location" in op["post"]["responses"]["201"]["headers"]
    for method in ["get", "post"]:
        assert {"400", "404", "500"} <= set(op[method]["responses"])
    assert (
        "input_snapshot" in spec["components"]["schemas"]["SavedPredictionResponse"]["properties"]
    )
