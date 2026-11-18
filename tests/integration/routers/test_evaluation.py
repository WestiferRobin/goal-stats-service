"""HTTP and PostgreSQL checks using owned disposable infrastructure only."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import delete, event, select, text

from infra.repositories.evaluation import EvaluationRepository
from models.competition import Competition
from models.enrichment import FifaTeamMapping, RankingObservation, RankingRelease
from models.match import Match
from models.prediction import Prediction
from models.scenario import Scenario
from models.team import Team
from schemas.evaluation.response import BacktestResponse
from services.evaluation import EvaluationPackage, EvaluationService

URL = "/api/v1/evaluations/backtests"
BODY = {"dataset_id": "womens-world-cup-recorded-v1"}


@pytest.fixture
def evaluation_client(import_database, app_factory, postgres_config, monkeypatch):
    with import_database.transaction() as session:
        session.add_all(
            [
                Team(team_id=i, name=name, name_key=name.lower(), category="women_senior_national")
                for i, name in [(1, "Alpha"), (2, "Beta")]
            ]
        )
        session.add(
            Competition(
                competition_id=1,
                name="FIFA Women's World Cup",
                name_key="fifa women's world cup",
                edition_label="2023",
                category="women_senior_national",
            )
        )
        session.flush()
        session.add(
            Match(
                match_id=1,
                competition_id=1,
                home_team_id=1,
                away_team_id=2,
                match_date=date(2023, 8, 1),
                home_score=9,
                away_score=8,
                score_basis="including_extra_time_no_shootout",
                neutral=True,
                city=None,
                country=None,
                source="synthetic",
                source_record_key="a" * 64,
                source_file_sha256="b" * 64,
                source_row=1,
                source_version="synthetic",
                source_url="synthetic://fixture",
                source_home_team="Alpha",
                source_away_team="Beta",
                source_tournament="synthetic",
            )
        )
        for identity, day, rank in [
            ("before", date(2023, 7, 31), 10),
            ("same-day", date(2023, 8, 1), 1),
            ("future", date(2023, 8, 2), 2),
        ]:
            session.add(
                RankingRelease(
                    release_id=identity,
                    published_on=day,
                    retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
                    source_url="synthetic://ranking",
                    sha256="c" * 64,
                    index_sha256="d" * 64,
                    release_metadata={},
                )
            )
            session.flush()
            session.add(
                RankingObservation(
                    release_id=identity, fifa_team_id="A", rank=rank, points=1234, status=0, raw={}
                )
            )
        session.add(FifaTeamMapping(team_id=1, fifa_team_id="A", source_name="Alpha"))
    monkeypatch.setattr("main.Database", lambda _: import_database)
    service = EvaluationService(
        EvaluationRepository(import_database),
        EvaluationPackage(evidence_kind="synthetic", source_hash="b" * 64, expected_matches=1),
    )
    monkeypatch.setattr("main.EvaluationService", lambda repo: service)
    app = app_factory(postgres_config)
    app.extensions["evaluation_under_test"] = service
    return app.test_client()


def test_endpoint_unavailable_schema_and_no_persistence(evaluation_client, import_database):
    sql = []

    def record(conn, cursor, statement, params, context, many):
        sql.append(statement)

    event.listen(import_database.engine, "before_cursor_execute", record)
    try:
        response = evaluation_client.post(URL, json=BODY)
    finally:
        event.remove(import_database.engine, "before_cursor_execute", record)
    assert response.status_code == 200
    result = BacktestResponse.model_validate(response.json)
    assert result.eligible_matches == 0 and result.excluded_matches == 1
    assert result.accuracy is None and result.log_loss is None and result.brier_score is None
    assert result.evidence_kind == "synthetic"
    assert all(s.lstrip().upper().startswith(("SELECT", "SET TRANSACTION")) for s in sql)
    assert any("READ ONLY" in s for s in sql)
    with import_database.transaction() as session:
        assert list(session.scalars(select(Scenario))) == []
        assert list(session.scalars(select(Prediction))) == []
    assert response.json == evaluation_client.post(URL, json=BODY).json


def test_repository_uses_prior_release_and_read_only_snapshot(evaluation_client, import_database):
    repo = EvaluationRepository(import_database)
    with repo.transaction() as session:
        rows = repo.candidates(session)
        assert len(rows) == 1
        assert session.scalar(text("SHOW transaction_read_only")) == "on"
        assert session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
        before = repo.ranking(session, 1, date(2023, 8, 1))
        assert before["release_id"] == "before" and before["rank"] == 10
        assert repo.ranking(session, 1, date(2023, 7, 31))["rank"] is None
        missing = repo.ranking(session, 2, date(2023, 8, 1))
        assert missing["rank"] is None and missing["reason"] == "missing_rank_in_pre_match_release"

    # A missing observation in the newest eligible release must not borrow an older rank.
    with import_database.transaction() as session:
        session.execute(delete(RankingObservation).where(RankingObservation.release_id == "future"))
    with repo.transaction() as session:
        repo.candidates(session)
        missing = repo.ranking(session, 1, date(2023, 8, 3))
        assert missing["release_id"] == "future" and missing["rank"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"dataset_id": "unapproved"},
        {"mode": "anything"},
        {"limit": 0},
        {"limit": 17},
        {"limit": 1.5},
        {"offset": 348},
        {"offset": -1},
        {"observations": []},
        {"mode": "retrospective_assumptions"},
        {"assumption_package_id": "not-strict"},
        {"assumptions": [{}] * 33},
    ],
)
def test_invalid_requests(evaluation_client, changes):
    response = evaluation_client.post(URL, json={**BODY, **changes})
    assert response.status_code == 400
    assert response.mimetype == "application/problem+json"


def test_size_limit_and_safe_errors(evaluation_client, monkeypatch):
    response = evaluation_client.post(
        URL, data='{"padding":"' + "x" * 33000 + '"}', content_type="application/json"
    )
    assert response.status_code == 413
    monkeypatch.setattr(
        EvaluationRepository,
        "candidates",
        lambda *args: (_ for _ in ()).throw(RuntimeError("/private/secret")),
    )
    response = evaluation_client.post(URL, json=BODY)
    assert response.status_code == 500
    assert "/private" not in response.text


def test_production_auth_and_openapi(app_factory, explicit_config, monkeypatch):
    token = "test-only-evaluation-token-0123456789"
    app = app_factory({**explicit_config, "APP_ENV": "production", "SERVICE_API_TOKEN": token})
    monkeypatch.setattr(
        EvaluationService, "evaluate", lambda self, body: {"authenticated_test_probe": True}
    )
    client = app.test_client()
    assert client.post(URL, json=BODY).status_code == 401
    assert client.post(URL, json=BODY, headers={"Authorization": "Bearer " + token}).json == {
        "authenticated_test_probe": True
    }
    spec = client.get("/swagger/v1/swagger.json").json
    assert "post" in spec["paths"][URL]
    assert "BacktestResponse" in spec["components"]["schemas"]


def test_synthetic_positive_api_and_assumption_manifest(
    evaluation_client, monkeypatch, import_database
):
    from dataclasses import replace
    from datetime import timedelta

    from football.team_ratings import Result
    from services.evaluation import RegulationEvidence

    day = date(2023, 8, 1)
    service = evaluation_client.application.extensions["evaluation_under_test"]
    service.package = replace(
        service.package,
        labels={
            "a" * 64: RegulationEvidence(
                day,
                "Alpha",
                "Beta",
                0,
                0,
                "synthetic://label",
                "e" * 64,
                regulation_minutes=90,
                completion_status="completed",
            )
        },
    )
    rows = [
        Result(
            day - timedelta(days=n),
            "Alpha" if n % 2 else "Beta",
            "Beta" if n % 2 else "Alpha",
            n % 3,
            1,
            True,
        )
        for n in range(1, 801)
    ]
    monkeypatch.setattr("services.evaluation.approved_source", lambda: rows)
    body = {
        **BODY,
        "mode": "retrospective_assumptions",
        "assumption_package_id": "synthetic-v1",
        "assumptions": [
            {"match_key": "a" * 64, "team_id": i, "star_power": 0, "clutch": 25} for i in (1, 2)
        ],
    }
    response = evaluation_client.post(URL, json=body)
    assert response.status_code == 200
    result = BacktestResponse.model_validate(response.json)
    assert result.eligible_matches == 1 and result.excluded_matches == 0
    assert result.evidence_kind == "synthetic"
    assert result.cases[0].outcome == "draw"
    assert result.assumptions[0].star_power == 0
    assert result == BacktestResponse.model_validate(evaluation_client.post(URL, json=body).json)
    with import_database.transaction() as session:
        assert list(session.scalars(select(Scenario))) == []
        assert list(session.scalars(select(Prediction))) == []
    for change in [{"star_power": -1}, {"clutch": 101}, {"star_power": None}]:
        invalid = {
            **body,
            "assumptions": [{**body["assumptions"][0], **change}, body["assumptions"][1]],
        }
        assert evaluation_client.post(URL, json=invalid).status_code == 400
    assert (
        evaluation_client.post(
            URL, json={**body, "assumptions": [body["assumptions"][0]] * 2}
        ).status_code
        == 400
    )
    assert (
        evaluation_client.post(
            URL, json={**body, "assumptions": [{**body["assumptions"][0], "team_id": 999}]}
        ).status_code
        == 400
    )


@pytest.mark.postgres
def test_unavailable_approved_asset_is_503_but_invalid_request_stays_400(
    evaluation_client, monkeypatch, tmp_path, caplog
):
    evaluation_client.application.extensions["evaluation_under_test"].package = None
    monkeypatch.setattr("services.evaluation_full.ROOT", tmp_path)
    logger = evaluation_client.application.logger
    logger.addHandler(caplog.handler)
    try:
        response = evaluation_client.post(URL, json={"dataset_id": "womens-world-cup-full-v1"})
    finally:
        logger.removeHandler(caplog.handler)
    assert response.status_code == 503
    assert response.json["reason"] == "evaluation_asset_unavailable"
    assert str(tmp_path) not in response.get_data(as_text=True)
    assert "Evaluation asset unavailable" in caplog.text
    assert evaluation_client.post(URL, json={"dataset_id": "unknown"}).status_code == 400
