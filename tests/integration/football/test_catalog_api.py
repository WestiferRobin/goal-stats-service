"""Catalog HTTP contracts against isolated, migrated disposable PostgreSQL schemas."""

from datetime import date

import pytest
from sqlalchemy import event

from football.datasets import import_datasets
from football.historical_import import import_historical_dataset
from models.catalog import Competition, Match, Team

pytestmark = pytest.mark.postgres
BASE = "/api/v1/catalog"


@pytest.fixture
def catalog_client(import_database, app_factory, postgres_config, monkeypatch):
    monkeypatch.setattr("main.Database", lambda _: import_database)
    return app_factory(postgres_config).test_client()


@pytest.fixture
def small_catalog(catalog_client, import_database):
    with import_database.transaction() as session:
        session.add_all(
            [
                Team(team_id=3, name="Spain", name_key="spain", category="women_senior_national"),
                Team(
                    team_id=1, name="England", name_key="england", category="women_senior_national"
                ),
                Team(team_id=2, name="Japan", name_key="japan", category="women_senior_national"),
                Competition(
                    competition_id=1,
                    name="FIFA Women's World Cup",
                    name_key="world cup",
                    edition_label="2023",
                    category="women_senior_national",
                ),
                Competition(
                    competition_id=2,
                    name="Friendly",
                    name_key="friendly",
                    edition_label="2023",
                    category="women_senior_national",
                ),
            ]
        )
        session.flush()
        for match_id, home, away, competition, day in [
            (3, 3, 1, 1, 20),
            (1, 2, 3, 1, 1),
            (2, 1, 2, 2, 1),
        ]:
            session.add(
                Match(
                    match_id=match_id,
                    home_team_id=home,
                    away_team_id=away,
                    competition_id=competition,
                    match_date=date(2023, 8, day),
                    home_score=1,
                    away_score=0,
                    score_basis="including_extra_time_no_shootout",
                    neutral=None,
                    city=None,
                    country=None,
                    source="test",
                    source_row=match_id,
                    source_record_key=f"{match_id:064x}",
                    source_file_sha256="a" * 64,
                    source_version="test",
                    source_url="https://example.com/fixture",
                    source_home_team="test home",
                    source_away_team="test away",
                    source_tournament="test tournament",
                )
            )
        import_datasets(session)
    return catalog_client


def test_empty_catalog(catalog_client):
    for collection in ("teams", "competitions", "matches"):
        response = catalog_client.get(f"{BASE}/{collection}")
        assert response.status_code == 200
        assert response.json == []


def test_teams_detail_nulls_and_separate_prediction_catalog(small_catalog, import_database):
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
    prototype = client.get("/api/v1/teams").json
    assert len(prototype) == 32
    assert next(t for t in prototype if t["name"] == "Spain")["offense"] is not None
    # Even attributed catalog ratings do not create a supported normalized-ID input path.
    with import_database.transaction() as session:
        team = session.get(Team, 3)
        team.offense = team.defense = team.form = team.star_power = team.clutch = 80
        team.ratings_source = "test fixture"
        team.fifa_rank, team.ranking_date, team.ranking_source = 1, date(2023, 8, 25), "test"
    detail = client.get(f"{BASE}/teams/3").json
    assert detail["offense"] == 80 and detail["ranking_date"] == "2023-08-25"
    assert detail["prediction_ready"] is False
    assert client.get("/api/v1/teams").json == prototype
    prediction = client.post("/api/v1/predictions", json={"team1": "Spain", "team2": "England"})
    assert prediction.status_code == 200
    assert sum(prediction.json["probabilities"].values()) == pytest.approx(1)


