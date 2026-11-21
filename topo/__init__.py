"""
topo
----
Deterministic 2D geometry engine: it repairs vector geometry and reads its
structure - closed contours, what lies inside what, what is connected.
Geometry and roles, no file format (MAP.md D123): files come in and go out
through the adapters, sibling packages in the same distribution (D124, D129;
the README shows them).

Public API - everything you need is here.
You do not have to import the internal modules directly.

    import topo

    plate = topo.geometry.rectangle(100, 60)
    hole = topo.geometry.circle(8, center=(20, 15))
    doc = topo.load_segments(plate + hole)    # or a Document from an adapter

    network = topo.heal(doc, label="part")    # the repair, once (D202)
    result = network.faces()                  # or network.outlines() for a sheet of views
    # holes, bends, engravings: a process reading, in snapbend (MAP.md D88)

    topo.save_json(result, "part.json")
    parts = topo.split(result)                # one Result per part, no format
"""

from .core.geometry_input import load_geometry, load_segments
from .core.readings.heal import heal
from .core.readings.network import Network
from .tools.anchor       import anchor_texts
# Un Result per parte, senza formato: ogni exporter ne scrive una (D124, D129)
from .tools.split        import split
from .rules.validator     import validate_document, validate_result
from .io.exporter         import to_json, save_json
# Conversione esplicita a shapely per overlay, buffer, WKT: il modello non
# espone tipi shapely (MAP.md D166).
from .io.shapes           import to_shapely
from .model         import (
    Result, Cluster, Contour, Document,
    Text,
    # cosa misura un testo, coi punti della sorgente (D264)
    MeasuredDistance, MeasuredRadius, MeasuredDiameter, MeasuredAngle,
    Overlay,
    # un avviso come in Rust: testo + campi, con la soglia che lo corregge (D227)
    Diagnostic,
)
# Un consumatore che marca la geometria prima di heal() (snapdraw: cornice /
# cartiglio) setta `edge.role` sugli Edge di `doc.edges` con uno slug ripulito
# da normalize_role, e is_structural_role dice se quel ruolo è contorno di
# pezzo o arredo che heal terrà fuori dal grafo. Vedi MAP.md D30.
from .model.role      import normalize_role, is_structural_role
# Regole del chiamante che assegnano il ruolo al load (D63).
from .model.role_rule import RoleRule, name_rules
# RoleStyle (D37, D128): come il chiamante vuole disegnato un ruolo, senza
# formato. Il dizionario {ruolo: RoleStyle} è suo e lo passa a ogni exporter.
from .model.style     import RoleStyle
# Stesso criterio che heal() usa internamente per escludere un edge dal grafo
# dei contorni (catene fra due nodi di branching, non sul bordo esterno, D111,
# D131) — senza dire cosa
# sia quell'edge. Un consumatore che vuole decidere `edge.role` prima di
# heal() con un'interpretazione propria (non "bending" come fa detect_flat()) lo
# chiama su doc.edges. Vedi MAP.md D55.
from .tools.non_contour import non_contour_candidates
# La geometria: fatti con nomi geometrici (forma di un contorno, cerchi
# concentrici, corde, rettangoli coperti, ...), tutti in `topo.geometry`.
# MAP.md D68, D91, D93-D95.
from .core import geometry
# Ogni soglia fissa di topo, in un file solo e non riassegnabile (D269).
from . import precision
# Tutto ciò che è esposto senza promessa di stabilità: i passi di faces() e di
# outlines(), il viewer, la lettura testuale, rotate_*, simplify_points
# (MAP.md D175 C, D176). Si scrive per intero: `topo.experimental.<nome>`.
from . import experimental
# Le primitive geometriche e i tipi del modello, pubblici: `topo.primitives`,
# `topo.model`. Sotto `topo.core` è interno (MAP.md D120).
from . import primitives, model
from .inspect             import inspect_document, inspect_result

try:
    from importlib.metadata import version as _pkg_version, PackageNotFoundError
    try:
        __version__ = _pkg_version("g-topo")
    except PackageNotFoundError:
        __version__ = "0.0.0+dev"
except ImportError:  # pragma: no cover
    __version__ = "0.0.0+dev"

__all__ = [
    # Geometria in ingresso (i file entrano dagli adapter)
    "load_geometry",
    "load_segments",
    # Validazione
    "validate_document",
    "validate_result",
    # Workflow
    "heal",
    "Network",
    "split",
    "anchor_texts",
    "geometry",
    "precision",
    "experimental",
    "primitives",
    "model",
    # Export
    "to_json",
    "save_json",
    "to_shapely",
    # Utilità
    # Ispezione / debug (Document → Result; il file grezzo lo ispeziona il suo adapter)
    "inspect_document",
    "inspect_result",
    # Modelli
    "Result",
    "Cluster",
    "Contour",
    "Document",
    "Text",
    "MeasuredDistance",
    "MeasuredRadius",
    "MeasuredDiameter",
    "MeasuredAngle",
    "Overlay",
    "Diagnostic",
    # Ruoli — aggancio per un consumatore che marca la geometria pre-heal
    "normalize_role",
    "is_structural_role",
    "RoleRule",
    "name_rules",
    "RoleStyle",
    "non_contour_candidates",
]