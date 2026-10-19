"""
topo/tools/promote.py
---------------------
Una curva sciolta diventa parte di un cluster (MAP.md D137). Cosa sia — una
linea che un consumatore legge come piega, una guida accanto al pezzo — lo
decide chi chiama: topo la sposta da `result.loose` a `cluster.detected`
(D44, D90), mai in tutti e due i posti, mai persa.
"""

from __future__ import annotations

from typing import Any, Optional

from ..model.cluster import Cluster
from ..model.curve import ClosedCurve, OpenCurve
from ..model.detected import DetectedFeatures
from ..model.result import Result


def promote(result: Result, curve: OpenCurve | ClosedCurve, cluster: Cluster,
            name: str, item: Optional[Any] = None) -> None:
    """
    Toglie `curve` da `result.loose` e mette `item` (la curva stessa se
    `None`: oppure l'oggetto che il chiamante ne ha fatto) nella collezione
    `name` di `cluster.detected`, creandolo se manca.

    Non conta dove sta la curva: anche una curva fuori da ogni cluster
    (`cluster_ref is None`) si attacca a quello che il chiamante sceglie.

    Solleva `ValueError` se `curve` non è in `result.loose` o `cluster` non
    è in `result.clusters`: niente viene scritto due volte né perso.
    """
    at = next((k for k, c in enumerate(result.loose) if c is curve), None)
    if at is None:
        raise ValueError("promote(): la curva non è in result.loose")
    if not any(c is cluster for c in result.clusters):
        raise ValueError("promote(): il cluster non è in result.clusters")
    if cluster.detected is None:
        cluster.detected = DetectedFeatures()
    cluster.detected.add(name, curve if item is None else item)
    del result.loose[at]
