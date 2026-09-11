"""Compact editor for plot-wide time-series legend settings."""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget,
)

from ...qt_compat import POPUP_WINDOW_FLAG
from .defaults_menu import createDefaultsMenu


class LegendPopup(QWidget):
    """Edit legend settings immediately, without an Apply button."""

    settingsChanged = pyqtSignal(str, bool, bool, bool, str, str, str, str, str, str)
    applySavedDefaultRequested = pyqtSignal()
    saveCurrentAsDefaultRequested = pyqtSignal()
    applyFactoryDefaultRequested = pyqtSignal()

    LOCATIONS = (
        ("Top right", "top_right"),
        ("Top left", "top_left"),
        ("Bottom right", "bottom_right"),
        ("Bottom left", "bottom_left"),
        ("Right", "right"),
        ("Left", "left"),
    )

    def __init__(self, parent=None):
        super().__init__(parent, POPUP_WINDOW_FLAG)
        self.setObjectName("legendPopup")
        self.setWindowTitle("Labels")

        layout = QVBoxLayout(self)
        placement = QGroupBox("Legend", self)
        placement_form = QFormLayout(placement)
        self.location_combo = QComboBox(placement)
        self.location_combo.setObjectName("combo_legend_location")
        for text, value in self.LOCATIONS:
            self.location_combo.addItem(text, value)
        self.location_combo.setAccessibleName("Legend location")
        self.location_combo.setToolTip("Choose where legends are placed in each plot.")
        placement_form.addRow("Location", self.location_combo)
        layout.addWidget(placement)

        additional = QGroupBox("Additional entries", self)
        form = QFormLayout(additional)
        self.include_fit_checkbox = QCheckBox("Include fit entries", additional)
        self.include_fit_checkbox.setObjectName("check_legend_include_fit")
        self.include_replica_checkbox = QCheckBox("Include replica entries", additional)
        self.include_replica_checkbox.setObjectName("check_legend_include_replica")
        self.include_ensemble_checkbox = QCheckBox("Include ensemble entries", additional)
        self.include_ensemble_checkbox.setObjectName("check_legend_include_ensemble")
        self.fit_prefix_edit = self._line_edit("edit_legend_fit_prefix", "Fit label prefix")
        self.fit_suffix_edit = self._line_edit("edit_legend_fit_suffix", "Fit label suffix")
        self.replica_prefix_edit = self._line_edit("edit_legend_replica_prefix", "Replica label prefix")
        self.replica_suffix_edit = self._line_edit("edit_legend_replica_suffix", "Replica label suffix")
        self.ensemble_prefix_edit = self._line_edit("edit_legend_ensemble_prefix", "Ensemble label prefix")
        self.ensemble_suffix_edit = self._line_edit("edit_legend_ensemble_suffix", "Ensemble label suffix")
        form.addRow(self.include_fit_checkbox)
        form.addRow("Fit prefix", self.fit_prefix_edit)
        form.addRow("Fit suffix", self.fit_suffix_edit)
        form.addRow(self.include_replica_checkbox)
        form.addRow("Replica prefix", self.replica_prefix_edit)
        form.addRow("Replica suffix", self.replica_suffix_edit)
        form.addRow(self.include_ensemble_checkbox)
        form.addRow("Ensemble prefix", self.ensemble_prefix_edit)
        form.addRow("Ensemble suffix", self.ensemble_suffix_edit)
        layout.addWidget(additional)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.defaults_button = createDefaultsMenu(
            self, self.applySavedDefaultRequested.emit,
            self.saveCurrentAsDefaultRequested.emit,
            self.applyFactoryDefaultRequested.emit,
            "button_legend_defaults",
        )
        actions.addWidget(self.defaults_button)
        layout.addLayout(actions)

        self.location_combo.currentIndexChanged.connect(self._emit_settings)
        self.include_fit_checkbox.toggled.connect(self._emit_settings)
        self.include_replica_checkbox.toggled.connect(self._emit_settings)
        self.include_ensemble_checkbox.toggled.connect(self._emit_settings)
        for editor in self._text_editors():
            editor.editingFinished.connect(self._emit_settings)

    def _line_edit(self, object_name, accessible_name):
        editor = QLineEdit(self)
        editor.setObjectName(object_name)
        editor.setAccessibleName(accessible_name)
        editor.setMaximumWidth(160)
        return editor

    def _text_editors(self):
        return (
            self.fit_prefix_edit, self.fit_suffix_edit,
            self.replica_prefix_edit, self.replica_suffix_edit,
            self.ensemble_prefix_edit, self.ensemble_suffix_edit,
        )

    def settings(self):
        """Return popup-managed legend settings currently displayed."""
        return (
            str(self.location_combo.currentData() or "top_right"),
            self.include_fit_checkbox.isChecked(), self.include_replica_checkbox.isChecked(),
            self.include_ensemble_checkbox.isChecked(),
            self.fit_prefix_edit.text(), self.fit_suffix_edit.text(),
            self.replica_prefix_edit.text(), self.replica_suffix_edit.text(),
            self.ensemble_prefix_edit.text(), self.ensemble_suffix_edit.text(),
        )

    def setSettings(self, settings):
        """Refresh controls without emitting a change signal."""
        widgets = (
            self.location_combo, self.include_fit_checkbox,
            self.include_replica_checkbox, self.include_ensemble_checkbox,
        ) + self._text_editors()
        previous = [widget.blockSignals(True) for widget in widgets]
        try:
            index = self.location_combo.findData(settings.location)
            self.location_combo.setCurrentIndex(max(0, index))
            self.include_fit_checkbox.setChecked(settings.include_fit)
            self.include_replica_checkbox.setChecked(settings.include_replica)
            self.include_ensemble_checkbox.setChecked(settings.include_ensemble)
            self.fit_prefix_edit.setText(settings.fit_prefix)
            self.fit_suffix_edit.setText(settings.fit_suffix)
            self.replica_prefix_edit.setText(settings.replica_prefix)
            self.replica_suffix_edit.setText(settings.replica_suffix)
            self.ensemble_prefix_edit.setText(settings.ensemble_prefix)
            self.ensemble_suffix_edit.setText(settings.ensemble_suffix)
        finally:
            for widget, blocked in zip(widgets, previous):
                widget.blockSignals(blocked)

    def _emit_settings(self, *_args):
        self.settingsChanged.emit(*self.settings())
