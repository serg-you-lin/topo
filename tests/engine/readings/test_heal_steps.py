"""
tests/engine/readings/test_heal_steps.py
----------------------------------
I passi di heal() usati da soli, come li usa un consumatore che compone la
sua ricetta (D62) â€” e la composizione nell'ordine di heal() che dÃ  lo stesso
risultato di heal().
"""

import math
import unittest
from dataclasses import replace


import topo
import topo_dxf
from topo.model.document import Document
from topo.model.curve import ClosedCurve, OpenCurve
from topo.model.role import ContourRole
from topo.core.topology.edge import Edge
from topo.core.primitives.segments import ArcSeg, LineSeg, CircleSeg, BSplineSeg
from topo import to_shapely
from tests.paths import DATA

EXAMPLES = DATA


def _line(p1, p2, role=ContourRole.UNKNOWN, decimals=3):
    r = lambda p: (round(p[0], decimals), round(p[1], decimals))
    return Edge(role=role, start=r(p1), end=r(p2), segment=LineSeg(start=p1, end=p2))


def _square(x0, y0, side, role=ContourRole.UNKNOWN):
    pts = [(x0, y0), (x0 + side, y0), (x0 + side, y0 + side), (x0, y0 + side)]
    return [_line(pts[i], pts[(i + 1) % 4], role) for i in range(4)]


def _circle(center, radius, role=ContourRole.UNKNOWN):
    pt = (center[0] + radius, center[1])
    return Edge(role=role, start=pt, end=pt, segment=CircleSeg(center=center, radius=radius))


def _broken_square(spur=False):
    # Angolo in basso a destra rotto: 10.03 vs 10.14, nodi a 1 decimale
    # 10.0 vs 10.1 â€” lo chiude solo la riparazione via clustering (D57).
    edges = [_line((0.0, 0.0), (10.03, 0.0), decimals=1),
             _line((10.14, 0.0), (10.14, 10.0), decimals=1),
             _line((10.14, 10.0), (0.0, 10.0), decimals=1),
             _line((0.0, 10.0), (0.0, 0.0), decimals=1)]
    if spur:
        # terzo estremo nello stesso cluster: riparazione a due non definita
        edges.append(_line((10.06, 0.0), (10.06, -5.0), decimals=1))
    return edges


class TestSplitLabeled(unittest.TestCase):

    def test_001_ruolo_non_strutturale_messo_da_parte(self):
        mark = _line((2, 2), (5, 5), role="engrave")
        kept, labeled = topo.experimental.split_labeled(_square(0, 0, 10) + [mark])
        self.assertEqual(len(kept), 4)
        self.assertEqual(labeled, [mark])

    def test_002_hole_resta_col_predicato_del_chiamante(self):
        # D30: senza predicato un "hole" non Ã¨ strutturale, con il predicato
        # del chiamante che lo riconosce sÃ¬
        hole = _circle((5, 5), 1, role="hole")
        _, labeled = topo.experimental.split_labeled(_square(0, 0, 10) + [hole])
        self.assertEqual(labeled, [hole])
        is_structural = lambda role: topo.is_structural_role(role) or role == "hole"
        kept, labeled = topo.experimental.split_labeled(_square(0, 0, 10) + [hole], is_structural)
        self.assertEqual(labeled, [])
        self.assertIn(hole, kept)


class TestCloseFreeGaps(unittest.TestCase):

    def test_001_gap_sotto_tolleranza_chiuso(self):
        edges = _square(0, 0, 10)
        edges[0] = _line((0, 0), (9.95, 0))
        # prima nessuna faccia, dopo una
        self.assertEqual(topo.experimental.face_loops(edges), [])
        self.assertEqual(len(topo.experimental.face_loops(topo.experimental.close_free_gaps(edges, 0.1))), 1)

    def test_002_gap_sopra_tolleranza_intatto(self):
        edges = _square(0, 0, 10)
        edges[0] = _line((0, 0), (9, 0))
        self.assertEqual(topo.experimental.close_free_gaps(edges, 0.1), edges)

    def test_003_parallele_si_chiudono_col_segmento_a_ogni_angolo(self):
        # G6e (drw_0015): due rette parallele con gli estremi a 0.004. Ruotate,
        # il parallelismo esatto si perde nell'ultimo bit e l'"incontro" cadeva
        # a 1e10 mm; un incontro oltre la tolleranza è un segmento (D60). Lontano
        # dall'origine, come nel disegno: lì l'errore della rotazione supera 1e-10
        for angle in (0.0, 0.7, 0.13, math.pi / 2):
            pieces = [LineSeg(start=(-71610.7, -3035.024), end=(-71537.6, -3035.024)),
                      LineSeg(start=(-71537.6, -3035.028), end=(-71513.2, -3035.028))]
            edges = [_line(s.start, s.end) for s in (p.rotated(angle) for p in pieces)]
            healed = topo.experimental.close_free_gaps(edges, 0.5)
            self.assertEqual(len(healed), 3, angle)
            for before, after in zip(edges, healed):
                self.assertLess(math.dist(before.segment.end, after.segment.end), 0.5, angle)
                self.assertLess(math.dist(before.segment.start, after.segment.start), 0.5, angle)


