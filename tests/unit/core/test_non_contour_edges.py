# tests/unit/core/test_non_contour_edges.py

import unittest
from topo.core.topology.graph import build_node_graph
from topo.core.topology.non_contour_edges import NonContourEdgeDetector
from topo.core.topology.edge import Edge
from topo.core.primitives.segments import LineSeg

def _make_edge(p1, p2):
    # Il ruolo qui è irrilevante per NonContourEdgeDetector, che lavora per
    # sola topologia (branching + faccia esterna), mai per ruolo
    # — una stringa qualunque non-strutturale basta (era ContourRole.BEND,
    # ora vocabolario di tools/manufacturing_role.py, non del motore).
    return Edge(
        role="bending",
        start=p1,
        end=p2,
        segment=LineSeg(start=p1, end=p2),
    )


class TestNonContourEdgeDetector(unittest.TestCase):

    def test_linea_interna_confermata(self):
        # rettangolo con diagonale interna
        #
        #  (0,2)-----(1,2)
        #    |    /    |
        #  (0,0)-----(1,0)
        #
        # la diagonale (0,0)-(1,2) è una catena di un edge fra due nodi
        # branching e il bordo della faccia esterna non la percorre → esclusa
        # dal grafo dei contorni

        edges = [
            _make_edge((0.0, 0.0), (1.0, 0.0)),
            _make_edge((1.0, 0.0), (1.0, 2.0)),
            _make_edge((1.0, 2.0), (0.0, 2.0)),
            _make_edge((0.0, 2.0), (0.0, 0.0)),
            _make_edge((0.0, 0.0), (1.0, 2.0)),  # edge non di contorno
        ]
        g = build_node_graph(edges)
        result = NonContourEdgeDetector(tolerance=0.01).detect(g, edges)
        non_contour_edge = edges[-1]
        self.assertIn(id(non_contour_edge), result)

    def test_linea_sul_bordo_ignorata(self):
        # triangolo semplice — nessun nodo branching → niente da escludere
        edges = [
            _make_edge((0.0, 0.0), (1.0, 0.0)),
            _make_edge((1.0, 0.0), (0.5, 1.0)),
            _make_edge((0.5, 1.0), (0.0, 0.0)),
        ]
        g = build_node_graph(edges)
        result = NonContourEdgeDetector(tolerance=0.01).detect(g, edges)
        self.assertEqual(len(result), 0)

    def test_nessun_branching_niente_da_escludere(self):
        # catena aperta — nessun nodo branching
        edges = [
            _make_edge((0.0, 0.0), (1.0, 0.0)),
            _make_edge((1.0, 0.0), (2.0, 0.0)),
        ]
        g = build_node_graph(edges)
        result = NonContourEdgeDetector(tolerance=0.01).detect(g, edges)
        self.assertEqual(len(result), 0)

    def test_hull_per_componente_non_per_foglio_intero(self):
        # Due forme sullo stesso foglio, non connesse tra loro (nessun edge in
        # comune): un rettangolo grande "A" e, tutto dentro la sua area, un
        # rettangolino "B" con una diagonale — identico schema del primo test,
        # in miniatura. Bug reale trovato su un disegno con più viste: un
        # hull calcolato su TUTTI i nodi del foglio è dominato da A, quindi
        # anche i lati veri del contorno di B (non solo la sua diagonale)
        # risultano "interni" a quell'hull enorme e finiscono esclusi per
        # errore. Oggi vale per la faccia esterna (D111): si percorre per
        # componente connessa.
        a = [
            _make_edge((0.0, 0.0), (100.0, 0.0)),
            _make_edge((100.0, 0.0), (100.0, 50.0)),
            _make_edge((100.0, 50.0), (0.0, 50.0)),
            _make_edge((0.0, 50.0), (0.0, 0.0)),
        ]
        b = [
            _make_edge((40.0, 20.0), (41.0, 20.0)),
            _make_edge((41.0, 20.0), (41.0, 22.0)),
            _make_edge((41.0, 22.0), (40.0, 22.0)),
            _make_edge((40.0, 22.0), (40.0, 20.0)),
            _make_edge((40.0, 20.0), (41.0, 22.0)),  # diagonale di B, non di contorno
        ]
        edges = a + b
        g = build_node_graph(edges)
        result = NonContourEdgeDetector(tolerance=0.01).detect(g, edges)

        b_contour_ids = {id(e) for e in b[:4]}
        b_diagonal_id = id(b[-1])

        self.assertEqual(result & b_contour_ids, set(),
                          "i lati veri del contorno di B non vanno esclusi")
        self.assertIn(b_diagonal_id, result,
                       "la diagonale di B resta un edge non di contorno")

    def test_lato_concavo_fra_due_corde_resta_contorno(self):
        # una L: il lato (10,10)-(10,30) della parte concava sta dentro il
        # convex hull; le due corde da (0,0) ai suoi vertici lo rendono
        # candidato (estremi a grado 3), ma confina con l'esterno (D111)
        #
        #  (0,30)-(10,30)
        #    |      |
        #    |    (10,10)----(30,10)
        #    |                  |
        #  (0,0)--------------(30,0)
        outline = [_make_edge(a, b) for a, b in [
            ((0.0, 0.0), (30.0, 0.0)), ((30.0, 0.0), (30.0, 10.0)), ((30.0, 10.0), (10.0, 10.0)),
            ((10.0, 10.0), (10.0, 30.0)), ((10.0, 30.0), (0.0, 30.0)), ((0.0, 30.0), (0.0, 0.0))]]
        chords = [_make_edge((0.0, 0.0), (10.0, 10.0)), _make_edge((0.0, 0.0), (10.0, 30.0))]
        edges = outline + chords
        result = NonContourEdgeDetector(tolerance=0.01).detect(build_node_graph(edges), edges)
        self.assertEqual(result, {id(e) for e in chords})

    def test_tacca_coi_fianchi_accavallati(self):
        # una tacca dal basso fino a (30,20), coi fianchi disegnati che si
        # incrociano poco sopra il fondo (il fianco destro torna a (27, 0.5),
        # a sinistra di dove parte il sinistro): senza un nodo nell'incrocio il
        # percorso della faccia esterna ci passava sopra e prendeva le pieghe
        # per bordo. Tre pieghe dal vertice della tacca (D111).
        outline = [_make_edge(a, b) for a, b in [
            ((0.0, 0.0), (28.0, 0.0)), ((28.0, 0.0), (30.0, 20.0)), ((30.0, 20.0), (27.0, 0.5)),
            ((27.0, 0.5), (60.0, 0.0)), ((60.0, 0.0), (60.0, 40.0)), ((60.0, 40.0), (30.0, 40.0)),
            ((30.0, 40.0), (0.0, 40.0)), ((0.0, 40.0), (0.0, 0.0))]]
        bends = [_make_edge((30.0, 20.0), (0.0, 0.0)), _make_edge((30.0, 20.0), (60.0, 0.0)),
                 _make_edge((30.0, 20.0), (30.0, 40.0))]
        edges = outline + bends
        result = NonContourEdgeDetector(tolerance=0.01).detect(build_node_graph(edges), edges)
        self.assertEqual(result, {id(e) for e in bends})


