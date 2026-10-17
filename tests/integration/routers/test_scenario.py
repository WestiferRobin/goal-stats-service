import json
from datetime import datetime

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from models.scenario import Scenario
from models.team import Team
from tests.fixtures.historical_database import create


@pytest.mark.postgres
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


URL = "/api/v1/scenarios"


@pytest.mark.postgres
@pytest.mark.parametrize("reverse", [False, True])
def test_optional_match_agreement(scenario_client, scenario_body, reverse):
    body = {**scenario_body, "match_id": 1, "team1_fifa_rank": 1}
    if reverse:
        body["team1_id"], body["team2_id"] = body["team2_id"], body["team1_id"]
    result = create(scenario_client, body).json
    assert result["match_id"] == 1 and result["team1_fifa_rank"] == 1
    assert result["team1_id"] == body["team1_id"]


@pytest.mark.postgres
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


@pytest.mark.postgres
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


@pytest.mark.postgres
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


@pytest.mark.postgres
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


@pytest.mark.postgres
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


@pytest.mark.postgres
def test_missing_scenario(scenario_client):
    for response in (
        scenario_client.get(URL + "/999"),
        scenario_client.patch(URL + "/999", json={"match_minute": 1}),
    ):
        assert response.status_code == 404
        assert response.mimetype == "application/problem+json"
        assert set(response.json) == {"type", "title", "status", "detail"}
        assert response.json["status"] == 404
    response = scenario_client.delete(URL + "/999")
    assert response.status_code == 405
    assert {"GET", "HEAD", "PATCH", "OPTIONS"} <= set(
        response.headers["Allow"].replace(" ", "").split(",")
    )


@pytest.mark.postgres
@pytest.mark.parametrize("method", ["post", "patch"])
@pytest.mark.parametrize("body", [[], None, "text", 42])
def test_nonobject_body(scenario_client, method, body):
    path = URL if method == "post" else URL + "/1"
    response = getattr(scenario_client, method)(
        path, data=json.dumps(body), content_type="application/json"
    )
    assert response.status_code == 400


@pytest.mark.postgres
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


@pytest.mark.postgres
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
