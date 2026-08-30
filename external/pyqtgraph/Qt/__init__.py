"""
This module exists to smooth out some of the differences between Qt versions.

* Reuse the PyQt binding selected by QGIS.
* Allow retained pyqtgraph code to import QtCore/QtGui/QtWidgets through one facade.
"""
import contextlib
import os
import platform
import re
import sys
import time
import warnings
from importlib import resources

PYSIDE = 'PySide'
PYSIDE2 = 'PySide2'
PYSIDE6 = 'PySide6'
PYQT4 = 'PyQt4'
PYQT5 = 'PyQt5'
PYQT6 = 'PyQt6'


class FailedImport(object):
    """Used to defer ImportErrors until we are sure the module is needed."""
    def __init__(self, err):
        self.err = err
        
    def __getattr__(self, attr):
        raise self.err


# Make a loadUiType function like PyQt has

# Credit:
# http://stackoverflow.com/questions/4442286/python-code-genration-with-pyside-uic/14195313#14195313

class _StringIO(object):
    """Alternative to built-in StringIO needed to circumvent unicode/ascii issues"""
    def __init__(self):
        self.data = []
    
    def write(self, data):
        self.data.append(data)
        
    def getvalue(self):
        return ''.join(map(str, self.data)).encode('utf8')

    
def _loadUiType(uiFile):
    raise RuntimeError(
        "PySide UI compilation is disabled in this QGIS-vendored PyQtGraph. "
    )


# For historical reasons, pyqtgraph maintains a Qt4-ish interface back when
# there wasn't a QtWidgets module. This _was_ done by monkey-patching all of
# QtWidgets into the QtGui module. This monkey-patching modifies QtGui at a
# global level.
# To avoid this, we now maintain a local "mirror" of QtCore, QtGui and QtWidgets.
# Thus, when monkey-patching happens later on in this file, they will only affect
# the local modules and not the global modules.
def _copy_attrs(src, dst):
    for o in dir(src):
        if not hasattr(dst, o):
            setattr(dst, o, getattr(src, o))

from . import QtCore, QtGui, QtWidgets, compat
from .compat import exec_qt

# This vendored pyqtgraph runs only inside QGIS. Reuse the binding selected by
# QGIS instead of probing or loading an independent PyQt/PySide installation.
from qgis.PyQt import QtCore as _QgisQtCore
from qgis.PyQt import QtGui as _QgisQtGui
from qgis.PyQt import QtWidgets as _QgisQtWidgets
from qgis.PyQt import sip, uic

_copy_attrs(_QgisQtCore, QtCore)
_copy_attrs(_QgisQtGui, QtGui)
_copy_attrs(_QgisQtWidgets, QtWidgets)

_pyqt_major = int(QtCore.PYQT_VERSION_STR.split('.', 1)[0])
QT_LIB = PYQT6 if _pyqt_major >= 6 else PYQT5

try:
    from qgis.PyQt import QtSvg
except ImportError as err:
    QtSvg = FailedImport(err)

try:
    from qgis.PyQt import QtTest
except ImportError as err:
    QtTest = FailedImport(err)

if QT_LIB == PYQT6:
    try:
        from qgis.PyQt import QtOpenGLWidgets
    except ImportError as err:
        QtOpenGLWidgets = FailedImport(err)

VERSION_INFO = QT_LIB + ' ' + QtCore.PYQT_VERSION_STR + ' Qt ' + QtCore.QT_VERSION_STR


if QT_LIB in [PYQT6, PYSIDE6]:
    # We're using Qt6 which has a different structure so we're going to use a shim to
    # recreate the Qt5 structure

    if not isinstance(QtOpenGLWidgets, FailedImport):
        QtWidgets.QOpenGLWidget = QtOpenGLWidgets.QOpenGLWidget

    # PySide6 incorrectly placed QFileSystemModel inside QtWidgets
    if QT_LIB == PYSIDE6 and hasattr(QtWidgets, 'QFileSystemModel'):
        module = getattr(QtWidgets, "QFileSystemModel")
        setattr(QtGui, "QFileSystemModel", module)

else:
    # Shim Qt5 namespace to match Qt6
    module_whitelist = [
        "QAction",
        "QActionGroup",
        "QFileSystemModel",
        "QShortcut",
        "QUndoCommand",
        "QUndoGroup",
        "QUndoStack",
    ]
    for module in module_whitelist:
        attr = getattr(QtWidgets, module)
        setattr(QtGui, module, attr)


# Common to PySide2 and PySide6
if QT_LIB in [PYSIDE2, PYSIDE6]:
    QtVersion = QtCore.__version__
    loadUiType = _loadUiType
    isQObjectAlive = shiboken.isValid

    # PySide does not implement qWait
    if not isinstance(QtTest, FailedImport):
        if not hasattr(QtTest.QTest, 'qWait'):
            @staticmethod
            def qWait(msec):
                start = time.time()
                QtWidgets.QApplication.processEvents()
                while time.time() < start + msec * 0.001:
                    QtWidgets.QApplication.processEvents()
            QtTest.QTest.qWait = qWait

    compat.wrapinstance = shiboken.wrapInstance
    compat.unwrapinstance = lambda x : shiboken.getCppPointer(x)[0]
    compat.voidptr = shiboken.VoidPtr

