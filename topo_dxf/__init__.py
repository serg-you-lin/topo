"""
topo_dxf/__init__.py
--------------------
topo's DXF adapter: a consumer of topo like any other, in the same repo and
the same distribution (`pip install g-topo[dxf]`), using only topo's public
names (MAP.md D123, D124, D129). topo does not know it exists.

    import topo, topo_dxf

    doc    = topo_dxf.load_dxf("part.dxf")           # DXF/DWG -> Document
    result = topo.heal(doc).faces()
    topo_dxf.to_dxf(result, doc).saveas("out.dxf")   # Result -> Drawing

    for part in topo.split(result):                  # one Result per part
        topo_dxf.to_dxf(part, doc).saveas(f"{part.clusters[0].label}.dxf")

Layers and colors are the caller's choice (`layers=`, `role_styles=`);
what the caller leaves unsaid is this adapter's default (`layers.py`).
"""

try:
    import ezdxf  # noqa: F401
except ImportError as exc:  # pragma: no cover - dipende dall'ambiente
    raise ImportError(
        "topo_dxf needs ezdxf: pip install g-topo[dxf]"
    ) from exc

from .loader import load_dxf, document_from_msp
from .writer import to_dxf
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
