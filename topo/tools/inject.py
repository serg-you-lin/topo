"""
inject.py
-----------
Arricchimento CAM opzionale di un Result già prodotto da heal() (+ la lettura di un consumatore).

Da MAP.md D8: il conteggio delle feature (fori per tipo, pieghe, incisioni) NON
si fa più qui — è `cluster.summary`, una property derivata dal modello. `inject()`
resta solo per il suo lavoro unico: passare a un `data_injector` esterno i testi
che ricadono dentro l'outer di ogni parte (codice pezzo, materiale, spessore) e
mettere il dict risultante in `cluster.custom`.

I testi vengono da `result.texts` (il modello tipato prodotto da
load_dxf): niente più `msp` o liste sciolte. Filtro per contenimento nell'outer
della parte — l'equivalente di quello che faceva `anchor_texts()`, ma
applicato al volo qui perché `inject()` deve funzionare anche se quella fase non
è stata chiamata.

Contratto:
    - Opera su un Result già prodotto da heal() (+ la lettura di un consumatore).
    - Lavora sul modello: non tocca ezdxf.
    - Il data_injector è opzionale — senza, inject() non fa nulla.
    - Muta result.clusters[i].custom in-place e ritorna il result.

Flusso tipico:

    doc    = topo_dxf.load_dxf("pezzo.dxf", role_rules=topo.name_rules({"Bend": "bending"}))
    result = topo.heal(doc)
    topo.inject(result, data_injector=leggi_cartiglio)
    topo.save_json(result, ...)   # i conteggi vengono da cluster.summary
"""

from typing import Callable, Dict, List, Optional

from shapely.geometry import Point

from ..core.primitives.polygon_builder import curve_polygon
from .anchor import _nearest_within


def inject(result, *, data_injector: Optional[Callable] = None,
           snap_distance: float = 0.0) -> None:
    """
    Arricchisce i Cluster con i dati estratti da un `data_injector` esterno.

    **Muta** `result.clusters[i].custom` (e `result.warnings` se il
    `data_injector` fallisce) e ritorna `None` (D176).

    Args:
        result:        Result prodotto da heal() (+ la lettura di un consumatore).
        data_injector: `callable(Cluster, list[str]) -> dict`. Riceve i testi
                       contenuti nell'outer della parte, restituisce i campi da
                       mettere in `cluster.custom` (materiale, spessore, codice, ...).
        snap_distance: > 0 → un testo fuori da ogni parte va alla parte più vicina
                       se dista al massimo tanto dal suo contorno (stessa regola di
                       `anchor_texts`). Default 0.0: solo contenimento.
    """
    if not result.clusters or data_injector is None:
        return

    testi = _texts_by_part(result, snap_distance)
    for i, cluster in enumerate(result.clusters):
        if i not in testi:
            continue
        try:
            injected = data_injector(cluster, testi[i])
            if injected:
                cluster.custom.update(injected)
        except Exception as ex:
            result.warnings.append(
                f"data_injector fallito su {cluster.label}: {ex}"
            )


def _texts_by_part(result, snap_distance: float) -> Dict[int, List[str]]:
    """
    Testi di `result.texts` per indice di parte. Un testo coperto da più
    outer va a ciascuno; uno fuori da tutti va alla parte più vicina entro
    `snap_distance`, altrimenti a nessuna.
    """
    refs = [
        (i, poly)
        for i, c in enumerate(result.clusters)
        if c.outer is not None
        for poly in [curve_polygon(c.outer)]
        if poly is not None and not poly.is_empty
    ]
    testi: Dict[int, List[str]] = {i: [] for i, _ in refs}
    for ann in result.texts:
        if not ann.text:
            continue
        probe = Point(ann.position)
        parts = [i for i, poly in refs if poly.covers(probe)]
        if not parts:
            nearest = _nearest_within(probe, refs, snap_distance)
            parts = [] if nearest is None else [nearest]
        for i in parts:
            testi[i].append(ann.text)
    return testi
