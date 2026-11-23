"""
topo_pdf/__init__.py
--------------------
topo's PDF adapter, EXPERIMENTAL: in the same repo and in the same
distribution (`pip install g-topo[pdf]`), it uses only topo's public names.
`load_pdf` returns list[Edge], not a Document: it cannot be passed to
`topo.heal()`, and the API may change or disappear. The work stalled in the
sister folder `forge-pdf-adapter` is resumed here.
"""

from .loader import load_pdf

__all__ = ["load_pdf"]