class TestDanglingSplines(unittest.TestCase):

    def test_001_spline_con_estremo_libero(self):
        spline = Edge(role=ContourRole.UNKNOWN, start=(0.0, 0.0), end=(5.0, 5.0),
                      segment=BSplineSeg(degree=1, control_points=[(0.0, 0.0), (5.0, 5.0)],
                                        knots=[0, 0, 1, 1]))
        self.assertEqual(topo.experimental.dangling_splines([spline]), [spline])
        self.assertEqual(topo.experimental.dangling_splines(_square(0, 0, 10)), [])


class TestFindNonContourEdges(unittest.TestCase):

    def test_001_diagonale_interna_esclusa(self):
        diagonal = _line((0.0, 0.0), (1.0, 2.0))
        edges = [_line((0.0, 0.0), (1.0, 0.0)), _line((1.0, 0.0), (1.0, 2.0)),
                 _line((1.0, 2.0), (0.0, 2.0)), _line((0.0, 2.0), (0.0, 0.0)), diagonal]
        self.assertEqual(topo.experimental.find_non_contour_edges(edges, 0.01), {id(diagonal)})

    def test_002_linea_fra_due_quadrati_esclusa(self):
        # percorsa andata e ritorno dal bordo esterno: non Ã¨ contorno di nessuno
        joint = _line((10.0, 10.0), (20.0, 20.0))
        edges = _square(0, 0, 10) + _square(20, 20, 10) + [joint]
        self.assertEqual(topo.experimental.find_non_contour_edges(edges, 0.01), {id(joint)})


class TestLooseEnds(unittest.TestCase):
    """Due quadrati uniti da una linea, piÃ¹ un moncone a 3 mm da un vertice:
    lo schema di F6 (D111)."""

    def setUp(self):
        self.joint = _line((10.0, 10.0), (20.0, 20.0))
        self.stub = _line((10.0, 0.0), (13.0, -4.0))
        self.chord = _line((0.0, 0.0), (10.0, 10.0))
        self.edges = _square(0, 0, 10) + _square(20, 20, 10) + [self.joint, self.stub]

    def test_001_la_linea_che_unisce_due_forme(self):
        candidates = topo.experimental.find_non_contour_edges(self.edges + [self.chord], 0.01)
        self.assertEqual(topo.experimental.find_joining_edges(self.edges + [self.chord], candidates), [self.joint],
                         "la diagonale di un quadrato Ã¨ una corda, non unisce niente")

    def test_002_estremo_libero_e_distanza(self):
        ends = topo.experimental.free_ends(self.edges)
        self.assertEqual([p for p, _ in ends], [(13.0, -4.0)])
        self.assertAlmostEqual(ends[0][1], 5.0)

    def test_003_heal_li_dice(self):
        result = topo.heal(Document(edges=self.edges, source_meta={"tolerance": 0.05})).faces()
        self.assertEqual(result.cluster_count, 2)
        self.assertTrue(any("estremi liberi" in w for w in result.warnings))
        self.assertTrue(any("uniscono due forme" in w for w in result.warnings))

    def test_004_pezzo_pulito_nessun_warning(self):
        result = topo.heal(Document(edges=_square(0, 0, 10), source_meta={"tolerance": 0.05})).faces()
        self.assertEqual(result.warnings, [])

    def test_005_estremo_fuso_dal_grafo_tollerante_non_e_libero(self):
        # l'angolo rotto lo chiude solo il grafo tollerante (D57): sui suoi
        # nodi i due capi dell'angolo sono uno, libero resta il moncone
        edges = _broken_square(spur=True)
        self.assertEqual([p for p, _ in topo.experimental.free_ends(edges)], [(10.0, 0.0), (10.1, -5.0)])
        self.assertEqual([p for p, _ in topo.experimental.free_ends(edges, epsilon=0.1)], [(10.1, -5.0)])


