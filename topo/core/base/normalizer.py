"""
topo/core/base/normalizer.py
----------------------------
Normalizzazione geometrica format-agnostic.

Zero dipendenze da ezdxf, PDF, SVG o qualsiasi formato.

Normalizzazioni sotto "due entità non dovrebbero contare come due" (la copia
identica, entità per entità, la toglie l'adapter DXF prima: D125):
    merge_collinear_overlaps — sovrapposizione geometrica reale: due o più
                             LineSeg sulla stessa retta infinita che si
                             coprono almeno in parte (anche a catena — il
                             primo non deve toccare l'ultimo, basta una
                             sequenza di sovrapposizioni intermedie) sono la
                             stessa riga tracciata più volte a spezzoni.
                             Lavora su `Edge` (già format-agnostic, D18),
                             non su chiavi opache: deve calcolare proiezioni
                             reali per produrre il segmento unico che
                             sostituisce il gruppo, non solo confrontare due
                             valori.

merge_cocircular_overlaps — stesso principio, sugli ArcSeg co-circolari
                             invece dei LineSeg collineari (v. MAP.md D52).

weld_degenerate_linesegs — non sovrapposizione ma degenerazione: un LineSeg
                             più corto di 0.05mm è solo rumore nel grafo,
                             i suoi due estremi vengono saldati in un nodo
                             (v. MAP.md D56).

refit_tessellations      — una catena di tanti LineSeg corti è una curva scritta
                             a punti: rifittata come arco/cerchio/spline
                             (fitting.simplify_points).

Funzioni pubbliche:
    merge_collinear_overlaps  — dato un iterabile di Edge, i gruppi LineSeg da fondere
    merge_cocircular_overlaps — dato un iterabile di Edge, i gruppi ArcSeg da fondere
    weld_degenerate_linesegs  — dato un iterabile di Edge, i LineSeg degeneri da saldare
    refit_tessellations       — dato un iterabile di Edge, le catene tassellate rifittate
"""

from __future__ import annotations
import math
from collections import Counter
from dataclasses import dataclass, replace
from typing import Any, Callable, Iterable, List, Tuple

from ..geometry.measure import FLOAT_NOISE, within_diameter
from ..primitives.segments import LineSeg, ArcSeg, CircleSeg, Point, segment_endpoints
from ..primitives.fitting import simplify_points
from ..topology.graph import build_node_graph, connected_groups
from ..topology.noding import _near_pairs
from ..topology.edge import Edge
from ...model.role import ContourRole


# ---------------------------------------------------------------------------
# merge_collinear_overlaps
# ---------------------------------------------------------------------------

_SAME_DIRECTION = 1e-7   # seno dell'angolo fra due direzioni: quasi-esatta per costruzione, non tollerante
_SAME_OFFSET    = 1e-3   # mm — "stessa retta / stesso cerchio", non "vicina"
_CHAIN_GAP_EPS  = FLOAT_NOISE  # guardia da rumore in virgola mobile, non tolleranza utente


def _same_line(a: LineSeg, b: LineSeg) -> bool:
    """
    `a` e `b` stanno sulla stessa retta infinita: direzioni parallele entro
    `_SAME_DIRECTION` (seno, in qualunque verso) e ogni estremo di ognuno a
    non più di `_SAME_OFFSET` dalla retta dell'altro. Giudicato sui
    segmenti veri, mai su una chiave arrotondata: una cella di griglia ha
    un bordo dove due spezzoni della stessa retta finiscono da parti
    diverse, e il bordo si sposta col riferimento (D184, G6e).

    Soglie FISSE, non la tolleranza di heal del chiamante: "sono la stessa
    retta" è precisione geometrica (rumore fra spezzoni nati identici), non
    "abbastanza vicine da chiudere un gap". Con la tolleranza di heal (provato,
    poi tolto) rette parallele **reali e distinte** a 0.5 mm si fondevano —
    un pattern di denti/asole sparito in un golden (`fa_che_non_mi_incazzi`).
    """
    da, db = _unit(a), _unit(b)
    if da is None or db is None or abs(da[0] * db[1] - da[1] * db[0]) > _SAME_DIRECTION:
        return False
    return max(_off_line(p, a.start, da) for p in (b.start, b.end)) <= _SAME_OFFSET         and max(_off_line(p, b.start, db) for p in (a.start, a.end)) <= _SAME_OFFSET


