"""
test_parsing_and_exporting.py
-------------------
Unit tests for adapters/dxf/parser.py and adapters/dxf/exporter.py.

It tests the parsing of mock ezdxf entities → pure primitives, the export
primitives → DXF, and segments_from_loop.
"""

import unittest
from unittest.mock import MagicMock, patch
import math
from types import SimpleNamespace

from topo.core.primitives import LineSeg, CircleSeg, BSplineSeg, CircleSeg, EllipseSeg
from topo.core.topology.edge import Edge
from topo_dxf.parser import DxfEntityDispatcher
from topo.core.topology.loops import segments_from_loop
from topo_dxf.exporter import (
    arc_seg_to_bulge,
    segments_to_pts_with_bulge,
    write_open_segments,
    write_segments,
)
from topo.model.role import ContourRole

# --- Helper — mock DXF entities ---

def make_line(x1, y1, x2, y2, layer="0"):
    e = MagicMock()
    e.dxftype.return_value = 'LINE'
    e.dxf.start.x = x1
    e.dxf.start.y = y1
    e.dxf.end.x = x2
    e.dxf.end.y = y2
    e.dxf.layer = layer
    return e


def make_arc(cx, cy, radius, start_angle, end_angle, layer="0"):
    e = MagicMock()
    e.dxftype.return_value = 'ARC'
    e.dxf.center.x = cx
    e.dxf.center.y = cy
    e.dxf.radius = radius
    e.dxf.start_angle = start_angle
    e.dxf.end_angle = end_angle
    e.dxf.layer = layer
    return e


def make_lwpolyline(points_with_bulge, layer="0", is_closed=True):
    """Create a mock LWPOLYLINE.
    points_with_bulge: list of tuples (x, y, bulge)"""
    e = MagicMock()
    e.dxftype.return_value = 'LWPOLYLINE'
    e.get_points.return_value = points_with_bulge
    e.dxf.layer = layer
    e.closed = is_closed
    e.is_closed = is_closed
    return e


def make_polyline(vertices, layer="0", is_closed=True):
    """Create a mock POLYLINE (3D)."""
    e = MagicMock()
    e.dxftype.return_value = 'POLYLINE'
    e.dxf.layer = layer
    e.closed = is_closed
    e.is_closed = is_closed
    
    mock_vertices = []
    for x, y, bulge in vertices:
        v = MagicMock()
        v.dxf.location.x = x
        v.dxf.location.y = y
        getattr(v.dxf, "bulge", 0.0)  # per mockare l'attributo
        v.dxf.bulge = bulge
        mock_vertices.append(v)
    e.vertices = mock_vertices
    return e


def make_spline_entity(points, layer="0"):
    e = MagicMock()
    e.dxftype.return_value = 'SPLINE'
    e._mock_points = points
    e.dxf.layer = layer
    
    def mock_flattening(tolerance):
        return [(p[0], p[1], 0.0) for p in points]
    e.flattening = mock_flattening
    return e


def make_circle(cx, cy, radius, layer="0"):
    e = MagicMock()
    e.dxftype.return_value = 'CIRCLE'
    e.dxf.center.x = cx
    e.dxf.center.y = cy
    e.dxf.radius = radius
    e.dxf.layer = layer
    return e


def make_ellipse(cx, cy, major_x, major_y, ratio, start_param, end_param, layer="0"):
    e = MagicMock()
    e.dxftype.return_value = 'ELLIPSE'
    e.dxf.center.x = cx
    e.dxf.center.y = cy
    e.dxf.major_axis.x = major_x
    e.dxf.major_axis.y = major_y
    e.dxf.ratio = ratio
    e.dxf.start_param = start_param
    e.dxf.end_param = end_param
    e.dxf.layer = layer
    return e


def make_edge(entity, layer="0", rev=False):
    """Create an Edge carrying the real primitive parsed from the mock entity.

    segments_from_loop() does not re-parse the source entity: it simply
    concatenates edge.segment. The primitive must therefore be built here, as the
    adapter does at translation time."""
    seg = DxfEntityDispatcher(entity).parse(rev=rev)
    if isinstance(seg, list):
        start = getattr(seg[0], "start", (0.0, 0.0))
        end = getattr(seg[-1], "end", (0.0, 0.0))
    else:
        start = getattr(seg, "start", (0.0, 0.0))
        end = getattr(seg, "end", (0.0, 0.0))
    return Edge(
        role=ContourRole.UNKNOWN,
        start=start,
        end=end,
        segment=seg,
    )


