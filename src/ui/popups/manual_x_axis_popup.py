"""Transactional editor for the session-local Time Series X-axis range."""

from datetime import datetime

from qgis.PyQt.QtCore import QDate, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox, QDateEdit, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout,
)

from ...qt_compat import FRAME_SHAPE_STYLED_PANEL, POPUP_WINDOW_FLAG
from ...time_series.settings.model import XAxisSettings


class ManualXAxisPopup(QFrame):
    """Anchored transactional editor for independent automatic X bounds."""

    applyRequested = pyqtSignal(str, str, object, object)
    cancelRequested = pyqtSignal()
    currentViewRequested = pyqtSignal()
    previewRequested = pyqtSignal(str, str, object, object)

    def __init__(self, parent=None):
        """Create per-bound Auto controls, date editors, and actions."""
        super().__init__(parent, POPUP_WINDOW_FLAG)
        self.setObjectName("popup_manual_x_axis")
        self.setFrameShape(FRAME_SHAPE_STYLED_PANEL)
        self._closing_after_commit = False
        self._loading = False
        self._data_range = (None, None)
        self._manual_range = (None, None)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        title = QLabel("Time range", self)
        title.setObjectName("label_manual_x_axis_title")
        layout.addWidget(title)

        form = QGridLayout()
        form.setColumnStretch(2, 1)
        self.start_edit = self._dateEditor("Manual X-axis start date")
        self.end_edit = self._dateEditor("Manual X-axis end date")
        self.start_auto_checkbox = QCheckBox("", self)
        self.end_auto_checkbox = QCheckBox("", self)
        self.start_auto_checkbox.setObjectName("check_x_axis_start_auto")
        self.end_auto_checkbox.setObjectName("check_x_axis_end_auto")
        self.start_auto_checkbox.setAccessibleName("Use automatic X-axis start from data")
        self.end_auto_checkbox.setAccessibleName("Use automatic X-axis end from data")
        form.addWidget(QLabel("Auto", self), 0, 1)
        form.addWidget(QLabel("Value", self), 0, 2)
        form.addWidget(QLabel("Start", self), 1, 0)
        form.addWidget(self.start_auto_checkbox, 1, 1)
        form.addWidget(self.start_edit, 1, 2)
        form.addWidget(QLabel("End", self), 2, 0)
        form.addWidget(self.end_auto_checkbox, 2, 1)
        form.addWidget(self.end_edit, 2, 2)
        layout.addLayout(form)

        self.current_view_button = QPushButton("Use current view", self)
        layout.addWidget(self.current_view_button)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_button = QPushButton("Cancel", self)
        self.apply_button = QPushButton("Apply", self)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.apply_button)
        layout.addLayout(actions)

        self.start_auto_checkbox.toggled.connect(self._autoToggled)
        self.end_auto_checkbox.toggled.connect(self._autoToggled)
        self.start_edit.dateChanged.connect(self._manualDateChanged)
        self.end_edit.dateChanged.connect(self._manualDateChanged)
        self.cancel_button.clicked.connect(self.close)
        self.apply_button.clicked.connect(self._apply)
        self.current_view_button.clicked.connect(self.currentViewRequested.emit)

    def _dateEditor(self, accessible_name):
        """Create one project-compatible calendar date editor."""
        editor = QDateEdit(self)
        editor.setCalendarPopup(True)
        editor.setDisplayFormat("yyyy-MM-dd")
        editor.setAccessibleName(accessible_name)
        return editor

    @staticmethod
    def _toQDate(value):
        """Convert a Python date-like value to QDate."""
        return QDate(value.year, value.month, value.day)

    @staticmethod
    def _toDatetime(value):
        """Convert QDate to a midnight datetime."""
        return datetime(value.year(), value.month(), value.day())

    def openForBounds(
        self, manual_start, manual_end, data_start, data_end,
        editor_start_policy, editor_end_policy,
    ):
        """Load retained drafts and the last committed per-bound editor policies."""
        self._loading = True
        self._data_range = (data_start, data_end)
        self._manual_range = (
            data_start if manual_start is None else manual_start,
            data_end if manual_end is None else manual_end,
        )
        try:
            self.start_auto_checkbox.setChecked(editor_start_policy == "from_data")
            self.end_auto_checkbox.setChecked(editor_end_policy == "from_data")
            self._showBounds()
        finally:
            self._loading = False
        self._closing_after_commit = False
        self._updateState()

    def openForRange(self, start, end):
        """Load a Manual/Manual candidate range for backward-compatible callers."""
        self.openForBounds(start, end, start, end, "manual", "manual")

    def range(self):
        """Return retained manual drafts independently of Auto selections."""
        return self._manual_range

    def policies(self):
        """Return the canonical policy pair represented by the checkboxes."""
        return (
            "from_data" if self.start_auto_checkbox.isChecked() else "manual",
            "from_data" if self.end_auto_checkbox.isChecked() else "manual",
        )

    def draftState(self):
        """Return a canonical draft state for shared effective-range resolution."""
        return XAxisSettings(
            start_policy=self.policies()[0], end_policy=self.policies()[1],
            manual_start=self._manual_range[0], manual_end=self._manual_range[1],
        )

    def activeRange(self):
        """Return the valid effective range, or None when the draft is invalid."""
        return self.draftState().effective_range(*self._data_range)

    def _setEditor(self, editor, value):
        """Set one editor value without emitting preview changes."""
        if value is None:
            return
        previous = editor.blockSignals(True)
        try:
            editor.setDate(self._toQDate(value))
        finally:
            editor.blockSignals(previous)

    def _showBounds(self):
        """Display each effective bound and independently enable its editor."""
        data_start, data_end = self._data_range
        manual_start, manual_end = self._manual_range
        start_auto = self.start_auto_checkbox.isChecked()
        end_auto = self.end_auto_checkbox.isChecked()
        self._setEditor(self.start_edit, data_start if start_auto else manual_start)
        self._setEditor(self.end_edit, data_end if end_auto else manual_end)
        self.start_edit.setEnabled(not start_auto)
        self.end_edit.setEnabled(not end_auto)

    def _manualDateChanged(self, *_args):
        """Update enabled manual drafts and preview one valid effective range."""
        if self._loading:
            return
        start, end = self._manual_range
        if self.start_edit.isEnabled():
            start = self._toDatetime(self.start_edit.date())
        if self.end_edit.isEnabled():
            end = self._toDatetime(self.end_edit.date())
        self._manual_range = (start, end)
        self._updateState(preview=True)

    def _autoToggled(self, _checked):
        """Refresh the affected bound presentation and preview exactly once."""
        if self._loading:
            return
        self._showBounds()
        self._updateState(preview=True)

    def _updateState(self, preview=False):
        """Validate the effective range and optionally request one live preview."""
        effective = self.activeRange()
        self.apply_button.setEnabled(effective is not None)
        if preview and effective is not None:
            self.previewRequested.emit(*self.policies(), *self._manual_range)

    def _apply(self):
        """Emit both policies and retained manual drafts, then close."""
        if not self.apply_button.isEnabled():
            return
        self._closing_after_commit = True
        self.applyRequested.emit(*self.policies(), *self._manual_range)
        self.close()

    def closeAfterCommit(self):
        """Close after an immediate commit without emitting Cancel."""
        self._closing_after_commit = True
        self.close()

    def closeEvent(self, event):
        """Treat dismissal and Escape as transaction cancellation."""
        if not self._closing_after_commit:
            self.cancelRequested.emit()
        self._closing_after_commit = False
        super().closeEvent(event)
