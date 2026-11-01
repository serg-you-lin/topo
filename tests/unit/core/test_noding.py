# tests/unit/core/test_noding.py

import math
import unittest
from topo.core.topology.noding import split_at_crossings, renode
from topo.core.topology.edge import Edge
from topo.core.primitives.segments import LineSeg, CircleSeg, ArcSeg


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _circle(center, radius):
    pt = (center[0] + radius, center[1])
    return Edge(role="unknown", start=pt, end=pt, segment=CircleSeg(center=center, radius=radius))


class TestSplitAtCrossings(unittest.TestCase):

    def test_incrocio_a_x_diventa_un_nodo(self):
        a, b = _line((0, 0), (10, 10)), _line((0, 10), (10, 0))
        noded = split_at_crossings([a, b], tolerance=0.05)
        self.assertEqual(len(noded.pieces), 4)
        # tutti e quattro i pezzi si incontrano nello stesso nodo (5, 5)
        ends = [p.end for p in noded.pieces if p.end == (5.0, 5.0)] + \
               [p.start for p in noded.pieces if p.start == (5.0, 5.0)]
        self.assertEqual(len(ends), 4)

    def test_contatto_a_t_spezza_solo_chi_viene_toccato(self):
        base, stem = _line((0, 0), (10, 0)), _line((5, 0), (5, 5))
        noded = split_at_crossings([base, stem], tolerance=0.05)
        self.assertEqual(len(noded.pieces), 3)
        self.assertIs(noded.parent_of(noded.pieces[-1]), stem)

    def test_estremi_originali_restano_i_nodi_dell_edge(self):
        a, b = _line((0, 0), (10, 0)), _line((5, -1), (5, 1))
        noded = split_at_crossings([a, b], tolerance=0.05)
        first = [p for p in noded.pieces if noded.parent_of(p) is a]
        self.assertEqual(first[0].start, a.start)
        self.assertEqual(first[-1].end, a.end)

    def test_cerchio_incrociato_diventa_archi(self):
        # un cerchio attraversato da una retta: due archi fra i due tagli
        noded = split_at_crossings([_circle((0, 0), 5), _line((-10, 0), (10, 0))], tolerance=0.05)
        arcs = [p for p in noded.pieces if isinstance(p.segment, ArcSeg)]
        self.assertEqual(len(arcs), 2)
        total = sum(p.segment.radius * p.segment._sweep() for p in arcs)
        self.assertAlmostEqual(total, 2 * math.pi * 5, places=6)

    def test_cerchio_non_toccato_resta_intero(self):
        c = _circle((0, 0), 1)
        noded = split_at_crossings([c, _line((5, 0), (6, 0))], tolerance=0.05)
        self.assertIn(c, noded.pieces)

    def test_quasi_tangenza_e_un_nodo_solo_non_due(self):
        """Una retta quasi tangente a un arco incrocia in due radici
        matematicamente distinte ma vicinissime (D100, D101): entro
        `tolerance` sono lo stesso contatto, non due nodi con uno sliver
        in mezzo."""
        radius, tol, gap = 10.0, 0.05, 0.02   # gap scelto < tol, >> _MIN_PIECE
        sink = (gap / 2) ** 2 / (2 * radius)  # affondamento che produce quel gap
        x = radius - sink
        half = math.sqrt(2 * radius * sink - sink * sink)
        arc = Edge(role="unknown", start=(0, -radius), end=(0, radius),
                   segment=ArcSeg(center=(0, 0), radius=radius,
                                  start_angle=-math.pi / 2, end_angle=math.pi / 2, ccw=True))
        line = _line((x, -half - 1), (x, half + 1))
        noded = split_at_crossings([arc, line], tolerance=tol)
        pieces_of = lambda parent: [p for p in noded.pieces if noded.parent_of(p) is parent]
        self.assertEqual(len(pieces_of(arc)), 2)
        self.assertEqual(len(pieces_of(line)), 2)