def _arc(radius, missing_deg, center=(0.0, 0.0)):
    half = math.radians(missing_deg) / 2
    return ArcSeg(center, radius, half, 2 * math.pi - half)


class TestShortElementsAndTolerance(unittest.TestCase):
    """D112: la tolleranza misura un gap, non la lunghezza di un lato. Quadrato
    100 con l'angolo in alto a destra raccordato/smussato, staccato di 0.3 ai
    due capi, tol 1: i lati vicini stanno entro tol fra loro, ma ognuno ha il
    capo dell'elemento corto piÃ¹ vicino."""

    GAP = 0.3

    def _heal(self, corner, a, b):
        g = self.GAP
        segs = [LineSeg((0, 0), (100, 0)), LineSeg((100, 0), (100, a - g)), corner,
                LineSeg((b - g, 100), (0, 100)), LineSeg((0, 100), (0, 0))]
        return topo.heal(topo.load_segments(segs, tolerance=1.0)).faces()

    def test_001_raccordo_resta(self):
        result = self._heal(ArcSeg((99.6, 99.6), 0.4, 0, math.pi / 2), 99.6, 99.6)
        self.assertEqual(result.cluster_count, 1)
        outer = result.clusters[0].outer
        self.assertIn("ArcSeg", [type(s).__name__ for s in outer.segments])
        self.assertAlmostEqual(outer.area, 10000 - (0.4 ** 2 - math.pi * 0.4 ** 2 / 4), places=3)

    def test_002_smusso_resta(self):
        c = 0.5 / math.sqrt(2)
        result = self._heal(LineSeg((100, 100 - c), (100 - c, 100)), 100 - c, 100 - c)
        self.assertEqual(result.cluster_count, 1)
        self.assertAlmostEqual(result.clusters[0].outer.area, 10000 - c * c / 2, places=3)

    def test_003_ogni_estremo_chiude_un_gap_solo(self):
        # tre estremi entro tol: si accoppiano i due piÃ¹ vicini, il terzo resta libero
        edges = [_line((0, 0), (10, 0)), _line((10.2, 0), (20, 0)), _line((10.5, 0.6), (10.5, 10))]
        healed = topo.experimental.close_free_gaps(edges, 1.0)
        self.assertEqual(len(topo.experimental.free_ends(healed)), 4, "i due capi esterni e i due del moncone")


class TestGapAtTolerance(unittest.TestCase):

    def test_gap_largo_quanto_la_tolleranza_si_chiude_a_ogni_moto(self):
        # G6e (regr_03): un foro con una cava larga 0.5, tolleranza 0.5. Il
        # confronto `d <= tol` lo decideva l'ultimo bit, diverso a ogni moto;
        # entro la tolleranza la comprende a meno del rumore (D183)
        from tests.invariants import MOTIONS, moved
        hole = [LineSeg(start=(52.659, 60.616), end=(60.0, 60.616)),
                LineSeg(start=(60.0, 60.616), end=(60.0, 70.0)),
                LineSeg(start=(60.0, 70.0), end=(45.0, 70.0)),
                LineSeg(start=(45.0, 70.0), end=(45.0, 60.616)),
                LineSeg(start=(45.0, 60.616), end=(52.159, 60.616))]
        plate = topo.geometry.rectangle(100, 100, center=(50, 60))
        doc = topo.load_segments(plate + hole, tolerance=0.5)
        for name, move, _, _ in [("al posto", lambda s: s, None, None)] + MOTIONS:
            result = topo.heal(moved(doc, move), tolerance=0.5).faces()
            self.assertEqual([len(c.inners) for c in result.clusters], [1], name)


def _closed_reading(doc, back):
    """Gli edge dopo close_free_gaps, riportati nel riferimento di partenza."""
    from shapely.geometry import LineString
    healed = topo.experimental.close_free_gaps(list(doc.edges), 0.5)
    return sorted(tuple(c for p in back(LineString(e.segment.discretize())).coords for c in p)
                  for e in healed)


