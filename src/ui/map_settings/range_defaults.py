"""Typed saved and factory defaults for reusable Map Settings range policies."""

from dataclasses import dataclass
from typing import Optional

from qgis.PyQt.QtCore import QSettings

from .range_state import COMPUTED_RANGE_SOURCES, RangeSource, StdCalculationMode

_KEY_ROOT = "insar_explorer/map_settings/range"


@dataclass(frozen=True)
class RangePolicyDefaults:
    """Dataset-independent policy values owned by the Range settings popup."""

    range_source: RangeSource
    calculation: StdCalculationMode
    symmetric_around_zero: bool


def factory_range_policy_defaults():
    """Return the reusable policy represented by the baseline factory behavior."""
    return RangePolicyDefaults(
        range_source=RangeSource.DATA_EXTENT,
        calculation=StdCalculationMode.FAST,
        symmetric_around_zero=False,
    )


def _coerce_bool(value, fallback):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes", "on"):
            return True
        if lowered in ("false", "0", "no", "off"):
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return bool(fallback)


def _coerce_range_source(value, fallback):
    if isinstance(value, RangeSource):
        source = value
    else:
        try:
            source = RangeSource(value)
        except (TypeError, ValueError):
            source = fallback
    # Custom owns explicit numeric bounds, so it is not a reusable policy default.
    if source not in COMPUTED_RANGE_SOURCES:
        source = fallback
    return source


def _coerce_calculation(value, fallback):
    if isinstance(value, StdCalculationMode):
        return value
    try:
        return StdCalculationMode(value)
    except (TypeError, ValueError):
        return fallback


def normalize_range_policy_defaults(settings):
    """Normalize one policy snapshot and reject stale/non-reusable values."""
    factory = factory_range_policy_defaults()
    return RangePolicyDefaults(
        range_source=_coerce_range_source(
            settings.range_source, factory.range_source
        ),
        calculation=_coerce_calculation(
            settings.calculation, factory.calculation
        ),
        symmetric_around_zero=_coerce_bool(
            settings.symmetric_around_zero, factory.symmetric_around_zero
        ),
    )


class RangePolicyDefaultsService:
    """Own saved and factory defaults for reusable Map Settings range policies."""

    def __init__(self, settings_store: Optional[QSettings] = None):
        self._store = settings_store or QSettings()

    def factory_defaults(self):
        """Return normalized built-in factory policy settings."""
        return factory_range_policy_defaults()

    def load_defaults(self):
        """Load and normalize the user's saved reusable range policy."""
        factory = factory_range_policy_defaults()
        raw = RangePolicyDefaults(
            range_source=self._store.value(
                self._key("range_source"), factory.range_source.value
            ),
            calculation=self._store.value(
                self._key("calculation"), factory.calculation.value
            ),
            symmetric_around_zero=self._store.value(
                self._key("symmetric_around_zero"),
                factory.symmetric_around_zero,
            ),
        )
        return normalize_range_policy_defaults(raw)

    def save_defaults(self, settings):
        """Persist only normalized dataset-independent range-policy fields."""
        settings = normalize_range_policy_defaults(settings)
        values = {
            "range_source": settings.range_source.value,
            "calculation": settings.calculation.value,
            "symmetric_around_zero": settings.symmetric_around_zero,
        }
        for name, value in values.items():
            self._store.setValue(self._key(name), value)
        self._store.sync()

    @staticmethod
    def _key(name):
        return "{}/{}".format(_KEY_ROOT, name)
