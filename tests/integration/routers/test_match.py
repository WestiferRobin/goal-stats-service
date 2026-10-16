import pytest
from sqlalchemy import event

from football.historical_import import import_historical_dataset


@pytest.mark.postgres
def test_empty_catalog(catalog_client):
    collection = "matches"
    response = catalog_client.get(f"{BASE}/{collection}")
    assert response.status_code == 200
    assert response.json == []


BASE = "/api/v1/catalog"


@pytest.mark.postgres
def test_joined_match_detail(small_catalog):
    client = small_catalog
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


@pytest.mark.postgres
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


@pytest.mark.postgres
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


@pytest.mark.postgres
@pytest.mark.parametrize("collection", ["matches"])
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
@pytest.mark.parametrize("path", ["matches", "matches/3"])
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


@pytest.mark.postgres
def test_historical_insights_preserve_orientation_dates_and_empty_meetings(
    small_catalog, import_database
):
    from tests.fixtures.historical_database import snapshot

    before = snapshot(import_database)
    client = small_catalog
    path = "/api/v1/catalog/matches/insights"
    response = client.get(path + "?team1_id=1&team2_id=3")
    assert response.status_code == 200, response.json
    data = response.json
    assert data["source"] == "approved_historical_results"
    assert [(m["home_team_id"], m["away_team_id"]) for m in data["head_to_head"]] == [(3, 1)]
    assert data["head_to_head"][0]["match_date"] == "2023-08-20"
    assert data["head_to_head"][0]["score_basis"] == "including_extra_time_no_shootout"
    assert client.get(path + "?team1_id=3&team2_id=1").json["head_to_head"] == data["head_to_head"]
    assert client.get(path + "?team1_id=1&team2_id=3&offset=1").json["head_to_head"] == []
    assert client.get(path + "?team1_id=1&team2_id=1").status_code == 400
    assert client.get(path + "?team1_id=1&team2_id=999").status_code == 404
    assert snapshot(import_database) == before
