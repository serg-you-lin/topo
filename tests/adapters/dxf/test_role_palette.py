"""
test_role_palette.py
--------------------
topo's palette: the colour of the roles topo produces is a single one, for
every format — outer green, inner yellow, unknown red, grey every other role —
and the caller's map goes on top field by field, without rewriting topo's roles.
"""

import unittest

from ezdxf.colors import aci2rgb


import topo
from topo.model import CONSUMER_ROLE_STYLE, DEFAULT_ROLE_STYLES, RoleStyle, role_style
from topo_dxf.layers import color_for_role


class TestRoleStyle(unittest.TestCase):

    def test_topo_roles(self):
        self.assertEqual(role_style("outer").color, (0, 255, 0))
        self.assertEqual(role_style("inner").color, (255, 255, 0))
        self.assertEqual(role_style("unknown").color, (255, 0, 0))
        self.assertEqual(role_style(None).color, (255, 0, 0))

    def test_consumer_role_grey(self):
        self.assertEqual(role_style("hole"), CONSUMER_ROLE_STYLE)

    def test_the_map_adds_without_rewriting(self):
        mine = {"hole": RoleStyle(color=(255, 0, 255))}
        self.assertEqual(role_style("hole", role_styles=mine).color, (255, 0, 255))
        self.assertEqual(role_style("outer", role_styles=mine).color, (0, 255, 0))

    def test_the_map_changes_a_field_and_keeps_the_others(self):
        style = role_style("outer", role_styles={"outer": RoleStyle(lineweight=0.3)})
        self.assertEqual(style.color, (0, 255, 0))
        self.assertEqual(style.lineweight, 0.3)


class TestOnePalettePerEveryFormat(unittest.TestCase):
    """DXF and SVG read the same palette: the ACI written by the DXF and the hex of
    the view model are the same RGB."""

    def _result(self):
        segs = topo.geometry.rectangle(100, 50)
        hole = topo.geometry.circle(5, center=(20, 0))
        return topo.heal(topo.load_segments([segs, hole])).faces()

    def test_dxf_translates_the_palette(self):
        for role, style in DEFAULT_ROLE_STYLES.items():
            self.assertEqual(tuple(aci2rgb(color_for_role(role))), style.color)
        self.assertEqual(tuple(aci2rgb(color_for_role("hole"))), CONSUMER_ROLE_STYLE.color)

    def test_svg_translates_the_palette(self):
        vm = topo.experimental.to_view_model(self._result())
        self.assertEqual(vm["clusters"][0]["outer"]["color"], "#00ff00")
        self.assertEqual(vm["palette"]["inner"], "#ffff00")

    def test_svg_with_the_consumer_map(self):
        vm = topo.experimental.to_view_model(self._result(), role_styles={"hole": RoleStyle(color=(255, 0, 255))})
        self.assertEqual(vm["palette"]["hole"], "#ff00ff")
        self.assertEqual(vm["palette"]["outer"], "#00ff00")


if __name__ == "__main__":
    unittest.main()
