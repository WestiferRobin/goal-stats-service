# mypy: ignore-errors
"""Original historical mapper; final scores never enter predictions."""


def _row_int(row, field_name, default=0):
    """
    Safely converts a CSV row value to an integer.
    """
    value = row.get(field_name, default)
    if value is None:
        return default
    value_text = str(value).strip()
    if value_text == "":
        return default
    try:
        return int(float(value_text))
    except (TypeError, ValueError):
        return default


def _row_bool(row, field_name, default=False):
    """
    Safely converts common CSV Boolean values.
    """
    value = row.get(field_name)
    if value is None:
        return default
    value_text = str(value).strip().lower()
    if value_text == "":
        return default
    return value_text in {"true", "1", "yes", "y"}


def _row_text(row, field_name, default=""):
    """
    Safely reads a text value from a CSV row.
    """
    value = row.get(field_name, default)
    if value is None:
        return default
    return str(value).strip()


def apply_historical_row_to_match(match, row):
    """
    Applies one historical snapshot row to a Match object.

    Returns:
        "historical"

    IMPORTANT:
    Snapshot goals are intentionally separate from final-result goals so the
    backtest does not accidentally leak the completed match result into the
    prediction.
    """
    match.match_minute = max(0, min(_row_int(row, "snapshot_minute", default=0), 120))
    match.match_extra_minute = max(0, _row_int(row, "snapshot_extra_minute", default=0))
    match.match_status_short = _row_text(row, "match_status_short", default="").upper()
    match.match_status_long = _row_text(row, "match_status_long", default="")
    match.team1.goals = _row_int(row, "snapshot_team1_goals", default=0)
    match.team2.goals = _row_int(row, "snapshot_team2_goals", default=0)
    team1_possession = _row_int(row, "team1_possession", default=50)
    team2_possession_value = row.get("team2_possession")
    if team2_possession_value is None or str(team2_possession_value).strip() == "":
        team2_possession = 100 - team1_possession
    else:
        team2_possession = _row_int(row, "team2_possession", default=50)
    match.team1.possession = max(0, min(team1_possession, 100))
    match.team2.possession = max(0, min(team2_possession, 100))
    match.team1.shots = _row_int(row, "team1_total_shots")
    match.team2.shots = _row_int(row, "team2_total_shots")
    match.team1.shots_on_target = _row_int(row, "team1_shots_on_target")
    match.team2.shots_on_target = _row_int(row, "team2_shots_on_target")
    match.team1.shots = max(match.team1.shots, match.team1.shots_on_target)
    match.team2.shots = max(match.team2.shots, match.team2.shots_on_target)
    match.team1.big_chances = _row_int(row, "team1_big_chances")
    match.team2.big_chances = _row_int(row, "team2_big_chances")
    match.team1.defender_blocks = _row_int(row, "team1_defender_blocks")
    match.team2.defender_blocks = _row_int(row, "team2_defender_blocks")
    match.team1.corners = _row_int(row, "team1_corners")
    match.team2.corners = _row_int(row, "team2_corners")
    match.team1.goalkeeper_saves = _row_int(row, "team1_goalkeeper_saves")
    match.team2.goalkeeper_saves = _row_int(row, "team2_goalkeeper_saves")
    match.team1.yellow_cards = _row_int(row, "team1_yellow_cards")
    match.team2.yellow_cards = _row_int(row, "team2_yellow_cards")
    match.team1.red_cards = _row_int(row, "team1_red_cards")
    match.team2.red_cards = _row_int(row, "team2_red_cards")
    if _row_bool(row, "team1_bad_star"):
        match.team1.add_modifier(
            "Star player is not playing well (historical snapshot)",
            match.team1.star_bad_game_penalty(),
        )
    if _row_bool(row, "team2_bad_star"):
        match.team2.add_modifier(
            "Star player is not playing well (historical snapshot)",
            match.team2.star_bad_game_penalty(),
        )
    return "historical"