# Common to PyQt5 and PyQt6
if QT_LIB in [PYQT5, PYQT6]:
    QtVersion = QtCore.QT_VERSION_STR

    # PyQt, starting in v5.5, calls qAbort when an exception is raised inside
    # a slot. To maintain backward compatibility (and sanity for interactive
    # users), we install a global exception hook to override this behavior.
    if sys.excepthook == sys.__excepthook__:
        sys_excepthook = sys.excepthook
        def pyqt_qabort_override(*args, **kwds):
            return sys_excepthook(*args, **kwds)
        sys.excepthook = pyqt_qabort_override
    
    def isQObjectAlive(obj):
        return not sip.isdeleted(obj)
    
    loadUiType = uic.loadUiType

    QtCore.Signal = QtCore.pyqtSignal

    compat.wrapinstance = sip.wrapinstance
    compat.unwrapinstance = sip.unwrapinstance
    compat.voidptr = sip.voidptr

from . import internals

# Alert user if using Qt < 5.15, but do not raise exception
versionReq = [5, 15]
m = re.match(r'(\d+)\.(\d+).*', QtVersion)
if m is not None and list(map(int, m.groups())) < versionReq:
    warnings.warn(
        f"PyQtGraph supports Qt version >= {versionReq[0]}.{versionReq[1]},"
        f" but {QtVersion} detected.",
        RuntimeWarning,
        stacklevel=2
    )

App = QtWidgets.QApplication
# subclassing QApplication causes segfaults on PySide{2, 6} / Python 3.8.7+

QAPP = None
def mkQApp(name=None):
    """
    Creates new QApplication or returns current instance if existing.
    
    ============== ========================================================
    **Arguments:**
    name           (str) Application name, passed to Qt
    ============== ========================================================
    """
    global QAPP

    QAPP = QtWidgets.QApplication.instance()
    if QAPP is None:
        # We do not have an already instantiated QApplication
        # let's add some sane defaults

        # hidpi handling
        qtVersionCompare = tuple(map(int, QtVersion.split(".")))
        if qtVersionCompare > (6, 0):
            # Qt6 seems to support hidpi without needing to do anything so continue
            pass
        elif qtVersionCompare > (5, 14):
            os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
            QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(
                QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
            )
        else:  # qt 5.12 and 5.13
            QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
            QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps)

        QAPP = QtWidgets.QApplication(sys.argv or ["pyqtgraph"])
        if QtVersion.startswith("6"):
            # issues with dark mode + windows + qt5
            QAPP.setStyle("fusion")

        # set the application icon
        # python 3.9 won't take "pyqtgraph.icons.peegee" directly
        traverse_path = resources.files("pyqtgraph.icons")  
        peegee_traverse_path = traverse_path.joinpath("peegee")

        # as_file requires I feed in a file from the directory...
        with resources.as_file(
            peegee_traverse_path.joinpath("peegee.svg")
        ) as path:
            # need the parent directory, not the filepath
            icon_path = path.parent

        applicationIcon = QtGui.QIcon()
        applicationIcon.addFile(
            os.fsdecode(icon_path / "peegee.svg"),
        )
        for sz in [128, 256, 512]:
            pathname = os.fsdecode(icon_path / f"peegee_{sz}px.png")
            applicationIcon.addFile(pathname, QtCore.QSize(sz, sz))

        # handles the icon showing up on the windows taskbar
        if platform.system() == 'Windows':
            import ctypes
            my_app_id = "pyqtgraph.Qt.mkQApp"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(my_app_id)
        QAPP.setWindowIcon(applicationIcon)

    # determine if dark mode
    try:
        # this only works in Qt 6.5+
        darkMode = QAPP.styleHints().colorScheme() == QtCore.Qt.ColorScheme.Dark
        with contextlib.suppress(TypeError):
            # some qt bindings raise a TypeError when using a UniqueConnection
            # to an already connected signal/slot
            QAPP.styleHints().colorSchemeChanged.connect(
                _onColorSchemeChange,
                type=QtCore.Qt.ConnectionType.UniqueConnection
            )
    except AttributeError:
        palette = QAPP.palette()
        windowTextLightness = palette.color(QtGui.QPalette.ColorRole.WindowText).lightness()
        windowLightness = palette.color(QtGui.QPalette.ColorRole.Window).lightness()
        darkMode = windowTextLightness > windowLightness
        with contextlib.suppress(TypeError):
            # some qt bindings raise a TypeError when using a UniqueConnection
            # to an already connected signal/slot
            QAPP.paletteChanged.connect(
                _onPaletteChange,
                type=QtCore.Qt.ConnectionType.UniqueConnection
            )
    QAPP.setProperty("darkMode", darkMode)

    if name is not None:
        QAPP.setApplicationName(name)
    return QAPP


def _onPaletteChange(palette):
    # Attempt to keep darkMode attribute up to date
    # QEvent.Type.PaletteChanged/ApplicationPaletteChanged will be emitted after
    # paletteChanged.emit()!
    # Using API deprecated in Qt 6.0
    app = mkQApp()
    windowTextLightness = palette.color(QtGui.QPalette.ColorRole.WindowText).lightness()
    windowLightness = palette.color(QtGui.QPalette.ColorRole.Window).lightness()
    darkMode = windowTextLightness > windowLightness
    app.setProperty('darkMode', darkMode)


def _onColorSchemeChange(colorScheme):
    # Attempt to keep darkMode attribute up to date
    # QEvent.Type.PaletteChanged/ApplicationPaletteChanged will be emitted before
    # QStyleHint().colorSchemeChanged.emit()!
    # Uses Qt 6.5+ API
    app = mkQApp()
    darkMode = colorScheme == QtCore.Qt.ColorScheme.Dark
    app.setProperty('darkMode', darkMode)


def exec():
    """Run the Qt application event loop using the active QGIS PyQt API."""
    return exec_qt(mkQApp())
