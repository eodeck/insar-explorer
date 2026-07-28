# coding=utf-8
"""Resources test.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 3 of the License, or
     (at your option) any later version.

"""

__author__ = 'insar-explorer@eodeck.com'
__date__ = '2024-11-01'
__copyright__ = 'Copyright 2024-2026, Mahmud Haghighi'

import unittest

from qgis.PyQt.QtGui import QIcon



class InsarExplorerDialogTest(unittest.TestCase):
    """Test rerources work."""

    def setUp(self):
        """Runs before each test."""
        pass

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_icon_png(self):
        """Test we can click OK."""
        path = ':/plugins/InsarExplorer/icon.svg'
        icon = QIcon(path)
        self.assertFalse(icon.isNull())

if __name__ == "__main__":
    suite = unittest.makeSuite(InsarExplorerResourcesTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)



