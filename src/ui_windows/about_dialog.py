"""Dedicated About dialog for InSAR Explorer."""

from qgis.PyQt.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ... import __version__


DOCUMENTATION_URL = "https://insar-explorer.eodeck.com/en/latest"
DATA_PREPARATION_URL = "https://insar-explorer.eodeck.com/en/latest/#data-preparation"
ZENODO_URL = "https://doi.org/10.5281/zenodo.14052813"
SOURCE_CODE_URL = "https://github.com/eodeck/insar-explorer"
ISSUES_URL = "https://github.com/eodeck/insar-explorer/issues"
PUBLICATION_URL = "https://ieeexplore.ieee.org/abstract/document/11313961"

PRODUCT_DESCRIPTION = (
    "InSAR Explorer is a QGIS plugin for interactive visualization and analysis "
    "of InSAR time-series data."
)
PUBLICATION_CITATION = (
    "M. H. Haghighi et al., “SARvey and InSAR Explorer: Open-source tools for "
    "InSAR data processing and visualization,” Proc. IGARSS 2025, pp. 9414–9417."
)


def _link_label(text, url, object_name=None):
    """Return a theme-aware rich-text label that opens one external URL."""
    label = QLabel(f'<a href="{url}">{text}</a>')
    label.setOpenExternalLinks(True)
    if object_name:
        label.setObjectName(object_name)
    return label


def _section_title(text):
    """Return a compact section heading using the active Qt font palette."""
    label = QLabel(text)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    return label


class AboutDialog(QDialog):
    """Show compact project, resource, citation, credit, and license details."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About InSAR Explorer")
        self.setMinimumSize(420, 320)
        self.resize(600, 540)
        self._build_ui()

    def _build_ui(self):
        """Build the dialog from structured, theme-aware Qt widgets."""
        outer_layout = QVBoxLayout(self)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        outer_layout.addWidget(scroll_area)

        content = QWidget(scroll_area)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(10)
        scroll_area.setWidget(content)

        title = QLabel("InSAR Explorer", content)
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 3)
        title.setFont(title_font)
        content_layout.addWidget(title)

        version = QLabel(f"Version {__version__}", content)
        version.setObjectName("about_version")
        content_layout.addWidget(version)

        description = QLabel(PRODUCT_DESCRIPTION, content)
        description.setObjectName("about_description")
        description.setWordWrap(True)
        content_layout.addWidget(description)

        content_layout.addWidget(_section_title("Resources"))
        resource_layout = QHBoxLayout()
        resource_layout.setSpacing(12)
        resource_layout.addWidget(
            _link_label("Documentation", DOCUMENTATION_URL, "about_documentation_link")
        )
        resource_layout.addWidget(
            _link_label("Data preparation", DATA_PREPARATION_URL, "about_data_preparation_link")
        )
        resource_layout.addWidget(
            _link_label("Sample data", ZENODO_URL, "about_sample_data_link")
        )
        resource_layout.addStretch(1)
        content_layout.addLayout(resource_layout)

        resource_layout_2 = QHBoxLayout()
        resource_layout_2.setSpacing(12)
        resource_layout_2.addWidget(
            _link_label("Source code", SOURCE_CODE_URL, "about_source_code_link")
        )
        resource_layout_2.addWidget(
            _link_label("Report an issue", ISSUES_URL, "about_issue_link")
        )
        resource_layout_2.addStretch(1)
        content_layout.addLayout(resource_layout_2)

        content_layout.addWidget(_section_title("Citation"))
        citation_intro = QLabel("If you use InSAR Explorer, please cite:", content)
        citation_intro.setWordWrap(True)
        content_layout.addWidget(citation_intro)

        citation = QLabel(
            f'{PUBLICATION_CITATION} '
            f'<a href="{PUBLICATION_URL}">DOI: 10.1109/IGARSS55030.2025.11313961</a>',
            content,
        )
        citation.setObjectName("about_citation")
        citation.setOpenExternalLinks(True)
        citation.setWordWrap(True)
        content_layout.addWidget(citation)

        zenodo_guidance = QLabel(
            'To refer to a specific version of InSAR Explorer, use the '
            f'<a href="{ZENODO_URL}">Zenodo DOI</a>.',
            content,
        )
        zenodo_guidance.setObjectName("about_zenodo_link")
        zenodo_guidance.setOpenExternalLinks(True)
        zenodo_guidance.setWordWrap(True)
        content_layout.addWidget(zenodo_guidance)

        content_layout.addWidget(_section_title("Credits"))
        credits = QLabel("Developed by Mahmud Haghighi", content)
        credits.setObjectName("about_credits")
        credits.setWordWrap(True)
        content_layout.addWidget(credits)

        content_layout.addWidget(_section_title("License"))
        license_label = QLabel("GNU General Public License v3.0", content)
        license_label.setObjectName("about_license")
        content_layout.addWidget(license_label)
        content_layout.addStretch(1)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        close_button = QPushButton("Close", self)
        close_button.setObjectName("about_close_button")
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        outer_layout.addLayout(button_layout)
