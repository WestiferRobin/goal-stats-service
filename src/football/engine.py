# mypy: ignore-errors
"""RoadToTheFinal model port; formulas preserved, tournament stage counting corrected."""

import math
import random
from collections import Counter

STAR_BAD_GAME_FACTOR = 0.1
EVENT_SCORE_FLOOR = -20
EVENT_SCORE_CEILING = 20
FULL_MATCH_EXPECTED_GOALS = 2.6
DANGEROUS_ATTACK_WEIGHT = 0.5
SHOT_ON_TARGET_WEIGHT = 2.0
BIG_CHANCE_WEIGHT = 3.0
GOAL_PRESSURE_WEIGHT = 6.0
MOMENTUM_SHOT_WEIGHT = 0.5
MOMENTUM_SHOT_ON_TARGET_WEIGHT = 1.5
MOMENTUM_BIG_CHANCE_WEIGHT = 2.5
MOMENTUM_BLOCKED_SHOT_WEIGHT = 0.5
MOMENTUM_CORNER_WEIGHT = 0.4
MOMENTUM_GOAL_WEIGHT = 3.0
MOMENTUM_POSSESSION_WEIGHT = 0.05
MOMENTUM_RED_CARD_PENALTY = 3.0
MOMENTUM_MINIMUM_BASE = 1.0


class Team:
    def __init__(
        self,
        name,
        offense,
        defense,
        form,
        star_power,
        clutch,
        fifa_rank=None,
        fifa_points=None,
        ranking_date="",
    ):
        self.name = name
        self.offense = float(offense)
        self.defense = float(defense)
        self.form = float(form)
        self.star_power = float(star_power)
        self.clutch = float(clutch)
        self.fifa_rank = int(float(fifa_rank)) if fifa_rank not in (None, "") else None
        self.fifa_points = float(fifa_points) if fifa_points not in (None, "") else None
        self.ranking_date = str(ranking_date or "")
        self.goals = 0
        self.yellow_cards = 0
        self.red_cards = 0
        self.possession = 50
        self.shots = 0
        self.shots_on_target = 0
        self.big_chances = 0
        self.defender_blocks = 0
        self.corners = 0
        self.goalkeeper_saves = 0
        self.modifiers = []

    def base_score(self):
        """
        Creates the pregame team-strength score from teams.csv ratings.
        """
        weighted_rating = (
            self.offense * 0.3
            + self.defense * 0.25
            + self.form * 0.2
            + self.star_power * 0.15
            + self.clutch * 0.1
        )
        ranking_bonus = 0.0
        if self.fifa_rank is not None:
            ranking_bonus = max(-2.0, min(2.0, (25 - self.fifa_rank) * 0.08))
        return weighted_rating + ranking_bonus

    def add_modifier(self, reason, value):
        self.modifiers.append((reason, float(value)))

    def star_bad_game_penalty(self):
        """
        Applies a penalty equal to a percentage of this team's star-power
        rating instead of applying the same flat penalty to every team.
        """
        return -round(self.star_power * STAR_BAD_GAME_FACTOR, 1)

    def event_score_breakdown(self):
        """
        Returns:
        - Raw modifier total
        - Capped modifier total
        - Whether the value was capped
        """
        raw_total = sum((value for reason, value in self.modifiers))
        capped_total = max(EVENT_SCORE_FLOOR, min(raw_total, EVENT_SCORE_CEILING))
        return (raw_total, capped_total, raw_total != capped_total)

    def event_score(self):
        """
        Returns the capped sum of live event modifiers.

        Red cards are handled separately and are not included in this cap.
        """
        _, capped_total, _ = self.event_score_breakdown()
        return capped_total

    def possession_score(self):
        if self.possession > 55:
            return 3
        if self.possession < 45:
            return -3
        return 0

    def scoreline_score(self):
        return self.goals * 8

    def red_card_score(self):
        return self.red_cards * -12

    def calculated_dangerous_attacks(self, opponent):
        """
        Estimates dangerous attacking sequences from available objective
        events.

        The opponent's goalkeeper saves represent shots from this team that
        reached the opposing goalkeeper.
        """
        saved_by_opponent = opponent.goalkeeper_saves
        chance_events = self.big_chances + self.defender_blocks + saved_by_opponent
        return max(self.shots_on_target, chance_events)

    def attack_pressure_score(self, opponent):
        """
        Produces a transparent attack-pressure number.

        This is an absolute score, not a percentage. A larger number means
        the team has generated more threatening attacking activity.
        """
        dangerous_attacks = self.calculated_dangerous_attacks(opponent)
        return (
            dangerous_attacks * DANGEROUS_ATTACK_WEIGHT
            + self.shots_on_target * SHOT_ON_TARGET_WEIGHT
            + self.big_chances * BIG_CHANCE_WEIGHT
            + self.goals * GOAL_PRESSURE_WEIGHT
        )

    def live_score(self, opponent=None):
        """
        Combines pregame strength and current match conditions.

        This value is used to divide the remaining expected goals between the
        two teams.
        """
        score = (
            self.base_score()
            + self.event_score()
            + self.possession_score()
            + self.scoreline_score()
            + self.red_card_score()
        )
        if opponent is not None:
            score += self.attack_pressure_score(opponent)
        return score


