"""Compact per-series editor for time-series legend entry state."""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QTabWidget, QVBoxLayout, QWidget,
)

from ...qt_compat import POPUP_WINDOW_FLAG
from .defaults_menu import createDefaultsMenu


class LegendEntryPopup(QWidget):
    """Edit only the current record's legend entry choices."""

    settingsChanged = pyqtSignal(object, str, str, bool, bool, bool)
    applySavedLegendDefaultRequested = pyqtSignal()
    saveLegendDefaultRequested = pyqtSignal()
    applyFactoryLegendDefaultRequested = pyqtSignal()
    applySavedRelatedDefaultRequested = pyqtSignal()
    saveRelatedDefaultRequested = pyqtSignal()
    applyFactoryRelatedDefaultRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, POPUP_WINDOW_FLAG)
        self.setObjectName("legendEntryPopup")
        self.setWindowTitle("Legend Entry")
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("tabs_legend_entry")
        self.tabs.addTab(self._buildLegendTab(), "Legend")
        self.tabs.addTab(self._buildRelatedTab(), "Related")
        layout.addWidget(self.tabs)
        self.field_combo.currentIndexChanged.connect(self._emitSettings)
        self.prefix_edit.editingFinished.connect(self._emitSettings)
        self.suffix_edit.editingFinished.connect(self._emitSettings)
        for checkbox in (self.fit_checkbox, self.replica_checkbox, self.ensemble_checkbox):
            checkbox.toggled.connect(self._emitSettings)

    def _buildLegendTab(self):
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        group = QGroupBox("Current time series", tab)
        form = QFormLayout(group)
        self.target_label = QLabel(group)
        self.target_label.setObjectName("label_legend_entry_target")
        self.field_combo = QComboBox(group)
        self.field_combo.setObjectName("combo_legend_entry_field")
        self.field_combo.setAccessibleName("Additional legend field")
        self.prefix_edit = QLineEdit(group)
        self.prefix_edit.setObjectName("edit_legend_entry_prefix")
        self.prefix_edit.setAccessibleName("Legend field prefix")
        self.suffix_edit = QLineEdit(group)
        self.suffix_edit.setObjectName("edit_legend_entry_suffix")
        self.suffix_edit.setAccessibleName("Legend field suffix")
        form.addRow("Editing", self.target_label)
        form.addRow("Additional field", self.field_combo)
        form.addRow("Prefix", self.prefix_edit)
        form.addRow("Suffix", self.suffix_edit)
        layout.addWidget(group)
        layout.addStretch(1)
        actions = QHBoxLayout(); actions.addStretch(1)
        self.legend_defaults_button = createDefaultsMenu(
            tab, self.applySavedLegendDefaultRequested.emit, self.saveLegendDefaultRequested.emit,
            self.applyFactoryLegendDefaultRequested.emit, "button_legend_entry_defaults",
        )
        actions.addWidget(self.legend_defaults_button); layout.addLayout(actions)
        return tab

    def _buildRelatedTab(self):
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        group = QGroupBox("Related entries", tab)
        form = QFormLayout(group)
        self.fit_checkbox = QCheckBox("Show in legend", group)
        self.fit_checkbox.setObjectName("check_legend_entry_fit")
        self.replica_checkbox = QCheckBox("Show in legend", group)
        self.replica_checkbox.setObjectName("check_legend_entry_replica")
        self.ensemble_checkbox = QCheckBox("Show in legend", group)
        self.ensemble_checkbox.setObjectName("check_legend_entry_ensemble")
        form.addRow("Fit", self.fit_checkbox)
        form.addRow("Replica", self.replica_checkbox)
        form.addRow("Ensemble", self.ensemble_checkbox)
        layout.addWidget(group); layout.addStretch(1)
        actions = QHBoxLayout(); actions.addStretch(1)
        self.related_defaults_button = createDefaultsMenu(
            tab, self.applySavedRelatedDefaultRequested.emit, self.saveRelatedDefaultRequested.emit,
            self.applyFactoryRelatedDefaultRequested.emit, "button_legend_entry_related_defaults",
        )
        actions.addWidget(self.related_defaults_button); layout.addLayout(actions)
        return tab

    def setRecord(self, record):
        """Populate controls from one immutable record without emitting changes."""
        settings = record.presentation.legend
        fields = () if record.target is None or record.target.kind.value != "point" else record.target_attributes.field_names()
        widgets = (self.field_combo, self.prefix_edit, self.suffix_edit, self.fit_checkbox, self.replica_checkbox, self.ensemble_checkbox)
        blocked = [widget.blockSignals(True) for widget in widgets]
        try:
            self.target_label.setText(str(record.presentation.label or "Unnamed"))
            self.field_combo.clear(); self.field_combo.addItem("None", None)
            for name in fields:
                self.field_combo.addItem(name, name)
            index = self.field_combo.findData(settings.field_name)
            self.field_combo.setCurrentIndex(max(0, index))
            has_fields = bool(fields)
            self.field_combo.setEnabled(has_fields)
            self.prefix_edit.setEnabled(has_fields); self.suffix_edit.setEnabled(has_fields)
            if not has_fields:
                self.field_combo.setToolTip("Additional fields are available for point-vector selections only.")
            self.prefix_edit.setText(settings.prefix); self.suffix_edit.setText(settings.suffix)
            self.fit_checkbox.setChecked(settings.include_fit)
            self.replica_checkbox.setChecked(settings.include_replica)
            self.ensemble_checkbox.setChecked(settings.include_ensemble)
            self.fit_checkbox.setEnabled(bool(record.analysis.fit.enabled))
            self.replica_checkbox.setEnabled(bool(record.analysis.replica.enabled))
            self.ensemble_checkbox.setEnabled(bool(record.data.hasEnsembleData()))
        finally:
            for widget, value in zip(widgets, blocked): widget.blockSignals(value)

    def settings(self):
        """Return the complete per-record entry configuration represented by the controls."""
        return (self.field_combo.currentData(), self.prefix_edit.text(), self.suffix_edit.text(),
                self.fit_checkbox.isChecked(), self.replica_checkbox.isChecked(), self.ensemble_checkbox.isChecked())

    def _emitSettings(self, *_args):
        self.settingsChanged.emit(*self.settings())
