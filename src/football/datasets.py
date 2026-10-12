"""Validated, transactional and repeatable import of RoadToTheFinal CSV files."""

import csv
import hashlib
import io
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from football.historical_dataset import (
    DatasetManifest,
    HistoricalMatchRecord,
    identity_issues,
    name_key,
    parse_match_date,
    parse_selected_record,
    validate_checksum,
    validate_headers,
)
from models.football import FootballHistory, FootballTeam

DATA_DIRECTORY = Path(__file__).resolve().parents[2] / "data" / "prototype"


class Ratings(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=100)
    offense: float = Field(ge=0, le=100)
    defense: float = Field(ge=0, le=100)
    form: float = Field(ge=0, le=100)
    star_power: float = Field(ge=0, le=100)
    clutch: float = Field(ge=0, le=100)
    fifa_rank: int | None = Field(default=None, ge=1)
    fifa_points: float | None = Field(default=None, ge=0)
    ranking_date: str = ""


def read_datasets(
    directory: Path = DATA_DIRECTORY,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with (directory / "teams.csv").open(newline="", encoding="utf-8-sig") as stream:
        teams = [
            Ratings.model_validate(
                {k: (v or None) if k in {"fifa_rank", "fifa_points"} else v for k, v in row.items()}
            ).model_dump()
            for row in csv.DictReader(stream)
        ]
    names = {team["name"] for team in teams}
    if len(names) != len(teams) or len({n.casefold() for n in names}) != len(teams):
        raise ValueError("Duplicate team names")
    history = []
    for source in ("match_history.csv", "historical_snapshots.csv"):
        with (directory / source).open(newline="", encoding="utf-8-sig") as stream:
            for number, raw in enumerate(csv.DictReader(stream), start=2):
                if None in raw:
                    raise ValueError(f"{source}:{number}: extra CSV fields")
                row = {key: value or "" for key, value in raw.items()}
                if (
                    row["team1"] not in names
                    or row["team2"] not in names
                    or row["team1"] == row["team2"]
                ):
                    raise ValueError(f"{source}:{number}: invalid teams")
                if row.get("actual_winner", "") not in {"", "Draw", row["team1"], row["team2"]}:
                    raise ValueError(f"{source}:{number}: invalid winner")
                for key, value in row.items():
                    if not value or key in {
                        "team1",
                        "team2",
                        "actual_winner",
                        "match_status_short",
                        "match_status_long",
                    }:
                        continue
                    if key.endswith("bad_star"):
                        if value.lower() not in {"true", "false", "0", "1", "yes", "no"}:
                            raise ValueError(f"{source}:{number}: invalid boolean")
                    elif not value.isdigit() or int(value) > 1000:
                        raise ValueError(f"{source}:{number}: invalid {key}")
                history.append(
                    {
                        "id": hashlib.sha256(f"{source}:{number}".encode()).hexdigest(),
                        "source": source,
                        "source_row": number,
                        "team1": row["team1"],
                        "team2": row["team2"],
                        "data": row,
                    }
                )
    return teams, history


def import_datasets(session: Session, directory: Path = DATA_DIRECTORY) -> dict[str, int]:
    teams, history = read_datasets(directory)  # validate everything before writing
    for team in teams:
        session.execute(
            insert(FootballTeam)
            .values(name=team["name"], ratings=team)
            .on_conflict_do_nothing(index_elements=["name"])
        )
    for row in history:
        session.execute(
            insert(FootballHistory).values(**row).on_conflict_do_nothing(index_elements=["id"])
        )
    return {"teams_read": len(teams), "history_rows_read": len(history)}


@dataclass
class ImportSummary:
    dataset: str
    source: str = ""
    source_version: str = ""
    rows_read: int = 0
    rows_selected: int = 0
    rows_filtered_out: int = 0
    teams_inserted: int = 0
    competitions_inserted: int = 0
    matches_inserted: int = 0
    unchanged: int = 0
    duplicate_input: int = 0
    rejected: int = 0
    conflicts: int = 0
    committed: bool = False
    insert_counts: str = "not_committed"
    issues: list[dict[str, str | int]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def discard_insert_counts(self) -> None:
        self.teams_inserted = self.competitions_inserted = self.matches_inserted = 0
        self.committed = False
        self.insert_counts = "not_committed"


class HistoricalImportError(ValueError):
    """Only safe authored messages, never raw driver/Pydantic exceptions."""

    def __init__(self, message: str, summary: ImportSummary) -> None:
        super().__init__(message)
        self.summary = summary


@dataclass(frozen=True)
class HistoricalBatch:
    manifest: DatasetManifest
    records: tuple[HistoricalMatchRecord, ...]
    summary: ImportSummary


def read_historical_dataset(directory: Path, manifest: DatasetManifest) -> HistoricalBatch:
    """Validate the full pinned CSV before returning a distinct, typed tournament batch."""
    summary = ImportSummary(manifest.dataset_id, manifest.source, manifest.upstream_revision)
    try:
        content = (directory / manifest.source_filename).read_bytes()
    except OSError:
        raise HistoricalImportError(
            "Cannot read the manifest's source CSV in --directory.", summary
        ) from None
    try:
        validate_checksum(content, manifest)
    except ValueError:
        summary.rejected = 1
        raise HistoricalImportError(
            "Full source CSV checksum mismatch; obtain the pinned file.", summary
        ) from None
    records = []
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        validate_headers(reader.fieldnames, manifest)
        for number, row in enumerate(reader, 2):
            summary.rows_read += 1
            if None in row or any(value is None for value in row.values()):
                summary.rejected += 1
                summary.issues.append({"source_row": number, "reason": "malformed CSV row"})
                continue
            # Missing selector values cannot safely be treated as an excluded row.
            if not row.get("tournament", "").strip() or not row.get("date", "").strip():
                summary.rejected += 1
                summary.issues.append({"source_row": number, "reason": "missing date/tournament"})
                continue
            if row["tournament"] != manifest.selection.tournament:
                summary.rows_filtered_out += 1
                continue
            try:
                played = parse_match_date(row["date"])
            except ValueError:
                summary.rejected += 1
                summary.issues.append({"source_row": number, "reason": "invalid or future date"})
                continue
            if not manifest.selection.date_from <= played <= manifest.selection.date_to:
                summary.rows_filtered_out += 1
                continue
            summary.rows_selected += 1
            try:
                records.append(parse_selected_record(row, source_row=number, manifest=manifest))
            except ValueError:
                summary.rejected += 1
                summary.issues.append({"source_row": number, "reason": "invalid selected record"})
        if summary.rejected:
            raise HistoricalImportError(
                "Invalid CSV records: check row shape, required values, "
                "ISO dates, teams, integer scores and venue flags.",
                summary,
            )
    except (UnicodeError, csv.Error, ValueError) as exc:
        if isinstance(exc, HistoricalImportError):
            raise
        summary.rejected += 1
        raise HistoricalImportError(
            "CSV encoding, structure or required headers are invalid.", summary
        ) from None
    issues = identity_issues(records)
    summary.duplicate_input = sum(issue.kind == "duplicate" for issue in issues)
    summary.conflicts = sum(issue.kind == "conflict" for issue in issues)
    summary.issues.extend(
        {
            "source_row": issue.source_row,
            "first_row": issue.first_row,
            "source_record_key": issue.source_record_key,
            "reason": issue.kind,
        }
        for issue in issues
    )
    if summary.conflicts:
        raise HistoricalImportError(
            "Conflicting input facts share a stable match identity.", summary
        )
    if summary.duplicate_input:
        summary.rejected += summary.duplicate_input
        raise HistoricalImportError("Duplicate input match identities are not allowed.", summary)
    unique: dict[str, HistoricalMatchRecord] = {}
    for record in records:
        unique.setdefault(record.source_record_key, record)
    teams = {
        team.name_key for record in unique.values() for team in (record.home_team, record.away_team)
    }
    if (
        len(unique) != manifest.expected_counts.matches
        or len(teams) != manifest.expected_counts.teams
        or len({record.competition.name_key for record in unique.values()})
        != manifest.expected_counts.competitions
    ):
        summary.rejected += 1
        raise HistoricalImportError(
            "Selected distinct match/team/competition counts differ from "
            "the manifest; no import is allowed.",
            summary,
        )
    expected_teams = {name_key(p) for p in manifest.approval.participants}
    if teams != expected_teams:
        summary.rejected += 1
        raise HistoricalImportError("Selected participant set differs from the manifest.", summary)
    if sum(r.home_score + r.away_score for r in unique.values()) != manifest.approval.total_goals:
        summary.rejected += 1
        raise HistoricalImportError("Selected total goals differ from the manifest.", summary)
    return HistoricalBatch(manifest, tuple(unique.values()), summary)
