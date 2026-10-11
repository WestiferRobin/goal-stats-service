from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from football.datasets import HistoricalImportError, read_historical_dataset
from football.historical_dataset import REQUIRED_COLUMNS, load_manifest


def test_valid_full_selection_and_filtered_counts(historical_csv):
    rows = historical_csv.rows + [
        {**historical_csv.rows[0], "tournament": "Friendly"},
        {**historical_csv.rows[0], "date": "2022-07-20"},
    ]
    manifest = historical_csv.write(rows)
    batch = read_historical_dataset(historical_csv.directory, manifest)
    assert len(batch.records) == 64
    assert (
        batch.summary.rows_read,
        batch.summary.rows_selected,
        batch.summary.rows_filtered_out,
    ) == (66, 64, 2)
    assert all(r.home_team.offense is None and r.home_team.fifa_rank is None for r in batch.records)
    assert batch.records[0].away_score == 0
    assert batch.records[0].country == "Australia"
    assert batch.records[0].neutral is True
    assert not batch.summary.committed


def test_checksum_before_any_parsing(historical_csv):
    with pytest.raises(HistoricalImportError, match="checksum") as error:
        read_historical_dataset(historical_csv.directory, load_manifest())
    assert error.value.summary.rows_read == 0
    assert not error.value.summary.committed


@pytest.mark.parametrize("headers", [REQUIRED_COLUMNS[:-1], (*REQUIRED_COLUMNS, "date")])
def test_required_and_duplicate_headers(historical_csv, headers):
    manifest = historical_csv.write(headers=headers)
    with pytest.raises(HistoricalImportError, match="headers"):
        read_historical_dataset(historical_csv.directory, manifest)


@pytest.mark.parametrize(
    "field,value",
    [
        ("date", ""),
        ("tournament", ""),
        ("home_team", ""),
        ("away_team", ""),
        ("home_score", ""),
        ("away_score", ""),
        ("date", "2023-02-30"),
        ("date", "20230720"),
        ("home_score", "-1"),
        ("away_score", "1.5"),
        ("home_score", "NaN"),
        ("away_team", " Team 0 "),
        ("neutral", "yes"),
        ("date", "2099-07-20"),
    ],
)
def test_invalid_records_are_rejected(historical_csv, field, value):
    rows = [{**historical_csv.rows[0], field: value}, *historical_csv.rows[1:]]
    manifest = historical_csv.write(rows)
    with pytest.raises(HistoricalImportError) as error:
        read_historical_dataset(historical_csv.directory, manifest)
    assert error.value.summary.rejected == 1
    assert error.value.summary.matches_inserted == 0


def test_empty_selection_and_unmapped_tournament(historical_csv):
    manifest = historical_csv.write(
        [{**row, "tournament": "Unknown"} for row in historical_csv.rows]
    )
    with pytest.raises(HistoricalImportError, match="counts") as error:
        read_historical_dataset(historical_csv.directory, manifest)
    assert error.value.summary.rows_selected == 0
    assert error.value.summary.rows_filtered_out == 64


def test_duplicates_are_counted_but_conflicts_abort(historical_csv):
    manifest = historical_csv.write([*historical_csv.rows, historical_csv.rows[0]])
    batch = read_historical_dataset(historical_csv.directory, manifest)
    assert len(batch.records) == 64
    assert batch.summary.duplicate_input == 1
    assert batch.summary.rows_selected == 65
    assert next(r for r in batch.records if r.source_home_team == "Team 0").source_row == 2
    manifest = historical_csv.write(
        [*historical_csv.rows, {**historical_csv.rows[0], "home_score": "5"}]
    )
    with pytest.raises(HistoricalImportError, match="Conflicting") as error:
        read_historical_dataset(historical_csv.directory, manifest)
    assert error.value.summary.conflicts == 1
    assert error.value.summary.issues[0]["source_row"] == 66


def test_row_order_and_score_corrections_preserve_keys(historical_csv):
    manifest = historical_csv.write()
    original = read_historical_dataset(historical_csv.directory, manifest)
    changed = [{**row, "home_score": "6"} for row in reversed(historical_csv.rows)]
    manifest = historical_csv.write(changed)
    revised = read_historical_dataset(historical_csv.directory, manifest)
    assert {r.source_record_key for r in original.records} == {
        r.source_record_key for r in revised.records
    }
    assert original.records[0].source_record_key == revised.records[-1].source_record_key


def test_optional_blanks_unicode_and_reviewed_aliases(historical_csv):
    rows = [
        {
            **row,
            "city": " ",
            "country": "",
            "neutral": "",
            "home_team": "  " + row["home_team"] + "\u00a0",
        }
        for row in historical_csv.rows
    ]
    manifest = historical_csv.write(rows).model_copy(
        update={"reviewed_team_aliases": {"team 0": "Reviewed Name"}}
    )
    batch = read_historical_dataset(historical_csv.directory, manifest)
    first = batch.records[0]
    assert first.home_team.name == "Reviewed Name"
    assert first.city is first.country is first.neutral is None
    assert first.source_home_team == rows[0]["home_team"]
    assert first.home_score == 0


def test_completed_results_cannot_be_future(historical_csv, monkeypatch):
    monkeypatch.setattr(
        "football.historical_dataset.datetime",
        SimpleNamespace(now=lambda tz: datetime(2023, 7, 19, tzinfo=UTC)),
    )
    with pytest.raises(HistoricalImportError) as error:
        read_historical_dataset(historical_csv.directory, historical_csv.write())
    assert error.value.summary.rejected == 64


def test_malformed_csv_is_rejected_after_verified_bytes(historical_csv):
    import hashlib

    content = b",".join(c.encode() for c in REQUIRED_COLUMNS) + b'\n"unterminated'
    (historical_csv.directory / "results.csv").write_bytes(content)
    manifest = load_manifest().model_copy(update={"sha256": hashlib.sha256(content).hexdigest()})
    with pytest.raises(HistoricalImportError, match="structure"):
        read_historical_dataset(historical_csv.directory, manifest)
