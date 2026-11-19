"""Evidence blockers must remain effective even when labels and ratings exist."""

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from football.duration_research import MODEL, SPEC, inspect_case
from research.duration_audit import build
from research.three_input import Ratings, predict
from schemas.evaluation.request import FULL_DATASET, BacktestRequest

ROOT = Path(__file__).resolve().parents[3]


def test_all_26_inventory_reproducibility_and_training_shortfall():
    artifact = json.loads((ROOT / "data/research/duration-80-v1/coverage.json").read_text())
    assert build() == artifact
    assert sum(artifact["full_inventory"].values()) == 348
    assert len({c["record"]["match_key"] for c in artifact["cases"]}) == 26
    assert artifact["rating_complete"] == 20
    assert artifact["training_candidates"] == 467
    assert artifact["calibration_candidates"] == 138
    assert artifact["qualified_training"] == artifact["qualified_calibration"] == 0
    missing = {
        c["record"]["match_id"] for c in artifact["cases"] if not c["research"]["rating_complete"]
    }
    assert missing == {3, 5, 10, 11, 16, 17}
    for c in artifact["cases"]:
        assert c["research"]["probabilities"] is None
        assert not c["research"]["eligible"]
        assert not c["research"]["rating_duration_compatible"]
    extra = [c for c in artifact["cases"] if c["record"]["extra_time_played"]]
    assert {c["record"]["match_id"] for c in extra} == {19, 21}
    assert all(c["research"]["observed_regulation_outcome"] == "draw" for c in extra)
    assert all(c["record"]["regulation_score"] != c["record"]["final_score"] for c in extra)


@pytest.fixture
def record():
    return json.loads((ROOT / "data/research/duration-80-v1/coverage.json").read_text())["cases"][
        0
    ]["record"]


@pytest.mark.parametrize(
    "change",
    [
        {"edition": 1995},
        {"regulation_minutes": 90},
        {"regulation_minutes": True},
        {"date": "1991-11-15"},
        {"date": "1991-12-01"},
    ],
)
def test_horizon_isolation(record, change):
    with pytest.raises(ValueError):
        inspect_case({**record, **change}, date(1991, 11, 15), True)


def test_cutoff_and_no_numerical_rescue(record):
    with pytest.raises(ValueError):
        inspect_case(record, date.fromisoformat(record["date"]), True)
    result = inspect_case(record, date(1991, 11, 15), True)
    changed = deepcopy(record)
    changed["regulation_score"] = [0, 9]
    changed["final_score"] = [99, 0]
    other = inspect_case(changed, date(1991, 11, 15), True)
    assert other["observed_regulation_outcome"] == "away_win"
    assert result["exclusion_reasons"] == other["exclusion_reasons"]
    assert result["parameter_version"] is other["parameter_version"] is None
    assert result == inspect_case(record, date(1991, 11, 15), True)
    unfinished = inspect_case(
        {**record, "completion_status": "abandoned"}, date(1991, 11, 15), False
    )
    assert "match_completion_unverified" in unfinished["exclusion_reasons"]
    assert SPEC["parameters"] is SPEC["accuracy"] is None
    assert SPEC["production_eligible"] is False
    # Prompt 3 cannot silently become an 80-minute prediction path.
    with pytest.raises(ValueError):
        predict(Ratings(50, 50, 50), Ratings(50, 50, 50), minutes=80)


@pytest.mark.parametrize(
    "change",
    [
        {"dataset_id": "womens-world-cup-recorded-v1"},
        {"edition": 1995},
        {"research_model_version": "odf-temperature-research-v1"},
    ],
)
def test_invalid_model_selection(change):
    with pytest.raises(ValidationError):
        BacktestRequest.model_validate(
            {"dataset_id": FULL_DATASET, "research_model_version": MODEL, **change}
        )


def test_opt_in_only():
    assert BacktestRequest(dataset_id=FULL_DATASET).research_model_version is None
    for year in (None, 1991):
        assert (
            BacktestRequest(
                dataset_id=FULL_DATASET, edition=year, research_model_version=MODEL
            ).research_model_version
            == MODEL
        )
