"""Global presentation settings for target/reference map indicators."""

from dataclasses import dataclass
from typing import Optional

from qgis.PyQt.QtCore import QObject, QSettings, pyqtSignal
from qgis.PyQt.QtGui import QColor

_KEY_ROOT = "insar_explorer/time_series/map_indicators"
POINT_SIZE_MIN = 4
POINT_SIZE_MAX = 24


@dataclass(frozen=True)
class MapIndicatorSettings:
    """Immutable global map-indicator presentation values."""

    target_color: QColor
    reference_color: QColor
    point_outer_color: QColor
    show_point_outer_ring: bool
    point_size: int
    opacity_percent: int


def factory_map_indicator_settings() -> MapIndicatorSettings:
    """Return a fresh copy of factory settings."""
    return MapIndicatorSettings(
        target_color=QColor(220, 45, 45),
        reference_color=QColor(0, 190, 230),
        point_outer_color=QColor(0, 0, 0),
        show_point_outer_ring=True,
        point_size=9,
        opacity_percent=100,
    )


def _copy(settings: MapIndicatorSettings) -> MapIndicatorSettings:
    return MapIndicatorSettings(
        QColor(settings.target_color),
        QColor(settings.reference_color),
        QColor(settings.point_outer_color),
        bool(settings.show_point_outer_ring),
        int(settings.point_size),
        int(settings.opacity_percent),
    )


def _valid(settings: MapIndicatorSettings) -> bool:
    return (
        settings.target_color.isValid()
        and settings.reference_color.isValid()
        and settings.point_outer_color.isValid()
        and isinstance(settings.show_point_outer_ring, bool)
        and isinstance(settings.point_size, int)
        and POINT_SIZE_MIN <= settings.point_size <= POINT_SIZE_MAX
        and isinstance(settings.opacity_percent, int)
        and 0 <= settings.opacity_percent <= 100
    )


class MapIndicatorSettingsService(QObject):
    """Own active, saved-default, and factory map-indicator settings."""

    settingsChanged = pyqtSignal(object)

    def __init__(self, settings_store: Optional[QSettings] = None, parent=None):
        super(MapIndicatorSettingsService, self).__init__(parent)
        self._store = settings_store or QSettings()
        self._active = self.load_defaults()

    @property
    def active(self) -> MapIndicatorSettings:
        return _copy(self._active)

    def factory_defaults(self) -> MapIndicatorSettings:
        return factory_map_indicator_settings()

    def load_defaults(self) -> MapIndicatorSettings:
        factory = factory_map_indicator_settings()
        return MapIndicatorSettings(
            self._read_color("target_color", factory.target_color),
            self._read_color("reference_color", factory.reference_color),
            self._read_color("point_outer_color", factory.point_outer_color),
            self._read_bool("show_point_outer_ring", factory.show_point_outer_ring),
            self._read_point_size(factory.point_size),
            self._read_opacity(factory.opacity_percent),
        )

    def apply(self, settings: MapIndicatorSettings, notify: bool = True) -> None:
        if not _valid(settings):
            raise ValueError(
                "Choose valid colors, a point size from {} to {} px, and an "
                "opacity from 0 to 100%.".format(POINT_SIZE_MIN, POINT_SIZE_MAX)
            )
        self._active = _copy(settings)
        if notify:
            self.settingsChanged.emit(self.active)

    def save_defaults(self, settings: MapIndicatorSettings) -> None:
        if not _valid(settings):
            raise ValueError(
                "Choose valid colors, a point size from {} to {} px, and an "
                "opacity from 0 to 100%.".format(POINT_SIZE_MIN, POINT_SIZE_MAX)
            )
        values = {
            "target_color": settings.target_color.name(),
            "reference_color": settings.reference_color.name(),
            "point_outer_color": settings.point_outer_color.name(),
            "show_point_outer_ring": bool(settings.show_point_outer_ring),
            "point_size": int(settings.point_size),
            "opacity_percent": int(settings.opacity_percent),
        }
        for name, value in values.items():
            self._store.setValue("{}/{}".format(_KEY_ROOT, name), value)
        sync = getattr(self._store, "sync", None)
        if sync is not None:
            sync()

    def _raw(self, name):
        return self._store.value("{}/{}".format(_KEY_ROOT, name), None)

    def _read_color(self, name, fallback):
        raw = self._raw(name)
        color = QColor(str(raw)) if raw is not None else QColor()
        return color if color.isValid() else QColor(fallback)

    def _read_bool(self, name, fallback):
        raw = self._raw(name)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, int) and raw in (0, 1):
            return bool(raw)
        if isinstance(raw, str):
            normalized = raw.strip().lower()
            if normalized in ("true", "1"):
                return True
            if normalized in ("false", "0"):
                return False
        return bool(fallback)

    def _read_point_size(self, fallback):
        try:
            value = int(self._raw("point_size"))
        except (TypeError, ValueError):
            return int(fallback)
        return value if POINT_SIZE_MIN <= value <= POINT_SIZE_MAX else int(fallback)

    def _read_opacity(self, fallback):
        try:
            value = int(self._raw("opacity_percent"))
        except (TypeError, ValueError):
            return int(fallback)
        return value if 0 <= value <= 100 else int(fallback)
