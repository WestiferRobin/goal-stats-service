import pytest

from football.engine import Match, Team, simulate_tournament
from tests.fixtures.calculations import REFERENCE_TEAMS


def test_tournament_stages_count_each_team_once():
    teams = REFERENCE_TEAMS
    results, _, _, _ = simulate_tournament([Team(**team) for team in teams[:4]], 1000)
    assert all(row["semifinal_probability"] == 100 for row in results)
    assert sum(row["final_probability"] for row in results) == pytest.approx(200, abs=0.03)
    assert sum(row["champion_probability"] for row in results) == pytest.approx(100, abs=0.03)


def test_prediction_matches_original_road_to_the_final_reference():
    # Independently evaluated from source app.py at 8f17bc42e30f436f5cd860f2791695421160ccd2.
    teams = REFERENCE_TEAMS
    match = Match(Team(**teams[0]), Team(**teams[1]))
    assert match.calculate_probabilities()[:3] == pytest.approx(
        (0.37074041064032975, 0.26390886112362144, 0.36535072823604886)
    )
    match.match_minute = 65
    match.team1.goals = 1
    match.team1.shots_on_target = 4
    match.team1.possession = 60
    match.team2.possession = 40
    assert match.calculate_probabilities()[:3] == pytest.approx(
        (0.8136391843803665, 0.15959690743009677, 0.026763908189536657)
    )


@pytest.fixture
def balanced_match():
    return Match(Team("Alpha", 70, 70, 70, 70, 70), Team("Beta", 70, 70, 70, 70, 70))


@pytest.mark.parametrize("possession,expected", [(44, -3), (45, 0), (55, 0), (56, 3)])
def test_possession_boundaries_and_standalone_live_score(balanced_match, possession, expected):
    """The possession band is inclusive; the optional-opponent score adds no attack pressure."""
    team = balanced_match.team1
    team.possession = possession
    assert team.possession_score() == expected
    assert team.live_score() == 70 + expected
    assert team.event_score_breakdown() == (0, 0, False)


@pytest.mark.parametrize(
    "minute,clamped,ratio", [(-10, 0, 1), (45, 45, 0.5), (90, 90, 0.03), (200, 120, 0.03)]
)
def test_remaining_time_clamps_regulation_and_extra_time(balanced_match, minute, clamped, ratio):
    """Clamp negative minutes and retain the residual floor in finished/extra-time matches."""
    match = Match(balanced_match.team1, balanced_match.team2, minute)
    assert match.match_minute == clamped
    assert match.remaining_time_ratio() == ratio


@pytest.mark.parametrize(
    "probabilities,expected",
    [
        ((0.34, 0.33, 0.33), (5, "Extremely Even Match")),
        ((0.38, 0.32, 0.30), (4, "Very Competitive Match")),
        ((0.42, 0.30, 0.28), (3, "Competitive Match")),
        ((0.50, 0.30, 0.20), (2, "Clear Favorite")),
        ((0.70, 0.20, 0.10), (1, "Heavy Favorite")),
    ],
)
def test_difficulty_uses_leading_probability_margin(balanced_match, probabilities, expected):
    """Difficulty labels follow the difference between the two leading outcomes."""
    assert balanced_match.match_difficulty(probabilities) == expected


@pytest.mark.parametrize(
    "probabilities,expected",
    [
        ((0.6, 0.3, 0.1), (37.5, "Low", "confidence-low")),
        ((0.7, 0.2, 0.1), (62.5, "Medium", "confidence-medium")),
        ((1, 0, 0), (100, "High", "confidence-high")),
    ],
)
def test_confidence_labels_and_ceiling(balanced_match, probabilities, expected):
    """Confidence remains bounded and exposes the corresponding presentation label."""
    score, label, css = balanced_match.prediction_confidence(probabilities)
    assert score == pytest.approx(expected[0])
    assert (label, css) == expected[1:]


