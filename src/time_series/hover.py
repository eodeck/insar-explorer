"""Pure helpers for time-series hover hit testing and readout formatting."""

from dataclasses import dataclass
from datetime import datetime
from math import hypot, isfinite
from typing import Iterable, Optional

import numpy as np


@dataclass(frozen=True)
class HoverObservation:
    """One inspectable plotted observation expressed in scene coordinates."""

    date: object
    value: float
    scene_x: float
    scene_y: float
    plot_x: float = 0.0
    plot_y: float = 0.0
    series_id: object = None


def select_nearest_hover_observation(
    observations: Iterable[HoverObservation], mouse_x: float, mouse_y: float,
    tolerance_px: float = 10.0,
) -> Optional[HoverObservation]:
    """Return the nearest finite observation within the pixel-space tolerance."""
    best = None
    best_distance = float(tolerance_px)
    for observation in observations:
        if not all(isfinite(float(value)) for value in (
            observation.value, observation.scene_x, observation.scene_y,
        )):
            continue
        distance = hypot(
            float(observation.scene_x) - float(mouse_x),
            float(observation.scene_y) - float(mouse_y),
        )
        if distance <= best_distance:
            best = observation
            best_distance = distance
    return best


def format_hover_date(value) -> str:
    """Return an ISO acquisition date for a supported date-like value."""
    if isinstance(value, np.datetime64):
        value = value.astype("datetime64[ms]").astype(datetime)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return datetime(value.year, value.month, value.day).strftime("%Y-%m-%d")


def format_hover_text(observation: Optional[HoverObservation]) -> str:
    """Return compact date/value hover text without assuming a dataset unit."""
    if observation is None or not isfinite(float(observation.value)):
        return ""
    return f"{format_hover_date(observation.date)} · {float(observation.value):.6g}"
