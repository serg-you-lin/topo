"""
tests/unit/test_anchor_texts.py
-------------------------------
`anchor_texts()`: assegna `cluster_ref` (indice della parte contenitrice)
ai testi del modello, `target` a chi ha un `pointer`, `references` a chi ha
dei `measured_points` (D138). Fase separata e opzionale (topo/tools/).
"""

import unittest

from shapely.geometry import Point, Polygon

import topo
from topo.model.cluster import Cluster
from topo.model.contour import Contour
from topo.model.result import Result
from topo.model.role import ContourRole
from topo.model.text import RenderedGeometry, RenderedText, Text
from topo.tools.anchor import anchor_texts, measured_references, resolve_target
from topo_dxf.text_extractor import _shown_text

# max_gap non ha default (D98); island_gap non esiste più (D99)
MAX_GAP = 0.5


def _part(x0, y0, x1, y1):
    poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return Cluster(outer=Contour(polygon=poly, role=ContourRole.OUTER))


def _result(*clusters, texts=()):
    return Result(clusters=list(clusters), texts=list(texts))


class TestAnchorTexts(unittest.TestCase):

    def test_containment_assigns_part_index(self):
        res = _result(
            _part(0, 0, 100, 100),
            _part(200, 0, 300, 100),
            texts=[
                Text(position=(50, 50), text="dentro parte 0"),
                Text(position=(250, 50), text="dentro parte 1"),
            ],
        )
        anchor_texts(res)
        self.assertEqual(res.texts[0].cluster_ref, 0)
        self.assertEqual(res.texts[1].cluster_ref, 1)

    def test_outside_all_parts_stays_none(self):
        res = _result(
            _part(0, 0, 100, 100),
            texts=[Text(position=(500, 500), text="cartiglio")],
        )
        anchor_texts(res)
        self.assertIsNone(res.texts[0].cluster_ref)

    def test_snap_distance_assigns_near_part(self):
        res = _result(
            _part(0, 0, 100, 100),
            texts=[Text(position=(105, 50), text="callout appena fuori")],
        )
        anchor_texts(res, snap_distance=0.0)
        self.assertIsNone(res.texts[0].cluster_ref)

        anchor_texts(res, snap_distance=10.0)
        self.assertEqual(res.texts[0].cluster_ref, 0)

    def test_first_covering_part_wins_on_overlap(self):
        res = _result(
            _part(0, 0, 100, 100),
            _part(50, 50, 150, 150),   # sovrapposta alla prima
            texts=[Text(position=(75, 75), text="nella zona comune")],
        )
        anchor_texts(res)
        self.assertEqual(res.texts[0].cluster_ref, 0)

    def test_no_parts_is_noop(self):
        res = _result(texts=[Text(position=(1, 1), text="x")])
        anchor_texts(res)
        self.assertIsNone(res.texts[0].cluster_ref)


def _plate_with_holes():
    """Piastra 100x50 con due fori: Ø8 in (20, 25), Ø20 in (70, 25)."""
    return topo.load_geometry([
        {"type": "polygon", "points": [(0, 0), (100, 0), (100, 50), (0, 50)]},
        {"type": "circle", "center": (20, 25), "radius": 4},
        {"type": "circle", "center": (70, 25), "radius": 10},
    ])


def _leader(*vertices):
    return Text(position=vertices[-1], text="M8", pointer=list(vertices))