def _unit(seg: LineSeg):
    dx, dy = seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]
    length = math.hypot(dx, dy)
    return (dx / length, dy / length) if length else None


def _off_line(p, origin, u) -> float:
    return abs((p[0] - origin[0]) * u[1] - (p[1] - origin[1]) * u[0])


def merge_collinear_overlaps(edges: Iterable[Edge], keep_junctions: bool = False) -> List[Edge]:
    """
    Fonde gruppi di LineSeg collineari (stessa retta infinita, `_same_line`)
    che si toccano o si sovrappongono in un solo Edge ciascuno — a catena: il
    primo membro non deve toccare/sovrapporsi all'ultimo, basta una sequenza
    di contatti/sovrapposizioni intermedi, esattamente come un fascio di
    segmenti che insieme disegnano una riga sola. Bastano 2 membri: l'unione
    di due intervalli 1D che si toccano o si sovrappongono è sempre e
    comunque ben definita (il segmento più lungo, se uno contiene l'altro;
    l'estensione totale, altrimenti) — non c'è modo di "sbagliare" a fondere
    solo 2 pezzi collineari, la domanda semmai è se DEVONO restare due
    feature distinte a valle (v. sotto).

    `keep_junctions=True` (lo usa `heal()`): due pezzi che si TOCCANO soltanto
    in un nodo dove arriva anche un edge su un'altra retta non si fondono — è
    uno spigolo o un innesto, e il grafo di `heal()`, che non noda da sé, lo
    perderebbe per sempre (MAP.md D110). `outlines()` noda la rete da sé e
    lascia il default.

    Storia della soglia minima che c'era qui prima (rimossa): un'ipotesi di
    "servono almeno 3 pezzi indipendenti, una coppia può essere coincidenza"
    è nata da due golden reali (`la_104`, `staffa_scarto_doppia`) dove fondere
    esattamente 2 tratti — due caratteri di un'incisione allineati per caso,
    non un errore di disegno — sembrava aver rotto un pezzo vicino. Causa
    vera, trovata dopo: un bug di arrotondamento (sotto), non il numero di
    pezzi. Con quel bug corretto, fondere quelle stesse coppie non rompe più
    niente su nessun file della suite — l'unione di 2 intervalli è sempre
    corretta, il numero di pezzi non era mai stato la variabile giusta.

    Due estremi, due scopi, mai mischiati (stesso principio già in
    `gap_solver.apply_gap_fixes`: "il segmento conserva il punto reale, solo
    il nodo topologico dell'Edge viene arrotondato"): `Edge.start`/`Edge.end`
    del fuso portano il punto ARROTONDATO (l'identità del nodo nel grafo,
    l'adapter li produce arrotondando `segment_endpoints(segment)`, D18 /
    adapter.py `_append_edge`) — quello serve a riagganciarsi esattamente al
    nodo del vicino reale (un ArcSeg che chiude l'angolo, un'altra LINE): un
    fuso il cui Edge.start/end fosse a piena precisione del segmento nativo
    può risultare vicinissimo ma non identico a quel nodo, e il sub-mm di
    scarto spezza il contorno. Il `LineSeg` fuso (`edge.segment`), invece,
    porta SEMPRE il punto reale a piena precisione — mai quello arrotondato:
    è quello che l'export legge per costruire la geometria in output (area,
    lunghezza, poligono scritto), e un fuso il cui segmento porta il punto
    arrotondato produce, appena affianca nello stesso contorno un lato
    nativo mai toccato dal merge, uno scalino visibile nel punto che
    dovrebbe essere lo stesso angolo — due fonti di verità diverse cucite
    insieme (trovato su un caso reale: un lato "verticale" con dx=0.031
    invece di 0, lunghezza 0.97 invece di 1). La proiezione `_t` per
    ordinamento/sovrapposizione resta a piena precisione in entrambi i casi.

    Esclusi a monte, mai candidati alla fusione:
      - segmenti non LineSeg (ARC/SPLINE non sono "collineari")
      - edge con `role` già diverso da UNKNOWN — un ruolo assegnato da
        role_rules (bending/engrave/hole/...) è dato di dominio: quegli edge
        non entrano mai nel graph-building (`steps.split_labeled` li leva
        prima), quindi fonderli non aiuta a chiudere niente e rischia di
        alterare geometria intenzionale — trovato su un golden reale
        (`la_104`): due tratti di un'incisione/testo si sovrappongono per
        disegno (font vettoriale), non per errore, e fonderli cambiava la
        feature attesa

    Niente qui guarda da dove viene l'edge nel formato sorgente (una
    polilinea già chiusa contro linee sciolte, un layer, un tipo di
    entità): una versione precedente escludeva gli edge di un percorso già
    chiuso per analogia con `NonContourEdgeDetector` (dove un'esclusione
    simile ha un significato diverso: un edge di un anello chiuso non può
    ANCHE essere una piega che lo attraversa), ma qui non proteggeva niente
    di reale — un lato vero disegnato come polilinea e un doppione
    disegnato come LINE sciolte sono la stessa identica situazione di
    qualunque altra coppia, e l'esclusione impediva di vederlo (golden
    reale `staffa_scarto_doppia`: una staffa di scarto a 3 lati duplicava
    esattamente un lato di una polilinea chiusa). Rimossa: `Edge` non porta
    più quel dato, per lo stesso motivo (MAP.md, seguito D50).

    Il segmento sostituto usa i due estremi reali più lontani lungo la retta
    (le proiezioni minima e massima) — mai un punto fabbricato — e conserva
    `style` del primo edge del gruppo in ordine di input (lo stile può
    differire leggermente fra spezzoni, si tiene quello del primo; `role` è
    UNKNOWN per ogni membro per costruzione).

    Restituisce una nuova lista di Edge della STESSA lunghezza relativa e nel
    MEDESIMO ordine di input per tutto ciò che non fonde: un pre-pass di
    pulizia non deve riordinare edge che non tocca. Un gruppo fuso occupa la
    posizione del suo primo membro in ordine di input; gli altri membri del
    gruppo spariscono (assorbiti), il resto della lista resta tale e quale.
    (Trovato per necessità, non per eleganza: raggruppare-per-retta-poi-
    riconcatenare cambiava l'ordine anche a zero fusioni effettive, e quel
    solo riordino bastava a far scegliere al loop-finder un percorso diverso
    a un bivio — probabilmente paritario — in un golden reale,
    `staffa_scarto_doppia`, senza che una sola fusione fosse coinvolta.)
    """
    return _merge_on_carrier(edges, LineSeg, _same_line, _line_spans, _merged_line, keep_junctions)


