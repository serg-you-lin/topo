"""
topo_dxf/recipes.py
-------------------
Le scorciatoie: mettono in fila i passi che stanno altrove (`topo.heal`,
`topo.split`, `to_dxf`) per il caller che non ha bisogno di orchestrarli a
mano.

Non c'è logica nuova qui — solo l'ordine comodo. Una lettura di processo
(fori, pieghe: snapbend) si fa sul result prima di `split`, non qui
(MAP.md D88).
"""

from __future__ import annotations

import os

import topo
from topo import DEFAULT_MIN_CLUSTER_AREA
from topo.model import Document, Result

from .layers import LAYER_ANNOTATION
from .writer import to_dxf


def split_to_files(doc: Document, output_folder, label="", source_file="",
                   tolerance=None, namer=None,
                   include_annotations=True,
                   min_area=DEFAULT_MIN_CLUSTER_AREA,
                   exclude_types=None,
                   annotation_layer=LAYER_ANNOTATION,
                   is_structural=None,
                   role_styles=None,
                   layers=None) -> Result:
    """
    Pipeline multi-pezzo + salvataggio su disco: heal → `topo.split` →
    `to_dxf` e `.saveas()` per parte. Il nome file è `f"{cluster.label}.dxf"`
    (cluster.label lo assegna `namer`). `is_structural` passa a `heal()`
    (vedi lì); `role_styles`, `layers`, `annotation_layer` ed
    `exclude_types` a `to_dxf()` (D128, D129).
    """
    result = topo.heal(doc, tolerance=tolerance, label=label, source_file=source_file,
                       is_structural=is_structural)

    if not result.is_valid or not result.clusters:
        return result

    parts = topo.split(result, namer=namer, min_area=min_area)

    os.makedirs(output_folder, exist_ok=True)
    for part in parts:
        drawing = to_dxf(part, doc,
                         include_annotations=include_annotations,
                         annotation_layer=annotation_layer,
                         role_styles=role_styles, layers=layers,
                         exclude_types=exclude_types)
        drawing.saveas(os.path.join(output_folder, f"{part.clusters[0].label}.dxf"))

    return result
