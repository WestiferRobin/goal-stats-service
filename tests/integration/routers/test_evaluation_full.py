"""Full real catalog, read-only evaluation and explicitly synthetic test assumptions."""

from datetime import date

import pytest
from sqlalchemy import event

from football import team_ratings
from football.historical_dataset import APPROVED_DATASETS
from football.historical_import import import_historical_dataset
from schemas.evaluation.request import FULL_DATASET
from services.evaluation_full import assets
from tests.fixtures.historical_database import snapshot


@pytest.mark.postgres
@pytest.mark.pinned_source
def test_full_http_cohort_metrics_replay_protocols_and_preservation(
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
    body = {"dataset_id": FULL_DATASET, "limit": 348}
    before = snapshot(import_database)
    statements = []

    def record(conn, cursor, statement, params, context, many):
        statements.append(statement)

    event.listen(import_database.engine, "before_cursor_execute", record)
    try:
        response = client.post(url, json=body)
        assert response.status_code == 200
        strict = response.json
        assert (
            strict["dataset_match_count"]
            == strict["cohort_match_count"]
            == strict["excluded_matches"]
            == 348
        )
        assert strict["eligible_matches"] == 0 and strict["accuracy"] is None
        assert len({c["match_key"] for c in strict["cases"]}) == 348
        assert [s["rating_complete"] for s in strict["edition_summaries"]] == [
            19,
            19,
            26,
            32,
            31,
            29,
            48,
            52,
            64,
        ]
        recovered_body = {**body, "recovery_package_id": "international-results-recovery-v1"}
        recovered_response = client.post(url, json=recovered_body)
        assert recovered_response.status_code == 200
        recovered = recovered_response.json
        assert recovered["dataset_hash"] == strict["dataset_hash"]
        assert recovered["package_hash"] != strict["package_hash"]
        assert recovered["eligible_matches"] == 0 and recovered["accuracy"] is None
        assert [s["rating_complete"] for s in recovered["edition_summaries"]] == [
            20,
            26,
            30,
            32,
            32,
            32,
            52,
            52,
            64,
        ]
        assert client.post(url, json=recovered_body).json == recovered
        research_body = {
            **recovered_body,
            "research_model_version": "odf-exposure-80-evidence-blocked-v1",
        }
        research_response = client.post(url, json=research_body)
        assert research_response.status_code == 200
        research = research_response.json
        assert len(research["cases"]) == 348
        assert research["accuracy"] is None
        assert research["metrics_horizon_minutes"] == 90
        assert client.post(url, json=research_body).json == research
        for prior, current in zip(recovered["cases"], research["cases"], strict=True):
            if current["regulation_minutes"] == 90:
                assert current == prior
            else:
                assert current["evidence_record"]["research"]["eligible"] is False
                assert current["probabilities"] is None
                assert (
                    "historical_star_power_clutch_evidence_missing"
                    not in current["exclusion_reasons"]
                )
        group = research["protocol_summaries"][0]
        assert group["total"] == group["excluded"] == 26
        assert group["rating_complete"] == 20 and group["accuracy"] is None
        assert group["research_protocol"]["parameters"] is None
        selected = client.post(url, json={**research_body, "edition": 1991}).json
        assert selected["cohort_match_count"] == 26 and len(selected["cases"]) == 26
        assert client.post(url, json={**research_body, "edition": 2023}).status_code == 400
        replay_body = {
            **recovered_body,
            "prediction_model_version": "odf-cross-goal-rate-research-v1",
            "mode": "retrospective_replay",
        }
        replay_response = client.post(url, json=replay_body)
        assert replay_response.status_code == 200
        replay = replay_response.json
        assert replay["eligible_matches"] == 320 and replay["excluded_matches"] == 28
        assert replay["accuracy"] == 0.553125
        assert replay["research_validation"]["production_eligible"] is False
        assert client.post(url, json=replay_body).json == replay
        pages = [
            client.post(url, json={**replay_body, "limit": 174, "offset": o}).json for o in (0, 174)
        ]
        assert sum(p["eligible_matches"] for p in pages) == replay["eligible_matches"]
        assert [c for p in pages for c in p["cases"]] == replay["cases"]
        for metric in ("accuracy", "log_loss", "brier_score"):
            combined = sum(p[metric] * p["eligible_matches"] for p in pages) / 320
            assert abs(combined - replay[metric]) < 1e-12
        strict_research = client.post(url, json={**replay_body, "mode": "strict_historical"}).json
        assert strict_research["eligible_matches"] == 0 and strict_research["accuracy"] is None
        calibrated = client.post(
            url, json={**replay_body, "prediction_model_version": "odf-temperature-research-v1"}
        ).json
        assert calibrated["eligible_matches"] == 200
        assert all(c["edition"] > 2007 for c in calibrated["cases"] if c["status"] == "eligible")
        assert (
            client.post(
                url, json={**replay_body, "prediction_model_version": "unapproved"}
            ).status_code
            == 400
        )
        request = {
            **body,
            "mode": "retrospective_assumptions",
            "assumption_package_id": "automated-test-only-v1",
        }
        missing = client.post(url, json=request).json
        assert missing["exclusion_reasons"]["explicit_star_power_clutch_assumptions_missing"] == 348
        # These numbers are only automated-test inputs, never a released assumption package.
        assumptions = [
            {"match_key": c["match_key"], "team_id": team, "star_power": 0, "clutch": 25}
            for c in strict["cases"]
            for team in (c["home_team_id"], c["away_team_id"])
        ]
        scored_request = {**request, "assumptions": assumptions}
        recovered_scored = client.post(
            url, json={**scored_request, "recovery_package_id": "international-results-recovery-v1"}
        )
        assert recovered_scored.status_code == 200
        recovered_result = recovered_scored.json
        assert recovered_result["eligible_matches"] == 320
        for case in recovered_result["cases"]:
            if case["status"] == "eligible":
                provenance = case["input_manifest"]
                assert provenance["rating_source_hash"] != team_ratings.SOURCE_SHA
                assert (
                    provenance["rating_source_hash"]
                    == (provenance["evaluation_package"]["rating_recovery"]["merged_source_hash"])
                )
        response = client.post(url, json=scored_request)
        assert response.status_code == 200
        result = response.json
        assert result["eligible_matches"] == 301 and result["excluded_matches"] == 47
        assert result["exclusion_reasons"]["model_80_minute_horizon_unvalidated"] == 26
        assert result["exclusion_reasons"]["historical_ratings_insufficient"] == 28
        assert result["protocol_summaries"][0]["eligible"] == 0
        assert result["protocol_summaries"][0]["accuracy"] is None
        assert result["protocol_summaries"][1]["eligible"] == 301
        assert sum(map(sum, result["confusion_matrix"])) == 301
        for c in result["cases"]:
            if c["status"] == "eligible":
                assert c["regulation_minutes"] == 90
                assert c["input_manifest"]["latest_source_day"] < c["match_date"]
                assert c["input_manifest"]["rating_reconstruction_hash"]
        # Aggregate losses from actual probability rows, independently of summary helpers.
        import math

        eligible = [c for c in result["cases"] if c["status"] == "eligible"]
        classes = ["home_win", "draw", "away_win"]
        loss = (
            -sum(
                math.log(max(c["probabilities"][classes.index(c["outcome"])], 1e-15))
                for c in eligible
            )
            / 301
        )
        assert result["log_loss"] == pytest.approx(loss)
        assert client.post(url, json=scored_request).json == result
        for edition in (1991, 1999, 2023):
            selected = [
                a
                for a in assumptions
                if any(
                    c["edition"] == edition and c["match_key"] == a["match_key"]
                    for c in strict["cases"]
                )
            ]
            edition_result = client.post(
                url, json={**request, "edition": edition, "assumptions": selected}
            ).json
            assert edition_result["dataset_match_count"] == 348
            assert all(c["edition"] == edition for c in edition_result["cases"])
            assert (
                edition_result["edition_summaries"][0]
                == result["edition_summaries"][list(range(1991, 2024, 4)).index(edition)]
            )
        # No 2026 source row can influence a historical input population.
        rows.append(team_ratings.Result(date(2026, 1, 1), "New Zealand", "Norway", 999, 0, True))
        assert client.post(url, json={**request, "edition": 1991}).json["eligible_matches"] == 0
        _, _, artifact = assets()
        # Recompute full reference populations for representative early, middle and late cutoffs.
        for cutoff in ("1991-11-15", "2007-09-09", "2023-07-19"):
            day = date.fromisoformat(cutoff)
            assert (
                team_ratings.calculate([r for r in rows if r.day <= day], day)
                == artifact["populations"][cutoff]["ratings"]
            )
        invalid = {**request, "assumptions": assumptions[:1] * 2}
        assert client.post(url, json=invalid).status_code == 400
        assert (
            client.post(
                url, json={**request, "assumptions": [{**assumptions[0], "team_id": 99999}]}
            ).status_code
            == 400
        )
        assert client.post(url, json={**body, "padding": "x" * 140000}).status_code == 413
    finally:
        event.remove(import_database.engine, "before_cursor_execute", record)
    assert all(s.lstrip().upper().startswith(("SELECT", "SET TRANSACTION")) for s in statements)
    assert snapshot(import_database) == before