def _line_spans(group: List[Edge]) -> List[_Span]:
    """Span lungo la retta comune: `t` è la proiezione sulla direzione del
    primo edge, la stessa per tutti, quindi confrontabile fra edge; il fuso
    va nel verso del primo edge (un verso canonico dipenderebbe dal
    riferimento, G6e)."""
    s0, e0 = group[0].segment.start, group[0].segment.end
    ux, uy = e0[0] - s0[0], e0[1] - s0[1]
    length0 = math.hypot(ux, uy)
    ux, uy = (ux / length0, uy / length0) if length0 else (1.0, 0.0)

    def _t(point):
        return (point[0] - s0[0]) * ux + (point[1] - s0[1]) * uy

    spans = []
    for e in group:
        seg = e.segment
        t_start, t_end = _t(seg.start), _t(seg.end)
        if t_start <= t_end:
            spans.append(_Span(t_start, e.start, t_end, e.end, e, (seg.start, seg.end)))
        else:
            spans.append(_Span(t_end, e.end, t_start, e.start, e, (seg.end, seg.start)))
    return _chain(spans)


def _merged_line(lo: _Span, hi: _Span):
    """Il fuso di una catena collineare: nodi arrotondati, segmento a piena
    precisione (v. docstring di `merge_collinear_overlaps`)."""
    return lo.lo_node, hi.hi_node, LineSeg(start=lo.extra[0], end=hi.extra[1])


