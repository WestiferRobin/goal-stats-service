"""Reconstruction, inventory, immutable source, and isolation checks."""

import ast
import hashlib
import json

from research.feasibility import PACKAGE, ROOT, build
from research.special_ratings import SPEC, digest


def test_full_inventory_and_deterministic_reconstruction():
    actual = build()
    assert actual == json.loads((PACKAGE / "coverage.json").read_text())
    assert actual["total_cases"] == 348
    assert {r["edition"]: r["matches"] for r in actual["editions"]} == {
        1991: 26,
        1995: 26,
        1999: 32,
        2003: 32,
        2007: 32,
        2011: 32,
        2015: 52,
        2019: 52,
        2023: 64,
    }
    assert sum(c["original_odf_complete"] for c in actual["cases"]) == 320
    assert sum(c["recovered_odf_complete"] for c in actual["cases"]) == 340
    assert len({c["match_key"] for c in actual["cases"]}) == 348
    for case in actual["cases"]:
        assert case["cutoff"] < case["date"]
        assert len(case["participants"]) == 2
        for participant in case["participants"]:
            for field in ["star", "clutch"]:
                estimate = participant[field]
                assert estimate["value"] is None and estimate["kind"] == "missing_evidence"
                assert estimate["production_eligible"] is False
    assert actual["approved_recovery_additional_special_observations"] == 0


def test_frozen_artifacts_and_source_inventory():
    manifest = json.loads((PACKAGE / "manifest.json").read_text())
    assert manifest["method_hash"] == digest(SPEC)
    assert json.loads((PACKAGE / "specification.json").read_text()) == SPEC
    for name, expected in manifest["files"].items():
        assert hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest() == expected
    sources = json.loads((PACKAGE / "sources.json").read_text())["sources"]
    assert all(s.get("url") and s["rights"] and s["publication_timing"] for s in sources)
    for source in sources:
        if source["id"].startswith("rsssf-"):
            assert source["available_years"] == [int(source["id"].split("-")[1])]
    assert {
        year
        for s in sources
        if isinstance(s["available_years"], list)
        for year in s["available_years"]
    } >= {1991, 1995, 1999, 2003, 2007, 2011, 2015, 2019, 2023}


def test_no_production_research_imports():
    for path in (ROOT / "src").rglob("*.py"):
        if "research" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("research")
            if isinstance(node, ast.Import):
                assert all(not alias.name.startswith("research") for alias in node.names)
