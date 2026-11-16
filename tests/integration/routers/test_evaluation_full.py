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