# ---------------------------------------------------------------------------
# Motore comune: unione di intervalli 1D su un supporto (retta o cerchio)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Span:
    """
    Un edge come intervallo [lo, hi] sul suo supporto (posizione lungo la
    retta, o angolo sul cerchio). `lo_node`/`hi_node` sono gli estremi
    arrotondati dell'Edge — l'identità del nodo nel grafo, che il fuso riusa
    per riagganciarsi al vicino; `extra` è ciò che serve al chiamante per
    costruire il segmento fuso a piena precisione.
    """
    lo:      float
    lo_node: Point
    hi:      float
    hi_node: Point
    edge:    Edge
    extra:   Any


def _chain(spans: List[_Span]) -> List[List[_Span]]:
    """
    Ordina per `lo` e incatena gli span che si toccano o si sovrappongono:
    l'unione di intervalli 1D che si toccano è sempre ben definita.
    `_CHAIN_GAP_EPS` è rumore in virgola mobile, non una tolleranza: un gap
    vero resta fuori dalla catena.
    """
    spans = sorted(spans, key=lambda s: s.lo)
    chains: List[List[_Span]] = [[spans[0]]]
    cur_hi = spans[0].hi
    for span in spans[1:]:
        if span.lo <= cur_hi + _CHAIN_GAP_EPS:
            chains[-1].append(span)
            cur_hi = max(cur_hi, span.hi)
        else:
            chains.append([span])
            cur_hi = span.hi
    return chains


def _merge_on_carrier(
    edges: Iterable[Edge],
    segment_type: type,
    same: Callable[[Any, Any], bool],
    chains_of: Callable[[List[Edge]], List[List[_Span]]],
    merged: Callable[[_Span, _Span], Tuple[Point, Point, Any]],
    keep_junctions: bool = False,
) -> List[Edge]:
    """
    Raggruppa per supporto gli edge di `segment_type` con ruolo UNKNOWN —
    due vicini con `same(a, b)`, a catena —, divide ogni gruppo in catene
    (`chains_of`) e sostituisce ogni catena di 2+ con un Edge solo:
    (start, end, segmento) da `merged(lo, hi)`, role/style del membro che
    viene prima in input. Il resto della lista resta nell'ordine di input.
    """
    edges = list(edges)
    original_index = {id(e): i for i, e in enumerate(edges)}

    typed = [e for e in edges if e.role == ContourRole.UNKNOWN and isinstance(e.segment, segment_type)]
    # solo pezzi che si toccano possono fondersi: le coppie da giudicare sono
    # le vicine, il supporto lo decide `same` sui segmenti veri
    pairs = [(i, j) for i, j in _near_pairs(typed, _SAME_OFFSET)
             if same(typed[i].segment, typed[j].segment)]
    groups = connected_groups(len(typed), pairs)
    carrier = {id(typed[i]): k for k, members in enumerate(groups) for i in members}
    buckets = [[typed[i] for i in members] for members in groups]

    carriers_at: dict = {}  # nodo -> supporti degli edge che finiscono lì
    for edge in edges:
        if edge.role != ContourRole.UNKNOWN:
            continue
        key = carrier.get(id(edge), ("edge", id(edge)))
        for node in (edge.start, edge.end):
            carriers_at.setdefault(node, set()).add(key)

    replacement: dict = {}  # id(rappresentante) -> Edge fuso
    drop: set = set()       # id(edge) assorbiti da una fusione
    junction = lambda node: len(carriers_at.get(node, ())) > 1
    for group in buckets:
        if len(group) < 2:
            continue
        chains = chains_of(group)
        if keep_junctions:
            chains = [c for whole in chains for c in _split_at_junctions(whole, junction)]
        for chain in chains:
            if len(chain) < 2:
                continue
            lo = min(chain, key=lambda s: s.lo)
            hi = max(chain, key=lambda s: s.hi)
            start, end, segment = merged(lo, hi)
            members = [s.edge for s in chain]
            representative = min(members, key=lambda e: original_index[id(e)])
            replacement[id(representative)] = replace(
                representative, start=start, end=end, segment=segment)
            drop.update(id(e) for e in members if e is not representative)

    return [replacement.get(id(e), e) for e in edges if id(e) not in drop]


