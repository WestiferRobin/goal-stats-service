"""Real HTTP/service/engine contracts with an in-memory read-only repository."""

import random
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from flask_openapi3 import OpenAPI

from exceptions.handlers import register_error_handlers, request_validation
from routers.competition import create_competition_blueprint
from schemas.problem import ProblemDetailSchema
from services.competition import CompetitionService
from services.team import TeamService


def payload(size=4, **options):
    return dict(
        teams=[
            dict(team_id=i, offense=70, defense=70, form=70, star_power=70, clutch=70)
            for i in range(1, size + 1)
        ],
        simulations=1000,
        **options,
    )


@pytest.fixture
def simulation_app():
    database = object()
    # Distinct catalog IDs deliberately share a display name.
    rows = {i: SimpleNamespace(team_id=i, name="Same" if i <= 2 else str(i)) for i in range(1, 33)}
    repo = SimpleNamespace(database=database, transaction=lambda: nullcontext(None))
    team_repo = SimpleNamespace(
        database=database,
        get_participants=lambda session, ids, **kw: [rows[i] for i in ids if i in rows],
    )
    service = CompetitionService(repo=repo, team_service=TeamService(repo=team_repo))
    app = OpenAPI(
        __name__,
        doc_ui=False,
        validation_error_status=400,
        validation_error_model=ProblemDetailSchema,
        validation_error_callback=request_validation,
    )
    register_error_handlers(app)
    app.register_api(create_competition_blueprint(service))
    return app


def post(app, body):
    with app.test_client() as client:
        return client.post("/api/v1/competitions/simulate", json=body)


@pytest.mark.parametrize("size", [4, 8, 16, 32])
def test_duplicate_names_progression_and_replay(simulation_app, size):
    body = payload(size)
    response = post(simulation_app, body)
    assert response.status_code == 200
    result = response.json
    assert result == post(simulation_app, {**body, "seed": result["seed"]}).json
    assert result["kind"] == "hypothetical_knockout"
    assert result["probability_unit"] == "percent"
    assert result["simulations"] == 1000
    rows = result["results"]
    assert {r["team_id"] for r in rows} == set(range(1, size + 1))
    assert sum(r["team"] == "Same" for r in rows) == 2
    assert result["predicted_champion_id"] == rows[0]["team_id"]
    assert result["predicted_champion"] == rows[0]["team"]
    for row in rows:
        assert (
            0
            <= row["champion_probability"]
            <= row["final_probability"]
            <= row["semifinal_probability"]
            <= 100
        )
    for field, total in [
        ("semifinal_probability", 400),
        ("final_probability", 200),
        ("champion_probability", 100),
    ]:
        assert sum(r[field] for r in rows) == pytest.approx(total, abs=size * 0.005)
    final = result["most_common_final"]
    assert (final["team1_id"] <= size // 2) != (final["team2_id"] <= size // 2)
    assert 0 < final["probability"] <= 100


def test_request_isolation(simulation_app):
    body = payload(seed=0)
    state = random.getstate()
    expected = post(simulation_app, body).json
    assert random.getstate() == state
    try:
        random.seed(987)
        for _ in range(100):
            random.random()
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(
                pool.map(
                    lambda seed: post(simulation_app, payload(seed=seed)).json, [0, 123, 0, 456]
                )
            )
        assert responses[0] == responses[2] == expected
        assert post(simulation_app, body).json == expected
    finally:
        random.setstate(state)


@pytest.mark.parametrize("seed", [-1, 4294967296, True, "42", 1.5])
def test_invalid_seed(simulation_app, seed):
    assert post(simulation_app, payload(seed=seed)).status_code == 400


@pytest.mark.parametrize("seed", [0, 4294967295, None])
def test_seed_boundaries(simulation_app, seed):
    response = post(simulation_app, payload(seed=seed))
    assert response.status_code == 200
    assert 0 <= response.json["seed"] <= 4294967295
    if seed is not None:
        assert response.json["seed"] == seed


def test_missing_team_and_simulation_limits(simulation_app):
    body = payload()
    body["teams"][0]["team_id"] = 999
    assert post(simulation_app, body).status_code == 404
    for count in (999, 2001, True):
        assert post(simulation_app, {**payload(), "simulations": count}).status_code == 400
    assert post(simulation_app, {**payload(), "simulations": 2000}).status_code == 200
