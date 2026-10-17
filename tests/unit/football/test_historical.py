from football.engine import Match, Team
from football.historical import apply_historical_row_to_match
from football.report import report
from tests.fixtures.calculations import REFERENCE_TEAMS


def test_final_result_does_not_leak_into_snapshot_prediction():
    ratings = {row["name"]: row for row in REFERENCE_TEAMS}
    row = {
        "team1": "Reference 1",
        "team2": "Reference 2",
        "snapshot_minute": "65",
        "snapshot_team1_goals": "1",
    }

    def predict():
        match = Match(Team(**ratings[row["team1"]]), Team(**ratings[row["team2"]]))
        apply_historical_row_to_match(match, row)
        return report(match)

    before = predict()
    row.update(final_team1_goals="99", final_team2_goals="0", actual_winner=row["team2"])
    assert predict() == before


def test_historical_snapshot_parsing_defaults_bounds_and_star_modifiers():
    """Bad/missing CSV values use defaults; completed scores remain outside snapshot state."""
    match = Match(Team("Alpha", 70, 70, 70, 80, 70), Team("Beta", 70, 70, 70, 60, 70))
    row = {
        "snapshot_minute": "999",
        "snapshot_extra_minute": "-4",
        "match_status_short": " ht ",
        "match_status_long": None,
        "snapshot_team1_goals": " 2.9 ",
        "snapshot_team2_goals": "bad",
        "team1_possession": "120",
        "team2_possession": "-5",
        "team1_total_shots": None,
        "team1_shots_on_target": "4",
        "team2_total_shots": "",
        "team2_shots_on_target": "3",
        "team1_bad_star": "YES",
        "team2_bad_star": "1",
        "final_team1_goals": "99",
    }
    assert apply_historical_row_to_match(match, row) == "historical"
    assert (match.match_minute, match.match_extra_minute) == (120, 0)
    assert (match.match_status_short, match.match_status_long) == ("HT", "")
    assert (match.team1.goals, match.team2.goals) == (2, 0)
    assert (match.team1.possession, match.team2.possession) == (100, 0)
    assert (match.team1.shots, match.team2.shots) == (4, 3)
    assert match.team1.modifiers == [("Star player is not playing well (historical snapshot)", -8)]
    assert match.team2.modifiers == [("Star player is not playing well (historical snapshot)", -6)]
    row.update(
        team1_bad_star=None, team2_bad_star=" ", team2_possession=None, team1_possession="60"
    )
    reset = Match(Team("Alpha", 70, 70, 70, 80, 70), Team("Beta", 70, 70, 70, 60, 70))
    apply_historical_row_to_match(reset, row)
    assert reset.team2.possession == 40
    assert reset.team1.modifiers == reset.team2.modifiers == []