def _split_at_junctions(chain: List[_Span], junction: Callable[[Point], bool]) -> List[List[_Span]]:
    """
    Spezza una catena dove due span consecutivi si toccano SOLO (nessuna
    sovrapposizione) in un nodo dove finisce anche un edge su un altro
    supporto: lì c'è uno spigolo o un innesto, un nodo vero del grafo, e
    fondere i due pezzi lo cancellerebbe (MAP.md D110). Una sovrapposizione
    vera si fonde sempre.
    """
    out = [[chain[0]]]
    cur_hi, cur_node = chain[0].hi, chain[0].hi_node
    for span in chain[1:]:
        touch_only = span.lo >= cur_hi - _CHAIN_GAP_EPS
        if touch_only and (junction(span.lo_node) or junction(cur_node)):
            out.append([span])
        else:
            out[-1].append(span)
        if span.hi > cur_hi:
            cur_hi, cur_node = span.hi, span.hi_node
    return out


# ---------------------------------------------------------------------------
# merge_cocircular_overlaps
# ---------------------------------------------------------------------------

_TWO_PI = 2.0 * math.pi


def _same_circle(a: ArcSeg, b: ArcSeg) -> bool:
    """Stesso cerchio: centri e raggi entro `_SAME_OFFSET` — v. `_same_line`."""
    return math.dist(a.center, b.center) <= _SAME_OFFSET and abs(a.radius - b.radius) <= _SAME_OFFSET


def merge_cocircular_overlaps(edges: Iterable[Edge]) -> List[Edge]:
    """
    `merge_collinear_overlaps` per gli ArcSeg: fonde gruppi co-circolari
    (stesso centro+raggio, `_same_circle`) che si toccano/sovrappongono
    angolarmente in un solo Edge ciascuno, incatenando a catena sul dominio
    circolare [0, 2*pi) (srotolando oltre il taglio 0/2*pi quando serve).
    Se la copertura totale chiude un giro intero, il fuso ha
    Edge.start == Edge.end (loop degenere, v. MAP.md D52).

    Stesse regole di `merge_collinear_overlaps`: esclude segmenti non ArcSeg
    e `role != UNKNOWN`; usa `edge.start`/`edge.end` (arrotondati) come
    estremi conservati, mai il punto ricalcolato a piena precisione;
    preserva l'ordine di input per tutto ciò che non fonde.
    """
    return _merge_on_carrier(edges, ArcSeg, _same_circle, _arc_chains, _merged_arc)