@pytest.mark.parametrize(
    "probabilities,expected",
    [
        ((0.4, 0.4, 0.2), ("Alpha Win", 0.4)),
        ((0.1, 0.7, 0.2), ("Draw", 0.7)),
        ((0.1, 0.2, 0.7), ("Beta Win", 0.7)),
    ],
)
def test_outcome_selection_and_stable_ties(balanced_match, probabilities, expected):
    """Select the leading outcome and preserve stable ordering for an exact tie."""
    assert balanced_match.predicted_outcome(probabilities) == expected


@pytest.mark.parametrize(
    "probabilities,expected", [((0.2, 0.6, 0.2), (0.5, 0.5)), ((0, 0, 0), (0, 0))]
)
def test_advancement_without_clutch_or_probability_mass(balanced_match, probabilities, expected):
    """Equal zero clutch splits a draw; zero probability mass is not divided by zero."""
    balanced_match.team1.clutch = balanced_match.team2.clutch = 0
    assert balanced_match.advancement_probabilities(probabilities) == pytest.approx(expected)


@pytest.mark.parametrize("side", [1, 2])
def test_reasoning_attributes_live_events_to_each_side(balanced_match, side):
    """Reasons name the team with each advantage and distinguish red-card harm and modifier caps."""
    team = getattr(balanced_match, f"team{side}")
    team.goals = 2
    team.red_cards = 1
    team.shots_on_target = 6
    team.big_chances = 10
    team.goalkeeper_saves = 1
    team.add_modifier("Support", 50)
    balanced_match.match_minute = 65
    reasons = balanced_match.reasoning_summary()
    for message in [
        "currently has more goals.",
        "has more red cards, which hurts its chances.",
        "has more shots on target.",
        "has created more big chances.",
        "has the higher attack pressure score.",
        "currently has more live momentum.",
        "has more calculated dangerous attacks.",
    ]:
        assert f"{team.name} {message}" in reasons
    assert f"{team.name}'s goalkeeper has made more saves." in reasons
    assert f"{team.name}: Support." in reasons
    assert f"{team.name}: stacked modifiers totaled +50.0, but were capped at +20.0." in reasons
    assert "The model is calculating remaining goals from minute 65." in reasons


@pytest.mark.parametrize(
    "scores,draw,expected",
    [((2, 0), 0.5, 1), ((0, 2), 0.5, 2), ((1, 1), 0.0, 1), ((1, 1), 0.99, 2)],
)
def test_knockout_score_winners_and_tiebreaks(monkeypatch, balanced_match, scores, draw, expected):
    """Controlled goal sampling exercises regulation wins and both weighted tiebreak outcomes."""
    from football import engine

    values = iter(scores)
    monkeypatch.setattr(engine, "_sample_poisson", lambda _: next(values))
    monkeypatch.setattr(engine.random, "random", lambda: draw)
    winner = engine._simulate_knockout_match(balanced_match.team1, balanced_match.team2)
    assert winner is getattr(balanced_match, f"team{expected}")
    assert balanced_match.team1.goals == balanced_match.team2.goals == 0


@pytest.mark.parametrize("size", [0, 1, 3, 8])
def test_tournament_empty_singleton_byes_and_semifinal_entry(monkeypatch, size):
    """Bracket counting handles byes and entry into semifinals without double counting stages."""
    from football import engine

    teams = [Team(str(i), 70, 70, 70, 70, 70) for i in range(size)]
    monkeypatch.setattr(engine, "_simulate_knockout_match", lambda first, second: first)
    results, champion, count, final = simulate_tournament(teams, 1)
    assert count == 1000
    assert champion == ("0" if size else None)
    assert sum(row["champion_probability"] for row in results) == (100 if size else 0)
    assert final == (
        None
        if size < 2
        else {"team1": "0", "team2": str(2 if size == 3 else 4), "probability": 100}
    )
    if size == 8:
        assert {r["team"] for r in results if r["semifinal_probability"] == 100} == {
            "0",
            "2",
            "4",
            "6",
        }
