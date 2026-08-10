"""Typed saved/factory defaults for the Map Symbology settings popup."""

from dataclasses import dataclass
from typing import Optional

from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtGui import QColor

from .marker_state import (
    DEFAULT_MARKER_SHAPE,
    DEFAULT_OUTLINE_COLOR,
    DEFAULT_OUTLINE_WIDTH_MM,
    normalize_marker_shape,
)

_KEY_ROOT = "insar_explorer/map_settings/symbology"
CLASSES_MIN = 1
CLASSES_MAX = 999
MARKER_SIZE_MIN = 0.0
MARKER_SIZE_MAX = 99.99
OUTLINE_WIDTH_MIN = 0.0
OUTLINE_WIDTH_MAX = 2.0
OPACITY_MIN = 0
OPACITY_MAX = 100


@dataclass(frozen=True)
class MapSymbologySettings:
    """Immutable values owned by the Symbology settings popup."""

    continuous_colormap: bool
    classes: int
    marker_shape: str
    marker_size: float
    outline_color: str
    outline_width_mm: float
    opacity_percent: int


def factory_map_symbology_settings():
    """Return canonical built-in Map Symbology defaults."""
    return MapSymbologySettings(
        continuous_colormap=True,
        classes=21,
        marker_shape=DEFAULT_MARKER_SHAPE,
        marker_size=1.0,
        outline_color=DEFAULT_OUTLINE_COLOR,
        outline_width_mm=DEFAULT_OUTLINE_WIDTH_MM,
        opacity_percent=100,
    )


def _clamp(value, lower, upper):
    return max(lower, min(upper, value))


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


def _coerce_int(value, fallback, lower, upper):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = int(fallback)
    return int(_clamp(value, lower, upper))


def _coerce_float(value, fallback, lower, upper):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = float(fallback)
    return float(_clamp(value, lower, upper))


def _normalize_color(value, fallback):
    color = QColor(str(value or ""))
    if not color.isValid():
        color = QColor(fallback)
    return color.name()


def normalize_map_symbology_settings(settings):
    """Normalize one settings value, including corrupt or legacy fields."""
    factory = factory_map_symbology_settings()
    return MapSymbologySettings(
        continuous_colormap=_coerce_bool(
            settings.continuous_colormap, factory.continuous_colormap
        ),
        classes=_coerce_int(
            settings.classes, factory.classes, CLASSES_MIN, CLASSES_MAX
        ),
        marker_shape=normalize_marker_shape(settings.marker_shape),
        marker_size=_coerce_float(
            settings.marker_size, factory.marker_size,
            MARKER_SIZE_MIN, MARKER_SIZE_MAX,
        ),
        outline_color=_normalize_color(
            settings.outline_color, factory.outline_color
        ),
        outline_width_mm=_coerce_float(
            settings.outline_width_mm, factory.outline_width_mm,
            OUTLINE_WIDTH_MIN, OUTLINE_WIDTH_MAX,
        ),
        opacity_percent=_coerce_int(
            settings.opacity_percent, factory.opacity_percent,
            OPACITY_MIN, OPACITY_MAX,
        ),
    )


class MapSymbologySettingsService:
    """Own saved and factory defaults for Map Symbology popup settings."""

    def __init__(self, settings_store: Optional[QSettings] = None):
        self._store = settings_store or QSettings()

    def factory_defaults(self):
        """Return normalized built-in factory settings."""
        return factory_map_symbology_settings()

    def load_defaults(self):
        """Load and normalize the user's saved Symbology default."""
        factory = factory_map_symbology_settings()
        raw = MapSymbologySettings(
            self._store.value(self._key("continuous_colormap"), factory.continuous_colormap),
            self._store.value(self._key("classes"), factory.classes),
            self._store.value(self._key("marker_shape"), factory.marker_shape),
            self._store.value(self._key("marker_size"), factory.marker_size),
            self._store.value(self._key("outline_color"), factory.outline_color),
            self._store.value(self._key("outline_width_mm"), factory.outline_width_mm),
            self._store.value(self._key("opacity_percent"), factory.opacity_percent),
        )
        return normalize_map_symbology_settings(raw)

    def save_defaults(self, settings):
        """Persist one normalized user default without changing active state."""
        settings = normalize_map_symbology_settings(settings)
        values = {
            "continuous_colormap": settings.continuous_colormap,
            "classes": settings.classes,
            "marker_shape": settings.marker_shape,
            "marker_size": settings.marker_size,
            "outline_color": settings.outline_color,
            "outline_width_mm": settings.outline_width_mm,
            "opacity_percent": settings.opacity_percent,
        }
        for name, value in values.items():
            self._store.setValue(self._key(name), value)
        self._store.sync()

    @staticmethod
    def _key(name):
        return "{}/{}".format(_KEY_ROOT, name)
