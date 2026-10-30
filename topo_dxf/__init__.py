"""
topo_dxf/__init__.py
--------------------
L'adapter DXF di topo: un consumer di topo come un altro, nello stesso repo e
nella stessa distribuzione (`pip install g-topo[dxf]`), che usa solo i nomi
pubblici di topo (MAP.md D123, D124, D129). topo non sa che esiste.

    import topo, topo_dxf

    doc    = topo_dxf.load_dxf("pezzo.dxf")          # DXF/DWG → Document
    result = topo.heal(doc)
    topo_dxf.to_dxf(result, doc).saveas("out.dxf")   # Result → Drawing

    for part in topo.split(result):                  # un Result per parte
        topo_dxf.to_dxf(part, doc).saveas(f"{part.clusters[0].label}.dxf")

I layer e i colori sono scelte del chiamante (`layers=`, `role_styles=`);
quello che non dice è il default di questo adapter (`layers.py`).
"""

try:
    import ezdxf  # noqa: F401
except ImportError as exc:  # pragma: no cover - dipende dall'ambiente
    raise ImportError(
        "topo_dxf ha bisogno di ezdxf: pip install g-topo[dxf]"
    ) from exc

from .loader import load_dxf, document_from_msp
from .writer import to_dxf
from .xdata import write_metadata_to_dxf, read_metadata_from_dxf
from .inspect import inspect_dxf, inspect_file
from .layers import (
    DEFAULT_LAYERS,
    LAYER_ANNOTATION,
    LAYER_INNER,
    LAYER_OUTER,
    SKIP_LAYERS,
    TRASH_LAYER,
    LayerMap,
    role_to_dxf_layer,
)

__all__ = [
    "load_dxf",
    "document_from_msp",
    "to_dxf",
    "write_metadata_to_dxf",
    "read_metadata_from_dxf",
    "inspect_dxf",
    "inspect_file",
    "DEFAULT_LAYERS",
    "LAYER_ANNOTATION",
    "LAYER_INNER",
    "LAYER_OUTER",
    "SKIP_LAYERS",
    "TRASH_LAYER",
    "LayerMap",
    "role_to_dxf_layer",
]
