"""
topo_pdf/__init__.py
--------------------
L'adapter PDF di topo, SPERIMENTALE (MAP.md D10): nello stesso repo e nella
stessa distribuzione (`pip install g-topo[pdf]`), usa solo i nomi pubblici di
topo (D123, D124, D129). `load_pdf` ritorna list[Edge], non un Document: non
è passabile a `topo.heal()`, e l'API può cambiare o sparire. Il lavoro fermo
nella cartella sorella `forge-pdf-adapter` si riprende qui (TODO.md).
"""

from .loader import load_pdf

__all__ = ["load_pdf"]
