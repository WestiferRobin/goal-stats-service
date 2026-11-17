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


@pytest.fixture
def summary_client(small_catalog, import_database):
    from models.competition import Competition

    # Adapt only this test's disposable data; leave shared fixture definitions intact.
    with import_database.transaction() as session:
        session.get(Competition, 1).name_key = "fifa women's world cup"
        session.add(
            Team(team_id=4, name="Empty", name_key="empty", category="women_senior_national")
        )
    return small_catalog


@pytest.mark.postgres
def test_summary_populated_and_existing_reads_unchanged(summary_client, import_database):
    paths = [
        "teams",
        "teams/3",
        "matches?team_id=3&limit=1&offset=1",
        "matches/insights?team1_id=3&team2_id=1",
    ]
    before = {path: summary_client.get(f"{BASE}/{path}").json for path in paths}
    statements = []

    def track(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(import_database.engine, "before_cursor_execute", track)
    try:
        response = summary_client.get(f"{BASE}/teams/3/summary")
        assert response.status_code == 200
        assert len(statements) == 2
        assert all(sql.lstrip().upper().startswith("SELECT") for sql in statements)
    finally:
        event.remove(import_database.engine, "before_cursor_execute", track)
    assert response.json == dict(
        team_id=3,
        name="Spain",
        matches_played=2,
        wins=1,
        draws=0,
        losses=1,
        goals_for=1,
        goals_against=1,
        goal_difference=0,
        tournament_appearances=1,
        filters={"competition_id": None, "date_from": None, "date_to": None},
        score_basis="including_extra_time_no_shootout",
        result_definition="recorded_final_score",
        coverage_status="available_records_only",
    )
    for field in (
        "team_id",
        "matches_played",
        "wins",
        "draws",
        "losses",
        "goals_for",
        "goals_against",
        "goal_difference",
        "tournament_appearances",
    ):
        assert type(response.json[field]) is int
    assert {path: summary_client.get(f"{BASE}/{path}").json for path in paths} == before


@pytest.mark.postgres
def test_summary_filters_serialized(summary_client):
    response = summary_client.get(
        f"{BASE}/teams/3/summary?competition_id=1&date_from=2023-08-20&date_to=2023-08-20"
    )
    assert response.status_code == 200
    assert response.json["filters"] == {
        "competition_id": 1,
        "date_from": "2023-08-20",
        "date_to": "2023-08-20",
    }
    assert response.json["matches_played"] == response.json["wins"] == 1
    assert response.json["goals_for"] == 1
    assert response.json["goals_against"] == 0


@pytest.mark.postgres
@pytest.mark.parametrize(
    "path",
    [
        "4/summary",
        "3/summary?competition_id=999",
        "3/summary?competition_id=2",
        "3/summary?date_from=2024-01-01",
    ],
)
def test_summary_empty_is_labeled(summary_client, path):
    response = summary_client.get(f"{BASE}/teams/{path}")
    assert response.status_code == 200
    assert response.json["coverage_status"] == "no_matching_records"
    assert response.json["score_basis"] is None
    for field in (
        "matches_played",
        "wins",
        "draws",
        "losses",
        "goals_for",
        "goals_against",
        "goal_difference",
        "tournament_appearances",
    ):
        assert response.json[field] == 0


@pytest.mark.parametrize(
    "path",
    [
        "0/summary",
        "-1/summary",
        "abc/summary",
        "1.5/summary",
        "2147483648/summary",
        "3/summary?competition_id=0",
        "3/summary?competition_id=abc",
        "3/summary?competition_id=2147483648",
        "3/summary?date_from=2023-02-29",
        "3/summary?date_to=2023-8-1",
        "3/summary?date_from=2023-08-20&date_to=2023-08-01",
        "3/summary?limit=1",
        "3/summary?offset=0",
        "3/summary?team_id=3",
        "3/summary?unknown=1",
    ],
)
def test_summary_invalid_requests_before_database(app, monkeypatch, path):
    from infra.repositories.team import TeamRepository

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid requests must not reach the repository")

    monkeypatch.setattr(TeamRepository, "get_by_id", forbidden)
    response = app.test_client().get(f"{BASE}/teams/{path}")
    assert response.status_code == 400
    assert response.mimetype == "application/problem+json"
    assert response.json["status"] == 400


@pytest.mark.postgres
def test_summary_unknown_does_not_aggregate(summary_client, monkeypatch):
    from infra.repositories.team import TeamRepository

    def forbidden(*args, **kwargs):
        pytest.fail("Unknown teams must not trigger aggregation")

    monkeypatch.setattr(TeamRepository, "summary", forbidden)
    response = summary_client.get(f"{BASE}/teams/999/summary")
    assert response.status_code == 404
    assert response.mimetype == "application/problem+json"


@pytest.mark.postgres
def test_summary_unsupported_scores_safe_error(summary_client, import_database):
    from models.match import Match

    with import_database.transaction() as session:
        session.get(Match, 1).score_basis = "private_unsupported_value"
    response = summary_client.get(f"{BASE}/teams/3/summary")
    assert response.status_code == 500
    assert response.mimetype == "application/problem+json"
    assert response.json == {
        "type": "about:blank",
        "title": "Internal Server Error",
        "status": 500,
        "detail": "An unexpected error occurred.",
    }
    assert "private_unsupported_value" not in response.get_data(as_text=True)


@pytest.mark.postgres
@pytest.mark.parametrize("operation", ["get_by_id", "summary"])
def test_summary_database_failures_safe(summary_client, monkeypatch, operation):
    from sqlalchemy.exc import OperationalError

    from infra.repositories.team import TeamRepository

    def fail(*args, **kwargs):
        raise OperationalError("private SQL", {}, RuntimeError("private credentials"))

    monkeypatch.setattr(TeamRepository, operation, fail)
    response = summary_client.get(f"{BASE}/teams/3/summary")
    assert response.status_code == 500
    assert response.mimetype == "application/problem+json"
    assert response.json == {
        "type": "about:blank",
        "title": "Internal Server Error",
        "status": 500,
        "detail": "An unexpected error occurred.",
    }
