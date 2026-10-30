"""
topo/core/geometry_input.py
---------------------------
Punto di ingresso per costruire un Document da geometria già nota — non da
un file. Stesso contratto di load_dxf/load_pdf (produce un Document, non
tipi interni), ma la "sorgente" è chi chiama: un generatore parametrico (es. uno
sviluppo di cono/cilindro calcolato altrove) o un ricostruttore di geometria da
punti (es. un contorno da computer vision già vettorializzato).

Chi chiama non importa NESSUN tipo interno di topo: le entità sono dict Python
puri. La traduzione in Edge (arrotondamento nodi, ruolo semantico) è identica
a quella di ogni adapter (`Edge.of`, la griglia dei nodi di topo) — cambia
solo la sorgente da tradurre. Non è un formato, quindi non sta tra gli
adapter: è un ingresso di topo (MAP.md D123, D125).

Pubblico da MAP.md D32 — provato da un caso reale (`bendly`, che lo usa in
`io/dxf.py` per portare uno sviluppo generato a `Document`).

Funzioni pubbliche:
    load_geometry — traduce una lista di descrizioni geometriche in Document
    load_segments — lo stesso, da segmenti di topo (`topo.geometry.rectangle`, ...)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

from .geometry.build import polygon
from .primitives.segments import LineSeg, ArcSeg, CircleSeg, BSplineSeg, EllipseSeg
from .topology.edge import Edge
from ..model.document import DEFAULT_NODE_TOLERANCE, Document
from ..model.role import normalize_role

_SUPPORTED_TYPES = frozenset({"line", "arc", "circle", "polygon", "spline", "ellipse"})


def _role_from(entity: Dict[str, Any]) -> str:
    """
    work_type stringa (stesso vocabolario di RoleRule.role) → ruolo. Un work_type
    sconosciuto viene conservato (via normalize_role), non schiacciato a UNKNOWN.
    """
    return normalize_role(entity.get("role"))


class GeometryReader:
    """
    Traduce descrizioni geometriche pure (dict) in Edge del dominio topo.

    Schema di ogni entità, per "type":
        line:     {"type": "line", "start": (x,y), "end": (x,y), "role": "outer"}
        arc:      {"type": "arc", "center": (x,y), "radius": r,
                   "start_angle": gradi, "end_angle": gradi,
                   "ccw": True, "role": "outer"}
        circle:   {"type": "circle", "center": (x,y), "radius": r, "role": "hole"}
        polygon:  {"type": "polygon", "points": [(x,y), ...], "role": "outer"}
                  — sempre chiuso: l'ultimo lato torna al primo punto (D96)
        spline:   {"type": "spline", "control_points": [(x,y), ...], "knots": [...],
                   "degree": 3, "weights": [...], "role": "outer"}
        ellipse:  {"type": "ellipse", "center": (x,y), "major_axis": (x,y),
                   "ratio": 0.5, "start_param": 0.0, "end_param": 2*pi,
                   "ccw": True, "role": "outer"}

    "role" è opzionale — stesso vocabolario di RoleRule.role (work_type stringa:
    "outer", "hole", "inner", "bending", "engrave", ...). Se omesso resta
    "unknown": non è un problema per il contorno più esterno di una
    parte, a cui HierarchyBuilder assegna comunque OUTER per posizione
    nell'albero di contenimento — serve solo per far riconoscere fori/inner
    espliciti prima che un consumatore li riclassifichi.

    Gli angoli di "arc" sono in GRADI (convenzione DXF/CAD, non i radianti di
    ArcSeg) — più naturale per chi consegna numeri calcolati a mano.

    Lo schema di "spline" ricalca 1:1 i campi di BSplineSeg (control_points,
    knots, degree, weights): chi ha in mano l'oggetto
    restituito da simplify_points() lo passa quasi senza toccarlo — vedi
    topo.core.primitives.fitting. Solo "control_points"/"knots"/"degree" sono
    obbligatori, il resto è opzionale.

    Lo schema di "ellipse" ricalca 1:1 i campi di EllipseSeg — stessa
    parametrizzazione del gruppo DXF ELLIPSE (center, major_axis come
    VETTORE dal centro, ratio, start_param/end_param in radianti). Solo
    "center"/"major_axis" sono obbligatori: "ratio"/"start_param"/
    "end_param" hanno gli stessi default DXF di un'ellisse piena
    (1.0 / 0.0 / 2π).
    """

    def __init__(self, entities: List[Dict[str, Any]]):
        self.entities = entities

    def to_edges(self) -> List[Edge]:
        edges: List[Edge] = []
        for i, entity in enumerate(self.entities):
            kind = str(entity.get("type", "")).lower()
            role = _role_from(entity)

            if kind == "line":
                edges.append(self._line_edge(entity, role))
            elif kind == "arc":
                edges.append(self._arc_edge(entity, role))
            elif kind == "circle":
                edges.append(self._circle_edge(entity, role))
            elif kind == "polygon":
                edges.extend(self._polygon_edges(entity, role))
            elif kind == "spline":
                edges.append(self._spline_edge(entity, role))
            elif kind == "ellipse":
                edges.append(self._ellipse_edge(entity, role))
            else:
                raise ValueError(
                    f"load_geometry(): tipo non supportato all'indice {i}: "
                    f"{entity.get('type')!r} — validi: {sorted(_SUPPORTED_TYPES)}"
                )
        return edges

    def _line_edge(self, entity: Dict[str, Any], role: str) -> Edge:
        return Edge.of(LineSeg(start=tuple(entity["start"]), end=tuple(entity["end"])), role)

    def _arc_edge(self, entity: Dict[str, Any], role: str) -> Edge:
        seg = ArcSeg(
            center=tuple(entity["center"]),
            radius=float(entity["radius"]),
            start_angle=math.radians(float(entity["start_angle"])),
            end_angle=math.radians(float(entity["end_angle"])),
            ccw=bool(entity.get("ccw", True)),
        )
        return Edge.of(seg, role)

    def _circle_edge(self, entity: Dict[str, Any], role: str) -> Edge:
        return Edge.of(CircleSeg(center=tuple(entity["center"]), radius=float(entity["radius"])), role)

    def _spline_edge(self, entity: Dict[str, Any], role: str) -> Edge:
        weights = entity.get("weights")
        seg = BSplineSeg(
            degree=int(entity.get("degree", 3)),
            control_points=[tuple(p) for p in entity["control_points"]],
            knots=[float(k) for k in entity["knots"]],
            weights=[float(w) for w in weights] if weights else None,
        )
        return Edge.of(seg, role)

    def _ellipse_edge(self, entity: Dict[str, Any], role: str) -> Edge:
        seg = EllipseSeg(
            center=tuple(entity["center"]),
            major_axis=tuple(entity["major_axis"]),
            ratio=float(entity.get("ratio", 1.0)),
            start_param=float(entity.get("start_param", 0.0)),
            end_param=float(entity.get("end_param", math.tau)),
            ccw=bool(entity.get("ccw", True)),
        )
        return Edge.of(seg, role)

    def _polygon_edges(self, entity: Dict[str, Any], role: str) -> List[Edge]:
        return [Edge.of(seg, role) for seg in polygon(entity["points"])]


# ---------------------------------------------------------------------------
# Entry point pubblico
# ---------------------------------------------------------------------------

def load_geometry(
    entities: List[Dict[str, Any]],
    *, tolerance: float = DEFAULT_NODE_TOLERANCE,
    source_path: str = "",
) -> Document:
    """
    Costruisce un Document da una lista di descrizioni geometriche pure —
    stesso contratto di load_dxf, ma la sorgente non è un file: è geometria già
    calcolata o ricostruita altrove (generatori parametrici, contorni
    vettorializzati da immagine, ...).

    Vedi GeometryReader per lo schema di ogni "type" di entità supportato
    (line / arc / circle / polygon / spline / ellipse).

    Esempio — settore anulare di uno sviluppo di cono:
        doc = topo.load_geometry([
            {"type": "arc",  "center": (0,0), "radius": r_est,
             "start_angle": -a/2, "end_angle": a/2, "role": "outer"},
            {"type": "line", "start": p_int_1, "end": p_est_1, "role": "outer"},
            {"type": "arc",  "center": (0,0), "radius": r_int,
             "start_angle": -a/2, "end_angle": a/2, "role": "outer"},
            {"type": "line", "start": p_int_2, "end": p_est_2, "role": "outer"},
        ])
        result = topo.heal(doc, label="sviluppo_cono")
        topo_dxf.to_dxf(result)

    Args:
        entities:    lista di dict geometrici (vedi GeometryReader)
        tolerance:   tolleranza di arrotondamento dei nodi topologici — stesso
                     significato di load_dxf(tolerance=...); passala identica
                     a heal() se la personalizzi
        source_path: etichetta libera per Document.source_path — non è un
                     file, serve solo per diagnostica/tracciabilità

    Returns:
        Document (edges + source_meta), pronto per heal().
    """
    edges = GeometryReader(entities).to_edges()
    return Document(
        edges=edges,
        source_path=source_path or "<load_geometry>",
        source_meta={"tolerance": tolerance},
    )


def load_segments(
    segments,
    *, tolerance: float = DEFAULT_NODE_TOLERANCE,
    role: str = "unknown",
    source_path: str = "",
) -> Document:
    """
    Un Document da segmenti di topo (`LineSeg`, `ArcSeg`, `CircleSeg`,
    ...) o da liste di segmenti, come le restituiscono i costruttori di
    `topo.geometry` (`rectangle`, `regular_polygon`, `polygon`, `circle`,
    `stadium`). Tutti gli edge prendono `role`. Stessa tolleranza dei nodi di
    `load_geometry` (D96).

        fg = topo.geometry
        doc = topo.load_segments(fg.rectangle(200, 100) + fg.circle(10))
        result = topo.heal(doc)
    """
    role = normalize_role(role)
    flat = []
    for item in segments:
        flat.extend(item if isinstance(item, (list, tuple)) else [item])
    edges = [Edge.of(seg, role) for seg in flat]
    return Document(
        edges=edges,
        source_path=source_path or "<load_segments>",
        source_meta={"tolerance": tolerance},
    )