def make_square_loop(side=100.0):
    s = side
    return [
        (make_edge(make_line(0, 0, s, 0)), False),
        (make_edge(make_line(s, 0, s, s)), False),
        (make_edge(make_line(s, s, 0, s)), False),
        (make_edge(make_line(0, s, 0, 0)), False),
    ]


class MockMSP:
    """Mock per ezdxf ModelSpace."""
    def __init__(self):
        self.doc = MagicMock()
        self.doc.dxfversion = "AC1015"
        self.entities = []
    
    def add_lwpolyline(self, pts, format="xyseb", dxfattribs=None, close=True):
        self.entities.append({
            'type': 'LWPOLYLINE',
            'points': pts,
            'format': format,
            'dxfattribs': dxfattribs,
            'close': close
        })
        return MagicMock()
    
    def add_polyline2d(self, pts, dxfattribs=None):
        self.entities.append({
            'type': 'POLYLINE2D',
            'points': pts,
            'dxfattribs': dxfattribs
        })
        return MagicMock()

    def add_ellipse(self, center, major_axis, ratio, start_param, end_param, dxfattribs=None):
        self.entities.append({
            'type': 'ELLIPSE',
            'center': center,
            'major_axis': major_axis,
            'ratio': ratio,
            'start_param': start_param,
            'end_param': end_param,
            'dxfattribs': dxfattribs,
        })
        return MagicMock()

    def add_spline(self, dxfattribs=None):
        spline = MagicMock()
        spline.dxf = SimpleNamespace(
            degree=None,
            flags=0,
            layer=dxfattribs.get("layer") if dxfattribs else None,
            color=dxfattribs.get("color") if dxfattribs else None,
        )
        spline.control_points = []
        spline.knots = []
        spline.weights = []
        self.entities.append({
            'type': 'SPLINE',
            'entity': spline,
            'dxfattribs': dxfattribs,
        })
        return spline


# ===========================================================================
# TESTS: DxfEntityDispatcher
# ===========================================================================

