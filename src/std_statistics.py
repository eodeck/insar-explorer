"""Helpers for deterministic standard-deviation statistics sampling."""

from dataclasses import dataclass
import math


STD_FAST_SAMPLE_SIZE = 2000
STD_FAST_EXACT_THRESHOLD = 5000
STD_FAST_GRID_SIZE = 4


@dataclass(frozen=True)
class StdStatistics:
    """Summarize mean/std output and how much data contributed to it."""

    mean: float
    std: float
    sample_size: int
    is_exact: bool


def summarize_std_values(values, *, is_exact):
    """Return population mean/std for finite numeric values using bounded memory."""
    count = 0
    mean = 0.0
    m2 = 0.0

    for value in values:
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(numeric):
            continue

        count += 1
        delta = numeric - mean
        mean += delta / count
        m2 += delta * (numeric - mean)

    if count == 0:
        return None

    variance = m2 / count
    # Guard against tiny negative values from floating-point roundoff.
    std = math.sqrt(max(0.0, variance))
    return StdStatistics(
        mean=mean,
        std=std,
        sample_size=count,
        is_exact=bool(is_exact),
    )
