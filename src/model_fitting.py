from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.optimize import curve_fit
from datetime import datetime


@dataclass(frozen=True)
class FitStatistics:
    """Numerical quality metrics for one successful fit calculation."""

    observation_count: int
    r_squared: Optional[float]
    rmse: float


def calculateFitStatistics(y_observed, y_fitted):
    """Return R-squared and RMSE for matching finite observation values."""
    observed = np.asarray(y_observed, dtype=np.float64)
    fitted = np.asarray(y_fitted, dtype=np.float64)

    if observed.ndim != 1 or fitted.ndim != 1:
        raise ValueError("Fit statistics require one-dimensional inputs.")
    if observed.shape != fitted.shape:
        raise ValueError("Fit statistics require matching input shapes.")
    if observed.size == 0:
        raise ValueError("Fit statistics require at least one observation.")

    finite_mask = np.isfinite(observed) & np.isfinite(fitted)
    if not np.all(finite_mask):
        raise ValueError("Fit statistics require finite observed and fitted values.")

    residuals = observed - fitted
    squared_residuals = np.square(residuals)
    rmse = float(np.sqrt(np.mean(squared_residuals)))
    if not np.isfinite(rmse):
        raise ValueError("Fit statistics produced a non-finite RMSE.")

    rss = float(np.sum(squared_residuals))
    centered = observed - np.mean(observed)
    tss = float(np.sum(np.square(centered)))
    if np.isclose(tss, 0.0):
        r_squared = None
    else:
        r_squared = float(1.0 - rss / tss)
        if not np.isfinite(r_squared):
            raise ValueError("Fit statistics produced a non-finite R-squared value.")

    return FitStatistics(
        observation_count=int(observed.size),
        r_squared=r_squared,
        rmse=rmse,
    )


class ModelFitError(RuntimeError):
    """Raised when a selected fitting model cannot produce a valid fit."""

    def __init__(self, model_id, message, *, finite_observation_count=None):
        super().__init__(message)
        self.model_id = model_id
        self.finite_observation_count = finite_observation_count


def modelPoly1(x, a, b):
    return a + b * x


def modelPoly2(x, a, b, c):
    return modelPoly1(x, a, b) + c * x * x


def modelPoly3(x, a, b, c, d):
    return modelPoly2(x, a, b, c) + d * x * x * x


def modelAnnual(x, a, b):
    return a * np.sin(x * 2 * np.pi / 365.25) + b * np.cos(x * 2 * np.pi / 365.25)


def modelExponential(x, a, b, c):
    return a + b * np.exp(c * x)


def modelLogarithmic(x, a, b, tau):
    """Evaluate a logarithmic trend with a strictly positive time scale."""
    return a + b * np.log1p(x / tau)


_MODEL_LABELS = {
    "exp": "Exponential",
    "log": "Logarithmic",
}


def _modelFitLabel(model_id):
    """Return the stable display label used in numerical fit errors."""
    return _MODEL_LABELS.get(model_id, model_id)


def _prepareNonlinearFitInputs(x, y, *, model_id, parameter_count):
    """Return finite one-dimensional float arrays suitable for nonlinear fitting."""
    label = _modelFitLabel(model_id)
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)

    if x.ndim != 1 or y.ndim != 1:
        raise ModelFitError(
            model_id, f"{label} fit requires one-dimensional inputs."
        )
    if len(x) != len(y):
        raise ModelFitError(
            model_id, f"{label} fit requires matching input lengths."
        )

    finite_mask = np.isfinite(x) & np.isfinite(y)
    finite_count = int(np.count_nonzero(finite_mask))
    minimum_count = parameter_count + 1
    if finite_count < minimum_count:
        raise ModelFitError(
            model_id,
            f"{label} fit requires at least {minimum_count} finite observations.",
            finite_observation_count=finite_count,
        )

    x_fit = x[finite_mask]
    y_fit = y[finite_mask]
    if np.ptp(x_fit) == 0:
        raise ModelFitError(
            model_id,
            f"{label} fit requires a non-zero time span.",
            finite_observation_count=finite_count,
        )

    return x_fit, y_fit


def _validateNonlinearFitResult(
    *, model_id, parameters, model_values, finite_observation_count=None
):
    """Raise ``ModelFitError`` when a nonlinear solution is numerically invalid."""
    label = _modelFitLabel(model_id)
    if not np.all(np.isfinite(parameters)):
        raise ModelFitError(
            model_id,
            f"{label} fit returned non-finite parameters.",
            finite_observation_count=finite_observation_count,
        )
    if not np.all(np.isfinite(model_values)):
        raise ModelFitError(
            model_id,
            f"{label} fit returned non-finite values.",
            finite_observation_count=finite_observation_count,
        )


def _fitExponentialPrepared(x_fit, y_fit):
    """Fit already prepared exponential inputs."""
    finite_count = len(x_fit)
    initial_params = [1.0, 1.0, 0.01]
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            popt, pcov = curve_fit(
                modelExponential, x_fit, y_fit, p0=initial_params, maxfev=2000
            )
            fitted = modelExponential(x_fit, *popt)
    except (RuntimeError, ValueError, FloatingPointError) as exc:
        raise ModelFitError(
            "exp",
            "Exponential fit failed.",
            finite_observation_count=finite_count,
        ) from exc

    _validateNonlinearFitResult(
        model_id="exp",
        parameters=popt,
        model_values=fitted,
        finite_observation_count=finite_count,
    )
    return popt, pcov


