"""Real pinned catalog/calculator, test-only assumptions, owned disposable PostgreSQL."""

import json
import math
from datetime import date, timedelta

import pytest
from sqlalchemy import event

from football import team_ratings
from football.historical_dataset import APPROVED_DATASETS
from football.historical_import import import_historical_dataset
from infra.repositories.evaluation import EvaluationRepository
from schemas.evaluation.request import PILOT_DATASET
from services.evaluation_pilot import ROOT, load_pilot
from tests.fixtures.historical_database import snapshot


@pytest.mark.postgres
@pytest.mark.pinned_source
def test_real_pilot_replay_and_database_preservation(
    import_database, import_target, pinned_source, app_factory, postgres_config, monkeypatch
):
    for dataset in APPROVED_DATASETS:
        import_historical_dataset(
            import_database, pinned_source.parent, import_target, dataset_id=dataset
        )
    rows = team_ratings.read_results(pinned_source.read_bytes())
    monkeypatch.setattr("services.evaluation.approved_source", lambda: rows)
    monkeypatch.setattr("main.Database", lambda _: import_database)
    client = app_factory(postgres_config).test_client()
    url = "/api/v1/evaluations/backtests"
    body = {"dataset_id": PILOT_DATASET, "limit": 2}
    before = snapshot(import_database)
    statements = []

    def record(conn, cursor, statement, params, context, many):
        statements.append(statement)

    event.listen(import_database.engine, "before_cursor_execute", record)
    try:
        response = client.post(url, json=body)
        assert response.status_code == 200
        strict = response.json
        assert strict["dataset_match_count"] == 348 and strict["cohort_match_count"] == 2
        assert strict["eligible_matches"] == 0
        assert {c["match_key"] for c in strict["cases"]} == set(load_pilot().match_keys)
        assert [c["match_id"] for c in strict["cases"]] == [285, 286]
        assert strict["exclusion_reasons"] == {
            "historical_star_power_clutch_evidence_missing": 2,
            "historical_source_availability_unverified": 2,
        }
        request = {
            **body,
            "mode": "retrospective_assumptions",
            "assumption_package_id": "automated-test-only",
        }
        missing = client.post(url, json=request).json
        assert missing["exclusion_reasons"] == {"explicit_star_power_clutch_assumptions_missing": 2}
        assumptions = [
            {"match_key": c["match_key"], "team_id": identity, "star_power": 0, "clutch": 25}
            for c in strict["cases"]
            for identity in (c["home_team_id"], c["away_team_id"])
        ]
        request["assumptions"] = assumptions
        response = client.post(url, json=request)
        assert response.status_code == 200
        result = response.json
        assert result["eligible_matches"] == 2 and result["excluded_matches"] == 0
        assert result["dataset_hash"] == strict["dataset_hash"]
        assert result["package_hash"] == strict["package_hash"]
        expected = json.loads((ROOT / "rating-reconstruction.json").read_text())
        for case in result["cases"]:
            assert case["outcome"] == "home_win"
            assert case["label_provenance"]["regulation_minutes"] == 90
            assert case["label_provenance"]["completion_status"] == "completed"
            manifest = case["input_manifest"]
            assert manifest["cutoff"] == "2023-07-19"
            assert manifest["source_rows_before_cutoff"] == 9416
            assert manifest["latest_source_day"] == "2023-07-18"
            for name, rating in manifest["ratings"].items():
                assert rating == expected["ratings"][name]
            assert all(s["kind"] == "hypothetical_assumption" for s in manifest["special_ratings"])
        assert result == client.post(url, json=request).json
        probabilities = [c["probabilities"] for c in result["cases"]]
        assert result["log_loss"] == pytest.approx(-sum(math.log(p[0]) for p in probabilities) / 2)
        assert result["brier_score"] == pytest.approx(
            sum((p[0] - 1) ** 2 + p[1] ** 2 + p[2] ** 2 for p in probabilities) / 2
        )
        assert result["accuracy"] == sum(p.index(max(p)) == 0 for p in probabilities) / 2
        assert sum(map(sum, result["confusion_matrix"])) == 2
        partial = client.post(url, json={**request, "assumptions": assumptions[:2]}).json
        assert partial["eligible_matches"] == 1 and partial["excluded_matches"] == 1
        for invalid in [assumptions[:1] * 2, [{**assumptions[0], "team_id": 999}]]:
            assert client.post(url, json={**request, "assumptions": invalid}).status_code == 400
        # Evaluation-day and future scores cannot affect either numerical reconstruction or replay.
        for offset in (0, 1):
            rows.append(
                team_ratings.Result(
                    date(2023, 7, 20) + timedelta(days=offset),
                    "New Zealand",
                    "Norway",
                    999,
                    0,
                    True,
                )
            )
        assert client.post(url, json=request).json == result
        original = client.post(
            url, json={"dataset_id": "womens-world-cup-recorded-v1", "offset": 284, "limit": 2}
        ).json
        assert original["eligible_matches"] == 0
        assert original["exclusion_reasons"]["regulation_outcome_evidence_missing"] == 2
    finally:
        event.remove(import_database.engine, "before_cursor_execute", record)
    assert statements and all(
        s.lstrip().upper().startswith(("SELECT", "SET TRANSACTION")) for s in statements
    )
    assert snapshot(import_database) == before
    with EvaluationRepository(import_database).transaction() as session:
        assert len(EvaluationRepository(import_database).candidates(session)) == 348