class TestPointerTarget(unittest.TestCase):
    """`Text.target`: l'elemento su cui cade la punta di `pointer` (D66)."""

    def _island(self, *leaders):
        result = topo.island(_plate_with_holes(), max_gap=MAX_GAP)
        result.texts = list(leaders)
        return anchor_texts(result)

    def _inner_at(self, result, center):
        return next(i for i, c in enumerate(result.clusters[0].inners)
                    if c.polygon.centroid.distance(Point(center)) < 0.1)

    def test_punta_sul_bordo_del_foro(self):
        result = self._island(_leader((24, 25), (40, 60)))
        k = self._inner_at(result, (20, 25))
        self.assertEqual(result.texts[0].target, f"clusters[0].inners[{k}]")
        self.assertIs(resolve_target(result, result.texts[0].target), result.clusters[0].inners[k])

    def test_punta_dentro_il_foro(self):
        result = self._island(_leader((72, 27), (90, 70)))
        k = self._inner_at(result, (70, 25))
        self.assertEqual(result.texts[0].target, f"clusters[0].inners[{k}]")

    def test_punta_sul_contorno_esterno(self):
        result = self._island(_leader((100, 40), (120, 60)))
        self.assertEqual(result.texts[0].target, "clusters[0].outer")

    def test_freccia_lontana_nessun_target(self):
        # freccia di sezione: si ferma a 5 mm dal pezzo
        result = self._island(_leader((-5, 25), (-15, 25)))
        self.assertIsNone(result.texts[0].target)

    def test_senza_vertici_nessun_target(self):
        result = self._island(Text(position=(20, 25), text="M8"))
        self.assertIsNone(result.texts[0].target)

    def test_elemento_dell_overlay(self):
        # un consumatore sposta un contorno in una sua collezione: il target segue
        from topo.model import DetectedFeatures
        result = topo.heal(_plate_with_holes())
        cluster = result.clusters[0]
        small = min(cluster.inners, key=lambda c: c.polygon.area)
        cluster.inners = [c for c in cluster.inners if c is not small]
        cluster.detected = DetectedFeatures()
        cluster.detected.attach("my_circles", [small])
        result.texts = [_leader((24, 25), (40, 60))]
        anchor_texts(result)
        target = resolve_target(result, result.texts[0].target)
        self.assertIn(".my_circles[", result.texts[0].target)
        self.assertAlmostEqual(target.polygon.centroid.x, 20, places=1)


class TestMeasuredReferences(unittest.TestCase):
    """`Text.references`: gli elementi su cui cadono i `measured_points` (D69)."""

    def _result(self, *dims):
        result = topo.island(_plate_with_holes(), max_gap=MAX_GAP)
        result.texts = list(dims)
        return anchor_texts(result)

    def test_diametro_sul_foro(self):
        dim = Text(position=(40, 40), measured_points=[(60, 25), (80, 25)])
        result = self._result(dim)
        self.assertEqual(len(dim.references), 1)
        hole = resolve_target(result, dim.references[0])
        self.assertAlmostEqual(topo.geometry.contour_shape(hole).diameter, 20)

    def test_raggio_sul_foro(self):
        dim = Text(position=(40, 40), measured_points=[(20, 29)])
        result = self._result(dim)
        self.assertAlmostEqual(topo.geometry.contour_shape(resolve_target(result, dim.references[0])).diameter, 8)

    def test_lineare_fra_due_elementi(self):
        # dal bordo sinistro del pezzo al bordo sinistro del foro Ø8
        dim = Text(position=(8, 60), measured_points=[(0, 25), (16, 25)])
        result = self._result(dim)
        self.assertEqual(dim.references[0], "clusters[0].outer")
        self.assertEqual(len(dim.references), 2)
        self.assertAlmostEqual(topo.geometry.contour_shape(resolve_target(result, dim.references[1])).diameter, 8)

    def test_punti_fuori_dalla_geometria(self):
        dim = Text(position=(0, 0), measured_points=[(-20, -20), (200, 200)])
        self._result(dim)
        self.assertEqual(dim.references, [])

    def test_senza_punti(self):
        result = topo.island(_plate_with_holes(), max_gap=MAX_GAP)
        self.assertEqual(measured_references(result, Text(position=(0, 0))), [])


def _texts(*contents):
    return RenderedGeometry(texts=[RenderedText(content=c, position=(0, 0)) for c in contents])


class TestShownText(unittest.TestCase):
    """La stringa di una quota DXF, risolta in lettura (`<>` = la misura, D138)."""

    def test_override_con_la_misura_disegnata(self):
        # il simbolo arriva come frammento a sé ("n" in un font di simboli): vale l'override
        self.assertEqual(_shown_text("Ø<>", _texts("n", "6.5"), 6.5), "Ø6.5")

    def test_override_usa_la_precisione_del_disegno(self):
        self.assertEqual(_shown_text("M<>", _texts("M", "5"), 5.000000004), "M5")

    def test_override_senza_testo_disegnato(self):
        self.assertEqual(_shown_text("(<>)", RenderedGeometry(), 35.0), "(35)")

    def test_frammenti_uniti(self):
        self.assertEqual(_shown_text(None, _texts("∅5,3", "+0,05^-0"), 6.625), "∅5,3+0,05^-0")

    def test_solo_misura(self):
        self.assertEqual(_shown_text(None, RenderedGeometry(), 12.50), "12.5")


if __name__ == "__main__":
    unittest.main()