def _same_at_every_motion(test, doc):
    from tests.invariants import MOTIONS, moved
    def same(a, b):
        return len(a) == len(b) and max(abs(u - v) for u, v in zip(a, b)) < 1e-6

    base = _closed_reading(doc, lambda g: g)
    for name, move, back, _ in MOTIONS:
        again = _closed_reading(moved(doc, move), back)
        # insiemi confrontati per vicinanza: ordinare coordinate col rumore
        # di un moto sarebbe di nuovo un ordine deciso dall'ultimo bit
        test.assertEqual(len(again), len(base), name)
        test.assertTrue(all(any(same(a, b) for b in base) for a in again), name)
        test.assertTrue(all(any(same(a, b) for a in again) for b in base), name)
    return base


class TestTiedGapPartners(unittest.TestCase):

    def test_capo_con_due_capi_alla_stessa_distanza_non_sceglie(self):
        # un capo che punta fra due capi liberi simmetrici, a 0.316 da tutti e
        # due, senza nessuna curva sulla sua strada: due compagni a pari
        # merito, nessuno scelto, e heal() lo dice (D185, D189)
        x, y = -71565.8225, -3048.0985
        pieces = [LineSeg(start=(x + 3, y + 0.3), end=(x, y + 0.3)),
                  LineSeg(start=(x - 0.1, y - 5), end=(x - 0.1, y)),
                  LineSeg(start=(x - 0.1, y + 5.6), end=(x - 0.1, y + 0.6))]
        doc = topo.load_segments(pieces, tolerance=0.5)
        _same_at_every_motion(self, doc)
        self.assertIn("stessa distanza", " ".join(topo.heal(doc, tolerance=0.5).faces().warnings))


class TestGapOntoCurve(unittest.TestCase):

    def test_il_capo_si_chiude_sulla_curva_piu_vicina(self):
        # G6e (drw_0015): il capo basso del tratto verticale sta a 0.125 dal
        # tratto orizzontale e a 0.28 dai suoi due capi: si chiude sul tratto,
        # a T, a ogni moto (D189)
        x, y = -71565.8225, -3048.0985
        pieces = [LineSeg(start=(x - 0.25, y), end=(x + 0.25, y)),
                  LineSeg(start=(x - 0.25, y + 0.375), end=(x + 0.25, y + 0.375)),
                  LineSeg(start=(x, y + 0.125), end=(x, y + 0.625))]
        doc = topo.load_segments(pieces, tolerance=0.5)
        base = _same_at_every_motion(self, doc)
        stem = next(e for e in base if abs(e[0] - x) < 1e-6 and abs(e[2] - x) < 1e-6)
        self.assertAlmostEqual(min(stem[1], stem[3]), y, places=6)

    def test_due_incontri_sulla_continuazione_vince_il_primo(self):
        # G6e, gruppo D, `gap_solver.py:250` (`min` sugli incontri): la retta
        # proseguita taglia il cerchio a 0.2 e a 0.4, il capo va a 0.2 a ogni
        # moto. Prova: la riga sceglie fra due incontri (contati al posto) e la
        # scelta non cambia. Non c'è un pari merito fra punti distinti da
        # provare: sulla continuazione (retta, o arco fino a un quarto di giro)
        # la distanza dal capo cresce lungo la curva, due incontri alla stessa
        # distanza sono lo stesso punto; la tangente dà un punto solo. Sui
        # disegni tracciati la riga non sceglie mai (un incontro solo, 14314
        # chiamate). Si confronta il capo della retta: la discretizzazione del
        # cerchio ruota con la sua griglia angolare (D145).
        from unittest import mock
        from shapely.geometry import Point
        from tests.invariants import MOTIONS, moved
        from topo.core.base import gap_solver
        x, y = -71565.8225, -3048.0985
        doc = topo.load_segments([LineSeg(start=(x - 5, y), end=(x, y)),
                                  CircleSeg(center=(x + 0.3, y), radius=0.1)], tolerance=0.5)
        counts = []
        real = gap_solver.intersections

        def counted(a, b, *args, **kwargs):
            hits = real(a, b, *args, **kwargs)
            counts.append(len(hits))
            return hits

        for name, move, back, _ in [("al posto", lambda d: d, lambda g: g, None)] + list(MOTIONS):
            counts.clear()
            with mock.patch.object(gap_solver, "intersections", counted):
                healed = topo.experimental.close_free_gaps(list(moved(doc, move).edges), 0.5)
            self.assertIn(2, counts, name)
            ends = [back(Point(e.segment.end)).coords[0] for e in healed if isinstance(e.segment, LineSeg)]
            self.assertEqual(len(ends), 1, name)
            self.assertAlmostEqual(ends[0][0], x + 0.2, places=6, msg=name)
            self.assertAlmostEqual(ends[0][1], y, places=6, msg=name)

    def test_un_angolo_rotto_si_chiude_nell_angolo(self):
        # le due rette si incontrano nell'angolo vero: quello di prima (D57)
        # che outlines() non chiudeva, ora uguale in tutte e due le letture
        pieces = [LineSeg(start=(0, 0), end=(99.9, 0)), LineSeg(start=(100, 0.1), end=(100, 50)),
                  LineSeg(start=(100, 50), end=(0, 50)), LineSeg(start=(0, 50), end=(0, 0))]
        doc = topo.load_segments(pieces)
        for result in (topo.heal(doc, tolerance=0.5).faces(), topo.heal(doc, max_gap=0.5).outlines()):
            self.assertEqual([round(to_shapely(c.outer).area, 3) for c in result.clusters], [5000.0])


