"""Shared schema helpers for Replica interval presets and marker symbols."""

import math

# Replica intervals represent half the nominal radar wavelength (lambda / 2).
REPLICA_INTERVAL_PRESETS = (
    ("s1", "Sentinel-1", 27.8),
    ("tsx", "TerraSAR-X", 15.5),
    ("alos", "ALOS", 118.0),
    ("nisar_l", "NISAR (L-band)", 120.0),
)

REPLICA_INTERVAL_MATCH_TOLERANCE_MM = 0.05


def replica_preset_id_for_interval(interval_mm):
    """Return the matching preset identifier, or ``None`` for a custom interval."""
    try:
        interval = float(interval_mm)
    except (TypeError, ValueError):
        return None
    for preset_id, _label, preset_interval in REPLICA_INTERVAL_PRESETS:
        if math.isclose(
            interval,
            preset_interval,
            rel_tol=0.0,
            abs_tol=REPLICA_INTERVAL_MATCH_TOLERANCE_MM,
        ):
            return preset_id
    return None


def replica_interval_for_preset(preset_id):
    """Return the interval for a named preset, or ``None`` for Custom/unknown."""
    for candidate_id, _label, interval in REPLICA_INTERVAL_PRESETS:
        if candidate_id == preset_id:
            return interval
    return None
