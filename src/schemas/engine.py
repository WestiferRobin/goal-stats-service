"""Engine contracts; external fields and validation preserved."""

from pydantic import Field

from schemas.common import Contract, Count


class Modifier(Contract):
    reason: str = Field(min_length=1, max_length=200)
    value: float = Field(ge=-100, le=100)


class TeamStats(Contract):
    goals: Count = 0
    possession: float = Field(default=50, ge=0, le=100)
    shots: Count = 0
    shots_on_target: Count = 0
    big_chances: Count = 0
    defender_blocks: Count = 0
    goalkeeper_saves: Count = 0
    corners: Count = 0
    yellow_cards: Count = 0
    red_cards: int = Field(default=0, ge=0, le=11)
    modifiers: list[Modifier] = Field(default_factory=list, max_length=30)


class Pair(Contract):
    team1: float
    team2: float


class OutcomeProbabilities(Pair):
    draw: float


class Scoreline(Contract):
    team1_goals: int
    team2_goals: int
    probability: float


class Confidence(Contract):
    percent: float
    label: str


class PredictionResponse(Contract):
    team1: str
    team2: str
    minute: int
    status: str
    probabilities: OutcomeProbabilities
    advancement: Pair
    expected_goals_remaining: Pair
    momentum_percent: Pair
    most_likely_score: list[int]
    top_scorelines: list[Scoreline]
    confidence: Confidence
    reasoning: list[str]
    model: str