class TestArcLineMeetUnderMotion(unittest.TestCase):
    """G6e, gruppo D, `intersections._closest_to`: un arco che finisce nel suo
    culmine e una retta che taglia il cerchio 0.05 sotto. I due incontri stanno
    alla stessa distanza dal capo dell'arco: prima vinceva l'ultimo bit (±0.312
    secondo il moto). Ora decide la distanza dal capo della retta, e se anche
    quella è pari il gap si chiude col ponte fra i due capi. Prova la scelta al
    posto (due candidati pari sul capo dell'arco, contati) e a sei moti. Sui
    disegni tracciati lo scarto minimo fra i due candidati è 2.08 mm: lì non
    cambia niente."""

    MOTIONS = [(0.0, 0.0, 0.0), (1e-12, 0.0, 0.0), (-1e-12, 0.0, 0.0),
               (0.7, 3.1, -2.2), (math.pi / 2, 0.0, 0.0), (2.1, -1e5, 3e4)]

    def _closed(self, motion, offset):
        from unittest import mock
        from tests.invariants import rigid
        from topo.core.base import gap_solver
        from topo.core.geometry.measure import FLOAT_NOISE
        from topo.core.primitives.segments import segment_endpoints
        x, y = -71565.8225, -3048.0985
        move_seg, move_pt = rigid(*motion)
        pieces = [ArcSeg(center=(x, y), radius=1.0, start_angle=0.0, end_angle=math.pi / 2, ccw=True),
                  LineSeg(start=(x - 5, y + 0.95), end=(x + offset, y + 0.95))]
        doc = topo.load_segments([move_seg(p) for p in pieces], tolerance=0.5)
        tied = []
        real = gap_solver._closest_to

        def counted(candidates, ref, *rest):
            d = [math.dist(q, ref) for q in candidates]
            tied.append(len(d) == 2 and abs(d[0] - d[1]) <= FLOAT_NOISE)
            return real(candidates, ref, *rest)

        with mock.patch.object(gap_solver, "_closest_to", counted):
            healed = topo.experimental.close_free_gaps(list(doc.edges), 0.5)
        self.assertEqual(tied, [True], motion)
        a, tx, ty = motion
        c, s = math.cos(-a), math.sin(-a)
        back = lambda p: (c * (p[0] - tx) - s * (p[1] - ty) - x, s * (p[0] - tx) + c * (p[1] - ty) - y)
        return [(type(e.segment).__name__, *(round(v, 6) + 0.0 for p in segment_endpoints(e.segment)
                                              for v in back(p))) for e in healed]

    def test_capo_della_retta_a_meta_ponte_a_ogni_moto(self):
        for motion in self.MOTIONS:
            closed = self._closed(motion, 0.0)
            self.assertEqual(len(closed), 3, motion)
            bridges = [{e[1:3], e[3:5]} for e in closed if e[0] == "LineSeg"]
            self.assertIn({(0.0, 0.95), (0.0, 1.0)}, bridges, motion)

    def test_capo_della_retta_di_lato_l_incontro_dal_suo_lato(self):
        for motion in self.MOTIONS:
            closed = self._closed(motion, -0.1)
            self.assertEqual(len(closed), 2, motion)
            line = next(e for e in closed if e[0] == "LineSeg")
            self.assertEqual(line[3:], (-0.31225, 0.95), motion)


