import sys
import os

try:
    from .. import __version__, __date__
except ImportError:
    __version__ = "xx.xx.xx"
    __date__ = "2026.xx.xx"

about = f"""
        <h3>InSAR Explorer</h3>
        <p>  {__version__} ({__date__}) </p>
        <p style="text-align: justify;">
            <span style="margin-left: 10em;">InSAR Explorer is designed for interactive visualization and analysis of InSAR time series results.
            </span>
        </p>

        <h3>Citation</h3>
            <p style="text-align: justify;">
                If you use <em>InSAR Explorer</em> in your research, please cite:
                    <li>
                        <cite>
                            M.&nbsp;H.&nbsp;Haghighi&nbsp;,&nbsp;
                            A.&nbsp;Piter&nbsp;,&nbsp;
                            M.&nbsp;Motagh&nbsp;,&nbsp;
                            "SARvey and InSAR Explorer: Open-source tools for InSAR data processing and visualization,"
                            in
                            <em>Proc.&nbsp;2025 IEEE Int.&nbsp;Geosci.&nbsp;Remote Sens.&nbsp;Symp.&nbsp;(IGARSS)</em>,
                            Brisbane,&nbsp;Australia, 2025, pp.&nbsp;9414–9417.&nbsp;
                            <a href="https://ieeexplore.ieee.org/abstract/document/11313961">
                                doi: 10.1109/IGARSS55030.2025.11313961
                            </a>
                        </cite>
                    </li>
            </p>

            <p  style="text-align:justify;">
                To cite a specific version of InSAR Explorer, you can use the DOI available in the
                <a href="https://doi.org/10.5281/zenodo.14052813"> InSAR Explorer Zenodo repository
                </a>.</span>
            </p>
         <h3>Help</h3>
         <h4><a href="https://doi.org/10.5281/zenodo.14052813">Sample Data</a></h4>
         <h4><a href="https://insar-explorer.eodeck.com/en/latest/#data-preparation">
         Supported InSAR Processors</a></h4>
         <h4><a href="https://insar-explorer.eodeck.com/en/latest">Full Documentation</a></h4>
         <h4><a href="https://github.com/eodeck/insar-explorer">Source Code on GitHub</a></h4>
         <h4><a href="https://github.com/eodeck/insar-explorer/issues">Recommendations or Bug Report</a></h5>
         """
