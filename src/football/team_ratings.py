"""Deterministic experimental ratings of recorded international results, not per-90 xG.

The Poisson likelihood models final scores including extra time, excluding shootouts.
No player assumptions, FIFA ranks, scenario inputs or prediction-engine code are used.
"""

import csv
import hashlib
import io
import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

MODEL = "international-recorded-score-poisson-v1"
SOURCE_SHA = "de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0"
SOURCE_URL = "https://github.com/martj42/womens-international-results/blob/1855e313ae8bcd0330426e62c8e4cf15ce45077c/results.csv"


@dataclass(frozen=True)
class Result:
    day: date
    home: str
    away: str
    goals_home: int
    goals_away: int
    neutral: bool


def read_results(raw: bytes) -> list[Result]:
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError("International results checksum differs from the approved source")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    expected = (
        "date home_team away_team home_score away_score tournament city country neutral".split()
    )
    if reader.fieldnames != expected:
        raise ValueError("International results schema changed")
    rows = []
    identities = set()
    for row in reader:
        day = date.fromisoformat(row["date"])
        home, away = row["home_team"], row["away_team"]
        gh, ga = int(row["home_score"]), int(row["away_score"])
        if (
            not home
            or not away
            or home == away
            or min(gh, ga) < 0
            or row["neutral"] not in ("TRUE", "FALSE")
        ):
            raise ValueError("Invalid international result")
        key = day, home, away
        if key in identities:
            raise ValueError("Duplicate international match identity")
        identities.add(key)
        rows.append(Result(day, home, away, gh, ga, row["neutral"] == "TRUE"))
    return sorted(rows, key=lambda r: (r.day, r.home, r.away))


@dataclass
class Fit:
    attack: dict[str, float]
    concede: dict[str, float]
    intercept: float
    home: float
    iterations: int

    def means(self, row: Result) -> tuple[float, float]:
        return (
            math.exp(
                self.intercept
                + self.attack.get(row.home, 0)
                + self.concede.get(row.away, 0)
                + (0 if row.neutral else self.home)
            ),
            math.exp(self.intercept + self.attack.get(row.away, 0) + self.concede.get(row.home, 0)),
        )


def fit(rows: list[Result], cutoff: date) -> Fit:
    selected = [r for r in rows if cutoff - timedelta(days=1461) < r.day <= cutoff]
    if len(selected) < 20:
        raise ValueError("Too few matches to fit a reference population")
    names = sorted({name for r in selected for name in (r.home, r.away)})
    games = [(r, 2 ** (-(cutoff - r.day).days / 730)) for r in selected]
    mean = sum(w * (r.goals_home + r.goals_away) for r, w in games) / (2 * sum(w for _, w in games))
    model = Fit(
        dict.fromkeys(names, 0.0), dict.fromkeys(names, 0.0), math.log(max(mean, 0.01)), 0.0, 0
    )
    # Block Newton steps: each team coefficient is conditionally independent within
    # an attack/defense block. Fixed damping and L2=8 make sparse estimates shrink.
    for iteration in range(400):
        largest = 0.0
        for block in (model.attack, model.concede):
            gradient = {n: -8 * block[n] for n in names}
            curvature = dict.fromkeys(names, 8.0)
            for row, weight in games:
                mh, ma = model.means(row)
                n1, n2 = (row.home, row.away) if block is model.attack else (row.away, row.home)
                gradient[n1] += weight * (row.goals_home - mh)
                gradient[n2] += weight * (row.goals_away - ma)
                curvature[n1] += weight * mh
                curvature[n2] += weight * ma
            for name in names:
                change = max(-0.25, min(0.25, 0.5 * gradient[name] / curvature[name]))
                block[name] += change
                largest = max(largest, abs(change))
        g0 = ghome = 0.0
        h0 = hhome = 0.0
        for row, weight in games:
            mh, ma = model.means(row)
            g0 += weight * (row.goals_home + row.goals_away - mh - ma)
            h0 += weight * (mh + ma)
            if not row.neutral:
                ghome += weight * (row.goals_home - mh)
                hhome += weight * mh
        d0 = max(-0.25, min(0.25, 0.5 * g0 / h0))
        dh = max(-0.25, min(0.25, 0.5 * (ghome - 8 * model.home) / (hhome + 8)))
        model.intercept += d0
        model.home += dh
        model.iterations = iteration + 1
        if max(largest, abs(d0), abs(dh)) < 1e-7:
            break
    return model


