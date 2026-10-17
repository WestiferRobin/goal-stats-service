"""Pure dataset contract for the later importer. No networking or database writes."""

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Literal, Self, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

MANIFEST_PATH = (
    Path(__file__).resolve().parents[2] / "data/womens-world-cup/womens-world-cup-2023.json"
)
Edition = Literal["1991", "1995", "1999", "2003", "2007", "2011", "2015", "2019", "2023"]
DatasetID = Literal[
    "womens-world-cup-1991",
    "womens-world-cup-1995",
    "womens-world-cup-1999",
    "womens-world-cup-2003",
    "womens-world-cup-2007",
    "womens-world-cup-2011",
    "womens-world-cup-2015",
    "womens-world-cup-2019",
    "womens-world-cup-2023",
]
APPROVED_DATASETS: tuple[str, ...] = get_args(DatasetID)
EDITION_SPECS = {
    "1991": ("1991-11-16", "1991-11-30", 26, 12, 99),
    "1995": ("1995-06-05", "1995-06-18", 26, 12, 99),
    "1999": ("1999-06-19", "1999-07-10", 32, 16, 123),
    "2003": ("2003-09-20", "2003-10-12", 32, 16, 107),
    "2007": ("2007-09-10", "2007-09-30", 32, 16, 111),
    "2011": ("2011-06-26", "2011-07-17", 32, 16, 86),
    "2015": ("2015-06-06", "2015-07-05", 52, 24, 146),
    "2019": ("2019-06-07", "2019-07-07", 52, 24, 146),
    "2023": ("2023-07-20", "2023-08-20", 64, 32, 164),
}
COVERAGE_PATH = MANIFEST_PATH.parent.parent / "verification/womens-world-cup-coverage.json"
REQUIRED_COLUMNS = (
    "date",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "tournament",
    "city",
    "country",
    "neutral",
)
Nonblank = Annotated[str, Field(pattern=r"\S")]


def normalize_label(value: str) -> str:
    """NFKC, Unicode whitespace collapse/trim; preserve display casing and accents."""
    return " ".join(unicodedata.normalize("NFKC", value).split())


def name_key(value: str) -> str:
    return unicodedata.normalize("NFKC", normalize_label(value).casefold())


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Selection(ContractModel):
    tournament: Literal["FIFA World Cup"]
    date_from: date
    date_to: date

    @model_validator(mode="after")
    def pinned_dates(self) -> Self:
        if (self.date_from.isoformat(), self.date_to.isoformat()) not in {
            spec[:2] for spec in EDITION_SPECS.values()
        }:
            raise ValueError("Selection must be an approved inclusive Women's World Cup interval")
        return self


class CompetitionRecord(ContractModel):
    source_tournament: Literal["FIFA World Cup"]
    name: Literal["FIFA Women's World Cup"]
    name_key: Literal["fifa women's world cup"]
    edition_label: Edition
    category: Literal["women_senior_national"]


class ExpectedCounts(ContractModel):
    matches: Literal[26, 32, 52, 64]
    teams: Literal[12, 16, 24, 32]
    competitions: Literal[1]


class EditionApproval(ContractModel):
    """Typed companion entry from the reviewed, checked-in coverage evidence."""

    dataset_id: DatasetID
    date_from: date
    date_to: date
    matches: Annotated[int, Field(strict=True, gt=0)]
    participant_count: Annotated[int, Field(strict=True, gt=0)]
    participants: tuple[Nonblank, ...]
    total_goals: Annotated[int, Field(strict=True, ge=0)]
    fixture_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    approval_status: Literal["approved_pinned_basic_results"]
    # Historical verification-time fact, not current runtime capability selection.
    runtime_supported: bool
    identity_policy: Literal["source-record-key-v1"]
    home_away_policy: Literal["preserve_source_order"]
    score_basis: Literal["including_extra_time_no_shootout"]


