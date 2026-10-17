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
