"""
topo/precision.py
-----------------
Every fixed threshold of topo, in one place (D269). Nothing else in the
package writes a threshold as a number: it imports it from here
(`tests/package/test_one_threshold.py` checks it). The values cannot be
reassigned: `topo.precision.SAME_POINT = 0.1` raises `AttributeError`.
A caller that needs another value for one operation passes it explicitly
(for gaps: `heal(doc, max_gap=...)`).

All lengths are millimetres (D245).
"""

import sys
import types

# ---------------------------------------------------------------------------
# La soglia (D268)
# ---------------------------------------------------------------------------

# Due punti più vicini di così sono lo stesso punto: nodi, contatti, stessa
# retta/cerchio, lato degenere, salti in un contorno, taglio delle spline.
# CAMBIARLA cambia le letture: più grande, capi e curve lontane fino a lei
# diventano un punto solo (contorni che si chiudono, lati corti che spariscono);
# più piccola, capi scritti con pochi decimali restano staccati (contorni aperti
# senza max_gap) e le spline si tagliano più fini (più lento). Misurata sui 631
# DXF di tests/: sotto 0,001 i contatti sulle spline, oggi calcolati sulla loro
# discretizzazione, rompono i contorni.
SAME_POINT = 1e-3
# È anche la sagitta di ogni poligono di una curva (D275): calcolo, disegno, testi.

# ---------------------------------------------------------------------------
# Aritmetica: il rumore dei calcoli, non il disegno
# ---------------------------------------------------------------------------

# rumore dei double: il margine di ogni soglia ("entro" la comprende, D183);
# sopra quello di un moto (~1e-11), sotto ogni soglia di contatto
FLOAT_NOISE = 1e-6
# due radici dello stesso calcolo d'intersezione sono lo stesso punto
ROOT_NOISE = 1e-7
# guardia contro una divisione per zero o un passo nullo
ZERO_GUARD = 1e-9

# ---------------------------------------------------------------------------
# Angoli: non lunghezze
# ---------------------------------------------------------------------------

SAME_DIRECTION_SINE = 1e-7     # seno: due direzioni uguali per costruzione, non tolleranti
COLLINEAR_ANGLE = 1e-6         # radianti: due rette con la stessa direzione
TANGENT_ANGLE = 1e-3           # radianti: sotto, due lati proseguono uno nell'altro
SHAPE_ANGLE_DEG = 1.0          # gradi: angolo retto / lati paralleli di una forma (contour_shape)
CORNER_TURN_DEG = 35.0         # gradi: una svolta più ampia è uno spigolo (simplify_points)
NEAR_FULL_ARC_MISSING_DEG = 2.0  # gradi: un arco cui manca di più non è un cerchio (D112)
NEAR_FULL_ARC_HINT_DEG = 8.0     # gradi: fin qui heal() avvisa che manca poco; un filetto (~90°) mai (D227)
ANGLE_BRACKET_DEG = 1.0        # gradi: attorno all'angolo trovato si cerca il riquadro d'area minima (contour_shape)

# ---------------------------------------------------------------------------
# Frazioni e rapporti: non lunghezze
# ---------------------------------------------------------------------------

SHAPE_FRACTION = 0.01          # della dimensione del contorno (contour_shape)
CIRCULAR_BBOX_ASPECT = 0.15    # lati del riquadro di un "quasi cerchio"
SIDE_COVERAGE = 0.85           # quota minima di un lato coperta dai tratti
MARK_FRACTION = 0.05           # della lunghezza di un tratto di linea a tratti
NEAR_GAP_FACTOR = 2.0          # un buco fino a questo multiplo di max_gap "c'è quasi" (D227)

# ---------------------------------------------------------------------------
# Altro, non ancora portato a SAME_POINT: da misurare (TODO, D268)
# ---------------------------------------------------------------------------

MIN_CONTOUR_AREA = 1e-3        # mm²: un contorno più piccolo non è un contorno
RING_TO_CIRCLE = 0.02          # mm: un anello scritto a punti entro così da un cerchio è quel cerchio (D236)
COLLINEAR_DISTANCE = 0.1       # mm: default di `group_collinear_lines`
CONCENTRIC_DISTANCE = 0.1      # mm: default di `concentric_groups`
NON_CONTOUR_DISTANCE = 0.1     # mm: default di `find_non_contour_edges`
AXIS_DEVIATION = 0.5           # mm: un tratto entro così dall'asse è orizzontale/verticale (fogli)
SAME_COORDINATE = 1.5          # mm: due coordinate di un foglio entro così sono la stessa
DIRECTION_SAMPLE = 3.0         # mm: dove si legge la direzione di un edge a un nodo
TESSELLATION_SIDE = 0.1        # mm: lati più corti possono essere punti di una curva scritta a punti (refit_tessellations)
PDF_SNAP = 0.15                # mm: adattatore PDF sperimentale, congelato (D10)


class _Frozen(types.ModuleType):
    """Il modulo non si riassegna: una soglia si cambia solo qui, con una decisione."""

    def __setattr__(self, name, value):
        raise AttributeError(f"topo.precision.{name} is fixed (D269); pass a value to the call instead")

    def __delattr__(self, name):
        raise AttributeError(f"topo.precision.{name} is fixed (D269)")


sys.modules[__name__].__class__ = _Frozen