class Match:
    def __init__(self, team1, team2, match_minute=0):
        self.team1 = team1
        self.team2 = team2
        self.match_minute = max(0, min(int(match_minute), 120))
        self.match_extra_minute = 0
        self.match_status_short = ""
        self.match_status_long = ""
        self.event_timeline = []

    @staticmethod
    def poisson_probability(goals, expected_goals):
        return math.exp(-expected_goals) * expected_goals**goals / math.factorial(goals)

    def remaining_time_ratio(self):
        if self.match_minute >= 90:
            return 0.03
        return max((90 - self.match_minute) / 90, 0.03)

    def team_momentum_score(self, team):
        """
        Creates one team's raw Live Momentum score.

        This calculation intentionally does not call
        attack_pressure_score(), preventing double-counting.
        """
        possession_above_even = max(team.possession - 50, 0)
        momentum_score = (
            team.shots * MOMENTUM_SHOT_WEIGHT
            + team.shots_on_target * MOMENTUM_SHOT_ON_TARGET_WEIGHT
            + team.big_chances * MOMENTUM_BIG_CHANCE_WEIGHT
            + team.defender_blocks * MOMENTUM_BLOCKED_SHOT_WEIGHT
            + team.corners * MOMENTUM_CORNER_WEIGHT
            + team.goals * MOMENTUM_GOAL_WEIGHT
            + possession_above_even * MOMENTUM_POSSESSION_WEIGHT
            - team.red_cards * MOMENTUM_RED_CARD_PENALTY
        )
        return max(momentum_score, MOMENTUM_MINIMUM_BASE)

    def live_momentum_percentages(self):
        """
        Converts both raw momentum scores into percentages totaling 100%.
        """
        team1_momentum_score = self.team_momentum_score(self.team1)
        team2_momentum_score = self.team_momentum_score(self.team2)
        total_momentum = team1_momentum_score + team2_momentum_score
        if total_momentum <= 0:
            return (50.0, 50.0)
        team1_momentum = team1_momentum_score / total_momentum * 100
        team2_momentum = team2_momentum_score / total_momentum * 100
        return (team1_momentum, team2_momentum)

    def expected_goals(self):
        """
        Estimates additional goals expected from the current match state.
        """
        team1_strength = max(self.team1.live_score(self.team2), 1.0)
        team2_strength = max(self.team2.live_score(self.team1), 1.0)
        total_strength = team1_strength + team2_strength
        remaining_ratio = self.remaining_time_ratio()
        remaining_expected_goals = FULL_MATCH_EXPECTED_GOALS * remaining_ratio
        team1_expected_goals = remaining_expected_goals * team1_strength / total_strength
        team2_expected_goals = remaining_expected_goals * team2_strength / total_strength
        team1_expected_goals -= self.team1.red_cards * 0.22 * remaining_ratio
        team2_expected_goals -= self.team2.red_cards * 0.22 * remaining_ratio
        team1_expected_goals += self.team2.red_cards * 0.18 * remaining_ratio
        team2_expected_goals += self.team1.red_cards * 0.18 * remaining_ratio
        team1_expected_goals = max(team1_expected_goals, 0.02)
        team2_expected_goals = max(team2_expected_goals, 0.02)
        return (team1_expected_goals, team2_expected_goals)

    def calculate_probabilities(self, max_additional_goals=10):
        team1_expected_goals, team2_expected_goals = self.expected_goals()
        team1_win_probability = 0.0
        draw_probability = 0.0
        team2_win_probability = 0.0
        scorelines = []
        for team1_extra_goals in range(max_additional_goals + 1):
            team1_goal_probability = self.poisson_probability(
                team1_extra_goals, team1_expected_goals
            )
            for team2_extra_goals in range(max_additional_goals + 1):
                team2_goal_probability = self.poisson_probability(
                    team2_extra_goals, team2_expected_goals
                )
                score_probability = team1_goal_probability * team2_goal_probability
                team1_final_score = self.team1.goals + team1_extra_goals
                team2_final_score = self.team2.goals + team2_extra_goals
                scorelines.append(
                    {
                        "team1_goals": team1_final_score,
                        "team2_goals": team2_final_score,
                        "probability": score_probability,
                    }
                )
                if team1_final_score > team2_final_score:
                    team1_win_probability += score_probability
                elif team1_final_score == team2_final_score:
                    draw_probability += score_probability
                else:
                    team2_win_probability += score_probability
        total_probability = team1_win_probability + draw_probability + team2_win_probability
        if total_probability <= 0:
            return (1 / 3, 1 / 3, 1 / 3, (self.team1.goals, self.team2.goals), [])
        team1_win_probability /= total_probability
        draw_probability /= total_probability
        team2_win_probability /= total_probability
        for scoreline in scorelines:
            scoreline["probability"] /= total_probability
        scorelines.sort(key=lambda item: item["probability"], reverse=True)
        top_scorelines = scorelines[:5]
        most_likely_score = (top_scorelines[0]["team1_goals"], top_scorelines[0]["team2_goals"])
        return (
            team1_win_probability,
            draw_probability,
            team2_win_probability,
            most_likely_score,
            top_scorelines,
        )

    def predicted_outcome(self, probabilities):
        team1_probability, draw_probability, team2_probability = probabilities
        outcomes = [
            (f"{self.team1.name} Win", team1_probability),
            ("Draw", draw_probability),
            (f"{self.team2.name} Win", team2_probability),
        ]
        return max(outcomes, key=lambda item: item[1])

    def prediction_confidence(self, probabilities):
        """
        Measures how far the leading outcome is ahead of the
        second-most likely outcome.

        Example:
        Spain 76%
        Draw 19%
        France 5%

        Probability margin:
        76% - 19% = 57%

        Confidence:
        57% x 1.25 = about 71%
        """
        ordered_probabilities = sorted(probabilities, reverse=True)
        highest_probability = ordered_probabilities[0]
        second_highest_probability = ordered_probabilities[1]
        probability_margin = highest_probability - second_highest_probability
        confidence_score = max(0, min(probability_margin * 125, 100))
        if confidence_score < 40:
            return (confidence_score, "Low", "confidence-low")
        if confidence_score < 70:
            return (confidence_score, "Medium", "confidence-medium")
        return (confidence_score, "High", "confidence-high")

    def match_difficulty(self, probabilities):
        ordered_probabilities = sorted(probabilities, reverse=True)
        margin = ordered_probabilities[0] - ordered_probabilities[1]
        if margin < 0.04:
            return (5, "Extremely Even Match")
        if margin < 0.09:
            return (4, "Very Competitive Match")
        if margin < 0.16:
            return (3, "Competitive Match")
        if margin < 0.25:
            return (2, "Clear Favorite")
        return (1, "Heavy Favorite")

    def advancement_probabilities(self, probabilities):
        team1_win_probability, draw_probability, team2_win_probability = probabilities
        clutch_total = self.team1.clutch + self.team2.clutch
        if clutch_total <= 0:
            team1_draw_share = 0.5
            team2_draw_share = 0.5
        else:
            team1_draw_share = self.team1.clutch / clutch_total
            team2_draw_share = self.team2.clutch / clutch_total
        team1_advance_probability = team1_win_probability + draw_probability * team1_draw_share
        team2_advance_probability = team2_win_probability + draw_probability * team2_draw_share
        total_probability = team1_advance_probability + team2_advance_probability
        if total_probability > 0:
            team1_advance_probability /= total_probability
            team2_advance_probability /= total_probability
        return (team1_advance_probability, team2_advance_probability)

    def reasoning_summary(self):
        reasons = []
        team1_pressure = self.team1.attack_pressure_score(self.team2)
        team2_pressure = self.team2.attack_pressure_score(self.team1)
        team1_dangerous = self.team1.calculated_dangerous_attacks(self.team2)
        team2_dangerous = self.team2.calculated_dangerous_attacks(self.team1)
        team1_momentum, team2_momentum = self.live_momentum_percentages()
        if self.team1.goals > self.team2.goals:
            reasons.append(f"{self.team1.name} currently has more goals.")
        elif self.team2.goals > self.team1.goals:
            reasons.append(f"{self.team2.name} currently has more goals.")
        if self.team1.red_cards > self.team2.red_cards:
            reasons.append(f"{self.team1.name} has more red cards, which hurts its chances.")
        elif self.team2.red_cards > self.team1.red_cards:
            reasons.append(f"{self.team2.name} has more red cards, which hurts its chances.")
        if self.team1.shots_on_target > self.team2.shots_on_target:
            reasons.append(f"{self.team1.name} has more shots on target.")
        elif self.team2.shots_on_target > self.team1.shots_on_target:
            reasons.append(f"{self.team2.name} has more shots on target.")
        if self.team1.big_chances > self.team2.big_chances:
            reasons.append(f"{self.team1.name} has created more big chances.")
        elif self.team2.big_chances > self.team1.big_chances:
            reasons.append(f"{self.team2.name} has created more big chances.")
        if team1_pressure > team2_pressure:
            reasons.append(f"{self.team1.name} has the higher attack pressure score.")
        elif team2_pressure > team1_pressure:
            reasons.append(f"{self.team2.name} has the higher attack pressure score.")
        if team1_momentum > team2_momentum:
            reasons.append(f"{self.team1.name} currently has more live momentum.")
        elif team2_momentum > team1_momentum:
            reasons.append(f"{self.team2.name} currently has more live momentum.")
        if team1_dangerous > team2_dangerous:
            reasons.append(f"{self.team1.name} has more calculated dangerous attacks.")
        elif team2_dangerous > team1_dangerous:
            reasons.append(f"{self.team2.name} has more calculated dangerous attacks.")
        if self.team1.goalkeeper_saves > self.team2.goalkeeper_saves:
            reasons.append(f"{self.team1.name}'s goalkeeper has made more saves.")
        elif self.team2.goalkeeper_saves > self.team1.goalkeeper_saves:
            reasons.append(f"{self.team2.name}'s goalkeeper has made more saves.")
        if self.match_minute > 0:
            reasons.append(
                f"The model is calculating remaining goals from minute {self.match_minute}."
            )
        for reason, _ in self.team1.modifiers:
            reasons.append(f"{self.team1.name}: {reason}.")
        for reason, _ in self.team2.modifiers:
            reasons.append(f"{self.team2.name}: {reason}.")
        for team in (self.team1, self.team2):
            raw_total, capped_total, was_clamped = team.event_score_breakdown()
            if was_clamped:
                reasons.append(
                    f"{team.name}: stacked modifiers totaled {raw_total:+.1f}, "
                    f"but were capped at {capped_total:+.1f}."
                )
        if not reasons:
            reasons.append(
                "No major live events yet. The prediction is based on team ratings "
                "and the Poisson model."
            )
        return reasons


