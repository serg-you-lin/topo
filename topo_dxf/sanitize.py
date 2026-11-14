"""
topo_dxf/sanitize.py
--------------------
Corregge dati DXF corrotti prima di qualsiasi processing geometrico.

Questo modulo opera su entità ezdxf grezze — non conosce il core.
Il chiamante è responsabile di aprire il documento e passare msp.
Le funzioni lavorano in-place e stampano messaggi per ogni fix applicato.

Funzioni pubbliche:
    sanitize — esegue tutti i sanitizer in sequenza
"""

from ezdxf import upright as _upright
from topo.model import Diagnostic

_FLATTENABLE_TYPES = frozenset({'LINE', 'ARC', 'CIRCLE', 'LWPOLYLINE', 'ELLIPSE'})


def normalize_ocs(msp, verbose: bool = False) -> None:
    """
    Normalizza il vettore di estrusione di tutte le entità OCS nel modelspace.
    Converte (0,0,-1) → (0,0,1) senza alterare la geometria in WCS.
    """
    _upright.upright_all(msp)
    if verbose:
        print("[sanitize] normalize_ocs: vettori di estrusione normalizzati")


def flatten_z(msp, verbose: bool = False) -> int:
    """
    Porta a 0 tutte le coordinate Z != 0 per LINE, ARC, CIRCLE,
    LWPOLYLINE e ELLIPSE.

    Restituisce il numero di entità corrette — il chiamante decide se
    stamparlo o metterlo nel canale warnings del Document.
    """
    fixed = 0
    skipped_types = set()

    for entity in msp:
        t = entity.dxftype()
        if t not in _FLATTENABLE_TYPES:
            skipped_types.add(t)
            continue

        if t == 'LINE':
            changed = False
            if entity.dxf.start.z != 0.0:
                entity.dxf.start = (entity.dxf.start.x, entity.dxf.start.y, 0.0)
                changed = True
            if entity.dxf.end.z != 0.0:
                entity.dxf.end = (entity.dxf.end.x, entity.dxf.end.y, 0.0)
                changed = True
            if changed:
                fixed += 1
                if verbose:
                    print(f"  [sanitize] LINE Z!=0 corretta su layer '{entity.dxf.layer}'")

        elif t in ('ARC', 'CIRCLE'):
            if entity.dxf.center.z != 0.0:
                entity.dxf.center = (entity.dxf.center.x, entity.dxf.center.y, 0.0)
                fixed += 1
                if verbose:
                    print(f"  [sanitize] {t} Z!=0 corretta su layer '{entity.dxf.layer}'")

        elif t == 'LWPOLYLINE':
            elev = entity.dxf.get('elevation', 0.0)
            if elev != 0.0:
                entity.dxf.elevation = 0.0
                fixed += 1
                if verbose:
                    print(f"  [sanitize] LWPOLYLINE elevation={elev:.3f} → 0 su layer '{entity.dxf.layer}'")

        elif t == 'ELLIPSE':
            center = entity.dxf.center
            if center.z != 0.0:
                entity.dxf.center = (center.x, center.y, 0.0)
                fixed += 1
                if verbose:
                    print(f"  [sanitize] ELLIPSE Z!=0 corretta su layer '{entity.dxf.layer}'")

    if skipped_types and verbose:
        print(f"[sanitize] flatten_z: tipi ignorati — {sorted(skipped_types)}")

    return fixed


def sanitize(msp, flatten_z_flag: bool = True, verbose: bool = False) -> int:
    """
    Esegue tutti i sanitizer in sequenza sul modelspace ricevuto.
    Il chiamante è responsabile di aprire e salvare il documento.

    Args:
        msp:            modelspace ezdxf
        flatten_z_flag: se True, esegue flatten_z
        verbose:        se True, stampa dettaglio per ogni entità corretta

    Restituisce il numero di entità con Z != 0 riportate sul piano
    (0 se flatten_z_flag è False).
    """
    normalize_ocs(msp, verbose=verbose)
    if flatten_z_flag:
        return flatten_z(msp, verbose=verbose)
    return 0

def _explode_inserts(msp, sink: list = None) -> int:
    """
    Esplode tutti gli INSERT (blocchi) nel modelspace in entità primitive.
    Restituisce il numero di INSERT esplosi.

    Se `sink` è una lista, i fallimenti di esplosione ci vengono aggiunti
    invece di essere stampati.
    """
    inserts = list(msp.query('INSERT'))
    if not inserts:
        return 0

    failed = []
    for insert in inserts:
        try:
            insert.explode()
        except Exception as ex:
            failed.append(str(ex))
    _explode_failed(sink, "INSERT", failed)

    return len(inserts)


