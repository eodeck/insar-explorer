from typing import NamedTuple

from qgis.PyQt.QtGui import QColor


class ColorMaps():
    def __init__(self):
        self.ramp = []

    def getColor(self, value):
        color_stops = self.ramp
        for i in range(len(color_stops) - 1):
            pos1, color1 = color_stops[i]
            pos2, color2 = color_stops[i + 1]

            if pos1 <= value <= pos2:
                ratio = (value - pos1) / (pos2 - pos1)
                r = color1.red() + (color2.red() - color1.red()) * ratio
                g = color1.green() + (color2.green() - color1.green()) * ratio
                b = color1.blue() + (color2.blue() - color1.blue()) * ratio
                return QColor(int(r), int(g), int(b))

        return color_stops[-1][1]

    def reverse(self):
        n = len(self.ramp)
        reversed_ramp = self.ramp[::-1]
        self.ramp = [(i / (n - 1), color) for i, (_, color) in enumerate(reversed_ramp)]


class Turbo(ColorMaps):
    def __init__(self):
        super().__init__()
        self.ramp = [
            (0.0, QColor(66, 30, 150)),  # Dark blue
            (0.1, QColor(29, 81, 201)),  # Darker blue
            (0.2, QColor(25, 150, 221)),  # Blue
            (0.3, QColor(18, 201, 187)),  # Cyan
            (0.4, QColor(33, 233, 127)),  # Greenish-cyan
            (0.5, QColor(93, 242, 73)),  # Green
            (0.6, QColor(170, 250, 42)),  # Yellow-green
            (0.7, QColor(239, 234, 26)),  # Yellow
            (0.8, QColor(252, 186, 28)),  # Yellow-orange
            (0.9, QColor(252, 102, 28)),  # Orange-red
            (1.0, QColor(252, 53, 28))  # Red
        ]


class TurboR(Turbo):
    def __init__(self):
        super().__init__()
        self.reverse()


class Roma(ColorMaps):
    """Roma color map. Crameri, F. (2018). Scientific colour maps. Zenodo. https://doi.org/10.5281/zenodo.1243862"""
    def __init__(self):
        super().__init__()
        self.ramp = [
            (0., QColor(126, 23, 0)),
            (0.04, QColor(138, 51, 8)),
            (0.08, QColor(148, 70, 16)),
            (0.12, QColor(157, 89, 24)),
            (0.16, QColor(166, 106, 32)),
            (0.20, QColor(174, 122, 39)),
            (0.25, QColor(183, 141, 50)),
            (0.29, QColor(192, 159, 64)),
            (0.33, QColor(201, 181, 86)),
            (0.37, QColor(209, 203, 115)),
            (0.41, QColor(211, 219, 144)),
            (0.45, QColor(206, 231, 174)),
            (0.5, QColor(193, 235, 196)),
            (0.54, QColor(174, 233, 209)),
            (0.58, QColor(148, 224, 215)),
            (0.62, QColor(121, 211, 216)),
            (0.66, QColor(94, 194, 212)),
            (0.70, QColor(72, 175, 206)),
            (0.75, QColor(57, 158, 199)),
            (0.79, QColor(47, 140, 192)),
            (0.83, QColor(40, 123, 185)),
            (0.87, QColor(34, 107, 178)),
            (0.91, QColor(28, 88, 170)),
            (0.95, QColor(20, 70, 162)),
            (1., QColor(3, 49, 153)),
        ]


class Vik(ColorMaps):
    """Vik color map. Crameri, F. (2018). Scientific colour maps. Zenodo. https://doi.org/10.5281/zenodo.1243862"""
    def __init__(self):
        super().__init__()
        self.ramp = [
            (0., QColor(0, 18, 97)),
            (0.04, QColor(2, 36, 108)),
            (0.08, QColor(2, 51, 118)),
            (0.12, QColor(3, 68, 129)),
            (0.16, QColor(6, 86, 141)),
            (0.20, QColor(21, 104, 153)),
            (0.25, QColor(48, 125, 167)),
            (0.29, QColor(78, 146, 181)),
            (0.33, QColor(113, 169, 196)),
            (0.37, QColor(148, 190, 211)),
            (0.41, QColor(180, 210, 224)),
            (0.45, QColor(214, 228, 234)),
            (0.5, QColor(237, 230, 225)),
            (0.54, QColor(238, 214, 201)),
            (0.58, QColor(229, 192, 171)),
            (0.62, QColor(221, 173, 145)),
            (0.66, QColor(212, 152, 117)),
            (0.70, QColor(204, 132, 91)),
            (0.75, QColor(196, 114, 67)),
            (0.79, QColor(186, 94, 43)),
            (0.83, QColor(170, 69, 18)),
            (0.87, QColor(148, 47, 6)),
            (0.91, QColor(126, 29, 6)),
            (0.95, QColor(108, 15, 7)),
            (1., QColor(90, 0, 8)),
        ]


class Gray(ColorMaps):
    """Gray color map."""
    def __init__(self):
        super().__init__()
        self.ramp = [
            (0.0, QColor(0, 0, 0)),       # Black
            (0.1, QColor(28, 28, 28)),
            (0.2, QColor(56, 56, 56)),
            (0.3, QColor(84, 84, 84)),
            (0.4, QColor(112, 112, 112)),
            (0.5, QColor(140, 140, 140)),
            (0.6, QColor(168, 168, 168)),
            (0.7, QColor(196, 196, 196)),
            (0.8, QColor(224, 224, 224)),
            (0.9, QColor(240, 240, 240)),
            (1.0, QColor(255, 255, 255))  # White
        ]


class ColormapSpec(NamedTuple):
    """Describe one canonical Map Settings colormap."""

    id: str
    label: str
    icon_path: str
    factory: type


DEFAULT_COLORMAP_ID = "roma"
FALLBACK_COLORMAP_ID = "gray"
COLORMAPS = (
    ColormapSpec("roma", "Roma", ":/colormaps/icons/colormaps/roma.png", Roma),
    ColormapSpec("vik", "Vik", ":/colormaps/icons/colormaps/vik.png", Vik),
    ColormapSpec(
        "turbo", "Turbo", ":/colormaps/icons/colormaps/turbo_r.png", TurboR
    ),
    ColormapSpec("gray", "Gray", ":/colormaps/icons/colormaps/gray.png", Gray),
)
COLORMAP_BY_ID = {spec.id: spec for spec in COLORMAPS}
_COLORMAP_ID_BY_ALIAS = {
    alias.casefold(): spec.id
    for spec in COLORMAPS
    for alias in (spec.id, spec.label)
}


def canonical_colormap_id(identifier):
    """Resolve current labels/ids to one renderer identifier."""
    key = str(identifier or "").strip().casefold()
    return _COLORMAP_ID_BY_ALIAS.get(key, FALLBACK_COLORMAP_ID)
