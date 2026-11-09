# tests/engine/base/test_normalizer.py

import math
import unittest
import topo
from topo import to_shapely
from topo.core.base.normalizer import (merge_collinear_overlaps, merge_cocircular_overlaps, weld_degenerate_linesegs,
                                       merge_near_copies)
from topo.core.topology.edge import Edge
from topo.core.primitives.segments import LineSeg, ArcSeg, CircleSeg


def _line(p1, p2, role="unknown"):
    return Edge(role=role, start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _arc(center, radius, start_deg, end_deg, role="unknown"):
    seg = ArcSeg(center=center, radius=radius,
                 start_angle=math.radians(start_deg), end_angle=math.radians(end_deg), ccw=True)
    start = (center[0] + radius * math.cos(seg.start_angle), center[1] + radius * math.sin(seg.start_angle))
    end = (center[0] + radius * math.cos(seg.end_angle), center[1] + radius * math.sin(seg.end_angle))
    return Edge(role=role, start=(round(start[0], 3), round(start[1], 3)),
                end=(round(end[0], 3), round(end[1], 3)), segment=seg)


def _line_raw(rounded_p1, rounded_p2, raw_p1, raw_p2, role="unknown"):
    # Come l'adapter reale: Edge.start/end sono il punto ARROTONDATO
    # (identità del nodo nel grafo), il LineSeg del segmento porta la
    # coordinata a piena precisione della sorgente — le due possono differire
    # di una frazione di mm su coordinate non tonde (v. MAP.md D50 seguito).
    return Edge(role=role, start=rounded_p1, end=rounded_p2, segment=LineSeg(start=raw_p1, end=raw_p2))


class TestMergeCollinearOverlaps(unittest.TestCase):

    def test_catena_di_tre_si_fonde(self):
        # A-B si sovrappongono, B-C si sovrappongono, A-C no direttamente —
        # deve fondersi comunque in un solo segmento (0,0)-(30,0).
        edges = [
            _line((0.0, 0.0), (10.0, 0.0)),
            _line((8.0, 0.0), (20.0, 0.0)),
            _line((18.0, 0.0), (30.0, 0.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0].segment.start, out[0].segment.end), ((0.0, 0.0), (30.0, 0.0)))

    def test_catena_di_due_si_fonde(self):
        # Due soli tratti che si sovrappongono: l'unione di due intervalli
        # 1D e' sempre ben definita (qui: (0,15)), non c'e' modo di
        # "sbagliare" fondendo solo 2 pezzi collineari — v. il seguito del
        # commit per la storia della soglia minima che c'era qui prima.
        edges = [
            _line((0.0, 0.0), (10.0, 0.0)),
            _line((5.0, 0.0), (15.0, 0.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0].segment.start, out[0].segment.end), ((0.0, 0.0), (15.0, 0.0)))

    def test_un_tratto_contenuto_nell_altro_si_fonde_nel_piu_lungo(self):
        # Caso reale (golden la_104): un tratto corto (15.68-21.36) e uno
        # lungo (10.0-21.36) sulla stessa retta, il corto interamente dentro
        # il lungo — due caratteri di un'incisione allineati per coincidenza,
        # non un errore di disegno. L'unione e' comunque solo il piu' lungo:
        # fonderli non fabbrica ne' perde geometria.
        edges = [
            _line((73.297, 15.68), (73.297, 21.36)),
            _line((73.297, 21.36), (73.297, 10.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual({out[0].segment.start, out[0].segment.end}, {(73.297, 10.0), (73.297, 21.36)})

    def test_contatto_punta_coda_si_fonde(self):
        # Tre segmenti che si toccano esattamente in successione (nessuna
        # sovrapposizione, solo continuita') sono la stessa riga tracciata a
        # pezzi quanto una sovrapposizione vera — l'unione e' comunque ben
        # definita, (0,0)-(30,0).
        edges = [
            _line((0.0, 0.0), (10.0, 0.0)),
            _line((10.0, 0.0), (20.0, 0.0)),
            _line((20.0, 0.0), (30.0, 0.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0].segment.start, out[0].segment.end), ((0.0, 0.0), (30.0, 0.0)))

    def test_rette_parallele_non_si_fondono(self):
        # Stessa direzione, offset diverso: NON è la stessa retta.
        edges = [
            _line((0.0, 0.0), (10.0, 0.0)),
            _line((3.0, 0.0), (13.0, 0.0)),
            _line((6.0, 0.0), (16.0, 0.0)),
            _line((0.0, 5.0), (10.0, 5.0)),
            _line((3.0, 5.0), (13.0, 5.0)),
            _line((6.0, 5.0), (16.0, 5.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 2)

    def test_ruolo_gia_assegnato_non_e_candidato(self):
        # Un ruolo diverso da UNKNOWN (assegnato da role_rules) non entra mai
        # nel graph-building: fonderlo non aiuta e può alterare geometria di
        # dominio intenzionale (v. golden la_104: tratti di un'incisione che
        # si sovrappongono per disegno, non per errore).
        edges = [
            _line((0.0, 0.0), (10.0, 0.0), role="engrave"),
            _line((5.0, 0.0), (15.0, 0.0), role="engrave"),
            _line((8.0, 0.0), (20.0, 0.0), role="engrave"),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 3)

    def test_ordine_preservato_per_tutto_il_resto(self):
        # Un pre-pass di pulizia non deve riordinare edge che non tocca —
        # anche a zero fusioni (v. golden staffa_scarto_doppia: il solo riordino,
        # senza nessuna fusione, cambiava il risultato del loop-finder).
        others = [_line((i * 100.0, 0.0), (i * 100.0 + 1.0, 0.0)) for i in range(5)]
        chain = [
            _line((0.0, 50.0), (10.0, 50.0)),
            _line((8.0, 50.0), (20.0, 50.0)),
            _line((18.0, 50.0), (30.0, 50.0)),
        ]
        edges = [others[0], others[1], chain[0], others[2], chain[1], others[3], chain[2], others[4]]
        out = merge_collinear_overlaps(edges)

        self.assertEqual(len(out), 6)  # 5 "others" + 1 fuso
        # Il fuso occupa la posizione del primo membro della catena in ordine
        # di input (indice 2 in `edges`), il resto non si è mosso.
        self.assertIs(out[0], others[0])
        self.assertIs(out[1], others[1])
        self.assertEqual((out[2].segment.start, out[2].segment.end), ((0.0, 50.0), (30.0, 50.0)))
        self.assertIs(out[3], others[2])
        self.assertIs(out[4], others[3])
        self.assertIs(out[5], others[4])

    def test_lista_vuota(self):
        self.assertEqual(merge_collinear_overlaps([]), [])

    def test_estremi_fusi_edge_arrotondato_segment_grezzo(self):
        # Su coordinate non tonde edge.start/end (arrotondati, identita' del
        # nodo nel grafo) e segment.start/end (piena precisione) differiscono
        # di una frazione di mm — due scopi diversi, mai mischiati (stesso
        # principio già in gap_solver.apply_gap_fixes):
        #   - Edge.start/end del fuso RESTANO arrotondati: servono a
        #     riagganciarsi al nodo del vicino reale nel grafo, altrimenti un
        #     pezzo vero può sparire del tutto (bug trovato su
        #     fa_che_non_mi_incazzi.dxf).
        #   - il LineSeg fuso (edge.segment) porta invece SEMPRE il punto
        #     grezzo a piena precisione, mai quello arrotondato: è quello che
        #     l'export legge per costruire la geometria in output, e un fuso
        #     il cui segmento porta il punto arrotondato produce uno scalino
        #     visibile appena affianca un lato nativo mai toccato dal merge
        #     nello stesso contorno (bug trovato su un foglio reale: un
        #     lato "verticale" con dx=0.031 invece di 0, lunghezza 0.97
        #     invece di 1).
        edges = [
            _line_raw((0.0, 0.0), (10.0, 0.0), (0.0000003, 0.0), (10.0000003, 0.0)),
            _line_raw((8.0, 0.0), (20.0, 0.0), (8.0000003, 0.0), (20.0000003, 0.0)),
            _line_raw((18.0, 0.0), (30.0, 0.0), (18.0000003, 0.0), (30.0000003, 0.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].start, (0.0, 0.0))
        self.assertEqual(out[0].end, (30.0, 0.0))
        self.assertEqual(out[0].segment.start, (0.0000003, 0.0))
        self.assertEqual(out[0].segment.end, (30.0000003, 0.0))

    def test_contatto_su_uno_spigolo_non_si_fonde(self):
        # Una traccia interna che parte da uno spigolo dell'outer, collineare
        # col lato che arriva lì: in (0,0) finisce anche il lato verticale, è
        # un nodo vero. Fonderli lo cancellerebbe (MAP.md D110). Senza
        # `keep_junctions` (`outlines()`, che noda da sé) si fondono come prima.
        edges = [
            _line((-40.0, 0.0), (0.0, 0.0)),
            _line((0.0, 0.0), (200.0, 0.0)),
            _line((0.0, 0.0), (0.0, -40.0)),
        ]
        self.assertEqual(len(merge_collinear_overlaps(edges, keep_junctions=True)), 3)
        self.assertEqual(len(merge_collinear_overlaps(edges)), 2)

    def test_contatto_senza_altri_edge_si_fonde(self):
        # Stesso contatto, ma nel punto non arriva nient'altro: è solo la
        # cucitura fra due spezzoni della stessa riga.
        edges = [_line((-40.0, 0.0), (0.0, 0.0)), _line((0.0, 0.0), (200.0, 0.0))]
        self.assertEqual(len(merge_collinear_overlaps(edges, keep_junctions=True)), 1)

    def test_sovrapposizione_su_uno_spigolo_si_fonde(self):
        # Una sovrapposizione vera si fonde anche dove arriva un altro edge.
        edges = [
            _line((-40.0, 0.0), (5.0, 0.0)),
            _line((0.0, 0.0), (200.0, 0.0)),
            _line((0.0, 0.0), (0.0, -40.0)),
        ]
        self.assertEqual(len(merge_collinear_overlaps(edges, keep_junctions=True)), 2)


class TestSameCarrierUnderMotion(unittest.TestCase):
    """G6e (drw_0015, drw_0016): la stessa retta in due spezzoni si fonde a ogni
    moto. La chiave arrotondata (angolo, offset) aveva un bordo di cella dove
    i due cadevano da parti diverse, e una cucitura sulle verticali (D184)."""

    def _merged_at_every_motion(self, pieces, merge, expected):
        import topo
        from tests.invariants import MOTIONS, moved
        doc = topo.load_segments(pieces)
        for name, move, _, _ in [("al posto", lambda s: s, None, None)] + MOTIONS:
            self.assertEqual(len(merge(moved(doc, move).edges)), expected, name)

    def test_doppione_verticale_a_cavallo_di_una_cella(self):
        # drw_0016: x = 578.1875 è a metà fra due celle di 1e-3, il doppione a
        # 2.5e-5 cade nell'altra; ruotati si fondevano, al posto no
        self._merged_at_every_motion(
            [LineSeg(start=(578.1875, 17.0), end=(578.1875, 25.0)),
             LineSeg(start=(578.1874750603, 24.9999881745), end=(578.1874750603, 16.9999881745))],
            merge_collinear_overlaps, 1)

    def test_doppione_verticale_sulla_cucitura(self):
        # drw_0015: 1e-11 di rumore su x manda un doppione verticale dall'altra
        # parte della cucitura a +-90 gradi della chiave (angolo, offset)
        self._merged_at_every_motion(
            [LineSeg(start=(-71582.466979507, -2985.743765108251),
                     end=(-71582.46697950704, -2991.205129665564)),
             LineSeg(start=(-71582.46697950701, -2985.823579579326),
                     end=(-71582.466979507, -2986.705129665514)),
             LineSeg(start=(-71582.46697950704, -2991.705129665551),
                     end=(-71582.46697950696, -2985.476083898161))],
            merge_collinear_overlaps, 1)

    def test_archi_dello_stesso_cerchio_a_cavallo_di_una_cella(self):
        # come drw_0016 per i cerchi: centro a metà fra due celle, l'altro a 2.5e-5
        self._merged_at_every_motion(
            [ArcSeg(center=(578.1875, 20.0), radius=12.0, start_angle=0.1, end_angle=1.3, ccw=True),
             ArcSeg(center=(578.187475, 20.0), radius=12.0, start_angle=1.2, end_angle=2.9, ccw=True)],
            merge_cocircular_overlaps, 1)


    def test_il_fuso_va_nel_verso_del_primo_pezzo(self):
        # G6e C, `normalizer.py:196`: la retta comune prendeva un verso
        # canonico (x crescente, poi y), che dipende dal riferimento: una
        # verticale ruotata di +1e-12 rad usciva fusa all'ingiù, e ogni retta
        # si girava a mezzo giro. Si vede nelle `loose` di `heal`.
        from tests.invariants import rigid
        for pieces in ([((0, 0), (0, 6)), ((0, 4), (0, 10))],
                       [((10, 0), (4, 0)), ((6, 0), (0, 0))]):
            for motion in [(0.0, 0.0, 0.0), (1e-12, 0.0, 0.0), (-1e-12, 0.0, 0.0),
                           (math.pi, 0.0, 0.0), (0.7, 3.1, -2.2)]:
                with self.subTest(pieces=pieces, motion=motion):
                    move_pt = rigid(*motion)[1]
                    edges = [_line(move_pt(a), move_pt(b)) for a, b in pieces]
                    merged = merge_collinear_overlaps(edges)
                    self.assertEqual(len(merged), 1)
                    seg, first = merged[0].segment, edges[0].segment
                    self.assertGreater((seg.end[0] - seg.start[0]) * (first.end[0] - first.start[0])
                                       + (seg.end[1] - seg.start[1]) * (first.end[1] - first.start[1]), 0)


class TestMergeNearCopies(unittest.TestCase):
    """D226: la retta quasi sopra un'altra, fusa solo da chi la chiama."""

    _PIECES = [LineSeg(start=(100, 0), end=(0.099, -0.0001)), LineSeg(start=(0, 0), end=(0, 50)),
               LineSeg(start=(0, 50), end=(100, 50)), LineSeg(start=(100, 50), end=(100, 0)),
               LineSeg(start=(0, 0), end=(0.0005, 17.7))]

    def test_resta_la_piu_lunga(self):
        long, copy = _line((0, 0), (0, 50)), _line((0, 0), (0.0005, 17.7))
        self.assertEqual(merge_near_copies([copy, long], distance=0.001), [long])

    def test_a_pari_lunghezza_la_mediana(self):
        out = merge_near_copies([_line((0, 0), (50, 0)), _line((50, 0.004), (0, 0.002))], distance=0.01)
        self.assertEqual(len(out), 1)
        seg = out[0].segment
        self.assertEqual((seg.start, seg.end), ((0.0, 0.001), (50.0, 0.002)))

    def test_la_copia_va_con_la_retta_piu_vicina(self):
        # seme 1468: un tratto corto a 0.006 da una retta e a 0.41 da un'altra
        # (le due rette lunghe si coprono solo in parte: non sono copia l'una dell'altra)
        near, far, copy = _line((0, 0), (3, 0)), _line((2, 0.41), (5, 0.41)), _line((2.2, 0.006), (2.5, 0.006))
        out = merge_near_copies([far, near, copy], distance=0.5)
        self.assertEqual(out, [far, near])

    def test_il_pezzo_che_continua_non_e_una_copia(self):
        # D235, forza bruta (seme 834): il pezzo dopo il capo, in fila o d'angolo, ha i due capi
        # entro la distanza dalla lunga ma non le sta sopra: resta, e heal() non avvisa
        long = _line((0, 0), (10, 0))
        for nxt in (_line((10, 0), (10.3, 0.001)), _line((10, 0), (10.2, 0.3))):
            self.assertEqual(merge_near_copies([long, nxt], distance=0.5), [long, nxt])
        net = topo.heal(topo.load_segments([long.segment, LineSeg(start=(10, 0), end=(10.2, 0.3))]), tolerance=0.5)
        self.assertNotIn("near-copy", [w.code for w in net.warnings if isinstance(w, topo.Diagnostic)])

    def test_oltre_la_distanza_restano_due(self):
        edges = [_line((0, 0), (0, 50)), _line((0, 0), (0.05, 17.7))]
        self.assertEqual(merge_near_copies(edges, distance=0.01), edges)

    def test_il_rovinato_si_chiude_solo_se_il_chiamante_fonde(self):
        # forza bruta, seme 1775: il lato in basso si ferma a 0.099
        # dall'angolo; una copia del lato sinistro parte dall'angolo e lo tiene
        # occupato, così il gap non si chiude. heal() lo dice, non lo fonde
        doc = topo.load_segments(self._PIECES)
        net = topo.heal(doc, tolerance=0.5)
        [d] = [w for w in net.warnings if isinstance(w, topo.Diagnostic)]
        self.assertEqual((d.code, d.param, round(d.value, 4)), ("near-copy", "distance", 0.0005))
        self.assertIn("distance=0.0005)", d.help)
        self.assertEqual(net.faces().cluster_count, 0)
        doc.edges = merge_near_copies(doc.edges, distance=0.0005)
        result = topo.heal(doc, tolerance=0.5).faces()
        self.assertEqual([round(to_shapely(c.outer).area) for c in result.clusters], [5000])


class TestMergeCocircularOverlaps(unittest.TestCase):

    def test_catena_di_frammenti_si_fonde(self):
        # golden piega_cazzuta: un arco tracciato a 4 spezzoni consecutivi
        # che si toccano esattamente -> un solo ArcSeg da 0 a 200 gradi.
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 50.0),
            _arc((0.0, 0.0), 10.0, 50.0, 120.0),
            _arc((0.0, 0.0), 10.0, 120.0, 160.0),
            _arc((0.0, 0.0), 10.0, 160.0, 200.0),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 1)
        seg = out[0].segment
        self.assertAlmostEqual(math.degrees(seg.start_angle), 0.0)
        self.assertAlmostEqual(math.degrees(seg.end_angle), 200.0)
        self.assertNotEqual(out[0].start, out[0].end)

    def test_sliver_degenere_assorbito(self):
        # golden piega_cazzuta: uno spezzone di 0.008 gradi (rumore) in mezzo
        # alla catena sparisce nel fuso invece di restare un nodo spurio.
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 50.0),
            _arc((0.0, 0.0), 10.0, 50.0, 50.008),
            _arc((0.0, 0.0), 10.0, 50.008, 120.0),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 1)

    def test_due_semicerchi_chiudono_il_cerchio(self):
        # golden cerchi_ciambella: un foro disegnato come 2 semicirchi ->
        # un giro intero e' un cerchio (CircleSeg), non un ArcSeg a 360 gradi
        # -- niente traccia di quale frammento fosse il primo.
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 180.0),
            _arc((0.0, 0.0), 10.0, 180.0, 360.0),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].start, out[0].end)
        self.assertIsInstance(out[0].segment, CircleSeg)
        self.assertEqual(out[0].segment.radius, 10.0)

    def test_gap_vero_non_si_chiude_per_errore(self):
        # arc_arc_gap: un gap reale (qui volutamente grande, 10 gradi) su un
        # lato non deve sparire solo perché l'altro lato tocca esattamente.
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 170.0),
            _arc((0.0, 0.0), 10.0, 180.0, 360.0),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 1)
        seg = out[0].segment
        self.assertAlmostEqual(math.degrees(seg._sweep()), 350.0)
        self.assertNotEqual(out[0].start, out[0].end)

    def test_ruolo_gia_assegnato_non_e_candidato(self):
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 50.0, role="engrave"),
            _arc((0.0, 0.0), 10.0, 50.0, 120.0, role="engrave"),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 2)

    def test_cerchi_diversi_non_si_fondono(self):
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 50.0),
            _arc((0.0, 0.0), 20.0, 0.0, 50.0),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 2)

    def test_ordine_preservato(self):
        others = [_line((i * 100.0, 0.0), (i * 100.0 + 1.0, 0.0)) for i in range(3)]
        chain = [
            _arc((0.0, 0.0), 10.0, 0.0, 50.0),
            _arc((0.0, 0.0), 10.0, 50.0, 120.0),
        ]
        edges = [others[0], chain[0], others[1], chain[1], others[2]]
        out = merge_cocircular_overlaps(edges)

        self.assertEqual(len(out), 4)  # 3 "others" + 1 fuso
        self.assertIs(out[0], others[0])
        seg = out[1].segment
        self.assertAlmostEqual(math.degrees(seg.end_angle), 120.0)
        self.assertIs(out[2], others[1])
        self.assertIs(out[3], others[2])

    def test_lista_vuota(self):
        self.assertEqual(merge_cocircular_overlaps([]), [])

    def test_cerchio_scritto_due_volte_e_un_cerchio(self):
        # forza bruta 7 novembre: due CircleSeg uguali erano due fori sovrapposti
        edges = [Edge.of(CircleSeg((0.0, 0.0), 5.0), "unknown") for _ in range(2)]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0].segment, CircleSeg)

    def test_arco_sopra_un_cerchio_sparisce_nel_cerchio(self):
        edges = [Edge.of(CircleSeg((0.0, 0.0), 10.0), "unknown"), _arc((0.0, 0.0), 10.0, -30.0, 30.0)]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0].segment, CircleSeg)

    def test_heal_cerchio_doppio_un_foro_solo(self):
        import topo
        square = [LineSeg((0, 0), (200, 0)), LineSeg((200, 0), (200, 100)),
                  LineSeg((200, 100), (0, 100)), LineSeg((0, 100), (0, 0))]
        result = topo.heal(topo.load_segments(square + [CircleSeg((50, 50), 5)] * 2)).faces()
        self.assertEqual([len(c.inners) for c in result.clusters], [1])

    def test_cerchi_concentrici_restano_due(self):
        edges = [Edge.of(CircleSeg((0.0, 0.0), 5.0), "unknown"), Edge.of(CircleSeg((0.0, 0.0), 6.0), "unknown")]
        self.assertEqual(len(merge_cocircular_overlaps(edges)), 2)


