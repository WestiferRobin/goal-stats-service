"""Runtime allowlist and contract enforcement without developer-local source files."""

from pathlib import Path

import pytest

from football.datasets import HistoricalImportError, read_historical_dataset
from football.historical_dataset import APPROVED_DATASETS, DatasetManifest, load_manifest


@pytest.mark.parametrize("dataset", APPROVED_DATASETS)
def test_supported_edition_schema(dataset):
    manifest = load_manifest(dataset)
    assert manifest.dataset_id == dataset
    assert manifest.competition.edition_label == dataset.rsplit("-", 1)[1]
    assert len(manifest.approval.participants) == manifest.expected_counts.teams
    assert manifest.approval.identity_policy == "source-record-key-v1"


@pytest.mark.parametrize(
    "dataset",
    [
        "womens-world-cup-2027",
        "../2023.json",
        Path("data/womens-world-cup/womens-world-cup-2023.json"),
        "all-approved",
        "",
    ],
)
def test_unknown_dataset_and_arbitrary_path_rejected(dataset):
    with pytest.raises(ValueError, match="Unknown historical dataset"):
        load_manifest(dataset)


@pytest.mark.parametrize(
    "section,field,value",
    [
        (None, "sha256", "0" * 64),
        (None, "upstream_revision", "0" * 40),
        (None, "source", "other"),
        (None, "dataset_id", "womens-world-cup-1991"),
        (None, "unexpected", True),
        ("competition", "edition_label", "2027"),
        ("competition", "edition_label", "1991"),
        ("selection", "tournament", "Friendly"),
        ("selection", "date_from", "2023-07-19"),
        ("expected_counts", "matches", 52),
        ("expected_counts", "teams", 16),
        ("approval", "total_goals", 163),
        ("approval", "approval_status", "pending"),
        ("approval", "identity_policy", "v2"),
        ("approval", "participants", ["Spain", "England"]),
    ],
)
def test_invalid_runtime_contract(section, field, value):
    data = load_manifest().model_dump()
    target = data if section is None else data[section]
    target[field] = value
    with pytest.raises(ValueError):
        DatasetManifest.model_validate(data)


@pytest.mark.parametrize("kind", ["missing", "unexpected", "goals"])
def test_selected_source_must_match_approved_participants_and_goals(historical_csv, kind):
    manifest = historical_csv.write()
    approval = manifest.approval
    if kind == "goals":
        approval = approval.model_copy(update={"total_goals": approval.total_goals + 1})
    else:
        names = list(approval.participants)
        if kind == "missing":
            names.pop()
        else:
            names[0] = "Unexpected Team"
        approval = approval.model_copy(update={"participants": tuple(names)})
    manifest = manifest.model_copy(update={"approval": approval})
    with pytest.raises(HistoricalImportError, match="participant set|total goals"):
        read_historical_dataset(historical_csv.directory, manifest)


def test_historical_reader_never_falls_back_to_prototype(tmp_path):
    for name in ("teams.csv", "match_history.csv", "historical_snapshots.csv"):
        (tmp_path / name).write_text("prototype only")
    with pytest.raises(HistoricalImportError, match="source CSV"):
        read_historical_dataset(tmp_path, load_manifest("womens-world-cup-1991"))


def test_2011_rejects_32_participants():
    data = load_manifest("womens-world-cup-2011").model_dump()
    data["expected_counts"]["teams"] = 32
    with pytest.raises(ValueError, match="must agree"):
        DatasetManifest.model_validate(data)


def test_extra_csv_header_rejected(historical_csv):
    from football.historical_dataset import REQUIRED_COLUMNS

    manifest = historical_csv.write(headers=(*REQUIRED_COLUMNS, "unsupported"))
    with pytest.raises(HistoricalImportError, match="headers"):
        read_historical_dataset(historical_csv.directory, manifest)


def test_incomplete_fixture_count_rejected(historical_csv):
    manifest = historical_csv.write(historical_csv.rows[:-1])
    with pytest.raises(HistoricalImportError, match="counts"):
        read_historical_dataset(historical_csv.directory, manifest)
