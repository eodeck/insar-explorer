"""Tabbed editor for plot-wide time-series legend settings."""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLineEdit,
    QGroupBox, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from ...qt_compat import POPUP_WINDOW_FLAG
from .defaults_menu import createDefaultsMenu


class LegendPopup(QWidget):
    """Edit General and Entries legend settings with immediate runtime updates."""

    settingsChanged = pyqtSignal(str, bool, float, float)
    applySavedGeneralDefaultRequested = pyqtSignal()
    saveCurrentGeneralAsDefaultRequested = pyqtSignal()
    applyFactoryGeneralDefaultRequested = pyqtSignal()

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
        self.setWindowTitle("Plot Legend")

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("tabs_legend_settings")
        self.general_tab = self._buildGeneralTab()
        self.tabs.addTab(self.general_tab, "General")
        layout.addWidget(self.tabs)

        self.sync_font_size_checkbox.setChecked(True)
        self.font_size_spin.setValue(9.0)
        self.background_opacity_spin.setValue(80)
        self._syncFontSizeEnabled(True)

        self.location_combo.currentIndexChanged.connect(self._emit_settings)
        self.sync_font_size_checkbox.toggled.connect(self._syncFontSizeEnabled)
        self.sync_font_size_checkbox.toggled.connect(self._emit_settings)
        self.font_size_spin.valueChanged.connect(self._emit_settings)
        self.background_opacity_spin.valueChanged.connect(self._emit_settings)

    def _buildGeneralTab(self):
        tab = QWidget(self)
        layout = QVBoxLayout(tab)

        legend_group = QGroupBox("Legend", tab)
        legend_form = QFormLayout(legend_group)
        self.location_combo = QComboBox(legend_group)
        self.location_combo.setObjectName("combo_legend_location")
        for text, value in self.LOCATIONS:
            self.location_combo.addItem(text, value)
        self.location_combo.setAccessibleName("Legend location")
        self.location_combo.setToolTip("Choose where legends are placed in each plot.")
        self.location_combo.setMaximumWidth(140)
        self.background_opacity_spin = QSpinBox(legend_group)
        self.background_opacity_spin.setObjectName("spin_legend_background_opacity")
        self.background_opacity_spin.setRange(0, 100)
        self.background_opacity_spin.setSuffix("%")
        self.background_opacity_spin.setMaximumWidth(80)
        self.background_opacity_spin.setSingleStep(5)
        legend_form.addRow("Location", self.location_combo)
        legend_form.addRow("Background opacity", self.background_opacity_spin)
        layout.addWidget(legend_group)

        text_group = QGroupBox("Text", tab)
        text_form = QFormLayout(text_group)
        self.sync_font_size_checkbox = QCheckBox("Match Appearance text size", text_group)
        self.sync_font_size_checkbox.setObjectName("check_legend_sync_font_size")
        self.font_size_spin = QDoubleSpinBox(text_group)
        self.font_size_spin.setObjectName("spin_legend_font_size")
        self.font_size_spin.setRange(1.0, 200.0)
        self.font_size_spin.setDecimals(1)
        self.font_size_spin.setSingleStep(1.0)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setMaximumWidth(80)
        text_form.addRow(self.sync_font_size_checkbox)
        text_form.addRow("Text size", self.font_size_spin)
        layout.addWidget(text_group)
        layout.addStretch(1)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.general_defaults_button = createDefaultsMenu(
            tab, self.applySavedGeneralDefaultRequested.emit,
            self.saveCurrentGeneralAsDefaultRequested.emit,
            self.applyFactoryGeneralDefaultRequested.emit,
            "button_legend_general_defaults",
        )
        actions.addWidget(self.general_defaults_button)
        layout.addLayout(actions)
        return tab

    def _buildEntriesTab(self):
        tab = QWidget(self)
        layout = QVBoxLayout(tab)

        fit_group = QGroupBox("Fit", tab)
        fit_form = QFormLayout(fit_group)
        self.include_fit_checkbox = QCheckBox("Include fit", fit_group)
        self.include_fit_checkbox.setObjectName("check_legend_include_fit")
        self.fit_prefix_edit = self._line_edit(
            fit_group, "edit_legend_fit_prefix", "Fit label prefix"
        )
        self.fit_suffix_edit = self._line_edit(
            fit_group, "edit_legend_fit_suffix", "Fit label suffix"
        )
        fit_form.addRow(self.include_fit_checkbox)
        fit_form.addRow("Prefix", self.fit_prefix_edit)
        fit_form.addRow("Suffix", self.fit_suffix_edit)
        layout.addWidget(fit_group)

        replica_group = QGroupBox("Replica", tab)
        replica_form = QFormLayout(replica_group)
        self.include_replica_checkbox = QCheckBox("Include replica", replica_group)
        self.include_replica_checkbox.setObjectName("check_legend_include_replica")
        self.replica_prefix_edit = self._line_edit(
            replica_group, "edit_legend_replica_prefix", "Replica label prefix"
        )
        self.replica_suffix_edit = self._line_edit(
            replica_group, "edit_legend_replica_suffix", "Replica label suffix"
        )
        replica_form.addRow(self.include_replica_checkbox)
        replica_form.addRow("Prefix", self.replica_prefix_edit)
        replica_form.addRow("Suffix", self.replica_suffix_edit)
        layout.addWidget(replica_group)

        ensemble_group = QGroupBox("Ensemble", tab)
        ensemble_form = QFormLayout(ensemble_group)
        self.include_ensemble_checkbox = QCheckBox("Include ensemble", ensemble_group)
        self.include_ensemble_checkbox.setObjectName("check_legend_include_ensemble")
        self.ensemble_prefix_edit = self._line_edit(
            ensemble_group, "edit_legend_ensemble_prefix", "Ensemble label prefix"
        )
        self.ensemble_suffix_edit = self._line_edit(
            ensemble_group, "edit_legend_ensemble_suffix", "Ensemble label suffix"
        )
        ensemble_form.addRow(self.include_ensemble_checkbox)
        ensemble_form.addRow("Prefix", self.ensemble_prefix_edit)
        ensemble_form.addRow("Suffix", self.ensemble_suffix_edit)
        layout.addWidget(ensemble_group)
        layout.addStretch(1)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.entries_defaults_button = createDefaultsMenu(
            tab, self.applySavedEntriesDefaultRequested.emit,
            self.saveCurrentEntriesAsDefaultRequested.emit,
            self.applyFactoryEntriesAsDefaultRequested.emit,
            "button_legend_entries_defaults",
        )
        actions.addWidget(self.entries_defaults_button)
        layout.addLayout(actions)
        return tab

    @staticmethod
    def _line_edit(parent, object_name, accessible_name):
        editor = QLineEdit(parent)
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

    def _syncFontSizeEnabled(self, checked):
        self.font_size_spin.setEnabled(not checked)

    def settings(self):
        """Return the plot-wide LegendSettings fields managed by this popup."""
        return (
            str(self.location_combo.currentData() or "top_right"),
            self.sync_font_size_checkbox.isChecked(),
            float(self.font_size_spin.value()),
            float(self.background_opacity_spin.value()) / 100.0,
        )

    def setSettings(self, settings):
        """Refresh all controls without emitting runtime updates."""
        widgets = (
            self.location_combo, self.sync_font_size_checkbox, self.font_size_spin,
            self.background_opacity_spin,
        )
        previous = [widget.blockSignals(True) for widget in widgets]
        try:
            self.location_combo.setCurrentIndex(max(0, self.location_combo.findData(settings.location)))
            self.sync_font_size_checkbox.setChecked(settings.sync_font_size)
            self.font_size_spin.setValue(float(settings.font_size))
            self.background_opacity_spin.setValue(int(round(settings.background_opacity * 100)))
            self._syncFontSizeEnabled(settings.sync_font_size)
        finally:
            for widget, blocked in zip(widgets, previous):
                widget.blockSignals(blocked)

    def _emit_settings(self, *_args):
        self.settingsChanged.emit(*self.settings())
