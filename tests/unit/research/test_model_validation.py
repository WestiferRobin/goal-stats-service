"""Approved historical reconstruction; no fabricated source facts or ratings."""

import hashlib
import json

import pytest

from research import model_validation as audit
from research.special_ratings import digest
from research.three_input import SPEC, A, B, C


def test_complete_inventory_pinned_sources_and_reconstruction():
    data = audit.reconstruct()
    assert data == json.loads((audit.PACKAGE / "predictions.json").read_text())
    assert len(data["cases"]) == 348
    assert sum(c["rating_complete"] for c in data["cases"]) == 340
    assert sum(B in c["predictions"] for c in data["cases"]) == 320
    assert sum(C in c["predictions"] for c in data["cases"]) == 200
    assert all(not c["five_input_eligible"] and not c["production_eligible"] for c in data["cases"])
    missing = [
        c["match_id"] for c in data["cases"] if c["edition"] != 1991 and B not in c["predictions"]
    ]
    assert sorted(missing) == [57, 65]
    for row in data["cases"]:
        assert row["cutoff"] < row["date"]
        if row["edition"] == 1991:
            assert not row["predictions"]
        if row["baseline_training"]:
            assert row["baseline_training"]["training_through"] < row["date"]
            assert row["baseline_training"]["training_through"] <= "2003-12-31"
        for rank in row["ranking_evidence"]:
            assert not rank.get("published_on") or rank["published_on"] < row["date"]
        if C in row["predictions"]:
            assert data["calibration"]["through"] < row["date"]
        assert row["rating_population_size"] >= len(row["inputs"])
    assert data["protocol_hash"] == digest(SPEC)
    report = audit.evaluate(data)
    assert report == json.loads((audit.PACKAGE / "results.json").read_text())
    assert sum(r["total"] for r in report["editions"]) == 348
    assert sum(r["excluded"] for r in report["editions"]) == 28
    assert report["results"]["validation"]["calibrated_common"]["sample_size"] == 84
    assert report["results"]["retrospective_holdout"]["calibrated_common"]["sample_size"] == 116
    assert report["results"]["all_exploratory"]["baseline_common"]["sample_size"] == 294
    assert report["primary_comparison_sample_size"] == 0
    for group in report["results"].values():
        for cohort in group.values():
            assert all(m["sample_size"] == cohort["sample_size"] for m in cohort["models"].values())
    assert (
        report["five_input_status"]
        == "Five-input historical comparison not yet supported by available evidence."
    )


def test_frozen_files_and_hypothesis_preservation():
    manifest = json.loads((audit.PACKAGE / "manifest.json").read_text())
    assert (
        manifest["protocol_hash"]
        == "43f1bd4637788464199d2ad9becb57c951fa99487000a61184dac7bc48e2110e"
    )
    assert json.loads((audit.PACKAGE / "protocol.json").read_text()) == SPEC
    for name, sha in manifest["files"].items():
        assert hashlib.sha256((audit.PACKAGE / name).read_bytes()).hexdigest() == sha
    assert SPEC["primary_model"] == B and A != B != C


def test_corrupt_ranking_projection_rejected(tmp_path, monkeypatch):
    (tmp_path / "rankings.json").write_text("{}")
    monkeypatch.setattr(audit, "PACKAGE", tmp_path)
    with pytest.raises(ValueError, match="checksum"):
        audit.reconstruct()


@pytest.mark.parametrize("change", ["inventory", "identity", "future"])
def test_ranking_integrity_and_cutoff_fail_closed(tmp_path, monkeypatch, change):
    data = json.loads((audit.PACKAGE / "rankings.json").read_text())
    key = next(iter(data["cases"]))
    if change == "inventory":
        del data["cases"][key]
    elif change == "identity":
        data["cases"][key][0]["team_id"] = -1
    else:
        data["cases"][key][0]["published_on"] = "2099-01-01"
    raw = (json.dumps(data) + "\n").encode()
    (tmp_path / "rankings.json").write_bytes(raw)
    monkeypatch.setattr(audit, "PACKAGE", tmp_path)
    monkeypatch.setattr(audit, "RANKING_SHA", hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError, match="Ranking"):
        audit.reconstruct()


def test_calibration_future_parameters_rejected(monkeypatch):
    monkeypatch.setattr(
        audit, "calibrate", lambda *args: {"through": "2099-01-01", "temperature": 1.0}
    )
    with pytest.raises(ValueError, match="Calibration leakage"):
        audit.reconstruct()