class TestDxfEntityDispatcher(unittest.TestCase):
    """Test of the dispatcher by DXF entity type."""

    def test_001_riconosce_tipi_noti(self):
        """Il dispatcher riconosce correttamente i tipi DXF."""
        self.assertEqual(DxfEntityDispatcher(make_line(0, 0, 10, 0)).kind, 'LINE')
        self.assertEqual(DxfEntityDispatcher(make_arc(0, 0, 10, 0, 180)).kind, 'ARC')
        self.assertEqual(
            DxfEntityDispatcher(make_spline_entity([(0, 0), (10, 10)])).kind,
            'SPLINE'
        )
        self.assertEqual(
            DxfEntityDispatcher(make_lwpolyline([(0, 0, 0), (10, 0, 0)])).kind,
            'LWPOLYLINE'
        )
        self.assertEqual(
            DxfEntityDispatcher(make_circle(0, 0, 10)).kind,
            'CIRCLE'
        )
        self.assertEqual(
            DxfEntityDispatcher(make_ellipse(0, 0, 10, 0, 0.5, 0, math.tau)).kind,
            'ELLIPSE'
        )

    def test_002_parse_line(self):
        """Parsing of a LINE → LineSeg."""
        parsed = DxfEntityDispatcher(make_line(0, 0, 10, 0)).parse(rev=False)
        self.assertIsInstance(parsed, LineSeg)
        self.assertEqual(parsed.start, (0.0, 0.0))
        self.assertEqual(parsed.end, (10.0, 0.0))

    def test_003_parse_line_reversed(self):
        """Parsing of a LINE with rev=True swaps start/end."""
        parsed = DxfEntityDispatcher(make_line(0, 0, 10, 0)).parse(rev=True)
        self.assertIsInstance(parsed, LineSeg)
        self.assertEqual(parsed.start, (10.0, 0.0))
        self.assertEqual(parsed.end, (0.0, 0.0))

    def test_004_parse_arc(self):
        """Parsing of an ARC → CircleSeg."""
        parsed = DxfEntityDispatcher(
            make_arc(0, 0, 10, 0, 180)
        ).parse(rev=False)
        self.assertIsInstance(parsed, CircleSeg)
        self.assertEqual(parsed.center, (0.0, 0.0))
        self.assertEqual(parsed.radius, 10.0)
        self.assertAlmostEqual(parsed.start_angle, 0.0)
        self.assertAlmostEqual(parsed.end_angle, math.pi)
        self.assertTrue(parsed.ccw)

    def test_005_parse_arc_reversed(self):
        """Parsing of an ARC with rev=True inverts ccw and angles."""
        parsed = DxfEntityDispatcher(
            make_arc(0, 0, 10, 0, 180)
        ).parse(rev=True)
        self.assertIsInstance(parsed, CircleSeg)
        self.assertAlmostEqual(parsed.start_angle, math.pi)
        self.assertAlmostEqual(parsed.end_angle, 0.0)
        self.assertFalse(parsed.ccw)

    def test_006_parse_circle(self):
        """Parsing of a CIRCLE → CircleSeg (pure geometric primitive)."""
        parsed = DxfEntityDispatcher(make_circle(0, 0, 10)).parse(rev=False)
        from topo.core.primitives import CircleSeg
        self.assertIsInstance(parsed, CircleSeg)
        self.assertEqual(parsed.center, (0.0, 0.0))
        self.assertEqual(parsed.radius, 10.0)

    def test_006b_parse_ellipse(self):
        """Parsing of an ELLIPSE → EllipseSeg (pure geometric primitive)."""
        parsed = DxfEntityDispatcher(
            make_ellipse(1, 2, 10, 0, 0.5, 0.0, math.tau)
        ).parse(rev=False)
        self.assertIsInstance(parsed, EllipseSeg)
        self.assertEqual(parsed.center, (1.0, 2.0))
        self.assertEqual(parsed.major_axis, (10.0, 0.0))
        self.assertEqual(parsed.ratio, 0.5)
        self.assertAlmostEqual(parsed.start_param, 0.0)
        self.assertAlmostEqual(parsed.end_param, math.tau)
        self.assertTrue(parsed.ccw)

    def test_006c_parse_ellipse_reversed(self):
        """Parsing of an ELLIPSE with rev=True swaps the parameters and negates ccw."""
        parsed = DxfEntityDispatcher(
            make_ellipse(0, 0, 10, 0, 0.5, 0.0, math.pi / 2)
        ).parse(rev=True)
        self.assertIsInstance(parsed, EllipseSeg)
        self.assertAlmostEqual(parsed.start_param, math.pi / 2)
        self.assertAlmostEqual(parsed.end_param, 0.0)
        self.assertFalse(parsed.ccw)

    def test_007_parse_lwpolyline_without_bulge(self):
        """LWPOLYLINE without bulge → LineSeg."""
        parsed = DxfEntityDispatcher(
            make_lwpolyline([(0, 0, 0), (10, 0, 0), (10, 10, 0)], is_closed=False)
        ).parse(rev=False)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 2)  # N-1 segmenti
        self.assertIsInstance(parsed[0], LineSeg)

    def test_008_parse_lwpolyline_with_bulge(self):
        """LWPOLYLINE with bulge → CircleSeg."""
        parsed = DxfEntityDispatcher(
            make_lwpolyline([
                (0, 0, 0),
                (10, 0, 1.0),  # bulge=1 → 180° arc
                (10, 10, 0),
            ], is_closed=False)
        ).parse(rev=False)
        
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 2)
        self.assertIsInstance(parsed[0], LineSeg)
        self.assertIsInstance(parsed[1], CircleSeg)
        
        # bulge=1, start=(10,0), end=(10,10) 
        # sweep = 4*atan(1) = π (180°)
        # half_chord = 5, radius = 5, d = 0
        # centro = (10, 5)
        self.assertAlmostEqual(parsed[1].center[0], 10.0)
        self.assertAlmostEqual(parsed[1].center[1], 5.0)
        self.assertAlmostEqual(parsed[1].radius, 5.0)

    def test_009_parse_lwpolyline_closed(self):
        """Closed LWPOLYLINE: N points → N segments."""
        parsed = DxfEntityDispatcher(
            make_lwpolyline([
                (0, 0, 0),
                (10, 0, 0),
                (10, 10, 0),
            ], is_closed=True)
        ).parse(rev=False)
        
        self.assertEqual(len(parsed), 3)  # N segmenti (chiusa)

    def test_010_parse_polyline_3d(self):
        """Parsing of a 3D POLYLINE with bulge."""
        parsed = DxfEntityDispatcher(
            make_polyline([
                (0, 0, 0),
                (10, 0, 1.0),
                (10, 10, 0),
            ], is_closed=False)
        ).parse(rev=False)
        
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 2)
        self.assertIsInstance(parsed[0], LineSeg)
        self.assertIsInstance(parsed[1], CircleSeg)

    def test_011_parse_tipo_sconosciuto_restituisce_none(self):
        """Tipo DXF sconosciuto → None."""
        e = MagicMock()
        e.dxftype.return_value = 'UNKNOWN'
        parsed = DxfEntityDispatcher(e).parse(rev=False)
        self.assertIsNone(parsed)


