"""
topo_pdf/sanitize.py
--------------------
Geometric sanitization of the data extracted from the PDF before conversion
into Edges.

Public functions:
    sanitize_pdf_geometries — snaps nearby nodes and removes duplicate or degenerate segments
"""



from topo.precision import PDF_SNAP


def sanitize_pdf_geometries(raw_items: list, page_height: float, snap_tolerance: float = PDF_SNAP) -> list:
    """Take the raw geometric items extracted by the extractor, apply the mm
    conversion with Y-axis inversion, snap nearby points within a tolerance, and
    remove degenerate micro-segments (e.g. lines shorter than the tolerance).

    Args:
        raw_items:       list of tuples (cmd, ...) coming from extractor_adapter
        page_height:     height of the PDF page in points (pt)
        snap_tolerance:  maximum distance in mm below which two points are merged (default 0.15 mm)

    Returns:
        list — ready items, sanitized and already converted to standard float coordinates (mm)"""
    from .geometry_adapter import transform_point, sample_bezier_cubic
    import math

    sanitized_items = []
    known_nodes = []

    def _get_snapped_point(pt_mm: tuple[float, float]) -> tuple[float, float]:
        """Trova un nodo esistente vicino entro la tolleranza, altrimenti lo registra."""
        for kn in known_nodes:
            dist = math.hypot(pt_mm[0] - kn[0], pt_mm[1] - kn[1])
            if dist <= snap_tolerance:
                return kn
        known_nodes.append(pt_mm)
        return pt_mm

    for item in raw_items:
        cmd = item[0]

        if cmd == "l":
            # 1. Converti in mm
            p1_raw = transform_point(item[1].x, item[1].y, page_height)
            p2_raw = transform_point(item[2].x, item[2].y, page_height)
            
            # 2. Applica lo snap ai nodi vicini
            p1 = _get_snapped_point(p1_raw)
            p2 = _get_snapped_point(p2_raw)
            
            # remove degenerate segments (points collapsing onto the same node, or too short)
            if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) > snap_tolerance:
                sanitized_items.append(("l", p1, p2))

        elif cmd == "re":
            rect = item[1]
            p0 = _get_snapped_point(transform_point(rect.x0, rect.y0, page_height))
            p1 = _get_snapped_point(transform_point(rect.x1, rect.y0, page_height))
            p2 = _get_snapped_point(transform_point(rect.x1, rect.y1, page_height))
            p3 = _get_snapped_point(transform_point(rect.x0, rect.y1, page_height))
            
            # avoid rectangles collapsed to lines or points
            if p0 != p1 and p1 != p2:
                sanitized_items.append(("re", [p0, p1, p2, p3]))

        elif cmd == "qu":
            quad = item[1]
            pts = [_get_snapped_point(transform_point(p.x, p.y, page_height)) for p in quad]
            if len(set(pts)) >= 3:  # at least 3 distinct points to make a valid quadrilateral
                sanitized_items.append(("qu", pts))

        elif cmd == "c":
            p1_raw = transform_point(item[1].x, item[1].y, page_height)
            p2_raw = transform_point(item[2].x, item[2].y, page_height)
            p3_raw = transform_point(item[3].x, item[3].y, page_height)
            p4_raw = transform_point(item[4].x, item[4].y, page_height)
            
            p1 = _get_snapped_point(p1_raw)
            p2 = _get_snapped_point(p2_raw)
            p3 = _get_snapped_point(p3_raw)
            p4 = _get_snapped_point(p4_raw)
            
            # sample the curve directly into a polyline (discretized points)
            pts_curve = sample_bezier_cubic(p1, p2, p3, p4, num_segments=16)
            
            # apply the snap to the sampled interior points of the curve too
            #
            pts_curve_snapped = [_get_snapped_point(pt) for pt in pts_curve]
            
            # Pulizia da duplicati consecutivi generati dallo snapping
            cleaned_curve_pts = [pts_curve_snapped[0]]
            for pt in pts_curve_snapped[1:]:
                if pt != cleaned_curve_pts[-1]:
                    cleaned_curve_pts.append(pt)
            
            if len(cleaned_curve_pts) >= 2:
                sanitized_items.append(("c_poly", cleaned_curve_pts))

    return sanitized_items


