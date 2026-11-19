"""Pure three-class metrics. Order: home win, draw, away win; Brier range [0, 2]."""

import math
from collections.abc import Sequence
from typing import Literal

Outcome = Literal["home_win", "draw", "away_win"]
CLASSES: tuple[Outcome, Outcome, Outcome] = ("home_win", "draw", "away_win")
LOG_EPSILON = 1e-15


def probabilities(values: Sequence[float]) -> tuple[float, float, float]:
    if len(values) != 3 or any(
        not isinstance(p, (int, float))
        or isinstance(p, bool)
        or not math.isfinite(p)
        or not 0 <= p <= 1
        for p in values
    ):
        raise ValueError("Expected three finite probabilities in [0, 1]")
    total = math.fsum(values)
    if abs(total - 1) > 1e-9:
        raise ValueError("Probability sum must equal one within 1e-9")
    return values[0] / total, values[1] / total, values[2] / total


def outcome(home: int, away: int) -> Outcome:
    if any(type(n) is not int or n < 0 for n in (home, away)):
        raise ValueError("Regulation scores must be nonnegative integers")
    return CLASSES[0 if home > away else 1 if home == away else 2]


def metrics(cases: Sequence[tuple[Sequence[float], str]]) -> dict[str, object]:
    confusion = [[0] * 3 for _ in CLASSES]
    losses, briers = [], []
    correct = 0
    for raw, actual in cases:
        if actual not in CLASSES:
            raise ValueError("An observed three-class outcome is required")
        p = probabilities(raw)
        truth = CLASSES.index(actual)
        predicted = max(range(3), key=lambda i: p[i])  # First class wins exact ties.
        confusion[truth][predicted] += 1
        correct += truth == predicted
        losses.append(-math.log(max(LOG_EPSILON, p[truth])))
        briers.append(math.fsum((p[i] - int(i == truth)) ** 2 for i in range(3)))
    count = len(cases)
    return {
        "accuracy": correct / count if count else None,
        "log_loss": math.fsum(losses) / count if count else None,
        "brier_score": math.fsum(briers) / count if count else None,
        "confusion_matrix": confusion if count else None,
    }