# ===========================================================================
# TESTS: segments_from_loop
# ===========================================================================

class TestSegmentsFromLoop(unittest.TestCase):
    """Test of segments_from_loop on an Edge loop."""

    def test_001_loop_void(self):
        """Loop vuoto → lista vuota."""
        self.assertEqual(segments_from_loop([]), [])

    def test_002_loop_line_singola(self):
        """Loop with a LINE → a LineSeg."""
        loop = [(make_edge(make_line(0, 0, 10, 0)), False)]
        result = segments_from_loop(loop)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], LineSeg)

    def test_003_loop_quadrate(self):
        """Loop quadrato → 4 LineSeg."""
        primitives = segments_from_loop(make_square_loop(100.0))
        self.assertEqual(len(primitives), 4)
        for p in primitives:
            self.assertIsInstance(p, LineSeg)
        self.assertEqual(primitives[0].start, (0.0, 0.0))
        self.assertEqual(primitives[0].end, (100.0, 0.0))

    def test_004_loop_with_arc(self):
        """Loop with an ARC → CircleSeg."""
        arc = make_arc(50, 0, 50, 0, 180)
        loop = [
            (make_edge(arc), False),
            (make_edge(make_line(0, 0, 100, 0)), False),
        ]
        result = segments_from_loop(loop)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], CircleSeg)
        self.assertIsInstance(result[1], LineSeg)

    def test_005_loop_with_lwpolyline(self):
        """Loop with an LWPOLYLINE → segments."""
        polyline = make_lwpolyline([
            (0, 0, 0),
            (10, 0, 0.5),
            (10, 10, 0),
            (0, 10, 0),
        ], is_closed=False)
        loop = [(make_edge(polyline), False)]
        result = segments_from_loop(loop)
        
        self.assertEqual(len(result), 3)  # N-1 segmenti
        self.assertIsInstance(result[0], LineSeg)
        self.assertIsInstance(result[1], CircleSeg)  # bulge convertito
        self.assertIsInstance(result[2], LineSeg)

    def test_006_loop_with_lwpolyline_reversed(self):
        """Loop with a reversed LWPOLYLINE → negated bulge and inverted points."""
        polyline = make_lwpolyline([
            (0, 0, 0),
            (10, 0, 0.5),
            (10, 10, 0),
        ], is_closed=False)
        loop = [(make_edge(polyline, rev=True), False)]
        result = segments_from_loop(loop)

        self.assertEqual(len(result), 2)
        
        # With reversal, the order of the points is inverted:
        # original: (0,0) → (10,0) → (10,10)
        # reversed: (10,10) → (10,0) → (0,0)
        # The bulge stays on the same segment but inverted: (10,0)→(0,0) with bulge=0.5
        
        # First segment: from (10,10) to (10,0) with bulge=0 → LineSeg
        self.assertIsInstance(result[0], LineSeg)
        self.assertEqual(result[0].start, (10.0, 10.0))
        self.assertEqual(result[0].end, (10.0, 0.0))
        
        # Second segment: from (10,0) to (0,0) with bulge=0.5 → CircleSeg
        self.assertIsInstance(result[1], CircleSeg)
        start1 = (
            result[1].center[0] + result[1].radius * math.cos(result[1].start_angle),
            result[1].center[1] + result[1].radius * math.sin(result[1].start_angle)
        )
        end1 = (
            result[1].center[0] + result[1].radius * math.cos(result[1].end_angle),
            result[1].center[1] + result[1].radius * math.sin(result[1].end_angle)
        )
        self.assertAlmostEqual(start1[0], 10.0)
        self.assertAlmostEqual(start1[1], 0.0)
        self.assertAlmostEqual(end1[0], 0.0)
        self.assertAlmostEqual(end1[1], 0.0)

    def test_007_loop_with_spline(self):
        """Loop with a SPLINE → BSplineSeg."""
        spline = make_spline_entity([(0, 0), (0, 50), (0, 100)])
        loop = [
            (make_edge(spline), False),
            (make_edge(make_line(0, 100, 100, 100)), False),
        ]
        result = segments_from_loop(loop)
        spline_prims = [p for p in result if isinstance(p, BSplineSeg)]
        self.assertEqual(len(spline_prims), 1)

    def test_008_loop_ottimizzazione_polyline_singola(self):
        """Loop with a single LWPOLYLINE is optimized."""
        polyline = make_lwpolyline([
            (0, 0, 0),
            (10, 0, 0),
            (10, 10, 0),
            (0, 10, 0),
        ], is_closed=True)
        loop = [(make_edge(polyline), False)]
        result = segments_from_loop(loop)
        self.assertEqual(len(result), 4)  # N segmenti (chiusa)