class TestContattoDecisoUnaVolta(unittest.TestCase):
    """D180: ogni contatto si decide una volta per coppia, sulle curve vere,
    e dà un nodo solo, la stessa tupla per tutti gli edge che tocca."""

    def _pieces_of(self, noded, parent):
        return [p for p in noded.pieces if noded.parent_of(p) is parent]

    def test_t_a_meno_di_un_centesimo_condivide_il_nodo(self):
        # il gambo finisce 0.004 sopra la base: la base si taglia e il suo
        # nodo è l'estremo del gambo, non la proiezione arrotondata
        base, stem = _line((0, 0), (10, 0)), _line((5, 0.004), (5, 5))
        noded = split_at_crossings([base, stem], tolerance=0.05)
        cuts = {p.end for p in self._pieces_of(noded, base)[:-1]}
        self.assertEqual(cuts, {stem.start})

    def test_t_su_una_spline_la_taglia(self):
        from topo.core.primitives.segments import BSplineSeg
        spline = BSplineSeg(degree=2, control_points=[(0, 0), (5, 2), (10, 0)],
                            knots=[0, 0, 0, 1, 1, 1])
        top = spline._evaluate(0.5)
        curve = Edge(role="unknown", start=(0.0, 0.0), end=(10.0, 0.0), segment=spline)
        stem = _line((round(top[0], 3), round(top[1] + 0.002, 3)), (5, 8))
        noded = split_at_crossings([curve, stem], tolerance=0.05)
        halves = self._pieces_of(noded, curve)
        self.assertEqual(len(halves), 2)
        self.assertTrue(all(isinstance(p.segment, BSplineSeg) for p in halves))
        self.assertEqual(halves[0].end, stem.start)
        self.assertEqual(halves[1].start, stem.start)

    def test_tangenza_mancata_e_un_contatto(self):
        # una retta passa 0.004 fuori da un cerchio senza toccarlo: un nodo
        # condiviso, e il cerchio, toccato una volta sola, resta intero
        c, line = _circle((0, 0), 5), _line((-10, 5.004), (10, 5.004))
        noded = split_at_crossings([c, line], tolerance=0.05)
        self.assertEqual(len(self._pieces_of(noded, line)), 2)
        self.assertIn(c, noded.pieces)

    def test_due_t_vicini_restano_due_nodi_ognuno_col_suo_gambo(self):
        # due gambi a 0.03 l'uno dall'altro (< tolerance, > GRAPH_EPSILON): due
        # contatti di coppie diverse, due nodi, ognuno uguale al suo gambo
        base = _line((0, 0), (10, 0))
        a, b = _line((5, 0), (5, 5)), _line((5.03, 0), (5.03, -5))
        noded = split_at_crossings([base, a, b], tolerance=0.05)
        nodes = [p.end for p in self._pieces_of(noded, base)[:-1]]
        self.assertEqual(nodes, [a.start, b.start])

    def test_un_lato_corto_non_sparisce(self):
        # un lato di 0.008 fra due rette: i suoi due estremi non diventano
        # un nodo solo, anche se ognuno è entro GRAPH_EPSILON dall'altro
        left, short, right = _line((0, 0), (5, 0)), _line((5, 0), (5.008, 0)), _line((5.008, 0), (10, 3))
        noded = split_at_crossings([left, short, right], tolerance=0.05)
        piece = self._pieces_of(noded, short)
        self.assertEqual(len(piece), 1)
        self.assertNotEqual(piece[0].start, piece[0].end)