def test_competitions_and_joined_match_detail(small_catalog):
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
    matches = client.get(f"{BASE}/matches").json
    assert [m["match_id"] for m in matches] == [1, 2, 3]
    assert client.get(f"{BASE}/matches").json == matches
    response = client.get(f"{BASE}/matches/3")
    assert response.status_code == 200
    assert response.json == {
        "match_id": 3,
        "match_date": "2023-08-20",
        "competition_id": 1,
        "competition_name": "FIFA Women's World Cup",
        "edition_label": "2023",
        "home_team_id": 3,
        "home_team_name": "Spain",
        "away_team_id": 1,
        "away_team_name": "England",
        "home_score": 1,
        "away_score": 0,
        "score_basis": "including_extra_time_no_shootout",
        "neutral": None,
        "city": None,
        "country": None,
    }
    assert response.json == matches[-1]


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("team_id=3", [1, 3]),
        ("competition_id=2", [2]),
        ("date_from=2023-08-01&date_to=2023-08-01", [1, 2]),
        ("date_from=2023-08-20", [3]),
        ("date_to=2023-08-01", [1, 2]),
        ("team_id=1&competition_id=1&date_from=2023-08-20&date_to=2023-08-20", [3]),
        ("limit=1&offset=1", [2]),
        ("limit=200", [1, 2, 3]),
        ("offset=100", []),
        ("team_id=200", []),
        ("competition_id=200", []),
        ("date_from=2024-01-01", []),
    ],
)
def test_filters_and_pagination(small_catalog, query, ids):
    response = small_catalog.get(f"{BASE}/matches?{query}")
    assert response.status_code == 200
    assert [row["match_id"] for row in response.json] == ids


@pytest.mark.parametrize(
    "query",
    [
        "team_id=abc",
        "team_id=0",
        "competition_id=-1",
        "competition_id=2147483648",
        "date_from=2023-02-29",
        "date_to=yesterday",
        "date_from=1692489600",
        "date_from=2023-08-20T00:00:00",
        "date_to=2023-8-1",
        "date_from=2023-08-20&date_to=2023-08-01",
        "limit=0",
        "limit=201",
        "limit=1.5",
        "offset=-1",
        "offset=abc",
        "offset=9223372036854775808",
        "unknown=value",
    ],
)
def test_invalid_filters(catalog_client, query):
    response = catalog_client.get(f"{BASE}/matches?{query}")
    assert response.status_code == 400
    assert response.mimetype == "application/problem+json"
    assert response.json["status"] == 400


@pytest.mark.parametrize("collection", ["teams", "matches"])
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


def test_one_select_per_endpoint_and_no_writes(small_catalog, import_database):
    statements = []

    def track(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(import_database.engine, "before_cursor_execute", track)
    try:
        for path in ("teams", "teams/3", "competitions", "matches", "matches/3"):
            statements.clear()
            assert small_catalog.get(f"{BASE}/{path}").status_code == 200
            assert len(statements) == 1
            assert statements[0].lstrip().upper().startswith("SELECT")
    finally:
        event.remove(import_database.engine, "before_cursor_execute", track)


def test_selected_dataset_size_and_default_page(
    catalog_client, import_database, import_target, pinned_fixture
):
    # Synthetic 32/64 importer fixture; verified real-source acceptance is run separately.
    import_historical_dataset(import_database, pinned_fixture.directory, import_target)
    assert len(catalog_client.get(f"{BASE}/teams").json) == 32
    competition = catalog_client.get(f"{BASE}/competitions").json
    assert len(competition) == 1 and competition[0]["edition_label"] == "2023"
    first = catalog_client.get(f"{BASE}/matches").json
    second = catalog_client.get(f"{BASE}/matches?offset=50").json
    all_matches = catalog_client.get(f"{BASE}/matches?limit=200").json
    assert len(first) == 50 and len(second) == 14
    assert first + second == all_matches
    assert len({row["match_id"] for row in all_matches}) == 64


def test_catalog_openapi(catalog_client):
    assert catalog_client.get("/swagger").status_code == 200
    spec = catalog_client.get("/swagger/v1/swagger.json").json
    for path in ("teams", "teams/{team_id}", "competitions", "matches", "matches/{match_id}"):
        operation = spec["paths"][f"{BASE}/{path}"]["get"]
        assert operation.get("summary") or operation.get("description")
        assert "200" in operation["responses"] and "400" in operation["responses"]
        assert "schema" in operation["responses"]["200"]["content"]["application/json"]
        if "{" in path:
            assert "404" in operation["responses"]
    parameters = spec["paths"][f"{BASE}/matches"]["get"]["parameters"]
    assert {p["name"] for p in parameters} == {
        "team_id",
        "competition_id",
        "date_from",
        "date_to",
        "limit",
        "offset",
    }
    for path in ("/teams", "/predictions", "/history", "/snapshots", "/backtests", "/insights"):
        assert f"/api/v1{path}" in spec["paths"]
