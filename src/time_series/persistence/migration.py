"""One-time migration from the retired legacy JSON preference source."""

import os

from .qsettings import SCHEMA_VERSION


class LegacyPreferencesMigrator:
    """Migrate legacy JSON preferences into QSettings once without overwrite."""

    MARKER = "migration/legacy_json_completed"

    def __init__(
        self, target, legacy_repository=None, legacy_path=None, diagnostic=None
    ):
        self.target = target
        self.legacy_repository = legacy_repository
        self.legacy_path = legacy_path
        self.diagnostic = diagnostic
        self._marker_commit_failed = False

    def migrate_if_needed(self):
        """Migrate missing values and durably commit completion in two stages."""
        if not self._marker_commit_failed and self.target.read_migration_completed(
            self.MARKER
        ):
            return False

        try:
            self._persist_migration_values()
            self._commit_completion_marker()
            self._marker_commit_failed = False
            return True
        except Exception as exc:
            if self.diagnostic:
                self.diagnostic(
                    "Legacy time-series preferences could not be migrated; "
                    "migration will be retried.",
                    exc,
                )
            return False

    def _persist_migration_values(self):
        """Stage 1: persist migrated values and schema version."""
        legacy_available = (
            self.legacy_repository is not None
            and (not self.legacy_path or os.path.isfile(self.legacy_path))
        )
        if legacy_available:
            preferences = self.legacy_repository.load()
            self.target.save_preferences_missing(preferences, sync=False)
        self.target.write_schema_version(SCHEMA_VERSION, sync=False)
        self.target.sync()

    def _commit_completion_marker(self):
        """Stage 2: durably commit migration completion."""
        self.target.write_migration_completed(self.MARKER, True, sync=False)
        try:
            self.target.sync()
            if not self.target.read_migration_completed(self.MARKER):
                raise RuntimeError("Migration completion marker was not persisted")
        except Exception:
            self._marker_commit_failed = True
            self._remove_uncommitted_marker()
            raise

    def _remove_uncommitted_marker(self):
        """Best-effort removal of a marker not durably committed."""
        try:
            self.target.remove(self.MARKER, sync=False)
            self.target.sync()
        except Exception:
            # Preserve the original marker-commit failure. The in-process flag
            # prevents this repository instance from accepting the live marker.
            pass
