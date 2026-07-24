"""Time-series domain and controller utilities."""

__all__ = ["TimeSeriesStore"]


def __getattr__(name):
    """Load collection services lazily to keep pure model imports acyclic."""
    if name == "TimeSeriesStore":
        from .store import TimeSeriesStore

        return TimeSeriesStore
    raise AttributeError(name)
