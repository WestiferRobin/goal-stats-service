"""Frozen production enrichment inputs; no network acquisition or model changes."""

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from football import enrichment, team_ratings

PACKAGE = Path(__file__).resolve().parents[2] / "data/bootstrap/fifa-enrichment-v1"
MANIFEST_SHA256 = "7e3ba3fbf31c6fd2dc6a67b451f004efac87179013a98e08a0b85fe96ce42f6a"
CUTOFF = date(2026, 6, 10)


@dataclass(frozen=True)
class EnrichmentInputs:
    manifest: dict[str, Any]
    package: list[tuple[dict[str, Any], list[dict[str, Any]]]]
    ratings: dict[str, dict[str, Any]]
    report: dict[str, Any]


def verify_evidence(
    directory: Path = PACKAGE,
) -> tuple[dict[str, Any], list[tuple[dict[str, Any], list[dict[str, Any]]]]]:
    """Pin the manifest itself as well as every index/response checksum it records."""
    if hashlib.sha256((directory / "manifest.json").read_bytes()).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Approved bootstrap FIFA manifest checksum mismatch")
    manifest, package = enrichment.load_package(directory)
    if len(package) != 96 or sum(len(rows) for _, rows in package) != 16525:
        raise ValueError("Approved bootstrap FIFA inventory mismatch")
    return manifest, package


def prepare(source: Path) -> EnrichmentInputs:
    manifest, package = verify_evidence(PACKAGE)
    rows = team_ratings.read_results(source.read_bytes())
    return EnrichmentInputs(
        manifest,
        package,
        team_ratings.calculate(rows, CUTOFF),
        team_ratings.validate_model(rows, CUTOFF),
    )