class TestRenode(unittest.TestCase):

    def test_nodi_dal_punto_reale(self):
        # nodo arrotondato a 1 decimale, punto reale a 3: il nodo segue il punto reale
        e = Edge(role="unknown", start=(0.0, 0.0), end=(1.0, 0.0),
                 segment=LineSeg(start=(0.0, 0.0), end=(1.034, 0.0)))
        self.assertEqual(renode([e])[0].end, (1.034, 0.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestNodesUnderMotion(unittest.TestCase):
    """G6e, gruppo B: `renode` arrotondava ogni capo da sé. Due archi di una
    polilinea con bulge (passo 0.004 mm) hanno il vertice comune in due copie
    a 1 ulp; con un bordo di cella fra loro diventano due nodi, e
    `decide_nodes` non li riunisce in un gruppo più largo di `epsilon` (D186):
    la catena si spezzava."""

    def test_un_vertice_su_un_bordo_di_cella_resta_un_nodo(self):
        from collections import Counter
        import topo
        from tests.invariants import rigid
        from topo.core.topology.noding import decide_nodes
        pts = [(k * 0.004, 0.002 * math.sin(k * 0.7)) for k in range(60)]
        arcs = [ArcSeg.from_chord(a, b, 0.02 if i % 2 else -0.02) for i, (a, b) in enumerate(zip(pts, pts[1:]))]
        # al posto; i vertici a metà fra due celle di 1e-3; e ruotato
        for motion in [(0.0, 0.0, 0.0), (0.0, 3000000.0005, -2500000.000476336),
                       (0.1, 3000000.0001767986, -2500000.0004505813)]:
            with self.subTest(motion=motion):
                segment, _ = rigid(*motion)
                out, _ = decide_nodes(topo.load_segments([segment(a) for a in arcs]).edges)
                ends = Counter(n for e in out for n in (e.start, e.end))
                self.assertEqual(sorted(ends.values()).count(1), 2)


class TestEndContactsUnderMotion(unittest.TestCase):
    """G6e, `noding.py:404` e `:658`: un contatto a meno di 1e-9 da un capo
    (`at_end`, `_EPS`) e due archi quasi concentrici (`d < _EPS`). Le due
    soglie sono vicine al rumore; questi casi, pensati per romperle, danno
    gli stessi pezzi e gli stessi nodi al posto, ruotati e lontano."""

    MOTIONS = [(0.031, 0.0, 0.0), (0.7, 3e6, -2.5e6), (2.294, 3e6, -2.5e6), (math.pi / 2, -7e5, 4e5)]

    def _reading(self, segs, motion):
        from collections import Counter
        import topo
        from tests.invariants import rigid
        segment, _ = rigid(*motion)
        out = split_at_crossings(topo.load_segments([segment(s) for s in segs]).edges, 0.5)
        nodes = Counter(n for e in out.pieces for n in (e.start, e.end))
        return len(out.pieces), sorted(nodes.values())

    def _same_at_every_motion(self, segs, at_rest):
        self.assertEqual(self._reading(segs, (0.0, 0.0, 0.0)), at_rest)
        for motion in self.MOTIONS:
            with self.subTest(motion=motion):
                self.assertEqual(self._reading(segs, motion), at_rest)

    def test_t_sul_capo_di_un_tratto_piu_corto_di_node(self):
        # 0.008 < node (0.01): il caso in cui `_union` può rifiutare
        self._same_at_every_motion(
            [LineSeg(start=(0.0, 0.0), end=(0.008, 0.0)), LineSeg(start=(0.008, 0.0), end=(0.008, 5.0)),
             LineSeg(start=(0.0, 0.0), end=(0.0, -5.0))], (3, [1, 1, 2, 2]))

    def test_retta_sul_capo_di_un_arco_corto(self):
        end = (0.05 * math.cos(0.15), 0.05 * math.sin(0.15))
        self._same_at_every_motion(
            [ArcSeg(center=(0.0, 0.0), radius=0.05, start_angle=0.0, end_angle=0.15),
             LineSeg(start=end, end=(3.0, 3.0))], (2, [1, 1, 2]))

    def test_archi_quasi_concentrici_a_meno_di_node(self):
        for offset in (0.0, 0.8e-9, 1.2e-9, 3e-9, 1e-7):
            with self.subTest(offset=offset):
                c = (offset * math.cos(0.7), offset * math.sin(0.7))
                self._same_at_every_motion(
                    [ArcSeg(center=(0.0, 0.0), radius=5.0, start_angle=0.2, end_angle=1.2),
                     ArcSeg(center=c, radius=5.005, start_angle=0.0, end_angle=1.4)], self._reading(
                        [ArcSeg(center=(0.0, 0.0), radius=5.0, start_angle=0.2, end_angle=1.2),
                         ArcSeg(center=c, radius=5.005, start_angle=0.0, end_angle=1.4)], (0.0, 0.0, 0.0)))


class TestEndNodeUnderMotion(unittest.TestCase):
    """G6e, gruppo D, `noding.py:536`: un nodo con più capi d'ingresso distinti
    era il più piccolo in (x, y), che un moto cambia. Il capo di una retta a
    (0.009, 0.009) dal capo (0, 0) di un'altra: a 0.009 dalla curva, entro
    `node` dal suo capo lungo di essa, i due capi sono un nodo. Al posto era
    (0, 0), a mezzo giro e a un quarto di giro (0.009, 0.009)."""

    SEGMENTS = [LineSeg(start=(0.0, 0.0), end=(10.0, 0.0)),
                LineSeg(start=(0.009, 0.009), end=(0.009, 5.0)),
                LineSeg(start=(0.0, 0.0), end=(0.0, -5.0))]

    def _node(self, motion):
        """(il nodo vicino ai due capi, il moto del punto)."""
        import topo
        from tests.invariants import rigid
        segment, point = rigid(*motion)
        out = split_at_crossings(topo.load_segments([segment(s) for s in self.SEGMENTS]).edges, 0.5)
        nodes = {n for e in out.pieces for n in (e.start, e.end)}
        return min(nodes, key=lambda n: math.dist(n, point((0.0, 0.0)))), point

    def test_il_nodo_dei_due_capi_non_dipende_dal_moto(self):
        at_rest, _ = self._node((0.0, 0.0, 0.0))
        for motion in [(math.pi, 0.0, 0.0), (math.pi / 2, 0.0, 0.0), (0.7, 3e3, -2e3)]:
            with self.subTest(motion=motion):
                node, point = self._node(motion)
                # entro due celle della griglia dei nodi (1e-3), non 0.0127
                self.assertLess(math.dist(node, point(at_rest)), 2e-3)


class TestCrossingNodesUnderMotion(unittest.TestCase):
    """G6e, gruppo B, `noding.py:539-540`: un nodo senza capi è la media dei
    suoi punti di contatto arrotondata alla griglia. Tre rette, la terza taglia
    le prime due vicino al loro incrocio: un triangolino con due vertici-incrocio
    a 0.01074, due nodi. Arrotondati, al moto qui sotto distano <= GRAPH_EPSILON
    e il grafo (`cluster_points`) li fondeva: outer di 2 lati, il terzo in loose."""

    SEGMENTS = [
        LineSeg(start=(-0.4038192179613853, -0.9069697819400884), end=(0.3999047733007083, 0.9244307056293919)),
        LineSeg(start=(0.949814645702292, -0.31496011887135034), end=(-0.9430275941383344, 0.33091003454582124)),
        LineSeg(start=(0.013853742779737218, -0.004663352290131094), end=(-0.9611844021439172, 0.2173740678530485)),
    ]

    def test_due_incroci_oltre_graph_epsilon_restano_due_nodi(self):
        import topo
        from tests.invariants import rigid
        for motion in [(0.0, 0.0, 0.0), (0.8126685826151423, -0.5047703326061714, -0.21810059373354584)]:
            with self.subTest(motion=motion):
                segment, _ = rigid(*motion)
                result = topo.island(topo.load_segments([segment(s) for s in self.SEGMENTS]), max_gap=0.0)
                self.assertEqual(len(result.clusters), 1)
                self.assertEqual(len(result.clusters[0].outer.segments), 3)
                self.assertEqual(len(result.loose), 5)
