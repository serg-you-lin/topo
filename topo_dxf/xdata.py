"""
topo_dxf/xdata.py
-----------------
I metadati di un cluster (`topo.build_metadata`, lo schema di
`metadata_schema.py`: gli stessi di `save_json`/`save_xml`) come XDATA
sull'entità del contorno esterno di un DXF scritto da topo.
"""

import json
from typing import Optional

from topo import build_metadata
from topo.model import Cluster

from .layers import LAYER_OUTER

def _outer_entity(doc):
    """L'entità su layer OuterContour che porta gli XDATA: prima una polilinea,
    altrimenti un cerchio. None se non c'è."""
    msp = doc.modelspace()
    for query in ("LWPOLYLINE POLYLINE", "CIRCLE"):
        for entity in msp.query(query):
            if entity.dxf.layer == LAYER_OUTER:
                return entity
    return None


def write_metadata_to_dxf(doc, cluster: Cluster, extra: Optional[dict] = None):
    """
    Scrive i metadati come XDATA sull'entità OuterContour.
    I campi seguono metadata_schema.py — stessa fonte di save_json e save_xml.
    Supporta LWPOLYLINE, POLYLINE e CIRCLE su layer OuterContour.

    `extra`: campi extra del chiamante per questo cluster — vedi `save_json`.
    """
    try:
        outer_entity = _outer_entity(doc)

        if outer_entity is None:
            print("  [WARN] write_metadata_to_dxf: nessuna entità su OuterContour.")
            return

        app_id = 'TOPO'
        if app_id not in doc.appids:
            doc.appids.add(app_id)

        meta = build_metadata(cluster, extra=extra)

        outer_entity.set_xdata(app_id, [
            (1000, json.dumps(meta, ensure_ascii=False)),
        ])

    except Exception as ex:
        print(f"  [WARN] write_metadata_to_dxf: {ex}")


def read_metadata_from_dxf(doc) -> dict:
    """
    Legge i metadati TOPO XDATA dall'entità OuterContour.
    Cerca su LWPOLYLINE, POLYLINE e CIRCLE.

    Returns:
        dict con i metadati secondo schema — o dict vuoto.
    """
    try:
        outer_entity = _outer_entity(doc)

        if outer_entity is None:
            return {}

        xdata = outer_entity.get_xdata('TOPO')
        if not xdata:
            return {}

        for tag in xdata:
            if tag.code == 1000:
                return json.loads(tag.value)

        return {}

    except Exception:
        return {}