def _explode_hatches(msp, sink: list = None, tolerance: float = 1e-6) -> int:
    """
    Sostituisce ogni HATCH a pattern con le LINE del suo pattern, tagliate
    sul bordo, con layer/colore/tipo linea dell'HATCH. Un riempimento pieno
    non ha righe: resta e finisce negli avvisi. Restituisce gli HATCH esplosi.

    Un bordo salvato a pezzi (percorsi aperti, lati fuori fila) si rimette in
    anelli chiusi coi soli lati del file (D253). `tolerance` è quasi zero: dentro
    un HATCH i capi in comune sono scritti uguali, e la tolleranza dei nodi
    renderebbe ambiguo un lato corto quanto lei.
    """
    from ezdxf.render.hatching import hatch_entity

    hatches = [h for h in msp.query("HATCH") if not h.dxf.solid_fill]
    failed = []
    open_left = []
    for hatch in hatches:
        attribs = {
            k: hatch.dxf.get(k)
            for k in ("layer", "color", "linetype", "true_color")
            if hatch.dxf.hasattr(k)
        }
        try:
            rings = None
            if _boundary_in_pieces(hatch, tolerance):
                rings = _boundary_rings(hatch, tolerance)
                if rings is None:
                    open_left.append(hatch.dxf.get("pattern_name", "?"))
            if rings is None:
                # jiggle_origin di ezdxf sposta l'origine del pattern a caso: le
                # righe devono essere quelle del file, uguali a ogni lettura
                segments = list(hatch_entity(hatch, jiggle_origin=False))
            else:
                segments = list(_pattern_lines(hatch, rings))
        except Exception as ex:
            failed.append(str(ex))
            continue
        for start, end in segments:
            msp.add_line(start, end, dxfattribs=attribs)
        msp.delete_entity(hatch)
    _explode_failed(sink, "HATCH", failed)
    if open_left and sink is not None:
        sink.append(Diagnostic(
            "dxf-hatch-open-boundary",
            f"{len(open_left)} HATCH with a boundary that does not close, each piece closed on its own chord",
            notes=[f"pattern {name}" for name in open_left[:5]]))
    return len(hatches)


def _edge_ends(edge):
    """I due capi di un lato di un EdgePath, come Vec2."""
    from ezdxf.math import Vec2
    if edge.type.name == "LINE":
        return Vec2(edge.start), Vec2(edge.end)
    return Vec2(edge.start_point), Vec2(edge.end_point)


def _boundary_in_pieces(hatch, tolerance: float) -> bool:
    """Il bordo ha un EdgePath i cui lati non vanno testa-coda fino a tornare al primo."""
    for path in hatch.paths.rendering_paths(hatch.dxf.hatch_style):
        if not hasattr(path, "edges") or not path.edges:
            continue
        ends = [_edge_ends(e) for e in path.edges]
        for (_, a), (b, _) in zip(ends, ends[1:] + ends[:1]):
            if not a.isclose(b, abs_tol=tolerance):
                return True
    return False


def _boundary_rings(hatch, tolerance: float):
    """
    I lati del bordo di `hatch` incatenati in anelli chiusi (ezdxf `Path`),
    in tutti e due i versi; i percorsi polilinea restano come sono. None se un
    lato non si chiude o un capo ha più di un seguito: allora non si sceglie.
    """
    from ezdxf.lldxf.const import BOUNDARY_PATH_TEXTBOX
    from ezdxf.path import from_hatch_boundary_path

    rings, pieces = [], []
    for path in hatch.paths.rendering_paths(hatch.dxf.hatch_style):
        if path.path_type_flags & BOUNDARY_PATH_TEXTBOX:
            continue
        if not hasattr(path, "edges"):
            rings.extend(sp for sp in from_hatch_boundary_path(path).sub_paths() if len(sp))
            continue
        pieces.extend(_edge_piece(e) for e in path.edges)

    while pieces:
        ring = pieces.pop(0)
        while not ring.start.isclose(ring.end, abs_tol=tolerance):
            nexts = [i for i, q in enumerate(pieces)
                     if ring.end.isclose(q.start, abs_tol=tolerance)
                     or ring.end.isclose(q.end, abs_tol=tolerance)]
            if len(nexts) != 1:
                return None
            q = pieces.pop(nexts[0])
            if not ring.end.isclose(q.start, abs_tol=tolerance):
                q = q.reversed()
            ring.append_path(q)
        ring.close()
        rings.append(ring)
    return rings


def _edge_piece(edge):
    """Un lato di un EdgePath come `Path` aperto, dal suo inizio alla sua fine."""
    from ezdxf.entities.boundary_paths import EdgePath
    from ezdxf.path import Command, Path, from_hatch_boundary_path

    if edge.type.name == "LINE":
        piece = Path(edge.start)
        piece.line_to(edge.end)
        return piece
    one = EdgePath()
    one.edges.append(edge)
    # ezdxf chiude ogni percorso tornando all'inizio: quel lato non è del file
    closed = from_hatch_boundary_path(one)
    piece = Path(closed.start)
    for cmd in list(closed.commands())[:-1]:
        if cmd.type == Command.LINE_TO:
            piece.line_to(cmd.end)
        elif cmd.type == Command.CURVE3_TO:
            piece.curve3_to(cmd.end, cmd.ctrl)
        elif cmd.type == Command.CURVE4_TO:
            piece.curve4_to(cmd.end, cmd.ctrl1, cmd.ctrl2)
    return piece


