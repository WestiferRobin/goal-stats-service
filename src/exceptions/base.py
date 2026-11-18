"""Framework-independent application exceptions with reviewed public messages."""


class DomainError(Exception):
    """Constructor details remain private; handlers expose only public_detail."""

    public_detail = "The operation could not be completed."


class PredictionGenerationError(Exception):
    """Calculation or persistence failed; original details remain private."""

    public_detail = (
        "Prediction generation failed. Reopen the saved scenario and check prediction "
        "history before retrying; scenario creation and generation are separate operations."
    )


class MatchStatisticsError(DomainError):
    public_detail = "Shots on target cannot exceed total shots."
    reason = "shots_on_target_exceeds_total"

    def __init__(self, fields: list[str]) -> None:
        self.fields = [f for f in fields if f in ("team1_shots_on_target", "team2_shots_on_target")]
        super().__init__(self.public_detail)


class EvaluationAssetUnavailable(Exception):
    """Server-owned assets cannot be loaded or verified; details stay in server logs."""

    public_detail = (
        "Backtesting is temporarily unavailable because an approved historical asset "
        "could not be loaded. Please try again later."
    )
    reason = "evaluation_asset_unavailable"

    def __init__(self, asset: str, cause: Exception) -> None:
        self.asset = asset
        self.cause_type = type(cause).__name__
        super().__init__(asset)
