"""Validated, transactional and repeatable import of RoadToTheFinal CSV files."""

import csv
import hashlib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from models.football import FootballHistory, FootballTeam

DATA_DIRECTORY = Path(__file__).resolve().parents[2] / "data"


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
