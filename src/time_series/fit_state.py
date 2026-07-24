"""UI-independent state for time-series model fitting."""

from dataclasses import dataclass


FIT_MODELS = ("poly-1", "poly-2", "poly-3", "exp", "log")
DEFAULT_FIT_MODEL = "poly-1"


@dataclass
class TimeSeriesFitState:
    """Represent fitting state independently from any concrete UI widgets."""

    fit_enabled: bool = False
    selected_fit_model: str = DEFAULT_FIT_MODEL
    seasonal_enabled: bool = False
    residual_enabled: bool = False

    def __post_init__(self):
        """Normalize invalid model identifiers to the default model."""
        if self.selected_fit_model not in FIT_MODELS:
            self.selected_fit_model = DEFAULT_FIT_MODEL

    def setFitEnabled(self, enabled):
        """Enable or disable fitting while enforcing the residual dependency."""
        self.fit_enabled = bool(enabled)
        if not self.fit_enabled:
            self.residual_enabled = False

    def setSelectedModel(self, model):
        """Select an actual fit model without implicitly enabling fitting."""
        if model not in FIT_MODELS:
            raise ValueError(f"Unsupported fit model: {model}")
        self.selected_fit_model = model

    def setSeasonalEnabled(self, enabled):
        """Set seasonal fitting and activate fitting when seasonal is enabled."""
        self.seasonal_enabled = bool(enabled)
        if self.seasonal_enabled:
            self.fit_enabled = True

    def setResidualEnabled(self, enabled):
        """Set residual visibility and activate fitting when residuals are enabled."""
        self.residual_enabled = bool(enabled)
        if self.residual_enabled:
            self.fit_enabled = True
