"""Exact certification arithmetic and real coverage artifact generation."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from coverage_report import evaluate


@pytest.mark.parametrize(
    "covered,passed", [(9499, False), (9500, True), (9501, True), (10000, True)]
)
def test_combined_threshold_never_rounds_up(covered, passed, capsys):
    report = {
        "meta": {"branch_coverage": True},
        "totals": {
            "num_statements": 9000,
            "num_branches": 1000,
            "covered_lines": 9000,
            "covered_branches": covered - 9000,
            "missing_lines": 0,
            "missing_branches": 10000 - covered,
        },
    }
    assert evaluate(report) is passed
    output = capsys.readouterr().out
    assert "Statement coverage: 100.000000%" in output
    assert "Branch coverage:" in output and "Combined coverage:" in output


@pytest.mark.parametrize("complete", [False, True])
def test_real_branch_reports_survive_gate_result(tmp_path, monkeypatch, complete):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COVERAGE_FILE", str(tmp_path / ".coverage"))
    (tmp_path / "src").mkdir()
    source = tmp_path / "src/example.py"
    source.write_text("def choose(value):\n    if value:\n        return 1\n    return 0\n")
    config = Path(__file__).resolve().parents[2] / ".coveragerc"
    (tmp_path / ".coveragerc").write_bytes(config.read_bytes())
    # Keep coverage.py's process-global path/tracer state out of the measured pytest process.
    program = """
import coverage
from pathlib import Path
cov = coverage.Coverage(config_file='.coveragerc')
cov.start()
source = Path('src/example.py')
namespace = {}
exec(compile(source.read_text(), str(source.resolve()), 'exec'), namespace)
assert namespace['choose'](True) == 1
if COMPLETE:
    assert namespace['choose'](False) == 0
cov.stop()
cov.save()
""".replace("COMPLETE", repr(complete))
    measured = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True)
    assert measured.returncode == 0, measured.stderr
    script = Path(__file__).resolve().parents[2] / "scripts/testing/coverage_report.py"
    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        env=dict(os.environ),
        capture_output=True,
        text=True,
    )
    assert result.returncode == (0 if complete else 2), result.stderr
    report = json.loads((tmp_path / "coverage.json").read_text())
    assert report["meta"]["branch_coverage"]
    assert report["totals"]["missing_branches"] == (0 if complete else 1)
    assert (tmp_path / "coverage.xml").stat().st_size > 0


def test_statement_only_measurement_is_rejected():
    with pytest.raises(ValueError, match="Branch coverage is required"):
        evaluate({"meta": {"branch_coverage": False}})
