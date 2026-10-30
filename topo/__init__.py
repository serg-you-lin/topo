"""
topo
----
Motore deterministico di geometria 2D per disegni tecnici: geometria e ruoli,
nessun formato di file (MAP.md D123). DXF e PDF entrano ed escono dagli
adapter, pacchetti fratelli nella stessa distribuzione: `topo_dxf`
(`pip install g-topo[dxf]`) e `topo_pdf` (`g-topo[pdf]`) — D124, D129.

API pubblica — tutto quello che serve è qui.
Non devi importare i moduli interni direttamente.

Workflow consigliato (file singolo):
    import topo, topo_dxf

    rules = [
        topo.RoleRule("construction", name_contains="constr", dashed=True),
    ]
    doc = topo_dxf.load_dxf("pezzo.dxf", role_rules=rules)
    # regole in ordine, vince la prima che matcha (D63);
    # topo.name_rules({"Costruzione": "construction"}) per le sole regole sul nome

    result = topo.heal(doc, label="pezzo", source_file="pezzo.dxf")
    # fori, pieghe, incisioni: lettura di processo, in snapbend (MAP.md D88)

    topo.inject(result)
    topo_dxf.to_dxf(result, doc).saveas("pezzo_healed.dxf")
    topo.save_json(result, "pezzo.json")

Un Result per parte, per ogni formato:
    parts = topo.split(result)                      # puro, senza formato
    for part in parts:
        topo_dxf.to_dxf(part, doc).saveas(f"{part.clusters[0].label}.dxf")

Senza file: `topo.load_geometry` / `topo.load_segments` costruiscono un
Document dalla geometria.
"""

from .core.geometry_input import load_geometry, load_segments
from .core.heal          import heal
from .tools.inject       import inject
from .tools.anchor       import anchor_texts, measured_references, pointer_target, resolve_target
# Un Result per parte, senza formato: ogni exporter ne scrive una (D124, D129)
from .tools.split        import split, DEFAULT_MIN_CLUSTER_AREA
from .rules.validator     import validate_document, validate_result
from .io.exporter         import (
    to_json,
    save_json,
    save_xml,
    build_metadata,
)
# Conversione esplicita a shapely per overlay, buffer, WKT: il modello non
# espone tipi shapely (MAP.md D166).
from .io.shapes           import to_shapely
from .model         import (
    Result, Cluster, Contour, Document,
    Text,
    DetectedFeature, DetectedFeatures,
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
# Seconda lettura di un documento, accanto a heal(): per isole, contorno
# esterno come faccia esterna della rete piana (disegni di viste, 3D
# proiettato). Vedi MAP.md D58.
from .core.island import island
# La geometria: fatti con nomi geometrici (forma di un contorno, cerchi
# concentrici, corde, rettangoli coperti, ...), tutti in `topo.geometry`.
# MAP.md D68, D91, D93-D95.
from .core import geometry
# Tutto ciò che è esposto senza promessa di stabilità: i passi di heal() e di
# island(), il viewer, la lettura testuale, rotate_*, simplify_points
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
    # Geometria in ingresso (i file entrano dagli adapter: topo_dxf, topo_pdf)
    "load_geometry",
    "load_segments",
    # Validazione
    "validate_document",
    "validate_result",
    # Workflow
    "heal",
    "island",
    "split",
    "DEFAULT_MIN_CLUSTER_AREA",
    "inject",
    "anchor_texts",
    "pointer_target",
    "measured_references",
    "resolve_target",
    "geometry",
    "experimental",
    "primitives",
    "model",
    # Export
    "to_json",
    "save_json",
    "save_xml",
    "to_shapely",
    # Metadati (gli stessi come XDATA DXF: topo_dxf.write_metadata_to_dxf)
    "build_metadata",
    # Lettura per isole: i mattoni di island()
    # I passi di heal()
    # Utilità
    # Ispezione / debug (Document → Result; il file grezzo: topo_dxf.inspect_dxf)
    "inspect_document",
    "inspect_result",
    # Modelli
    "Result",
    "Cluster",
    "Contour",
    "Document",
    "Text",
    "DetectedFeature",
    "DetectedFeatures",
    # Ruoli — aggancio per un consumatore che marca la geometria pre-heal
    "normalize_role",
    "is_structural_role",
    "RoleRule",
    "name_rules",
    "RoleStyle",
    "non_contour_candidates",
]