def _arc_chains(group: List[Edge]) -> List[List[_Span]]:
    """
    Catene angolari di un gruppo sullo stesso cerchio. Se l'ultima catena
    chiude il giro nella prima, le unisce: la prima viene srotolata di +2*pi
    (solo l'angolo usato per ordinare; i nodi restano quelli reali).
    """
    spans = []
    for e in group:
        seg = e.segment
        if seg.ccw:
            lo, lo_node, hi_node = seg.start_angle % _TWO_PI, e.start, e.end
        else:
            lo, lo_node, hi_node = seg.end_angle % _TWO_PI, e.end, e.start
        spans.append(_Span(lo, lo_node, lo + seg._sweep(), hi_node, e, (seg.center, seg.radius)))
    chains = _chain(spans)

    if len(chains) > 1:
        first_lo = chains[0][0].lo
        last_hi = max(s.hi for s in chains[-1])
        if last_hi >= first_lo + _TWO_PI - _CHAIN_GAP_EPS:
            shifted = [replace(s, lo=s.lo + _TWO_PI, hi=s.hi + _TWO_PI) for s in chains[0]]
            chains[-1] = chains[-1] + shifted
            chains.pop(0)
    return chains


def _merged_arc(lo: _Span, hi: _Span):
    """Il fuso di una catena cocircolare: un arco, o un cerchio se chiude il
    giro — stesso primitivo di un CIRCLE nativo, nessuna traccia di quale
    frammento fosse il primo."""
    center, radius = lo.extra
    if hi.hi - lo.lo >= _TWO_PI - _CHAIN_GAP_EPS:
        circle = CircleSeg(center=center, radius=radius)
        point = segment_endpoints(circle)[0]
        return point, point, circle
    arc = ArcSeg(center=center, radius=radius, start_angle=lo.lo, end_angle=hi.hi, ccw=True)
    return lo.lo_node, hi.hi_node, arc


# ---------------------------------------------------------------------------
# weld_degenerate_linesegs
# ---------------------------------------------------------------------------

_DEGENERATE_LENGTH_EPS = 0.05  # mm — fisso, non la tolerance del chiamante (v. MAP.md D56)


def weld_degenerate_linesegs(edges: Iterable[Edge]) -> List[Edge]:
    """
    Salda (non cancella) i LineSeg `role == UNKNOWN` di lunghezza reale
    sotto `_DEGENERATE_LENGTH_EPS`: l'Edge sparisce, i suoi due nodi
    diventano uno e ogni altro Edge che li toccava viene rimappato lì — la
    catena resta connessa. Solo i nodi (Edge.start/end) si spostano, il
    `segment` conserva il punto reale. Ordine di input preservato.

    Si giudica il gruppo intero: i tratti corti collegati fra loro si saldano
    tutti se i loro nodi distano al più `_DEGENERATE_LENGTH_EPS` l'uno
    dall'altro, altrimenti nessuno — una curva disegnata a tratti corti non
    collassa in un punto (D152) e quali tratti saldarne non lo decide un
    ordine, che cambia col riferimento (D186). Un tratto con un capo libero
    (nessun altro edge lo tocca) resta: è una punta, non un nodo doppio (D164).
    """
    edges = list(edges)
    # una punta libera non ha due nodi da unire: saldarla cancellerebbe il
    # tratto e sposterebbe il capo libero, che poi nessun gap ritrova (D164)
    degree: Counter = Counter()
    for edge in edges:
        degree[edge.start] += 1
        degree[edge.end] += 1
    candidates = [edge for edge in edges
                  if degree[edge.start] >= 2 and degree[edge.end] >= 2
                  and isinstance(edge.segment, LineSeg) and edge.role == ContourRole.UNKNOWN
                  and math.dist(edge.segment.start, edge.segment.end) < _DEGENERATE_LENGTH_EPS]
    if not candidates:
        return edges

    nodes = sorted({p for e in candidates for p in (e.start, e.end)})
    index = {p: k for k, p in enumerate(nodes)}
    groups = connected_groups(len(nodes), [(index[e.start], index[e.end]) for e in candidates])
    target: dict = {}
    for members in groups:
        points = [nodes[k] for k in members]
        if len(points) > 1 and within_diameter(points, _DEGENERATE_LENGTH_EPS):
            # il rappresentante è il nodo minimo del gruppo, un estremo reale
            target.update((p, points[0]) for p in points)
    degenerate_ids = {id(e) for e in candidates if e.start in target}
    if not degenerate_ids:
        return edges

    result: List[Edge] = []
    for edge in edges:
        if id(edge) in degenerate_ids:
            continue
        new_start, new_end = target.get(edge.start, edge.start), target.get(edge.end, edge.end)
        if new_start != edge.start or new_end != edge.end:
            edge = replace(edge, start=new_start, end=new_end)
        result.append(edge)
    return result


