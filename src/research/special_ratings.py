"""Frozen candidate aggregation interfaces; never production observations or eligibility.

Upstream RAPM coefficients and independent 90-minute forecasts are required evidence,
not manufactured here. Historical bundles currently contain neither.
"""

import hashlib
import json
import math
from datetime import date, timedelta
from statistics import mean, variance
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1, pattern=r"\S")]
SHA = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Number = Annotated[float, Field(strict=True, allow_inf_nan=False)]
Probability = Annotated[Number, Field(ge=0, le=1)]
Role = Literal["GK", "DF", "MF", "FW"]
STAR_VERSION = "star-role-rapm-aggregation-research-v1"
CLUTCH_VERSION = "clutch-regulation-residual-contrast-research-v1"
RAPM_VERSION = "player-segment-ridge-goal-difference-v1"
SPEC: dict[str, Any] = {
    "star_version": STAR_VERSION,
    "clutch_version": CLUTCH_VERSION,
    "rapm_version": RAPM_VERSION,
    "star": {
        "window_days": 730,
        "minimum_minutes": 900,
        "minimum_role_peers": 30,
        "minimum_peer_teams": 5,
        "maximum_reference_age_days": 30,
        "maximum_availability_age_days": 7,
        "minimum_available_squad": 11,
        "top_per_role": {"GK": 1, "DF": 2, "MF": 2, "FW": 2},
        "role_weights": "equal_quarters",
        "ridge_lambda": 20,
        "uncertainty": "input_interval_sensitivity_not_confidence_interval",
    },
    "clutch": {
        "window_days": 4383,
        "minimum_pressure": 6,
        "minimum_control": 6,
        "minimum_pressure_editions": 2,
        "maximum_pressure_age_days": 1461,
        "shrinkage_pseudocount": 12,
        "pressure": ["round_of_16", "quarterfinal", "semifinal", "final"],
        "control": "group",
        "minutes": 90,
        "uncertainty": "approximate_independent_residual_interval_not_calibrated",
    },
    "cutoff_policy": "All observations through previous calendar day; no evaluated-match inputs",
    "star_formula": "Mean of four role means of top 1 GK / 2 DF / 2 MF / 2 FW midrank percentiles",
    "rapm_formula": (
        "min sum(minutes/90 * (90*goal_difference/minutes - intercepts - X*beta)^2) "
        "+ 20*sum(beta^2)"
    ),
    "rapm_segments": (
        "Prior 730 days; regulation 11v11 only; home and competition intercepts; "
        "no fitted model provided"
    ),
    "clutch_formula": (
        "clip(50+50*(neff/(neff+12))*(mean_pressure_residual-mean_group_residual),0,100)"
    ),
    "clutch_residual": (
        "win=1/draw=0.5/loss=0 minus (pregame_p_win+0.5*pregame_p_draw); neff=1/(1/nP+1/nC)"
    ),
    "clutch_context": (
        "Verified published pre-match context; no third place, shootouts or extra-time goals"
    ),
    "status": "unvalidated_research_not_production_eligible",
}


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Source(Contract):
    url: Annotated[str, Field(pattern=r"^https://\S+$")]
    publisher: Text
    revision: Text
    sha256: SHA
    retrieved_on: date
    rights_basis: Text
    published_on: date | None
    publication_verified: bool

    @model_validator(mode="after")
    def timing(self) -> Self:
        if (self.publication_verified and self.published_on is None) or (
            self.published_on is not None and self.published_on > self.retrieved_on
        ):
            raise ValueError("Invalid source publication provenance")
        return self


class Player(Contract):
    player_id: Text
    team: Text
    role: Role
    available: bool


class Roster(Contract):
    team: Text
    announced_on: date
    availability_checked_on: date
    source: Source
    availability_source: Source
    players: tuple[Player, ...]

    @model_validator(mode="after")
    def identities(self) -> Self:
        if len({p.player_id for p in self.players}) != len(self.players):
            raise ValueError("Duplicate roster identity")
        if any(p.team != self.team for p in self.players):
            raise ValueError("Roster team identity mismatch")
        return self


class Impact(Contract):
    player_id: Text
    team: Text
    role: Role
    minutes: Annotated[int, Field(ge=0)]
    value: Number
    lower: Number
    upper: Number
    source: Source

    @model_validator(mode="after")
    def interval(self) -> Self:
        if not self.lower <= self.value <= self.upper:
            raise ValueError("Player impact must lie inside its uncertainty interval")
        return self


