"""Historical team reads using the caller's transaction."""

from collections.abc import Sequence
from contextlib import AbstractContextManager

from sqlalchemy import select
from sqlalchemy.orm import Session

from infra.resources.db import Database
from models.team import Team


class TeamRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def transaction(self) -> AbstractContextManager[Session]:
        """Provide a context whose boundary is chosen by the calling service."""
        return self.database.transaction()

    def get_by_id(self, session: Session, team_id: int) -> Team | None:
        return session.get(Team, team_id)

    def get_participants(
        self, session: Session, team_ids: Sequence[int], *, for_key_share: bool = False
    ) -> list[Team]:
        statement = select(Team).where(Team.team_id.in_(team_ids)).order_by(Team.team_id)
        if for_key_share:
            statement = statement.with_for_update(read=True, key_share=True)
        return list(session.scalars(statement))

    def list(self, session: Session) -> list[Team]:
        return list(session.scalars(select(Team).order_by(Team.name, Team.team_id)))

    def historical_statistics(
        self,
        session: Session,
        team_id: int,
    ) -> dict[str, int]:  # return dictionary value ex: wins: 10

        # Find every match where this team played whether as home or away
        # from the matches table
        statement = select(Match).where(
            or_(
                Match.home_team_id == team_id,
                Match.away_team_id == team_id,
            )
        )

        # Store the matches in a list
        matches = list(session.scalars(statement))

        # Start all statistics at zero
        wins = 0
        draws = 0
        losses = 0
        goals_scored = 0
        goals_conceded = 0

        # A set prevents counting the same tournament more than once
        tournament_ids = set()

        # Loop to examine each match
        for match in matches:

            # Store which tournament this match belongs to
            tournament_ids.add(match.competition_id)

            # Figure out whether our team was home or away
            if match.home_team_id == team_id:
                team_score = match.home_score
                opponent_score = match.away_score
            else:
                team_score = match.away_score
                opponent_score = match.home_score

            # Add the goals
            goals_scored += team_score
            goals_conceded += opponent_score

            # Decide whether the team won, drew, or lost
            if team_score > opponent_score:
                wins += 1
            elif team_score == opponent_score:
                draws += 1
            else:
                losses += 1

        # Return the final statistics
        return {
            "team_id": team_id,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "goals_scored": goals_scored,
            "goals_conceded": goals_conceded,
            "tournament_appearances": len(tournament_ids),
        }