# ---------------------------------------------------------------------------
# refit_tessellations
# ---------------------------------------------------------------------------

def refit_tessellations(
    edges: Iterable[Edge],
    max_segment: float = 0.1,
    min_run: int = 10,
    tolerance: float = 0.02,
    node_decimals: int = 3,
) -> List[Edge]:
    """
    Una catena di almeno `min_run` LineSeg (`role == UNKNOWN`) più corti di
    `max_segment`, collegati uno dopo l'altro, è una curva scritta a punti:
    diventa le primitive di `simplify_points` (linee, archi, spline entro
    `tolerance`; uno spigolo è una svolta su `max_segment`, D141). Gli
    estremi della catena tengono i nodi originali, così resta attaccata ai
    vicini. Il resto non si tocca.
    """
    edges = list(edges)
    short = [e for e in edges
             if isinstance(e.segment, LineSeg) and e.role == ContourRole.UNKNOWN
             and e.start != e.end
             and math.dist(e.segment.start, e.segment.end) < max_segment]
    replaced, new_edges = set(), []
    for path, closed in chain_runs(short):
        if len(path) < min_run:
            continue
        pts = []
        for edge, rev in path:
            a, b = (edge.segment.end, edge.segment.start) if rev else (edge.segment.start, edge.segment.end)
            if not pts:
                pts.append(a)
            pts.append(b)
        if closed:
            pts = pts[:-1]
        prims = simplify_points(pts, tolerance=tolerance, scale=max_segment, closed=closed)
        if not prims:
            continue
        first, last = path[0], path[-1]
        start_node = first[0].end if first[1] else first[0].start
        end_node = last[0].start if last[1] else last[0].end
        # una giunzione è un nodo solo: arrotondata una volta, dalla fine del
        # pezzo che arriva; l'inizio del successivo (a 1 ulp) non si arrotonda
        # da sé, o un bordo di cella fra le due copie stacca la catena (G6e)
        grid = lambda p: (round(p[0], node_decimals), round(p[1], node_decimals))
        nodes = [grid(segment_endpoints(prims[0])[0])] + [grid(segment_endpoints(p)[1]) for p in prims]
        if closed:
            nodes[-1] = nodes[0]
        else:
            nodes[0], nodes[-1] = start_node, end_node
        for k, prim in enumerate(prims):
            new_edges.append(replace(first[0], segment=prim, start=nodes[k], end=nodes[k + 1]))
        replaced |= {id(edge) for edge, _ in path}
    if not replaced:
        return edges
    return [e for e in edges if id(e) not in replaced] + new_edges


def chain_runs(short_edges: List[Edge]) -> list:
    """Catene massimali: percorsi fra nodi di grado != 2, o anelli.
    [( [(edge, percorso_al_contrario)], chiusa )]."""
    graph = build_node_graph(short_edges)
    used: set = set()
    runs = []

    def walk(start, first_edge, first_other):
        path, node, edge, other = [], start, first_edge, first_other
        while True:
            used.add(id(edge))
            path.append((edge, graph.canonical(edge.start) != node))
            node = other
            nxt = [(e, o) for e, o in graph[node] if id(e) not in used]
            if len(graph[node]) != 2 or not nxt:
                return path, node
            edge, other = nxt[0]

    for n in [n for n in graph if len(graph[n]) != 2]:
        for e, o in graph[n]:
            if id(e) not in used:
                path, _ = walk(n, e, o)
                runs.append((path, False))
    for n in graph:
        for e, o in graph[n]:
            if id(e) not in used:
                path, last = walk(n, e, o)
                runs.append((path, last == n))
    return runs