class DatasetManifest(ContractModel):
    dataset_id: DatasetID
    source: Literal["martj42_womens_results"]
    source_name: Nonblank
    author: Literal["Mart Jürisoo"]
    source_url: Nonblank
    upstream_revision: Literal["1855e313ae8bcd0330426e62c8e4cf15ce45077c"]
    sha256: Literal["de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0"]
    attribution_reference: Nonblank
    license_reference: Nonblank
    source_filename: Literal["results.csv"]
    required_columns: tuple[str, ...]
    selection: Selection
    competition: CompetitionRecord
    team_category: Literal["women_senior_national"]
    score_basis: Literal["including_extra_time_no_shootout"]
    expected_counts: ExpectedCounts
    reviewed_team_aliases: dict[str, str]
    approval: EditionApproval

    @model_validator(mode="after")
    def coherent_contract(self) -> Self:
        year = self.competition.edition_label
        start, end, matches, teams, goals = EDITION_SPECS[year]
        a = self.approval
        if (
            self.dataset_id != f"womens-world-cup-{year}"
            or a.dataset_id != self.dataset_id
            or (self.selection.date_from.isoformat(), self.selection.date_to.isoformat())
            != (start, end)
            or (a.date_from, a.date_to) != (self.selection.date_from, self.selection.date_to)
            or (self.expected_counts.matches, self.expected_counts.teams) != (matches, teams)
            or (a.matches, a.participant_count, a.total_goals) != (matches, teams, goals)
        ):
            raise ValueError("Edition, selection, counts and approval must agree")
        if (
            tuple(sorted(set(a.participants))) != a.participants
            or len(a.participants) != teams
            or len({name_key(p) for p in a.participants}) != teams
        ):
            raise ValueError("Exact approved participant identities must be unique and complete")
        if self.required_columns != REQUIRED_COLUMNS:
            raise ValueError("Required source columns differ from the pinned contract")
        base = "https://github.com/martj42/womens-international-results/blob/"
        if self.source_url != f"{base}{self.upstream_revision}/{self.source_filename}":
            raise ValueError("Source URL must point to the pinned CSV")
        for alias, target in self.reviewed_team_aliases.items():
            if alias != name_key(alias) or not alias or not normalize_label(target):
                raise ValueError("Reviewed aliases require normalized keys and nonblank targets")
        return self


def load_manifest(dataset_id: str = "womens-world-cup-2023") -> DatasetManifest:
    """Only allowlisted repository contracts; no path or source override."""
    if dataset_id not in APPROVED_DATASETS:
        raise ValueError("Unknown historical dataset; arbitrary manifest paths are not allowed")
    path = MANIFEST_PATH.parent / f"{dataset_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    coverage = json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))
    if (
        coverage["source_revision"] != data["upstream_revision"]
        or coverage["source_sha256"] != data["sha256"]
        or data["dataset_id"] != dataset_id
        or "approval" in data
    ):
        raise ValueError("Manifest and checked-in approval provenance differ")
    entries = [e for e in coverage["editions"] if e["dataset_id"] == dataset_id]
    if len(entries) != 1:
        raise ValueError("Dataset requires exactly one approved coverage entry")
    return DatasetManifest.model_validate({**data, "approval": entries[0]})


def validate_headers(headers: Iterable[str] | None, manifest: DatasetManifest) -> None:
    columns = list(headers or ())
    if tuple(columns) != manifest.required_columns:
        raise ValueError("Missing required or duplicate CSV headers")


def validate_checksum(content: bytes, manifest: DatasetManifest) -> None:
    """Verify the full upstream file before selecting any rows."""
    if hashlib.sha256(content).hexdigest() != manifest.sha256:
        raise ValueError("Full upstream CSV checksum mismatch")