# ===========================================================================
# TESTS: arc_seg_to_bulge
# ===========================================================================

class TestArcToBulge(unittest.TestCase):
    """Test conversione CircleSeg → bulge DXF."""

    def test_001_bulge_90_ccw(self):
        """Arco 90° CCW → bulge = tan(π/8)."""
        arc = CircleSeg(center=(0, 0), radius=10, start_angle=0, end_angle=math.pi/2, ccw=True)
        bulge = arc_seg_to_bulge(arc)
        self.assertAlmostEqual(bulge, math.tan(math.pi/8), places=6)

    def test_002_bulge_90_cw(self):
        """Arco 90° CW (da π/2 a 0) → bulge = -tan(π/8)."""
        arc = CircleSeg(center=(0, 0), radius=10, start_angle=math.pi/2, end_angle=0, ccw=False)
        bulge = arc_seg_to_bulge(arc)
        self.assertAlmostEqual(bulge, -math.tan(math.pi/8), places=6)

    def test_002b_bulge_inverted_arc_is_not_the_complement(self):
        """Regression: a CW arc has as swept angle the real stretch start→end walked
        clockwise, NOT the complement to 2π.

        segments_from_loop produces arcs with ccw=False when it orients the loop CCW;
        if arc_seg_to_bulge used (end-start)%2π the arc would be rewritten "upside
        down" (the complementary arc's bulge)."""
        ccw_arc = CircleSeg(center=(0, 0), radius=10,
                         start_angle=math.radians(350),
                         end_angle=math.radians(10), ccw=True)
        cw_arc = CircleSeg(center=(0, 0), radius=10,
                        start_angle=math.radians(10),
                        end_angle=math.radians(350), ccw=False)
        # Same physical arc (sweep 20°), opposite direction → bulges opposite in sign
        # and equal in modulus, both small (tan(5°) ≈ 0.087), not ~11.4.
        self.assertAlmostEqual(arc_seg_to_bulge(ccw_arc), math.tan(math.radians(5)), places=6)
        self.assertAlmostEqual(arc_seg_to_bulge(cw_arc), -math.tan(math.radians(5)), places=6)

    def test_003_bulge_180_ccw(self):
        """Arco 180° CCW → bulge = tan(π/4)."""
        arc = CircleSeg(center=(0, 0), radius=10, start_angle=0, end_angle=math.pi, ccw=True)
        bulge = arc_seg_to_bulge(arc)
        self.assertAlmostEqual(bulge, math.tan(math.pi/4), places=6)

    def test_004_negative_bulge_for_cw(self):
        """Arco CW produce bulge negativo."""
        arc = CircleSeg(center=(0, 0), radius=10, start_angle=math.pi, end_angle=0, ccw=False)
        bulge = arc_seg_to_bulge(arc)
        self.assertLess(bulge, 0)

    def test_005_roundtrip_inverted_arc(self):
        """A CircleSeg and its reversed version (as segments_from_loop produces it when
        the loop is oriented CCW) must discretize on the same set of points and
        produce bulges of equal modulus: no "upside-down" arc in the write-back."""
        arc = CircleSeg(center=(3, -2), radius=7.5,
                     start_angle=math.radians(20),
                     end_angle=math.radians(140), ccw=True)
        rev = arc.reversed()

        pts_fwd = arc.discretize(tolerance=0.01)
        pts_rev = rev.discretize(tolerance=0.01)
        self.assertEqual(len(pts_fwd), len(pts_rev))
        for (xf, yf), (xr, yr) in zip(pts_fwd, reversed(pts_rev)):
            self.assertAlmostEqual(xf, xr, places=6)
            self.assertAlmostEqual(yf, yr, places=6)

        self.assertAlmostEqual(
            abs(arc_seg_to_bulge(arc)), abs(arc_seg_to_bulge(rev)), places=9
        )


