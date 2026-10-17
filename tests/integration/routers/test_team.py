from datetime import date

import pytest
from sqlalchemy import event

from models.team import Team


@pytest.mark.postgres
def test_empty_catalog(catalog_client):
    collection = "teams"
    response = catalog_client.get(f"{BASE}/{collection}")
    assert response.status_code == 200
    assert response.json == []


BASE = "/api/v1/catalog"


@pytest.mark.postgres
def test_teams_detail_nulls_and_no_parallel_prediction_catalog(small_catalog, import_database):
    client = small_catalog
    response = client.get(f"{BASE}/teams")
    assert response.status_code == 200
    teams = response.json
    assert [t["name"] for t in teams] == ["England", "Japan", "Spain"]
    assert client.get(f"{BASE}/teams").json == teams
    for team in teams:
        assert client.get(f"{BASE}/teams/{team['team_id']}").json == team
        assert set(team) == {
            "team_id",
            "name",
            "category",
            "offense",
            "defense",
            "form",
            "star_power",
            "clutch",
            "fifa_rank",
            "ranking_date",
            "prediction_ready",
        }
        assert all(
            team[key] is None
            for key in (
                "offense",
                "defense",
                "form",
                "star_power",
                "clutch",
                "fifa_rank",
                "ranking_date",
            )
        )
        assert team["prediction_ready"] is False
    assert client.get("/api/v1/teams").status_code == 404
    # Catalog ratings remain visible; prediction requests require explicit assumptions.
    with import_database.transaction() as session:
        team = session.get(Team, 3)
        team.offense = team.defense = team.form = team.star_power = team.clutch = 80
        team.ratings_source = "test fixture"
        team.fifa_rank, team.ranking_date, team.ranking_source = 1, date(2023, 8, 25), "test"
    detail = client.get(f"{BASE}/teams/3").json
    assert detail["offense"] == 80 and detail["ranking_date"] == "2023-08-25"
    assert detail["prediction_ready"] is False
    assert client.get("/api/v1/teams").status_code == 404
    prediction = client.post("/api/v1/predictions", json={"team1": "Spain", "team2": "England"})
    assert prediction.status_code == 404


@pytest.mark.postgres
@pytest.mark.parametrize("collection", ["teams"])
@pytest.mark.parametrize(
    ("identifier", "status"),
    [
        ("abc", 400),
        ("-1", 400),
        ("0", 400),
        ("1.5", 400),
        ("2147483648", 400),
        ("12345", 404),
    ],
)
def test_detail_errors(catalog_client, collection, identifier, status):
    response = catalog_client.get(f"{BASE}/{collection}/{identifier}")
    assert response.status_code == status
    assert response.mimetype == "application/problem+json"
    assert response.json["status"] == status


@pytest.mark.postgres
@pytest.mark.parametrize("path", ["teams", "teams/3"])
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