def copy_team(team):
    return Team(
        team.name,
        team.offense,
        team.defense,
        team.form,
        team.star_power,
        team.clutch,
        team.fifa_rank,
        team.fifa_points,
        team.ranking_date,
    )


def _sample_poisson(expected_goals):
    """Samples one Poisson goal total without requiring NumPy."""
    limit = math.exp(-max(expected_goals, 0.0))
    product = 1.0
    goals = 0
    while product > limit:
        goals += 1
        product *= random.random()
    return max(goals - 1, 0)


def _simulate_knockout_match(team1, team2):
    match = Match(copy_team(team1), copy_team(team2), match_minute=0)
    team1_xg, team2_xg = match.expected_goals()
    team1_goals = _sample_poisson(team1_xg)
    team2_goals = _sample_poisson(team2_xg)
    if team1_goals > team2_goals:
        return team1
    if team2_goals > team1_goals:
        return team2
    p1, draw, p2, _, _ = match.calculate_probabilities()
    advance1, _ = match.advancement_probabilities((p1, draw, p2))
    return team1 if random.random() < advance1 else team2


def simulate_tournament(teams, simulation_count=10000):
    """Runs thousands of Monte Carlo knockout brackets."""
    simulation_count = max(1000, min(int(simulation_count), 50000))
    champion_counts = Counter()
    final_counts = Counter()
    semifinal_counts = Counter()
    final_matchups = Counter()
    for _ in range(simulation_count):
        current_round = [copy_team(team) for team in teams]
        if len(current_round) == 4:
            for team in current_round:
                semifinal_counts[team.name] += 1
        while len(current_round) > 1:
            next_round = []
            round_size = len(current_round)
            for index in range(0, round_size, 2):
                team1 = current_round[index]
                if index + 1 >= round_size:
                    next_round.append(team1)
                    continue
                team2 = current_round[index + 1]
                next_round.append(_simulate_knockout_match(team1, team2))
            if len(next_round) == 4:
                for team in next_round:
                    semifinal_counts[team.name] += 1
            if len(next_round) == 2:
                for team in next_round:
                    final_counts[team.name] += 1
                final_matchups[tuple(sorted([next_round[0].name, next_round[1].name]))] += 1
            current_round = next_round
        if current_round:
            champion_counts[current_round[0].name] += 1
    results = []
    for team in teams:
        results.append(
            {
                "team": team.name,
                "fifa_rank": team.fifa_rank,
                "semifinal_probability": round(
                    100 * semifinal_counts[team.name] / simulation_count, 2
                ),
                "final_probability": round(100 * final_counts[team.name] / simulation_count, 2),
                "champion_probability": round(
                    100 * champion_counts[team.name] / simulation_count, 2
                ),
            }
        )
    results.sort(key=lambda row: row["champion_probability"], reverse=True)
    most_common_final = None
    if final_matchups:
        matchup, count = final_matchups.most_common(1)[0]
        most_common_final = {
            "team1": matchup[0],
            "team2": matchup[1],
            "probability": round(100 * count / simulation_count, 2),
        }
    champion = results[0]["team"] if results else None
    return (results, champion, simulation_count, most_common_final)
