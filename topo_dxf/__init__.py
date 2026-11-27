"""
topo_dxf/__init__.py
--------------------
topo's DXF adapter: a consumer of topo like any other, in the same repo and
the same distribution (`pip install g-topo[dxf]`), using only topo's public
names. topo does not know it exists.

    import topo, topo_dxf

    doc    = topo_dxf.load_dxf("part.dxf")           # DXF/DWG -> Document
    result = topo.heal(doc).faces()
    topo_dxf.to_dxf(result).saveas("out.dxf")   # Result -> Drawing

    for index, piece in enumerate(topo.split(result).pieces):   # one Result per piece
        topo_dxf.to_dxf(piece).saveas(f"piece_{index + 1}.dxf")

Layers and colors are the caller's choice (`layers=`, `role_styles=`);
what the caller leaves unsaid is this adapter's default (`layers.py`).
"""

try:
    import ezdxf  # noqa: F401
except ImportError as exc:  # pragma: no cover - depends on the environment
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