class TestWeldUnderMotion(unittest.TestCase):

    def test_arco_a_corde_uguali_saldato_uguale_a_ogni_moto(self):
        # G6e (J0118158): un raccordo scritto a corde da 0.04 fra due lati. Con
        # le corde tutte uguali l'ordine di saldatura lo decideva l'ultimo bit,
        # e il tetto di 0.05 ne lasciava un'alternanza diversa a ogni moto.
        # Ora il gruppo si giudica intero: più largo di 0.05, nessuna (D186)
        import topo
        from tests.invariants import MOTIONS, moved
        center, r, n = (251.0, 21.0), 1.25, 12
        step = 2 * math.asin(0.02 / r)
        pts = [(center[0] + r * math.cos(k * step), center[1] + r * math.sin(k * step)) for k in range(n + 1)]
        pieces = [LineSeg(start=(pts[0][0], pts[0][1] - 10), end=pts[0])]
        pieces += [LineSeg(start=a, end=b) for a, b in zip(pts, pts[1:])]
        pieces.append(LineSeg(start=pts[-1], end=(pts[-1][0] - 10, pts[-1][1])))
        doc = topo.load_segments(pieces)
        base = len(weld_degenerate_linesegs(doc.edges))
        for name, move, _, _ in MOTIONS:
            self.assertEqual(len(weld_degenerate_linesegs(moved(doc, move).edges)), base, name)
        self.assertEqual(base, n + 2)