class Reference(Contract):
    metric_version: Literal["player-segment-ridge-goal-difference-v1"]
    window_start: date
    through: date
    trained_through: date
    training_hash: SHA
    source: Source
    impacts: tuple[Impact, ...]

    @model_validator(mode="after")
    def integrity(self) -> Self:
        if self.window_start != self.through - timedelta(days=730):
            raise ValueError("Incompatible player observation window")
        if self.trained_through > self.through:
            raise ValueError("Player model training leakage")
        if len({p.player_id for p in self.impacts}) != len(self.impacts):
            raise ValueError("Duplicate reference player")
        return self


class Forecast(Contract):
    match_key: SHA
    team: Text
    cutoff: date
    trained_through: date
    training_hash: SHA
    model_version: Text
    feature_set: Literal["offense_defense_form_rank_only"]
    horizon_minutes: Literal[90]
    win: Probability
    draw: Probability
    loss: Probability
    source: Source

    @model_validator(mode="after")
    def validity(self) -> Self:
        if abs(self.win + self.draw + self.loss - 1) > 1e-12:
            raise ValueError("Forecast probabilities must sum to one")
        if self.trained_through > self.cutoff:
            raise ValueError("Forecast model training leakage")
        return self


class Observation(Contract):
    match_key: SHA
    day: date
    edition: Literal[1991, 1995, 1999, 2003, 2007, 2011, 2015, 2019, 2023]
    team: Text
    opponent: Text
    stage: Literal["group", "round_of_16", "quarterfinal", "semifinal", "final"]
    context_known_on: date | None
    context_source: Source | None = None
    regulation_minutes: Literal[90]
    goals_for: Annotated[int, Field(ge=0)]
    goals_against: Annotated[int, Field(ge=0)]
    source: Source
    forecast: Forecast | None = None

    @model_validator(mode="after")
    def validity(self) -> Self:
        if self.day.year != self.edition:
            raise ValueError("Observation edition/date mismatch")
        if self.team == self.opponent or (
            self.context_known_on is not None and self.context_known_on >= self.day
        ):
            raise ValueError("Invalid team identity or ex-post pressure classification")
        if self.forecast is not None and (
            self.forecast.match_key != self.match_key
            or self.forecast.team != self.team
            or self.forecast.cutoff >= self.day
        ):
            raise ValueError("Forecast identity or historical cutoff mismatch")
        return self


def result(
    version: str,
    used: dict[str, Any],
    reasons: list[str],
    counts: dict[str, int],
    value: float | None = None,
    bounds: tuple[float, float] | None = None,
) -> dict[str, Any]:
    return {
        "version": version,
        "method_hash": digest(SPEC),
        "evidence_hash": digest(used),
        "kind": "missing_evidence" if value is None else "derived_model_estimate",
        "value": value,
        "bounds": list(bounds) if bounds is not None else None,
        "uncertainty": SPEC["star" if version == STAR_VERSION else "clutch"]["uncertainty"],
        "counts": counts,
        "reasons": reasons,
        "production_eligible": False,
        "historical_publication_availability": "not_established_for_complete_input_chain",
    }


def percentile(value: float, peers: list[float]) -> float:
    return 100 * (sum(p < value for p in peers) + 0.5 * sum(p == value for p in peers)) / len(peers)