def source_record_key(
    *,
    source: str,
    category: str,
    competition_key: str,
    edition: str,
    match_date: date,
    source_home_team: str,
    source_away_team: str,
) -> str:
    """SHA-256 of compact UTF-8 JSON, ensure_ascii=False, ordered seven-field array.

    Scores, row numbers, version and checksum intentionally cannot be supplied.
    Team identity uses normalized original labels, before any reviewed alias mapping.
    """
    values = [
        source,
        category,
        competition_key,
        edition,
        match_date.isoformat(),
        name_key(source_home_team),
        name_key(source_away_team),
    ]
    if any(not normalize_label(value) for value in values):
        raise ValueError("Identity fields must be nonblank")
    return hashlib.sha256(
        json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class HistoricalTeamRecord(ContractModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    name_key: Annotated[str, Field(min_length=1, max_length=120)]
    category: Literal["women_senior_national"] = "women_senior_national"
    # This source provides no model ratings or rankings. They cannot be fabricated here.
    offense: None = None
    defense: None = None
    form: None = None
    star_power: None = None
    clutch: None = None
    fifa_rank: None = None
    ratings_source: None = None
    ranking_source: None = None
    ranking_date: None = None

    @model_validator(mode="after")
    def normalized_identity(self) -> Self:
        if not normalize_label(self.name) or self.name_key != name_key(self.name):
            raise ValueError("Team identity must have a nonblank name and matching normalized key")
        return self


class HistoricalMatchRecord(ContractModel):
    competition: CompetitionRecord
    home_team: HistoricalTeamRecord
    away_team: HistoricalTeamRecord
    match_date: date
    home_score: Annotated[int, Field(strict=True, ge=0, le=32767)]
    away_score: Annotated[int, Field(strict=True, ge=0, le=32767)]
    score_basis: Literal["including_extra_time_no_shootout"]
    neutral: bool | None
    city: str | None
    country: str | None
    source: Literal["martj42_womens_results"]
    source_record_key: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    source_version: Nonblank
    source_file_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    source_row: Annotated[int, Field(strict=True, gt=0)]
    source_url: Nonblank
    source_home_team: Nonblank
    source_away_team: Nonblank
    source_tournament: Nonblank

    @model_validator(mode="after")
    def distinct_teams(self) -> Self:
        if self.home_team.name_key == self.away_team.name_key:
            raise ValueError("Identical home and away teams")
        return self


def _required(row: Mapping[str, str | None], column: str) -> str:
    value = row.get(column)
    if value is None or not normalize_label(value):
        raise ValueError(f"Missing required value: {column}")
    return value


def parse_match_date(value: str) -> date:
    """Strict source format and completed-result date semantics, also used for selection."""
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Date must be ISO YYYY-MM-DD")
    played = date.fromisoformat(value)
    if played > datetime.now(UTC).date():
        raise ValueError("Completed historical results cannot have a future date")
    return played


def _score(value: str) -> int:
    if not re.fullmatch(r"[0-9]+", value.strip()):
        raise ValueError("Scores must be nonnegative whole numbers")
    result = int(value)
    if result > 32767:
        raise ValueError("Score exceeds PostgreSQL SMALLINT")
    return result


def parse_selected_record(
    row: Mapping[str, str | None],
    *,
    source_row: int,
    manifest: DatasetManifest,
) -> HistoricalMatchRecord:
    """Validate one selected CSV record, retaining original source labels verbatim.

    The future importer selects the explicit tournament/date interval first, then
    calls this function. Unmapped tournaments and out-of-window rows are rejected.
    """
    validate_headers(row.keys(), manifest)
    raw_date = _required(row, "date")
    played = parse_match_date(raw_date)
    tournament = _required(row, "tournament")
    if tournament != manifest.competition.source_tournament:
        raise ValueError("Unknown competition mapping")
    if not manifest.selection.date_from <= played <= manifest.selection.date_to:
        raise ValueError("Match date is outside the explicit selection")
    home, away = _required(row, "home_team"), _required(row, "away_team")

    def team(label: str) -> HistoricalTeamRecord:
        canonical = normalize_label(manifest.reviewed_team_aliases.get(name_key(label), label))
        return HistoricalTeamRecord(name=canonical, name_key=name_key(canonical))

    neutral_text = normalize_label(row.get("neutral") or "").casefold()
    if neutral_text not in {"", "true", "false"}:
        raise ValueError("Neutral must be TRUE, FALSE, or blank")
    return HistoricalMatchRecord(
        competition=manifest.competition,
        home_team=team(home),
        away_team=team(away),
        match_date=played,
        home_score=_score(_required(row, "home_score")),
        away_score=_score(_required(row, "away_score")),
        score_basis=manifest.score_basis,
        neutral=None if not neutral_text else neutral_text == "true",
        city=normalize_label(row.get("city") or "") or None,
        country=normalize_label(row.get("country") or "") or None,
        source=manifest.source,
        source_record_key=source_record_key(
            source=manifest.source,
            category=manifest.team_category,
            competition_key=manifest.competition.name_key,
            edition=manifest.competition.edition_label,
            match_date=played,
            source_home_team=home,
            source_away_team=away,
        ),
        source_version=manifest.upstream_revision,
        source_file_sha256=manifest.sha256,
        source_row=source_row,
        source_url=manifest.source_url,
        source_home_team=home,
        source_away_team=away,
        source_tournament=tournament,
    )


class IdentityIssue(ContractModel):
    kind: Literal["duplicate", "conflict"]
    source_record_key: str
    first_row: int
    source_row: int


def identity_issues(records: Iterable[HistoricalMatchRecord]) -> list[IdentityIssue]:
    """Report every repeated identity; never silently deduplicate or overwrite."""
    seen: dict[tuple[str, str], HistoricalMatchRecord] = {}
    issues = []
    ignored = {
        "source_row",
        "source_version",
        "source_file_sha256",
        "source_url",
        "source_home_team",
        "source_away_team",
        "source_tournament",
    }
    for record in records:
        key = (record.source, record.source_record_key)
        previous = seen.get(key)
        if previous is None:
            seen[key] = record
        else:
            identical = previous.model_dump(exclude=ignored) == record.model_dump(exclude=ignored)
            issues.append(
                IdentityIssue(
                    kind="duplicate" if identical else "conflict",
                    source_record_key=record.source_record_key,
                    first_row=previous.source_row,
                    source_row=record.source_row,
                )
            )
    return issues
