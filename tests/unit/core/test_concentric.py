# tests/unit/core/test_concentric.py
"""`concentric_groups` e `arcs_around`: fatti geometrici fra più contorni (D91)."""

import math
import unittest

import topo
from topo.core.primitives.segments import ArcSeg, CircleSeg, LineSeg
from topo.core.geometry.shape import arcs_around, concentric_groups


def _circle(c, r):
    return [CircleSeg(center=c, radius=r)]


def _square(c, half):
    x, y = c
    pts = [(x - half, y - half), (x + half, y - half), (x + half, y + half), (x - half, y + half)]
    return [LineSeg(start=pts[i], end=pts[(i + 1) % 4]) for i in range(4)]


class TestConcentricGroups(unittest.TestCase):

    def test_due_cerchi_concentrici_e_uno_isolato(self):
        small, big, alone = _circle((0, 0), 2), _circle((0.05, 0), 4), _circle((20, 0), 2)
        groups = concentric_groups([big, alone, small])
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0].items, (small, big))
        self.assertEqual(groups[0].diameters, (4, 8))
        self.assertEqual(groups[0].center, (0, 0))
        self.assertEqual(groups[1].items, (alone,))

    def test_fuori_tolleranza_non_si_uniscono(self):
        a, b = _circle((0, 0), 2), _circle((0.5, 0), 4)
        self.assertEqual(len(concentric_groups([a, b])), 2)
        self.assertEqual(len(concentric_groups([a, b], tolerance=1.0)), 1)

    def test_i_non_cerchi_non_compaiono(self):
        groups = concentric_groups([_square((0, 0), 5), _circle((0, 0), 2)])
        self.assertEqual([len(g.items) for g in groups], [1])

    def test_tre_cerchi_dal_minore_al_maggiore(self):
        rings = [_circle((0, 0), r) for r in (6, 2, 4)]
        (group,) = concentric_groups(rings)
        self.assertEqual(group.diameters, (4, 8, 12))

    def test_api_pubblica(self):
        self.assertIs(topo.geometry.concentric_groups, concentric_groups)
        self.assertIs(topo.geometry.arcs_around, arcs_around)


def _moved(p, angle, shift):
    c, s = math.cos(angle), math.sin(angle)
    return (c * p[0] - s * p[1] + shift[0], s * p[0] + c * p[1] + shift[1])


MOTIONS = [(0.0, (0, 0)), (math.pi, (0, 0)), (2.0, (1e5, 3e4)), (0.5, (-7, 3)),
           (math.pi / 2, (0, 0)), (4.1, (-3e5, 2e5)), (1.0, (0.3, 0)), (3.0, (5e4, -5e4)), (5.5, (1, 1))]


class TestConcentricGroupsUnderMotion(unittest.TestCase):
    """G6e: la partizione non dipende dal riferimento."""

    def test_il_cerchio_grande_va_col_centro_piu_vicino(self):
        # A e B uguali a 0.15 (due gruppi); C più grande a 0.06 da A e 0.09 da B:
        # entra in A. Prima entrava nel gruppo nato prima, cioè nel centro con
        # la x minore, e una rotazione di 180° lo mandava in B.
        spec = [((0, 0), 2), ((0.15, 0), 2), ((0.06, 0), 4)]
        for angle, shift in MOTIONS:
            with self.subTest(angle=angle, shift=shift):
                items = [_circle(_moved(c, angle, shift), r) for c, r in spec]
                parts = {tuple(items.index(list(i)) for i in g.items) for g in concentric_groups(items)}
                self.assertEqual(parts, {(0, 2), (1,)})

    def test_a_pari_diametro_il_riferimento_e_il_primo_dato(self):
        # A e B uguali a 0.05 (un gruppo): il centro del gruppo è quello di A,
        # il primo dato, in ogni riferimento; D a 0.09 da A e 0.14 da B ci entra.
        spec = [((0, 0), 2), ((0.05, 0), 2), ((-0.09, 0), 4)]
        for angle, shift in MOTIONS:
            with self.subTest(angle=angle, shift=shift):
                items = [_circle(_moved(c, angle, shift), r) for c, r in spec]
                (group,) = concentric_groups(items)
                self.assertEqual(group.items, (items[0], items[1], items[2]))
                self.assertEqual(group.center, items[0][0].center)

    def test_gruppi_impilati_restano_in_ordine_di_y(self):
        # Due fori uno sopra l'altro, stessa x a riposo: una traslazione sposta
        # le x di un ulp, l'ordine resta quello delle y.
        for shift in [(0, 0), (0.1, 0), (1e5 + 0.3, 7), (-3e5 + 0.7, 0)]:
            with self.subTest(shift=shift):
                low = _circle((0.1 + shift[0], 0 + shift[1]), 2)
                high = _circle((0.3 - 0.2 + shift[0], 10 + shift[1]), 2)
                groups = concentric_groups([high, low])
                self.assertEqual([g.items for g in groups], [(low,), (high,)])


class TestArcsAround(unittest.TestCase):

    def _arc(self, c, r, sweep_deg):
        return ArcSeg(center=c, radius=r, start_angle=0.0, end_angle=math.radians(sweep_deg))

    def test_arco_di_tre_quarti(self):
        (found,) = arcs_around((0, 0), 2.5, [self._arc((0, 0), 3, 270)])
        self.assertAlmostEqual(found.sweep, 270)
        self.assertAlmostEqual(found.radius_ratio, 1.2)

    def test_solo_archi_piu_grandi_e_concentrici(self):
        arcs = [self._arc((0, 0), 2, 270),       # più piccolo
                self._arc((5, 0), 3, 270),       # altro centro
                self._arc((0, 0), 10, 90),
                self._arc((0, 0.05), 3, 270)]
        found = arcs_around((0, 0), 2.5, arcs)
        self.assertEqual([a.arc for a in found], [arcs[3], arcs[2]])

    def test_ignora_cio_che_non_e_arco(self):
        self.assertEqual(arcs_around((0, 0), 1, [CircleSeg(center=(0, 0), radius=2)]), [])

    def test_arco_orario(self):
        arc = ArcSeg(center=(0, 0), radius=3, start_angle=0.0, end_angle=math.radians(90), ccw=False)
        (found,) = arcs_around((0, 0), 2, [arc])
        self.assertAlmostEqual(found.sweep, 270)


if __name__ == "__main__":
    unittest.main()
