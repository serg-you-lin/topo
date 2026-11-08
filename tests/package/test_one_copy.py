"""
tests/package/test_one_copy.py
------------------------------
Un nome, una copia: ogni disegno di `tests/data/` sta in una cartella sola e
tutti i test lo trovano con `tests.paths.drawing(nome)`. Una copia in due
posti si modifica in uno e il test che legge l'altro non lo sa.

`SAME_NAME_DIFFERENT_CONTENT`: i nomi ancora doppi con contenuti diversi,
da risolvere uno per uno (TODO). La lista può solo accorciarsi: un nome nuovo
doppio fa fallire il test, e anche un nome della lista che torna unico.
"""

import collections
import unittest

from tests.paths import DATA

SAME_NAME_DIFFERENT_CONTENT = {
    "anch_01.dxf", "anch_02.dxf", "anch_03.dxf", "anch_04.dxf",
    "anch_05.dxf", "anch_06.dxf", "anch_07.dxf", "anch_08.dxf",
    "cerchi_ciambella_P1.dxf", "cerchi_ciambella_P2.dxf",
    "la_104.DXF", "maniglia_no_raccordi.dxf", "piastra_sei_fori.dxf",
    "pline_with_hole.dxf", "rect_lines.dxf", "rect_with_countersink.dxf",
    "rect_with_hole_lines.dxf", "two_parts.dxf",
}


class TestOneCopy(unittest.TestCase):

    def test_un_nome_una_copia(self):
        by_name = collections.defaultdict(list)
        for p in DATA.rglob("*"):
            # `*healed*` sono uscite locali, fuori da git (.gitignore)
            if p.is_file() and p.suffix.lower() == ".dxf" and "healed" not in p.name:
                by_name[p.name].append(p.relative_to(DATA).as_posix())
        doubles = {n for n, paths in by_name.items() if len(paths) > 1}
        self.assertEqual(sorted(doubles - SAME_NAME_DIFFERENT_CONTENT), [],
                         msg="nomi doppi nuovi: una copia sola, letta con drawing()")
        self.assertEqual(sorted(SAME_NAME_DIFFERENT_CONTENT - doubles), [],
                         msg="tornati unici: toglierli da SAME_NAME_DIFFERENT_CONTENT")


if __name__ == "__main__":
    unittest.main()
