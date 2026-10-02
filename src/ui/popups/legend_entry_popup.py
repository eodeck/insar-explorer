"""Compact per-series editor for time-series legend entry state."""

from dataclasses import replace

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QTabWidget, QVBoxLayout, QWidget,
)

from ...qt_compat import POPUP_WINDOW_FLAG, SIZE_POLICY_EXPANDING, SIZE_POLICY_MINIMUM
from .defaults_menu import createDefaultsMenu
from ...models.time_series import SeriesLegendSettings
from ...time_series.legend_formatting import format_series_legend_label


class LegendEntryPopup(QWidget):
    """Edit only the current record's legend entry choices."""

    settingsChanged = pyqtSignal(object, str, str, bool, bool, bool, bool, bool)
    applySavedLegendDefaultRequested = pyqtSignal()
    saveLegendDefaultRequested = pyqtSignal()
    applyFactoryLegendDefaultRequested = pyqtSignal()
    applySavedRelatedDefaultRequested = pyqtSignal()
    saveRelatedDefaultRequested = pyqtSignal()
    applyFactoryRelatedDefaultRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, POPUP_WINDOW_FLAG)
        self.setObjectName("legendEntryPopup")
        self.setWindowTitle("Legend entry")
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("tabs_legend_entry")
        self.tabs.addTab(self._buildLegendTab(), "Main")
        self.tabs.addTab(self._buildRelatedTab(), "Related")
        layout.addWidget(self.tabs)
        self.field_combo.currentIndexChanged.connect(self._emitSettings)
        self.include_label_checkbox.toggled.connect(self._emitSettings)
        self.include_field_checkbox.toggled.connect(self._emitSettings)
        self.prefix_edit.editingFinished.connect(self._emitSettings)
        self.suffix_edit.editingFinished.connect(self._emitSettings)
        self.prefix_edit.textChanged.connect(self._updatePreview)
        self.suffix_edit.textChanged.connect(self._updatePreview)
        self.field_combo.currentIndexChanged.connect(self._updatePreview)
        self.include_label_checkbox.toggled.connect(self._updatePreview)
        self.include_field_checkbox.toggled.connect(self._updatePreview)
        for checkbox in (self.fit_checkbox, self.replica_checkbox, self.ensemble_checkbox):
            checkbox.toggled.connect(self._emitSettings)

    def _buildLegendTab(self):
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        self.target_label = QLabel(tab)
        self.target_label.setObjectName("label_legend_entry_target")
        self.include_label_checkbox = QCheckBox("Include label", tab)
        self.include_label_checkbox.setObjectName("check_legend_entry_include_label")
        self.include_field_checkbox = QCheckBox("Include field", tab)
        self.include_field_checkbox.setObjectName("check_legend_entry_include_field")
        self.field_combo = QComboBox(tab)
        self.field_combo.setObjectName("combo_legend_entry_field")
        self.field_combo.setAccessibleName("Legend field")
        self.prefix_edit = QLineEdit(tab)
        self.prefix_edit.setObjectName("edit_legend_entry_prefix")
        self.prefix_edit.setAccessibleName("Legend field prefix")
        self.prefix_edit.setMaxLength(32)
        self.suffix_edit = QLineEdit(tab)
        self.suffix_edit.setObjectName("edit_legend_entry_suffix")
        self.suffix_edit.setAccessibleName("Legend field suffix")
        self.suffix_edit.setMaxLength(32)
        self.preview_label = QLabel(tab)
        self.preview_label.setObjectName("label_legend_entry_preview")
        self.preview_label.setWordWrap(True)
        self.preview_label.setSizePolicy(SIZE_POLICY_EXPANDING, SIZE_POLICY_MINIMUM)
        form.addRow("Editing", self.target_label)
        form.addRow(self.include_label_checkbox)
        form.addRow(self.include_field_checkbox)
        form.addRow("Field", self.field_combo)
        form.addRow("Prefix", self.prefix_edit)
        form.addRow("Suffix", self.suffix_edit)
        form.addRow("Preview", self.preview_label)
        layout.addLayout(form)
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
        group = QGroupBox("Show in legend", tab)
        related_layout = QVBoxLayout(group)
        self.fit_checkbox = QCheckBox("Fit", group)
        self.fit_checkbox.setObjectName("check_legend_entry_fit")
        self.replica_checkbox = QCheckBox("Replica", group)
        self.replica_checkbox.setObjectName("check_legend_entry_replica")
        self.ensemble_checkbox = QCheckBox("Ensemble", group)
        self.ensemble_checkbox.setObjectName("check_legend_entry_ensemble")
        related_layout.addWidget(self.fit_checkbox)
        related_layout.addWidget(self.replica_checkbox)
        related_layout.addWidget(self.ensemble_checkbox)
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
        self._record = record
        widgets = (self.field_combo, self.include_label_checkbox, self.include_field_checkbox, self.prefix_edit, self.suffix_edit, self.fit_checkbox, self.replica_checkbox, self.ensemble_checkbox)
        blocked = [widget.blockSignals(True) for widget in widgets]
        try:
            self.target_label.setText(str(record.presentation.label or "Unnamed"))
            self.field_combo.clear()
            for name in fields:
                self.field_combo.addItem(name, name)
            index = self.field_combo.findData(settings.field_name)
            self.field_combo.setCurrentIndex(index if index >= 0 else (0 if fields else -1))
            self.prefix_edit.setText(settings.prefix); self.suffix_edit.setText(settings.suffix)
            self.include_label_checkbox.setChecked(settings.include_label)
            self.include_field_checkbox.setChecked(settings.include_field and index >= 0)
            self.fit_checkbox.setChecked(settings.include_fit)
            self.replica_checkbox.setChecked(settings.include_replica)
            self.ensemble_checkbox.setChecked(settings.include_ensemble)
            self.fit_checkbox.setEnabled(True)
            self.fit_checkbox.setToolTip("" if record.analysis.fit.enabled else "Applies when Fit is enabled.")
            self.replica_checkbox.setEnabled(True)
            self.replica_checkbox.setToolTip("" if record.analysis.replica.enabled else "Applies when Replica is enabled.")
            self.ensemble_checkbox.setEnabled(bool(record.data.hasEnsembleData()))
        finally:
            for widget, value in zip(widgets, blocked): widget.blockSignals(value)
        self._updateLegendControlStates()
        self._updatePreview()

    def settings(self):
        """Return the complete per-record entry configuration represented by the controls."""
        return (self.field_combo.currentData(), self.prefix_edit.text(), self.suffix_edit.text(), self.include_label_checkbox.isChecked(), self.include_field_checkbox.isChecked(),
                self.fit_checkbox.isChecked(), self.replica_checkbox.isChecked(), self.ensemble_checkbox.isChecked())

    def _updateLegendControlStates(self):
        """Keep point and polygon controls in a valid non-empty configuration."""
        record = getattr(self, "_record", None)
        if record is None:
            return
        is_point = record.target is not None and record.target.kind.value == "point"
        self.legend_defaults_button.save_default_action.setEnabled(is_point)
        has_field = bool(is_point and self.field_combo.count())
        include_label = self.include_label_checkbox.isChecked()
        include_field = self.include_field_checkbox.isChecked() and has_field
        if not is_point:
            include_label, include_field = True, False
        elif not include_label and not include_field:
            include_label = True
        widgets = (self.include_label_checkbox, self.include_field_checkbox)
        blocked = [widget.blockSignals(True) for widget in widgets]
        try:
            self.include_label_checkbox.setChecked(include_label)
            self.include_field_checkbox.setChecked(include_field)
        finally:
            for widget, value in zip(widgets, blocked): widget.blockSignals(value)
        self.include_label_checkbox.setEnabled(is_point and include_field)
        self.include_field_checkbox.setEnabled(is_point and has_field and include_label)
        self.field_combo.setEnabled(is_point and self.field_combo.count() > 0)
        self.prefix_edit.setEnabled(is_point and include_field)
        self.suffix_edit.setEnabled(is_point and include_field)
        if not is_point:
            self.include_label_checkbox.setToolTip("Polygon legend entries use the series label in this version.")
            self.field_combo.setToolTip("Fields are available for point-vector selections only.")

    def _updatePreview(self, *_args):
        """Render a non-mutating preview through the shared record formatter."""
        record = getattr(self, "_record", None)
        if record is None:
            return
        self._updateLegendControlStates()
        field_name, prefix, suffix, include_label, include_field, include_fit, include_replica, include_ensemble = self.settings()
        settings = SeriesLegendSettings(
            field_name=field_name, prefix=prefix, suffix=suffix, include_label=include_label, include_field=include_field,
            include_fit=include_fit, include_replica=include_replica, include_ensemble=include_ensemble,
        )
        preview = format_series_legend_label(replace(record, presentation=replace(record.presentation, legend=settings)))
        self.preview_label.setText(preview or "No main legend entry")
        self.preview_label.updateGeometry()
        if self.isVisible():
            width = self.width()
            self.adjustSize()
            if width > 0:
                self.resize(width, self.height())

    def _emitSettings(self, *_args):
        self._updateLegendControlStates()
        self.settingsChanged.emit(*self.settings())