class TestCloseNearFullArcs(unittest.TestCase):
    """D112: un arco diventa cerchio solo se il gap Ã¨ entro tolleranza (Ã¨ un
    gap) E l'angolo mancante Ã¨ entro la soglia (Ã¨ un cerchio)."""

    def _close(self, seg, tolerance, **kw):
        doc = topo.load_segments([seg], tolerance=0.01)
        edges, n = topo.experimental.close_near_full_arcs(list(doc.edges), tolerance, **kw)
        return type(edges[0].segment).__name__, n

    def test_001_export_rotto_diventa_cerchio(self):
        self.assertEqual(self._close(_arc(3.0, 0.4), 0.05), ("CircleSeg", 1))

    def test_002_gap_entro_tol_ma_non_e_un_cerchio(self):
        self.assertEqual(self._close(_arc(0.4, 90), 1.0), ("ArcSeg", 0), "un tre quarti piccolo")
        self.assertEqual(self._close(_arc(10.0, 2.9), 1.0), ("ArcSeg", 0))

    def test_003_quasi_cerchio_ma_gap_oltre_tol(self):
        self.assertEqual(self._close(_arc(500.0, 1.5), 0.1), ("ArcSeg", 0))

    def test_004_solo_angolo_a_scelta_del_chiamante(self):
        self.assertEqual(self._close(_arc(500.0, 1.5), math.inf), ("CircleSeg", 1))

    def test_005_capo_collegato_non_si_chiude(self):
        arc = _arc(10.0, 1.0)
        end = arc._point_at(arc.end_angle)
        doc = topo.load_segments([arc, LineSeg(end, (end[0] + 5, end[1]))], tolerance=0.01)
        _, n = topo.experimental.close_near_full_arcs(list(doc.edges), 1.0)
        self.assertEqual(n, 0)

    def _close_all(self, segs, tolerance):
        doc = topo.load_segments(segs, tolerance=0.01)
        edges, n = topo.experimental.close_near_full_arcs(list(doc.edges), tolerance)
        return [type(e.segment).__name__ for e in edges], n

    def test_008_due_archi_coi_buchi_sotto_i_2_gradi_sono_un_cerchio(self):
        # D218: ogni buco (1,72°, corda 0,15) è entro tolleranza e sotto i 2°
        arcs = [ArcSeg((0, 0), 5, 0.015, math.pi - 0.015), ArcSeg((0, 0), 5, math.pi + 0.015, 2 * math.pi - 0.015)]
        self.assertEqual(self._close_all(arcs, 0.5), (["CircleSeg"], 1))

    def test_009_buco_da_1_si_unisce_quello_da_3_resta_aperto(self):
        # D218: il buco da 1° si chiude, gli archi sono uno solo aperto di 3°
        h = lambda deg: math.radians(deg) / 2
        arcs = [ArcSeg((0, 0), 5, h(1), math.pi - h(3)), ArcSeg((0, 0), 5, math.pi + h(3), 2 * math.pi - h(1))]
        doc = topo.load_segments(arcs, tolerance=0.01)
        edges, n = topo.experimental.close_near_full_arcs(list(doc.edges), 0.5)
        self.assertEqual((len(edges), n), (1, 1))
        self.assertAlmostEqual(math.degrees(2 * math.pi - edges[0].segment._sweep()), 3.0)
        self.assertNotEqual(edges[0].start, edges[0].end)

    def test_010_due_archi_oltre_tolleranza_non_fanno_il_cerchio(self):
        arcs = [ArcSeg((0, 0), 5, 0.015, math.pi - 0.015), ArcSeg((0, 0), 5, math.pi + 0.015, 2 * math.pi - 0.015)]
        self.assertEqual(self._close_all(arcs, 0.1), (["ArcSeg", "ArcSeg"], 0))

    def test_007_punta_di_spigolo_coi_capi_fusi_non_si_chiude(self):
        # i due capi cadono nello stesso nodo, ma a quel nodo arrivano due lati
        arc = _arc(1.5, 0.01)
        a, b = arc._point_at(arc.start_angle), arc._point_at(arc.end_angle)
        # senza griglia (D216) i capi a 0,00026 mm restano due punti: il nodo
        # unico lo dà un'unione di nodi, qui scritta a mano
        node = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        edges = [Edge.of(LineSeg((20, 0.3), a), ContourRole.UNKNOWN), Edge.of(arc, ContourRole.UNKNOWN),
                 Edge.of(LineSeg(b, (20, -0.3)), ContourRole.UNKNOWN)]
        edges = [replace(edges[0], end=node), replace(edges[1], start=node, end=node),
                 replace(edges[2], start=node)]
        _, n = topo.experimental.close_near_full_arcs(edges, 0.1)
        self.assertEqual(n, 0)