# un rettangolo 40 × 20 coi lati in basso e in alto non spezzati
_RECT = [((0.0, 0.0), (40.0, 0.0)), ((40.0, 0.0), (40.0, 20.0)),
         ((40.0, 20.0), (0.0, 20.0)), ((0.0, 20.0), (0.0, 0.0))]


class TestChainCandidates(unittest.TestCase):
    """Si giudica la catena fra due nodi di diramazione, non l'edge (D131):
    i nodi di grado 2 non sono bivi."""

    def test_catena_a_t_sui_lati(self):
        # pieghe da vertice a vertice per due punti a metà lato, che il grafo
        # di heal non spezza: (10,0) e (30,20) hanno grado 2 lì
        #
        #  (0,20)-----(30,20)--(40,20)
        #    |       /             |
        #  (0,0)--(10,0)--------(40,0)
        outline = [_make_edge(a, b) for a, b in _RECT]
        chain = [_make_edge((0.0, 20.0), (10.0, 0.0)), _make_edge((10.0, 0.0), (30.0, 20.0)),
                 _make_edge((30.0, 20.0), (40.0, 0.0))]
        edges = outline + chain
        result = NonContourEdgeDetector(tolerance=0.01).detect(build_node_graph(edges), edges)
        self.assertEqual(result, {id(e) for e in chain})

    def test_catena_con_vertice_interno(self):
        # una corda spezzata in (20,10), un punto libero dentro il pezzo
        outline = [_make_edge(a, b) for a, b in _RECT]
        chain = [_make_edge((0.0, 0.0), (20.0, 10.0)), _make_edge((20.0, 10.0), (40.0, 20.0))]
        edges = outline + chain
        result = NonContourEdgeDetector(tolerance=0.01).detect(build_node_graph(edges), edges)
        self.assertEqual(result, {id(e) for e in chain})

    def test_lato_spezzato_resta_contorno(self):
        # il lato in basso in due tratti, una diagonale dai suoi due capi: i
        # due tratti sono una catena candidata, ma sul bordo esterno
        outline = [_make_edge(a, b) for a, b in [
            ((0.0, 0.0), (20.0, 0.0)), ((20.0, 0.0), (40.0, 0.0)), ((40.0, 0.0), (40.0, 20.0)),
            ((40.0, 20.0), (0.0, 20.0)), ((0.0, 20.0), (0.0, 0.0))]]
        chord = _make_edge((0.0, 0.0), (40.0, 20.0))
        edges = outline + [chord]
        result = NonContourEdgeDetector(tolerance=0.01).detect(build_node_graph(edges), edges)
        self.assertEqual(result, {id(chord)})

    def test_foro_che_tocca_il_contorno_resta(self):
        # un giro chiuso attaccato al contorno in un nodo solo (0,0): una
        # catena coi due capi uguali è già un giro, mai una corda
        outline = [_make_edge(a, b) for a, b in _RECT]
        lobe = [_make_edge((0.0, 0.0), (10.0, 5.0)), _make_edge((10.0, 5.0), (5.0, 10.0)),
                _make_edge((5.0, 10.0), (0.0, 0.0))]
        edges = outline + lobe
        result = NonContourEdgeDetector(tolerance=0.01).detect(build_node_graph(edges), edges)
        self.assertEqual(result, set())


class TestGraphChains(unittest.TestCase):

    def test_ogni_edge_in_una_catena_sola(self):
        outline = [_make_edge(a, b) for a, b in _RECT]
        chain = [_make_edge((0.0, 20.0), (10.0, 0.0)), _make_edge((10.0, 0.0), (30.0, 20.0)),
                 _make_edge((30.0, 20.0), (40.0, 0.0))]
        chains = build_node_graph(outline + chain).chains()
        # theta: tre catene fra (0,20) e (40,0)
        self.assertEqual(len(chains), 3)
        self.assertEqual(sorted(len(run) for run, _, _ in chains), [2, 2, 3])
        for _, a, b in chains:
            self.assertEqual({a, b}, {(0.0, 20.0), (40.0, 0.0)})
        ids = [id(e) for run, _, _ in chains for e in run]
        self.assertEqual(sorted(ids), sorted(id(e) for e in outline + chain))

    def test_anello_senza_diramazioni(self):
        chains = build_node_graph([_make_edge(a, b) for a, b in _RECT]).chains()
        self.assertEqual(len(chains), 1)
        run, a, b = chains[0]
        self.assertEqual((len(run), a), (4, b))


if __name__ == "__main__":
    unittest.main(verbosity=2)