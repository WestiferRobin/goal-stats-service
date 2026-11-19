"""Opt-in pregame 90-minute research models; no production engine imports."""

import math
from dataclasses import dataclass
from datetime import date
from typing import Any

from football.evaluation import probabilities
from research.special_ratings import digest

A = "odf-reweighted-poisson-research-v1"
B = "odf-cross-goal-rate-research-v1"
C = "odf-temperature-research-v1"
FREQUENCY = "prior-wwc-class-frequency-research-v1"
POISSON = "prior-wwc-poisson-research-v1"
SPEC: dict[str, Any] = {
    "protocol": "odf-chronological-retrospective-v1",
    "primary_model": B,
    "models": {
        A: "s=max(1,(.30*O+.25*D+.20*F)/.75); lambda_i=2.6*s_i/(s_h+s_a)",
        B: "lambda_i=1.3*exp(log(2)*(O_i-D_j)/100+log(1.5)*(F_i-F_j)/100)",
        C: "p_i=normalize(p_B_i**(1/T)); T selected only on 2007 calibration log loss",
        FREQUENCY: "(prior_class_count+1)/(prior_90_minute_WWC_matches+3)",
        POISSON: "Independent Poisson with shared mean=sum(prior_regulation_goals)/(2*n)",
    },
    "minutes": 90,
    "ranking_used_by_three_input": False,
    "development_editions": [1995, 1999, 2003],
    "calibration_editions": [2007],
    "validation_editions": [2011, 2015],
    "retrospective_holdout_editions": [2019, 2023],
    "excluded_horizon_editions": [1991],
    "temperature_grid": [0.75, 1.0, 1.25],
    "temperature_tie_break": "grid order",
    "minimum_calibration_cases": 20,
    "minimum_baseline_training_cases": 20,
    "baseline_window": (
        "Reviewed 90-minute development editions <=2003, strictly earlier than prediction; "
        "baseline parameters frozen after 2003"
    ),
    "rating_window": "Existing unchanged 1461-day model and 365-day Form reconstruction",
    "cutoff": "Previous calendar day; retain full reference populations",
    "selection": (
        "B primary by cross-opponent mathematical design before metrics; "
        "no outcome-based A/B selection"
    ),
    "metrics": ["log_loss", "brier_score", "accuracy"],
    "brier_range": [0, 2],
    "calibration_bins": 5,
    "bootstrap_replicates": 1000,
    "bootstrap_seed": 20261116,
    "uncertainty": (
        "Edition-block bootstrap when >=2 editions; within-edition bootstrap "
        "otherwise; descriptive percentile 95% intervals"
    ),
    "historical_publication_verified": False,
    "holdout_status": (
        "Retrospective; all registry outcomes previously exposed; not untouched or prospective"
    ),
    "missing_policy": "Exclude; no imputation; 1991 excluded regardless of rating availability",
    "five_input_status": (
        "Five-input historical comparison not yet supported by available evidence."
    ),
}


@dataclass(frozen=True)
class Ratings:
    offense: float
    defense: float
    form: float

    def __post_init__(self) -> None:
        for value in (self.offense, self.defense, self.form):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 <= value <= 100
            ):
                raise ValueError("Three finite ratings in [0,100] are required")


def poisson(home: float, away: float) -> tuple[float, float, float]:
    def marginal(rate: float) -> list[float]:
        if isinstance(rate, bool) or not math.isfinite(rate) or not 0 <= rate <= 20:
            raise ValueError("Research Poisson mean must be in [0,20]")
        values = [math.exp(-rate)]
        while True:
            k = len(values)
            nxt = values[-1] * rate / k
            ratio = rate / (k + 1)
            if ratio < 1 and nxt / (1 - ratio) <= 2.5e-13:
                return values
            values.append(nxt)

    h, a = marginal(home), marginal(away)
    result = [0.0, 0.0, 0.0]
    for i, x in enumerate(h):
        for j, y in enumerate(a):
            result[0 if i > j else 1 if i == j else 2] += x * y
    if home == away:
        result[0] = result[2] = (result[0] + result[2]) / 2
    total = math.fsum(result)
    return probabilities([x / total for x in result])


def predict(
    home: Ratings, away: Ratings, model: str = B, *, minutes: int = 90, temperature: float = 1.0
) -> tuple[float, float, float]:
    if not isinstance(home, Ratings) or not isinstance(away, Ratings):
        raise ValueError("Both complete historical rating triples are required")
    if model != C and temperature != 1.0:
        raise ValueError("Only the calibrated model accepts a temperature")
    if type(minutes) is not int or minutes != 90:
        raise ValueError("Only 90-minute pregame regulation is supported")
    if model == A:

        def strength(r: Ratings) -> float:
            return max(1.0, (0.30 * r.offense + 0.25 * r.defense + 0.20 * r.form) / 0.75)

        h, a = strength(home), strength(away)
        return poisson(2.6 * h / (h + a), 2.6 * a / (h + a))
    if model not in (B, C):
        raise ValueError("Unknown isolated research model version")

    def rate(x: Ratings, y: Ratings) -> float:
        return 1.3 * math.exp(
            math.log(2) * (x.offense - y.defense) / 100 + math.log(1.5) * (x.form - y.form) / 100
        )

    p = poisson(rate(home, away), rate(away, home))
    if model == B:
        return p
    if (
        isinstance(temperature, bool)
        or not math.isfinite(temperature)
        or temperature not in SPEC["temperature_grid"]
    ):
        raise ValueError("Temperature must belong to the frozen calibration grid")
    values = [x ** (1 / temperature) for x in p]
    return probabilities([x / math.fsum(values) for x in values])


def period(edition: int) -> str:
    for name in (
        "development",
        "calibration",
        "validation",
        "retrospective_holdout",
        "excluded_horizon",
    ):
        if edition in SPEC[name + "_editions"]:
            return name
    raise ValueError("Edition outside the frozen protocol")


def calibrate(cases: list[dict[str, Any]], prediction_day: date) -> dict[str, Any]:
    if not cases or any(
        c["edition"] != 2007 or date.fromisoformat(c["date"]) >= prediction_day for c in cases
    ):
        raise ValueError("Calibration must use only 2007 cases strictly before prediction")
    if any(type(c["truth"]) is not int or c["truth"] not in range(3) for c in cases):
        raise ValueError("Invalid calibration outcome")
    if len({c["match_key"] for c in cases}) != len(cases):
        raise ValueError("Duplicate calibration cases")
    if len(cases) < 20:
        raise ValueError("Insufficient calibration observations")
    scores = []
    for temperature in SPEC["temperature_grid"]:
        losses = []
        for case in cases:
            p = probabilities(case["predictions"][B])
            q = [v ** (1 / temperature) for v in p]
            losses.append(-math.log(max(1e-15, q[case["truth"]] / math.fsum(q))))
        scores.append(math.fsum(losses) / len(losses))
    index = min(range(len(scores)), key=lambda i: scores[i])
    return {
        "temperature": SPEC["temperature_grid"][index],
        "calibration_losses": scores,
        "calibration_cases": len(cases),
        "calibration_hash": digest(cases),
        "through": max(c["date"] for c in cases),
        "parameter_version": "odf-temperature-2007-v1",
    }
