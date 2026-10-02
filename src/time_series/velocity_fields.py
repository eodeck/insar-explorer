"""Canonical velocity-field recognition shared by map and legend workflows."""

VELOCITY_FIELD_NAME_OPTIONS = ("velocity", "VEL", "mean_velocity")


def get_velocity_field_name(field_names):
    """Return the first recognized velocity name present in ``field_names``."""
    names = {str(name) for name in (field_names or ())}
    return next((name for name in VELOCITY_FIELD_NAME_OPTIONS if name in names), None)
