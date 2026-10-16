import pytest
from sqlalchemy import event


@pytest.mark.postgres
def test_empty_catalog(catalog_client):
    collection = "competitions"
    response = catalog_client.get(f"{BASE}/{collection}")
    assert response.status_code == 200
    assert response.json == []


BASE = "/api/v1/catalog"


@pytest.mark.postgres
def test_competitions(small_catalog):
    client = small_catalog
    competitions = client.get(f"{BASE}/competitions").json
    assert competitions == [
        {
            "competition_id": 1,
            "name": "FIFA Women's World Cup",
            "edition_label": "2023",
            "category": "women_senior_national",
        },
        {
            "competition_id": 2,
            "name": "Friendly",
            "edition_label": "2023",
            "category": "women_senior_national",
        },
    ]


@pytest.mark.postgres
@pytest.mark.parametrize("path", ["competitions"])
def test_one_select_per_endpoint_and_no_writes(small_catalog, import_database, path):
    statements = []

    def track(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(import_database.engine, "before_cursor_execute", track)
    try:
        statements.clear()
        assert small_catalog.get(f"{BASE}/{path}").status_code == 200
        assert len(statements) == 1
        assert statements[0].lstrip().upper().startswith("SELECT")
    finally:
        event.remove(import_database.engine, "before_cursor_execute", track)


@pytest.mark.postgres
def test_simulation_uses_normalized_ids_without_writes(catalog_client, import_database):
    import random

    from models.team import Team
    from tests.fixtures.historical_database import snapshot

    with import_database.transaction() as session:
        session.add_all(
            [
                Team(team_id=i, name=n, name_key=n.lower(), category="women_senior_national")
                for i, n in enumerate(["Spain", "England", "Japan", "Sweden"], 1)
            ]
        )
    teams = [
        dict(team_id=i, offense=70, defense=70, form=70, star_power=70, clutch=70)
        for i in [4, 3, 2, 1]
    ]
    body = dict(teams=teams, simulations=1000)
    before = snapshot(import_database)
    state = random.getstate()
    try:
        random.seed(514)
        first = catalog_client.post("/api/v1/competitions/simulate", json=body)
        random.seed(514)
        second = catalog_client.post("/api/v1/competitions/simulate", json=body)
    finally:
        random.setstate(state)
    assert first.status_code == 200, first.json
    assert first.json == second.json
    result = first.json
    assert result["kind"] == "hypothetical_knockout" and result["probability_unit"] == "percent"
    assert sum(r["champion_probability"] for r in result["results"]) == pytest.approx(100, abs=0.03)
    assert sum(r["final_probability"] for r in result["results"]) == pytest.approx(200, abs=0.03)
    assert all(r["semifinal_probability"] == 100 for r in result["results"])
    teams[0]["team_id"] = 999
    assert catalog_client.post("/api/v1/competitions/simulate", json=body).status_code == 404
    assert snapshot(import_database) == before