# ===========================================================================
# TESTS: segments_to_pts_with_bulge
# ===========================================================================

class TestSegmentsToPtsWithBulge(unittest.TestCase):
    """Test of the conversion of segments → points with bulge."""

    def test_001_line_segments(self):
        """LineSeg → bulge=0."""
        segments = [
            LineSeg(start=(0, 0), end=(10, 0)),
            LineSeg(start=(10, 0), end=(10, 10)),
        ]
        result = segments_to_pts_with_bulge(segments)
        self.assertEqual(len(result), 2)
        for pt in result:
            self.assertEqual(pt[4], 0.0)  # bulge=0

    def test_002_arc_segment(self):
        """CircleSeg → start point + computed bulge."""
        arc = CircleSeg(center=(0, 0), radius=10, start_angle=0, end_angle=math.pi/2, ccw=True)
        result = segments_to_pts_with_bulge([arc])
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0][0], 10.0)  # x start
        self.assertAlmostEqual(result[0][1], 0.0)   # y start
        self.assertAlmostEqual(result[0][4], math.tan(math.pi/8), places=6)

    def test_003_arc_with_different_start_angle(self):
        """CircleSeg with start_angle ≠ 0."""
        arc = CircleSeg(
            center=(5, 5), radius=10,
            start_angle=math.pi/4,
            end_angle=3*math.pi/4,
            ccw=True
        )
        result = segments_to_pts_with_bulge([arc])
        expected_x = 5 + 10 * math.cos(math.pi/4)
        expected_y = 5 + 10 * math.sin(math.pi/4)
        self.assertAlmostEqual(result[0][0], expected_x)
        self.assertAlmostEqual(result[0][1], expected_y)

    def test_004_segments_misti(self):
        """Segmenti misti LineSeg + CircleSeg."""
        segments = [
            LineSeg(start=(0, 0), end=(10, 0)),
            CircleSeg(center=(10, 0), radius=10, start_angle=-math.pi/2, end_angle=0, ccw=True),
        ]
        result = segments_to_pts_with_bulge(segments)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][4], 0.0)   # line → bulge 0
        self.assertNotEqual(result[1][4], 0.0)  # arc → bulge != 0


# ===========================================================================
# TESTS: write_contour_to_msp
# ===========================================================================