def star_power(
    team: str, cutoff: date, roster: Roster | None, reference: Reference | None
) -> dict[str, Any]:
    used: dict[str, Any] = {"team": team, "cutoff": cutoff.isoformat()}
    if roster is None or reference is None:
        return result(
            STAR_VERSION, used, ["missing_roster_availability_or_player_impact_reference"], {}
        )
    if roster.team != team:
        raise ValueError("Requested roster team mismatch")
    used.update(roster=roster.model_dump(mode="json"), reference=reference.model_dump(mode="json"))
    if (
        reference.through > cutoff
        or roster.announced_on > cutoff
        or roster.availability_checked_on > cutoff
    ):
        raise ValueError("Future roster or reference population")
    for source, event in (
        (roster.source, roster.announced_on),
        (roster.availability_source, roster.availability_checked_on),
    ):
        if (
            not source.publication_verified
            or source.published_on is None
            or not event <= source.published_on <= cutoff
        ):
            return result(
                STAR_VERSION, used, ["pre_match_roster_or_availability_publication_unverified"], {}
            )
    if (cutoff - reference.through).days > 30 or (cutoff - roster.availability_checked_on).days > 7:
        return result(STAR_VERSION, used, ["stale_reference_or_availability"], {})
    players = [p for p in roster.players if p.available]
    counts = {"available_players": len(players)}
    if len(players) < 11:
        return result(STAR_VERSION, used, ["insufficient_available_squad"], counts)
    lookup = {p.player_id: p for p in reference.impacts}
    for player in players:
        impact = lookup.get(player.player_id)
        if impact is None or impact.minutes < 900:
            return result(STAR_VERSION, used, ["missing_or_insufficient_player_minutes"], counts)
        if (impact.team, impact.role) != (player.team, player.role):
            raise ValueError("Player identity/team/role reconciliation required")
    role_scores: list[list[float]] = [[], [], []]
    for role, top in (("GK", 1), ("DF", 2), ("MF", 2), ("FW", 2)):
        peers = [p for p in reference.impacts if p.role == role and p.minutes >= 900]
        selected = [lookup[p.player_id] for p in players if p.role == role]
        if len(peers) < 30 or len({p.team for p in peers}) < 5 or len(selected) < top:
            return result(STAR_VERSION, used, ["insufficient_position_reference_or_roster"], counts)
        for index, (field, peer_field) in enumerate(
            (("value", "value"), ("lower", "upper"), ("upper", "lower"))
        ):
            scores = sorted(
                (
                    percentile(getattr(p, field), [getattr(q, peer_field) for q in peers])
                    for p in selected
                ),
                reverse=True,
            )
            role_scores[index].append(mean(scores[:top]))
    value, low, high = [round(mean(scores), 6) for scores in role_scores]
    return result(STAR_VERSION, used, [], counts, value, (low, high))


def clutch(team: str, cutoff: date, observations: tuple[Observation, ...]) -> dict[str, Any]:
    keys = [(o.match_key, o.team) for o in observations]
    fixtures = [(o.day, o.team, o.opponent) for o in observations]
    if len(fixtures) != len(set(fixtures)):
        raise ValueError("Duplicate fixture under different keys")
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate pressure/control observation")
    selected = sorted(
        (
            o
            for o in observations
            if o.team == team and cutoff - timedelta(days=4383) < o.day <= cutoff
        ),
        key=lambda o: (o.day, o.match_key),
    )
    pressure = [o for o in selected if o.stage != "group"]
    controls = [o for o in selected if o.stage == "group"]
    editions = len({o.edition for o in pressure})
    counts = {
        "pressure": len(pressure),
        "controls": len(controls),
        "pressure_editions": editions,
        "missing_baseline_forecasts": sum(o.forecast is None for o in selected),
        "missing_context_evidence": sum(
            o.context_known_on is None
            or o.context_source is None
            or not o.context_source.publication_verified
            or o.context_source.published_on is None
            or o.context_source.published_on >= o.day
            for o in selected
        ),
    }
    used = {
        "team": team,
        "cutoff": cutoff.isoformat(),
        "observations": [o.model_dump(mode="json") for o in selected],
    }
    reasons = []
    if len(pressure) < 6 or len(controls) < 6 or editions < 2:
        reasons.append("insufficient_pressure_control_or_edition_sample")
    if not pressure or (cutoff - pressure[-1].day).days > 1461:
        reasons.append("no_recent_pressure_observation")
    if counts["missing_baseline_forecasts"]:
        reasons.append("missing_independent_pregame_90_minute_baseline")
    if counts["missing_context_evidence"]:
        reasons.append("missing_verified_pre_match_pressure_context")
    if len({o.forecast.model_version for o in selected if o.forecast is not None}) > 1:
        raise ValueError("Incompatible baseline model versions")
    if reasons:
        return result(CLUTCH_VERSION, used, reasons, counts)
    residuals: list[list[float]] = [[], []]
    for group, rows in zip(residuals, (pressure, controls), strict=True):
        for row in rows:
            assert row.forecast is not None
            outcome = (
                1.0
                if row.goals_for > row.goals_against
                else 0.5
                if row.goals_for == row.goals_against
                else 0.0
            )
            group.append(outcome - row.forecast.win - 0.5 * row.forecast.draw)
    p, c = residuals
    effective_n = 1 / (1 / len(p) + 1 / len(c))
    shrink = effective_n / (effective_n + 12)
    delta = mean(p) - mean(c)
    se = math.sqrt(variance(p) / len(p) + variance(c) / len(c))

    def scale(x: float) -> float:
        return round(max(0.0, min(100.0, 50 + 50 * shrink * x)), 6)

    return result(
        CLUTCH_VERSION,
        used,
        [],
        counts,
        scale(delta),
        (scale(delta - 1.96 * se), scale(delta + 1.96 * se)),
    )