class TestSingleNodeGrid(unittest.TestCase):
    """D113: la tolleranza chiude i gap, non arrotonda i nodi. Lecca-lecca:
    quadrato con un arco r=1.5 di 359.4Â° in punta a un cuneo strettissimo, i
    due lati attaccati esatti ai capi dell'arco, capi a 0.016 fra loro."""

    def _lollipop(self):
        arc = _arc(1.5, 0.6)
        a, b = arc._point_at(arc.start_angle), arc._point_at(arc.end_angle)
        return [LineSeg((20, 0.3), (20, 20)), LineSeg((20, 20), (60, 20)), LineSeg((60, 20), (60, -20)),
                LineSeg((60, -20), (20, -20)), LineSeg((20, -20), (20, -0.3)), LineSeg((20, -0.3), b),
                arc, LineSeg(a, (20, 0.3))]

    def test_001_l_arco_in_punta_resta_nell_outer(self):
        for tol in (0.05, 0.5):
            with self.subTest(tolerance=tol):
                result = topo.heal(topo.load_segments(self._lollipop(), tolerance=tol)).faces()
                self.assertEqual(result.cluster_count, 1)
                cluster = result.clusters[0]
                self.assertEqual(cluster.inners, [], "l'arco non Ã¨ un foro")
                arcs = [s for s in cluster.outer.segments if isinstance(s, ArcSeg)]
                self.assertEqual(len(arcs), 1)
                self.assertGreater(math.degrees(arcs[0]._sweep()), 359)

    def test_002_i_nodi_non_dipendono_dalla_tolleranza(self):
        nodes = lambda tol: [(e.start, e.end) for e in topo.load_segments(self._lollipop(), tolerance=tol).edges]
        self.assertEqual(nodes(0.005), nodes(0.5))

    def test_006_heal_non_chiude_un_arco_per_sola_tolleranza(self):
        result = topo.heal(topo.load_segments([_arc(10.0, 2.9)], tolerance=1.0)).faces()
        self.assertEqual(result.cluster_count, 0)


class TestFaceLoops(unittest.TestCase):
    """I giri delle facce limitate: uno per faccia, mai scelto da un ordine (D189)."""

    def test_001_un_quadrato_un_giro(self):
        self.assertEqual(len(topo.experimental.face_loops(_square(0, 0, 10))), 1)

    def test_002_due_asole_che_si_toccano_due_giri(self):
        # due fori quadri che si toccano in un angolo: due giri, non il giro a otto
        loops = topo.experimental.face_loops(_square(0, 0, 100) + _square(20, 20, 20) + _square(40, 40, 20))
        self.assertEqual(sorted(round(to_shapely(c).area) for c in topo.experimental.loops_to_curves(loops)),
                         [400, 400, 10000])

    def test_003_nessuna_faccia(self):
        self.assertEqual(topo.experimental.face_loops([_line((0, 0), (10, 0)), _line((20, 0), (20, 10))]), [])

    def test_004_un_cerchio_da_solo_e_un_giro(self):
        self.assertEqual(len(topo.experimental.face_loops([_circle((50, 5), 2)])), 1)

    def test_005_non_tocca_gli_edge_in_ingresso(self):
        edges = _square(0, 0, 10)
        before = [e.segment for e in edges]
        topo.experimental.face_loops(edges)
        self.assertEqual([e.segment for e in edges], before)


