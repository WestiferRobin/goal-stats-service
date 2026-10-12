"""Executed only after the canonical runner recreates its disposable Gunicorn app."""

import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.smoke


def test_saved_records_survive_app_recreation(smoke_client):
    saved = json.loads(Path(os.environ["SMOKE_RESULTS"]).read_text())
    assert smoke_client.request(saved["scenario_path"])[0] == saved["scenario"]
    for path, prediction in saved["predictions"].items():
        assert smoke_client.request(path)[0] == prediction
    history, _ = smoke_client.request(saved["scenario_path"] + "/predictions")
    assert {row["prediction_id"] for row in history} == {
        row["prediction_id"] for row in saved["predictions"].values()
    }
