"""Synthetic CSV fixtures only; never a substitute for the pinned upstream dataset."""

import csv
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

import pytest

from football.historical_dataset import REQUIRED_COLUMNS, load_manifest


@dataclass
class HistoricalFixture:
    directory: Path
    rows: list[dict[str, str]]

    def write(self, rows=None, *, headers=REQUIRED_COLUMNS):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(self.rows if rows is None else rows)
        content = stream.getvalue().encode()
        (self.directory / "results.csv").write_bytes(content)
        # Test-only immutable model copy. Runtime CLI has no manifest/checksum override.
        return load_manifest().model_copy(update={"sha256": hashlib.sha256(content).hexdigest()})


@pytest.fixture
def historical_csv(tmp_path):
    rows = []
    for round_number in range(4):
        for pair in range(16):
            rows.append(
                dict(
                    zip(
                        REQUIRED_COLUMNS,
                        [
                            f"2023-07-{20 + round_number}",
                            f"Team {2 * pair}",
                            f"Team {2 * pair + 1}",
                            str(pair % 4),
                            "0",
                            "FIFA World Cup",
                            "Sydney",
                            "Australia",
                            "TRUE",
                        ],
                        strict=True,
                    )
                )
            )
    fixture = HistoricalFixture(tmp_path, rows)
    fixture.write()
    return fixture
