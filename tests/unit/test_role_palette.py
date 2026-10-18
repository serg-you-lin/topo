"""
test_role_palette.py
--------------------
La palette di topo (MAP.md D128): il colore dei ruoli che topo produce è uno
solo, per ogni formato — outer verde, inner giallo, unknown rosso, grigio
ogni altro ruolo — e la mappa del chiamante ci si mette sopra campo per
campo, senza riscrivere i ruoli di topo.
"""

import sys
import unittest
from pathlib import Path

from ezdxf.colors import aci2rgb

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import topo
from topo.model import CONSUMER_ROLE_STYLE, DEFAULT_ROLE_STYLES, RoleStyle, role_style
from topo_dxf.layers import color_for_role


class TestRoleStyle(unittest.TestCase):

    def test_ruoli_di_topo(self):
        self.assertEqual(role_style("outer").color, (0, 255, 0))
        self.assertEqual(role_style("inner").color, (255, 255, 0))
        self.assertEqual(role_style("unknown").color, (255, 0, 0))
        self.assertEqual(role_style(None).color, (255, 0, 0))

    def test_ruolo_di_consumatore_grigio(self):
        self.assertEqual(role_style("hole"), CONSUMER_ROLE_STYLE)

    def test_la_mappa_aggiunge_senza_riscrivere(self):
        mine = {"hole": RoleStyle(color=(255, 0, 255))}
        self.assertEqual(role_style("hole", mine).color, (255, 0, 255))
        self.assertEqual(role_style("outer", mine).color, (0, 255, 0))

    def test_la_mappa_cambia_un_campo_e_tiene_gli_altri(self):
        style = role_style("outer", {"outer": RoleStyle(lineweight=0.3)})
        self.assertEqual(style.color, (0, 255, 0))
        self.assertEqual(style.lineweight, 0.3)


class TestUnaPalettePerOgniFormato(unittest.TestCase):
    """DXF e SVG leggono la stessa palette: l'ACI scritto dal DXF e l'hex
    del view model sono lo stesso RGB."""

    def _result(self):
        segs = topo.geometry.rectangle(100, 50)
        hole = topo.geometry.circle(5, center=(20, 0))
        return topo.heal(topo.load_segments([segs, hole]))

    def test_dxf_traduce_la_palette(self):
        for role, style in DEFAULT_ROLE_STYLES.items():
            self.assertEqual(tuple(aci2rgb(color_for_role(role))), style.color)
        self.assertEqual(tuple(aci2rgb(color_for_role("hole"))), CONSUMER_ROLE_STYLE.color)

    def test_svg_traduce_la_palette(self):
        vm = topo.to_view_model(self._result())
        self.assertEqual(vm["clusters"][0]["outer"]["color"], "#00ff00")
        self.assertEqual(vm["palette"]["inner"], "#ffff00")

    def test_svg_con_la_mappa_del_consumer(self):
        vm = topo.to_view_model(self._result(), role_styles={"hole": RoleStyle(color=(255, 0, 255))})
        self.assertEqual(vm["palette"]["hole"], "#ff00ff")
        self.assertEqual(vm["palette"]["outer"], "#00ff00")


if __name__ == "__main__":
    unittest.main()