class TestWriteContourToMsp(unittest.TestCase):
    """Test esportazione contour su ModelSpace."""

    def setUp(self):
        self.msp = MockMSP()

    def test_001_segments_void(self):
        """Segments vuoti → None."""
        contour = MagicMock()
        contour.segments = []
        result = write_segments(contour.segments, self.msp, "TEST")
        self.assertIsNone(result)

    def test_002_segments_with_spline(self):
        """Spline singola → esportata come SPLINE nativa."""
        contour = MagicMock()
        contour.segments = [
            BSplineSeg(degree=0, control_points=[(0, 0), (10, 0)], knots=[], weights=None)
        ]
        result = write_segments(contour.segments, self.msp, "TEST")
        self.assertIsNotNone(result)
        self.assertEqual(len(self.msp.entities), 1)
        entity = self.msp.entities[0]
        self.assertEqual(entity['type'], 'SPLINE')
        self.assertEqual(entity['entity'].dxf.degree, 0)
        self.assertEqual(entity['entity'].control_points, [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)])

    def test_002b_segments_with_closed_ellipse(self):
        """Ellisse chiusa singola → esportata come ELLIPSE nativa, mai spline."""
        contour = MagicMock()
        contour.segments = [
            EllipseSeg(center=(1, 2), major_axis=(10, 0), ratio=0.5,
                       start_param=0.0, end_param=math.tau)
        ]
        result = write_segments(contour.segments, self.msp, "TEST")
        self.assertIsNotNone(result)
        self.assertEqual(len(self.msp.entities), 1)
        entity = self.msp.entities[0]
        self.assertEqual(entity['type'], 'ELLIPSE')
        self.assertEqual(entity['center'], (1, 2))
        self.assertEqual(entity['major_axis'], (10, 0, 0.0))
        self.assertEqual(entity['ratio'], 0.5)

    def test_003_line_segments_soli(self):
        """Solo LineSeg → LWPOLYLINE."""
        contour = MagicMock()
        contour.segments = [
            LineSeg(start=(0, 0), end=(10, 0)),
            LineSeg(start=(10, 0), end=(10, 10)),
            LineSeg(start=(10, 10), end=(0, 10)),
            LineSeg(start=(0, 10), end=(0, 0)),
        ]
        result = write_segments(contour.segments, self.msp, "TEST")
        self.assertIsNotNone(result)
        self.assertEqual(len(self.msp.entities), 1)
        entity = self.msp.entities[0]
        self.assertEqual(entity['type'], 'LWPOLYLINE')
        self.assertEqual(len(entity['points']), 4)

    def test_004_with_arc_segments(self):
        """With CircleSeg → LWPOLYLINE with bulge."""
        contour = MagicMock()
        contour.segments = [
            CircleSeg(center=(10, 0), radius=10, start_angle=0, end_angle=math.pi/2, ccw=True),
            LineSeg(start=(10, 10), end=(0, 10)),
            LineSeg(start=(0, 10), end=(0, 0)),
            LineSeg(start=(0, 0), end=(10, 0)),
        ]
        result = write_segments(contour.segments, self.msp, "TEST")
        self.assertIsNotNone(result)
        entity = self.msp.entities[0]
        # First point = arc start
        self.assertAlmostEqual(entity['points'][0][0], 20.0)
        self.assertAlmostEqual(entity['points'][0][1], 0.0)
        self.assertNotEqual(entity['points'][0][4], 0.0)  # bulge != 0

    def test_005_r12_compatibility(self):
        """R12 version → POLYLINE2D instead of LWPOLYLINE."""
        self.msp.doc.dxfversion = "AC1009"
        contour = MagicMock()
        contour.segments = [
            LineSeg(start=(0, 0), end=(10, 0)),
            LineSeg(start=(10, 0), end=(10, 10)),
        ]
        result = write_segments(contour.segments, self.msp, "TEST")
        self.assertIsNotNone(result)
        entity = self.msp.entities[0]
        self.assertEqual(entity['type'], 'POLYLINE2D')

    def test_006_leap_remains_visible(self):
        """A ring with a jump (anch_01: a 0.05 dash removed) is not written closed: the
        closed polyline would draw a crooked side over the hole and the jump would
        vanish from the DXF."""
        segments = [
            LineSeg(start=(171.0068, 90.4406), end=(171.0068, 138.3906)),
            LineSeg(start=(171.0068, 138.3906), end=(168.0068, 138.3906)),
            LineSeg(start=(168.0068, 138.3906), end=(168.0068, 90.3906)),
            LineSeg(start=(168.0068, 90.3906), end=(171.0068, 90.3906)),
        ]
        write_segments(segments, self.msp, "TEST")
        self.assertTrue(all(not e.get('close', False) for e in self.msp.entities))
        points = [tuple(p[:2]) for e in self.msp.entities for p in e['points']]
        self.assertIn((171.0068, 90.3906), points)   # the end of the bottom side
        self.assertIn((171.0068, 90.4406), points)   # the start of the next side

    def test_007_leap_within_an_open_stretch(self):
        """write_open_segments splits the polyline where a segment does not start at the
        end of the previous: no vertex skips the end of a stretch."""
        segments = [
            LineSeg(start=(0, 0), end=(10, 0)),
            LineSeg(start=(10, 0.05), end=(10, 10)),
        ]
        write_open_segments(segments, self.msp, "TEST")
        points = [tuple(p[:2]) for e in self.msp.entities for p in e['points']]
        self.assertIn((10, 0), points)
        self.assertIn((10, 0.05), points)
        self.assertEqual(len(self.msp.entities), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)