def _pattern_lines(hatch, rings):
    """Le righe del pattern di `hatch` dentro `rings`, come `hatch_entity` (senza jiggle)."""
    from ezdxf.math import Vec3
    from ezdxf.render.hatching import hatch_paths, pattern_baselines

    ocs = hatch.ocs()
    elevation = hatch.dxf.elevation.z
    for baseline in pattern_baselines(hatch, jiggle_origin=False):
        for line in hatch_paths(baseline, rings):
            for s, e in baseline.pattern_renderer(line.distance).render(line.start, line.end):
                if ocs.transform:
                    yield ocs.to_wcs((s.x, s.y, elevation)), ocs.to_wcs((e.x, e.y, elevation))
                else:
                    yield Vec3(s), Vec3(e)


def _explode_failed(sink, dxftype: str, failed: list) -> None:
    """Un `Diagnostic` per tipo con tutte le esplosioni fallite (D233); senza
    `sink` lo stampa."""
    if not failed:
        return
    msg = Diagnostic("dxf-explode-failed", f"{len(failed)} {dxftype} could not be exploded, left out",
                     notes=failed[:5])
    if sink is not None:
        sink.append(msg)
    else:
        print(msg)


"""
adapters/dxf/dedup_adapter.py
------------------------------
Normalizzazione entità DXF — traduzione formato → normalizer.

Due entità DXF con la stessa geometria sono una copia: si tiene la prima.
La chiave la calcola questo modulo dal formato nativo; il confronto è suo
anche lui (era in core/healing/normalizer, D125: un adapter usa solo i nomi
pubblici di topo).

Funzioni pubbliche:
    extract_keyed_entities — msp → List[(key, entity)]
    delete_entities        — elimina entità dal msp
    deduplicate            — shortcut: extract + find + delete → int
"""

from typing import Any, Hashable, Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Calcolo chiave geometrica per tipo DXF
# ---------------------------------------------------------------------------

def _key_for(entity) -> Optional[Hashable]:
    """
    Restituisce una chiave hashable che identifica univocamente
    la geometria dell'entità, indipendente dall'handle DXF.
    Restituisce None per tipi non gestiti o in caso di errore.
    """
    t     = entity.dxftype()
    layer = entity.dxf.get('layer', '0')

    try:
        if t == 'LINE':
            s   = (round(entity.dxf.start.x, 2), round(entity.dxf.start.y, 2))
            e   = (round(entity.dxf.end.x,   2), round(entity.dxf.end.y,   2))
            pts = tuple(sorted([s, e]))          # ordine canonico: A→B == B→A
            return (t, layer, pts)

        if t in ('LWPOLYLINE', 'POLYLINE'):
            pts = tuple(
                (round(p[0], 2), round(p[1], 2))
                for p in entity.get_points()
            )
            return (t, layer, pts)

        if t == 'CIRCLE':
            c = entity.dxf.center
            return (t, layer,
                    round(c.x, 2), round(c.y, 2),
                    round(entity.dxf.radius, 2))

        if t == 'ARC':
            c = entity.dxf.center
            return (t, layer,
                    round(c.x, 2), round(c.y, 2),
                    round(entity.dxf.radius,      2),
                    round(entity.dxf.start_angle, 1),
                    round(entity.dxf.end_angle,   1))

    except Exception:
        return None

    return None


# ---------------------------------------------------------------------------
# Funzioni pubbliche
# ---------------------------------------------------------------------------

def extract_keyed_entities(msp) -> List[Tuple[Hashable, Any]]:
    """
    Produce la lista (key, entity) per tutte le entità del msp.
    Le entità con tipo non gestito producono key=None e vengono
    ignorate da _find_duplicates.
    """
    return [(_key_for(entity), entity) for entity in msp]


def delete_entities(refs: List[Any], msp) -> None:
    """Elimina le entità dal msp in-place."""
    for entity in refs:
        msp.delete_entity(entity)


def _find_duplicates(
    keyed_entities: Iterable[Tuple[Hashable, Any]],
) -> List[Any]:
    """
    Restituisce i ref delle entità duplicate (seconda occorrenza in poi).

    Parametri:
        keyed_entities : iterabile di (key, ref) — l'adapter produce le chiavi,
                         ref è opaco (l'adapter sa come eliminarlo)

    Restituisce:
        Lista di ref da eliminare. L'ordine riflette l'ordine di input.
    """
    seen:      set       = set()
    to_delete: List[Any] = []

    for key, ref in keyed_entities:
        if key is None:
            continue
        if key in seen:
            to_delete.append(ref)
        else:
            seen.add(key)

    return to_delete


def deduplicate(msp) -> int:
    """
    Shortcut: estrae chiavi, trova duplicati, li elimina.

    Restituisce il numero di entità eliminate.
    """
    keyed    = extract_keyed_entities(msp)
    to_delete = _find_duplicates(keyed)
    delete_entities(to_delete, msp)
    return len(to_delete)