def fitExponential(x, y):
    """Fit the exponential model or raise ``ModelFitError`` on expected failure."""
    x_fit, y_fit = _prepareNonlinearFitInputs(
        x, y, model_id="exp", parameter_count=3
    )
    return _fitExponentialPrepared(x_fit, y_fit)



def _fitLogarithmicPrepared(x_fit, y_fit):
    """Fit already prepared, normalized logarithmic inputs."""
    finite_count = len(x_fit)
    tau0 = 1.0
    scale = np.log1p(1.0 / tau0)
    a0 = float(y_fit[0])
    b0 = float((y_fit[-1] - y_fit[0]) / scale) if scale != 0 else 0.0
    initial_params = [a0, b0, tau0]
    bounds = ([-np.inf, -np.inf, 1e-6], [np.inf, np.inf, 1e3])
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            popt, pcov = curve_fit(
                modelLogarithmic,
                x_fit,
                y_fit,
                p0=initial_params,
                bounds=bounds,
                maxfev=4000,
            )
            fitted = modelLogarithmic(x_fit, *popt)
    except (RuntimeError, ValueError, FloatingPointError) as exc:
        raise ModelFitError(
            "log",
            "Logarithmic fit failed.",
            finite_observation_count=finite_count,
        ) from exc

    _validateNonlinearFitResult(
        model_id="log",
        parameters=popt,
        model_values=fitted,
        finite_observation_count=finite_count,
    )
    return popt, pcov


def fitLogarithmic(x, y):
    """Fit the logarithmic model to validated time-series observations."""
    x_fit, y_fit = _prepareNonlinearFitInputs(
        x, y, model_id="log", parameter_count=3
    )
    x_fit = (x_fit - x_fit.min()) / np.ptp(x_fit)
    return _fitLogarithmicPrepared(x_fit, y_fit)


def normalize(x, ref=None):
    if ref is None:
        return (x - x.min()) / (x.max() - x.min())
    else:
        return (x - ref.min()) / (ref.max() - ref.min())


def ordinalTodates(ordinals):
    return [datetime.fromordinal(int(x)) for x in ordinals]


class FittingModels:
    def __init__(self, x=None, y=None, model="poly-1"):
        self.x = x
        self.y = y
        self.mask = np.isfinite(np.array(y, dtype=np.float64))

        self.model = model
        self.ordinal_dates = self.datesToOrdinal()

    def datesToOrdinal(self):
        return np.array([x.toordinal() for x in self.x])

    def fit(self, model=None, seasonal=False):
        # normalize dates for better curve fitting and avoid overflow
        # Caution: a uniform reference should be used for date normalization
        # Caution: seasonal signal should not be normalized
        mask = self.mask
        x = self.ordinal_dates
        y = np.asarray(self.y, dtype=np.float64)

        if model is None:
            model = self.model

        nonlinear_models = {
            "exp": (modelExponential, _fitExponentialPrepared),
            "log": (modelLogarithmic, _fitLogarithmicPrepared),
        }
        if model not in nonlinear_models and len(x) != len(y):
            raise ValueError("Fitting inputs must have matching lengths.")
        fit_models_dict = {
            "poly-1": modelPoly1,
            "poly-2": modelPoly2,
            "poly-3": modelPoly3,
            "exp": modelExponential,
            "log": modelLogarithmic,
        }
        fit_model = fit_models_dict[model]
        if model in nonlinear_models:
            x_fit, y_fit = _prepareNonlinearFitInputs(
                x, y, model_id=model, parameter_count=3
            )
            x_min = x_fit.min()
            x_span = x_fit.max() - x_min
            x_fit_norm = (x_fit - x_min) / x_span
            fit_model, prepared_fitter = nonlinear_models[model]
            popt, pcov = prepared_fitter(x_fit_norm, y_fit)
            x_norm = (x - x_min) / x_span
        else:
            x_norm = normalize(x, ref=x[mask])
            popt, pcov = curve_fit(fit_model, x_norm[mask], y[mask])

        model_x_linspace = np.linspace(min(x), max(x), 100)
        model_x = ordinalTodates(model_x_linspace)
        if model in nonlinear_models:
            model_x_linspace_norm = (model_x_linspace - x_min) / x_span
        else:
            model_x_linspace_norm = normalize(model_x_linspace, ref=x[mask])
        model_y = fit_model(model_x_linspace_norm, *popt)
        fit_y = fit_model(x_norm, *popt)

        if seasonal:
            residual = y - fit_y
            popt_seasonal, _ = curve_fit(modelAnnual, x[mask], residual[mask])
            model_y_seasonal = modelAnnual(model_x_linspace, *popt_seasonal)
            fit_y_seasonal = modelAnnual(x, *popt_seasonal)
            model_y += model_y_seasonal
            fit_y += fit_y_seasonal

        return fit_y, model_x, model_y

    def fitVelocity(self):
        x = self.ordinal_dates
        y = self.y
        mask = self.mask
        popt, pcov = curve_fit(modelPoly1, x[mask], y[mask])
        return popt[1] * 365.25
