"""Deprecated compatibility helper backed by the user-preferences abstraction."""


def persist_default_time_series_style(repository, style):
    """Persist a legacy style through an injected user-preferences repository."""
    from .settings.model import SeriesStyleSettings

    repository.save_series_defaults(SeriesStyleSettings.from_params(style.params))
