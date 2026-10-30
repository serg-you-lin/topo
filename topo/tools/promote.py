"""
topo/tools/promote.py
---------------------
Una curva sciolta diventa parte di un cluster (MAP.md D137). Cosa sia — una
linea che un consumatore legge come piega, una guida accanto al pezzo — lo
decide chi chiama: topo la sposta da `result.loose` a `cluster.detected`
(D44, D90), mai in tutti e due i posti, mai persa. Più curve che il chiamante
legge come una cosa sola (un foro e la sua sede) diventano un solo item
(D172).
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from ..model.cluster import Cluster
from ..model.curve import ClosedCurve, OpenCurve
from ..model.detected import DetectedFeatures
from ..model.result import Result


def promote(result: Result,
            curves: OpenCurve | ClosedCurve | Sequence[OpenCurve | ClosedCurve],
            cluster: Cluster, name: str, item: Optional[Any] = None) -> None:
    """
    Toglie `curves` (una curva o più) da `result.loose` e mette un solo
    `item` nella collezione `name` di `cluster.detected`, creandolo se manca.
    `item` è l'oggetto che il chiamante ne ha fatto; con una curva sola può
    mancare e allora è la curva stessa.

    Non conta dove stanno le curve: anche una curva fuori da ogni cluster
    (`cluster_ref is None`) si attacca a quello che il chiamante sceglie.

    Solleva `ValueError`, senza toccare niente, se una curva non è in
    `result.loose` o è data due volte, se `curves` è vuoto, se `cluster` non
    è in `result.clusters`, o se le curve sono più d'una e `item` manca:
    niente viene scritto due volte né perso.
    """
    group = [curves] if isinstance(curves, (OpenCurve, ClosedCurve)) else list(curves)
    if not group:
        raise ValueError("promote(): nessuna curva")
    if item is None and len(group) > 1:
        raise ValueError("promote(): più curve sono un solo item, e item manca")
    at = {id(c): k for k, c in enumerate(result.loose)}
    if len({id(c) for c in group}) < len(group):
        raise ValueError("promote(): una curva è data due volte")
    if any(id(c) not in at for c in group):
        raise ValueError("promote(): una curva non è in result.loose")
    if not any(c is cluster for c in result.clusters):
        raise ValueError("promote(): il cluster non è in result.clusters")
    if cluster.detected is None:
        cluster.detected = DetectedFeatures()
    cluster.detected.add(name, group[0] if item is None else item)
    for k in sorted((at[id(c)] for c in group), reverse=True):
        del result.loose[k]