def recent_form(rows: list[Result], cutoff: date) -> tuple[dict[str, float], dict[str, int]]:
    start = cutoff - timedelta(days=365)
    baseline = fit(rows, start)  # frozen before EVERY observation used for form
    totals: dict[str, float] = {}
    weights: dict[str, float] = {}
    counts: dict[str, int] = {}
    for row in rows:
        if (
            not start < row.day <= cutoff
            or row.home not in baseline.attack
            or row.away not in baseline.attack
        ):
            continue
        mh, ma = baseline.means(row)
        residual = (row.goals_home - row.goals_away - mh + ma) / math.sqrt(mh + ma)
        weight = 2 ** (-(cutoff - row.day).days / 180)
        for name, value in ((row.home, residual), (row.away, -residual)):
            totals[name] = totals.get(name, 0) + weight * value
            weights[name] = weights.get(name, 0) + weight
            counts[name] = counts.get(name, 0) + 1
    return {n: v / (5 + weights[n]) for n, v in totals.items()}, counts


def percentile(value: float, population: list[float]) -> float:
    return round(
        100
        * (sum(x < value for x in population) + 0.5 * sum(x == value for x in population))
        / len(population),
        2,
    )


def calculate(rows: list[Result], cutoff: date) -> dict[str, dict[str, Any]]:
    model = fit(rows, cutoff)
    form, form_counts = recent_form(rows, cutoff)
    counts: dict[str, int] = {}
    last: dict[str, date] = {}
    for row in rows:
        if cutoff - timedelta(days=1461) < row.day <= cutoff:
            for n in (row.home, row.away):
                counts[n] = counts.get(n, 0) + 1
                last[n] = max(last.get(n, row.day), row.day)
    eligible = [n for n in model.attack if counts[n] >= 8 and (cutoff - last[n]).days <= 730]
    forms = [form[n] for n in eligible if form_counts.get(n, 0) >= 3]
    attacks = [model.attack[n] for n in eligible]
    defenses = [-model.concede[n] for n in eligible]
    output = {}
    for n in model.attack:
        ok = n in eligible
        form_ok = ok and form_counts.get(n, 0) >= 3
        output[n] = {
            "offense": percentile(model.attack[n], attacks) if ok else None,
            "defense": percentile(-model.concede[n], defenses) if ok else None,
            "form": percentile(form[n], forms) if form_ok else None,
            "evidence": {
                "matches": counts[n],
                "form_matches": form_counts.get(n, 0),
                "last_match": last[n].isoformat(),
                "reference_teams": len(eligible),
                "reason": None if ok and form_ok else "insufficient_recent_results",
                "status": "experimental",
                "score_basis": "recorded_final_including_extra_time_no_shootout",
            },
        }
    return output


def validate_model(rows: list[Result], cutoff: date) -> dict[str, Any]:
    """Two disjoint chronological holdouts; hyperparameters are never fitted on them."""
    folds = []
    for end in (cutoff - timedelta(days=365), cutoff):
        start = end - timedelta(days=180)
        model = fit(rows, start)
        form, counts = recent_form(rows, start)
        training = [r for r in rows if start - timedelta(days=1461) < r.day <= start]
        base = sum(r.goals_home + r.goals_away for r in training) / (2 * len(training))
        losses = [0.0, 0.0, 0.0]
        tested = 0
        for row in rows:
            if (
                not start < row.day <= end
                or row.home not in model.attack
                or row.away not in model.attack
            ):
                continue
            mh, ma = model.means(row)
            delta = (
                (form.get(row.home, 0) - form.get(row.away, 0)) / 2
                if min(counts.get(row.home, 0), counts.get(row.away, 0)) >= 3
                else 0
            )
            pairs = ((base, base), (mh, ma), (mh * math.exp(delta), ma * math.exp(-delta)))
            for i, means in enumerate(pairs):
                losses[i] += sum(
                    mu - g * math.log(mu) + math.lgamma(g + 1)
                    for g, mu in zip((row.goals_home, row.goals_away), means, strict=True)
                )
            tested += 1
        if not tested:
            raise ValueError("No eligible held-out matches")
        folds.append(
            {
                "train_through": start.isoformat(),
                "test_through": end.isoformat(),
                "matches": tested,
                "baseline_nll": losses[0] / tested,
                "opponent_adjusted_nll": losses[1] / tested,
                "with_form_nll": losses[2] / tested,
            }
        )
    return {
        "model": MODEL,
        "status": "experimental_not_calibrated",
        "folds": folds,
        "parameters": {
            "window_days": 1461,
            "half_life_days": 730,
            "l2": 8,
            "form_days": 365,
            "form_half_life_days": 180,
            "form_shrinkage": 5,
        },
        "limitations": [
            "Recorded scores may include extra time; these are not per-90 ratings.",
            "No uncertainty intervals or proof of incremental form predictive value.",
            "Source completeness and opponent coverage vary; "
            "percentile scores are cohort-relative.",
        ],
    }
