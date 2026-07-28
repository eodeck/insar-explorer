"""Compact editor for independent manual Time Series Y-axis bounds."""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...time_series.y_axis_range import resolve_manual_y_range
from ...qt_compat import (
    FRAME_SHAPE_STYLED_PANEL,
    POPUP_WINDOW_FLAG,
    SIZE_POLICY_FIXED,
)


class ManualYAxisPopup(QFrame):
    """Anchored transactional editor for independent Series and Residual ranges."""

    previewChanged = pyqtSignal(str, object, object)
    applyRequested = pyqtSignal(object, object, object, object, object, object, object, object, object, object)
    cancelRequested = pyqtSignal()
    currentViewRequested = pyqtSignal(str)

    def __init__(self, parent=None):
        """Create compact tabbed lower/upper Auto and numeric editors."""
        super().__init__(parent, POPUP_WINDOW_FLAG)
        self.setObjectName("popup_manual_y_axis")
        self.setFrameShape(FRAME_SHAPE_STYLED_PANEL)
        self._closing_after_apply = False
        self._loading = False
        self._editors = {}
        self._control_axes = {}
        self._changed = {"series": False, "residual": False}
        self._captured_exact = {"series": None, "residual": None}
        self._data_bounds = {"series": None, "residual": None}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        title = QLabel("Manual Y-axis", self)
        title.setObjectName("label_manual_y_axis_title")
        layout.addWidget(title)

        self.tabs = QTabWidget(self)
        self.series_tab = self._createAxisTab("series")
        self.residual_tab = self._createAxisTab("residual")
        self.tabs.addTab(self.series_tab, "Time series")
        self.tabs.addTab(self.residual_tab, "Residuals")
        layout.addWidget(self.tabs)

        self.residual_message = QLabel("Residual inactive.", self.residual_tab)
        self.residual_message.setToolTip("Residual inactive.")
        self.residual_message.setWordWrap(False)
        self.residual_tab.layout().insertWidget(0, self.residual_message)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_button = QPushButton("Cancel", self)
        self.apply_button = QPushButton("Apply", self)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.apply_button)
        layout.addLayout(actions)

        self.cancel_button.clicked.connect(self.close)
        self.apply_button.clicked.connect(self._apply)

    def _createAxisTab(self, axis_name):
        """Create one compact axis tab and register its controls."""
        tab = QWidget(self)
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(4, 6, 4, 4)
        outer.setSpacing(4)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        grid.addWidget(QLabel("Auto", tab), 0, 1)
        grid.addWidget(QLabel("Value", tab), 0, 2)
        controls = {}
        for row, bound in enumerate(("upper", "lower"), 1):
            auto = QCheckBox("", tab)
            auto.setAccessibleName(f"{axis_name} {bound} automatic Y-axis bound")
            value = QDoubleSpinBox(tab)
            value.setRange(-1000000000.0, 1000000000.0)
            value.setDecimals(1)
            value.setSingleStep(1.0)
            value.setFixedWidth(105)
            value.setSizePolicy(SIZE_POLICY_FIXED, SIZE_POLICY_FIXED)
            value.setAccessibleName(f"{axis_name} {bound} manual Y-axis bound")
            auto.toggled.connect(self._editorChanged)
            value.valueChanged.connect(self._editorChanged)
            self._control_axes[auto] = axis_name
            self._control_axes[value] = axis_name
            grid.addWidget(QLabel(bound.title(), tab), row, 0)
            grid.addWidget(auto, row, 1)
            grid.addWidget(value, row, 2)
            controls[bound] = (auto, value)
        self._editors[axis_name] = controls
        outer.addLayout(grid)
        use_current_view = QPushButton("Use current view", tab)
        use_current_view.setCheckable(False)
        use_current_view.clicked.connect(
            lambda _checked=False, name=axis_name: self.currentViewRequested.emit(name)
        )
        outer.addWidget(use_current_view)
        controls["use_current_view"] = use_current_view
        return tab

    def openForBounds(self, series_range, residual_range, series_data, residual_data, residual_active):
        """Load endpoint policies and retained values, seeding only missing drafts from data."""
        self._loading = True
        self._changed = {"series": False, "residual": False}
        self._captured_exact = {"series": None, "residual": None}
        self._data_bounds = {
            "series": tuple(series_data),
            "residual": tuple(residual_data),
        }
        for axis_name, manual, data_bounds in (
            ("series", series_range, series_data),
            ("residual", residual_range, residual_data),
        ):
            data_lower, data_upper = data_bounds
            for bound_name, active, retained, seeded in (
                ("lower", manual.lower, manual.retained_lower, data_lower),
                ("upper", manual.upper, manual.retained_upper, data_upper),
            ):
                auto, value = self._editors[axis_name][bound_name]
                draft = retained if retained is not None else seeded
                value.setValue(float(draft))
                auto.setChecked(active is None)
        self._loading = False
        self.setResidualActive(residual_active)
        self._updateState()
        self._closing_after_apply = False

    def setResidualActive(self, active):
        """Keep the Residual tab visible while toggling editor availability."""
        for bound_name in ("lower", "upper"):
            auto, value = self._editors["residual"][bound_name]
            auto.setEnabled(active)
            value.setEnabled(active and not auto.isChecked())
        self._editors["residual"]["use_current_view"].setEnabled(active)
        self.residual_message.setVisible(not active)


    def setCurrentView(self, axis_name, lower, upper):
        """Populate one tab from its visible Y-range without previewing or persisting."""
        if axis_name not in self._editors:
            return
        button = self._editors[axis_name]["use_current_view"]
        if not button.isEnabled():
            return
        self._loading = True
        for bound_name, value_number in (("lower", lower), ("upper", upper)):
            auto, value = self._editors[axis_name][bound_name]
            value.setValue(float(value_number))
            auto.setChecked(False)
        self._loading = False
        self._changed[axis_name] = True
        self._captured_exact[axis_name] = (float(lower), float(upper))
        self._updateState()

    def bounds(self, axis_name):
        """Return one tab's current bounds, using ``None`` for Auto."""
        captured = self._captured_exact.get(axis_name)
        if captured is not None:
            return captured
        controls = self._editors[axis_name]
        return tuple(
            None if controls[name][0].isChecked() else float(controls[name][1].value())
            for name in ("lower", "upper")
        )


    def retainedBounds(self, axis_name):
        """Return both numeric editor drafts regardless of Auto checkbox state."""
        captured = self._captured_exact.get(axis_name)
        if captured is not None:
            return captured
        controls = self._editors[axis_name]
        return tuple(float(controls[name][1].value()) for name in ("lower", "upper"))

    def _isValid(self, axis_name):
        data_bounds = self._data_bounds.get(axis_name)
        if data_bounds is None:
            return False
        lower, upper = self.bounds(axis_name)
        return resolve_manual_y_range(*data_bounds, lower, upper) is not None

    def _updateState(self):
        residual_active = self._editors["residual"]["lower"][0].isEnabled()
        for axis_name in ("series", "residual"):
            for bound_name in ("lower", "upper"):
                auto, value = self._editors[axis_name][bound_name]
                value.setEnabled(auto.isEnabled() and not auto.isChecked())
        self.apply_button.setEnabled(
            self._isValid("series") and (not residual_active or self._isValid("residual"))
        )

    def _editorChanged(self, *_args):
        self._updateState()
        if self._loading:
            return
        axis_name = self._control_axes.get(self.sender())
        if axis_name is None:
            return
        self._changed[axis_name] = True
        self._captured_exact[axis_name] = None
        if self._isValid(axis_name):
            self.previewChanged.emit(axis_name, *self.bounds(axis_name))

    def _apply(self):
        if not self.apply_button.isEnabled():
            return
        self._closing_after_apply = True
        self.applyRequested.emit(
            *self.bounds("series"),
            *self.bounds("residual"),
            *self.retainedBounds("series"),
            *self.retainedBounds("residual"),
            self._changed["series"],
            self._changed["residual"],
        )
        self.close()

    def closeAfterCommit(self):
        """Close after an external shortcut commits without emitting Cancel."""
        self._closing_after_apply = True
        self.close()

    def closeEvent(self, event):
        """Treat popup dismissal and Escape exactly like Cancel."""
        if not self._closing_after_apply:
            self.cancelRequested.emit()
        self._closing_after_apply = False
        super().closeEvent(event)