class TestLoopsToCurves(unittest.TestCase):

    def test_001_loop_con_un_edge_non_strutturale_scartato(self):
        engraved = _square(20, 0, 5, role="engrave")
        loops = topo.experimental.face_loops(_square(0, 0, 10) + engraved)
        self.assertEqual(len(loops), 2)
        kept = topo.experimental.structural_loops(loops)
        self.assertEqual(len(kept), 1)
        curves = topo.experimental.loops_to_curves(kept)
        self.assertEqual([round(to_shapely(f).area) for f in curves], [100])

    @staticmethod
    def _arc_with_chords(center=(5.0, 5.0), radius=0.64, n=15):
        # Un quarto di cerchio disegnato due volte: l'arco e la sua copia a
        # corde. Chiudono un giro di area ~6e-4, sotto MIN_CONTOUR_AREA.
        arc = ArcSeg(center=center, radius=radius, start_angle=0.0,
                     end_angle=math.pi / 2, ccw=True)
        pts = [arc._point_at(k * (math.pi / 2) / n) for k in range(n + 1)]
        return [arc] + [LineSeg(start=pts[i], end=pts[i + 1]) for i in range(n)]

    def test_002_giro_senza_area_torna_come_curve_aperte(self):
        doc = topo.load_segments(self._arc_with_chords())
        loops = topo.experimental.face_loops(doc.edges)
        self.assertEqual(len(loops), 1)
        curves = topo.experimental.loops_to_curves(loops)
        self.assertEqual(len(curves), 16)
        self.assertTrue(all(isinstance(c, OpenCurve) for c in curves))

    def test_003_micro_cerchio_torna_come_curva_aperta(self):
        loops = topo.experimental.face_loops([_circle((0.0, 0.0), 0.01)])
        curves = topo.experimental.loops_to_curves(loops)
        self.assertEqual(len(curves), 1)
        self.assertIsInstance(curves[0], OpenCurve)
        self.assertIsInstance(curves[0].segments[0], CircleSeg)

    def test_004_heal_non_perde_il_giro_senza_area(self):
        # D137: l'arco e le corde non sono contorno, stanno in loose (D151).
        # Otto corde: troppo poche per essere una curva scritta a punti, che
        # heal rifitterebbe e fonderebbe con l'arco (D189); il giro resta
        # senza area (8e-4 mm², sotto MIN_CONTOUR_AREA)
        square = [LineSeg(start=a, end=b) for a, b in
                  [((0, 0), (10, 0)), ((10, 0), (10, 10)), ((10, 10), (0, 10)), ((0, 10), (0, 0))]]
        result = topo.heal(topo.load_segments(square + self._arc_with_chords(radius=0.4, n=8))).faces()
        self.assertEqual(result.cluster_count, 1)
        loose = [s for curve in result.loose for s in curve.segments]
        self.assertEqual(sum(isinstance(s, ArcSeg) for s in loose), 1)
        self.assertEqual(sum(isinstance(s, LineSeg) for s in loose), 8)


class TestLabeledAndHierarchy(unittest.TestCase):

    def test_001_loose_curves_chiuso_e_aperto(self):
        # una regola sola per loose (D162): chiuso da sé esce chiuso, ruolo intatto
        curves = topo.experimental.loose_curves([_circle((5, 5), 1, role="engrave"),
                                                 _line((0, 0), (3, 0), role="engrave")])
        self.assertEqual(sorted(type(f).__name__ for f in curves), ["ClosedCurve", "OpenCurve"])
        self.assertTrue(all(f.role == "engrave" for f in curves))

    def test_002_quadrato_dentro_quadrato(self):
        loops = topo.experimental.face_loops(_square(0, 0, 10) + _square(3, 3, 4))
        clusters, trash = topo.experimental.build_hierarchy(topo.experimental.loops_to_curves(loops), label="p")
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].inners), 1)
        self.assertEqual(clusters[0].inners[0].depth, 1)
        self.assertEqual(clusters[0].label, "p")
        self.assertEqual(trash, [])


class TestComposition(unittest.TestCase):
    """I passi composti a mano nell'ordine di heal() danno i cluster di heal()."""

    def _compose(self, doc, tol):
        prepared = topo.experimental.prepare(doc.edges)
        edges = topo.experimental.normalize(prepared.edges, tol + 1e-6, keep_junctions=True).edges
        noded = topo.experimental.split_at_crossings(edges, tol)
        non_contour = topo.experimental.non_contour_pieces(noded, tol)
        loops = [noded.whole(loop) for loop in topo.experimental.face_loops(
            [p for p in noded.pieces if id(p) not in non_contour])]
        kept = topo.experimental.structural_loops(loops)
        clusters, _ = topo.experimental.build_hierarchy(topo.experimental.loops_to_curves(kept))
        return clusters

    def test_001_stessi_cluster_di_heal(self):
        for name in ("rect_with_circle_hole.dxf", "flangia con fori.DXF", "two_parts.dxf"):
            with self.subTest(name=name):
                doc = topo_dxf.load_dxf(str(EXAMPLES / name))
                expected = topo.heal(doc).faces().clusters
                got = self._compose(doc, doc.source_meta.get("tolerance", 0.05))
                self.assertEqual([to_shapely(c.outer).wkt for c in got],
                                 [to_shapely(c.outer).wkt for c in expected])
                self.assertEqual([len(c.inners) for c in got], [len(c.inners) for c in expected])


if __name__ == "__main__":
    unittest.main(verbosity=2)