class TestWeldDegenerateLinesegs(unittest.TestCase):

    def _chain(self):
        return [
            _line_raw((0.0, 0.0), (10.0, 0.0), (0.0, 0.0), (10.0, 0.0)),
            _line_raw((10.0, 0.0), (10.02, 0.0), (10.0, 0.0), (10.02, 0.0)),
            _line_raw((10.02, 0.0), (20.0, 0.0), (10.02, 0.0), (20.0, 0.0)),
        ]

    def test_catena_resta_connessa(self):
        # D56: il LineSeg da 0.02mm sparisce, ma i due vicini devono ritrovarsi
        # sullo stesso nodo — cancellarlo e basta staccherebbe la catena.
        out = weld_degenerate_linesegs(self._chain())
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0].end, out[1].start)

    def test_segmento_conserva_il_punto_reale(self):
        # si sposta solo il nodo, il segment resta a piena precisione
        out = weld_degenerate_linesegs(self._chain())
        self.assertEqual(out[1].segment.start, (10.02, 0.0))

    def test_ruolo_gia_assegnato_non_e_saldato(self):
        edges = [_line((0.0, 0.0), (0.02, 0.0), role="engrave")]
        self.assertEqual(weld_degenerate_linesegs(edges), edges)

    def test_sopra_soglia_non_e_saldato(self):
        edges = [_line((0.0, 0.0), (0.06, 0.0)), _line((0.06, 0.0), (5.0, 0.0))]
        out = weld_degenerate_linesegs(edges)
        self.assertEqual(len(out), 2)
        self.assertIs(out[0], edges[0])
        self.assertIs(out[1], edges[1])

    def test_punta_libera_non_e_saldata(self):
        # D164: un tratto corto con un capo che non tocca nessuno è una punta,
        # non un nodo doppio: saldarlo sposterebbe il capo libero di 0.03 e il
        # gap di 0.004 verso l'arco accanto non si chiuderebbe più
        edges = [_line((10.0, 0.0), (20.0, 0.0)), _line((10.03, 0.0), (10.0, 0.0))]
        self.assertEqual(weld_degenerate_linesegs(edges), edges)

    def test_lista_vuota(self):
        self.assertEqual(weld_degenerate_linesegs([]), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestRefitJointsUnderMotion(unittest.TestCase):
    """G6e, gruppo B: una curva scritta a punti (retta, quarto di cerchio,
    retta) rifittata in tre primitive resta una catena sola. Ogni giunzione
    si arrotondava due volte, dalla fine di un pezzo e dall'inizio del
    successivo: due copie a 1 ulp, e con un bordo di cella fra loro i due
    pezzi prendevano nodi diversi."""

    def _profile(self, angle, dx, dy):
        import topo
        from tests.invariants import rigid
        pts = [(x * 0.05, 0.0) for x in range(41)]
        pts += [(2.0 + 3 * math.sin(a / 100 * math.pi / 2), 3 - 3 * math.cos(a / 100 * math.pi / 2))
                for a in range(1, 101)]
        pts += [(5.0, 3.0 + y * 0.05) for y in range(1, 41)]
        segment, _ = rigid(angle, dx, dy)
        return topo.load_segments([segment(LineSeg(start=a, end=b)) for a, b in zip(pts, pts[1:])]).edges

    def test_una_giunzione_su_un_bordo_di_cella_resta_un_nodo(self):
        from collections import Counter
        from topo.core.base.normalizer import refit_tessellations
        # il moto mette la giunzione fra la retta e l'arco a metà fra due celle di 1e-3
        for motion in [(0.0, 0.0, 0.0), (1.209, 2999999.9996208353, -2499999.9996809117)]:
            with self.subTest(motion=motion):
                out = refit_tessellations(self._profile(*motion))
                ends = Counter(n for e in out for n in (e.start, e.end))
                self.assertEqual(len(out), 3)
                self.assertEqual(sorted(ends.values()), [1, 1, 2, 2])
