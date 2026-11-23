"""
topo_pdf/loader.py
------------------
Single entry point to open, extract and convert geometries from a PDF file.

Public functions:
    load_pdf — opens the PDF, extracts the drawings, sanitizes them by
               geometric snap and returns a list of Edges for the core.
"""

from topo.precision import PDF_SNAP
import os
try:
    import fitz
except ImportError:
    fitz = None

from .extractor_adapter import extract_drawings_from_page
from .sanitize import sanitize_pdf_geometries
from .graph_adapter import map_sanitized_item_to_edge


def load_pdf(path: str, snap_tolerance: float = PDF_SNAP) -> list:
    """Open a PDF document, extract the vector geometries from all the pages, apply
    a heavy sanitization (geometric snap of nearby nodes), convert them to real
    scale (mm) with the Cartesian Y axis corrected, and return a list of
    topological Edges ready for the graph core.

    Args:
        path:           path of the .pdf file
        snap_tolerance: maximum distance in mm below which two nearby nodes are merged

    Returns:
        list[Edge] — ready to be passed to build_node_graph() or put in a virtual msp"""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"PDF file not found: {path}")

    all_edges = []

    try:
        doc = fitz.open(path)
        print(f"[pdf/loader] Opened PDF: {path} ({len(doc)} pages)")

        for page_idx, page in enumerate(doc):
            page_height = page.rect.height
            page_edges_count = 0  # reset the counter for the current page

            # Extraction of the raw graphic packets (islands of native Python data)
            drawings_packages = extract_drawings_from_page(page)

            # Unroll all the single raw items present in the page's various packets
            raw_items = []
            for package in drawings_packages:
                raw_items.extend(package["items"])

            # 4. Heavy sanitization and geometric snap (removes the micro-disconnections)
            sanitized_items = sanitize_pdf_geometries(
                raw_items=raw_items, 
                page_height=page_height, 
                snap_tolerance=snap_tolerance
            )

            for item in sanitized_items:
                # the nodes are the true points (Edge.of): no decimal digits of the adapter's own
                mapped = map_sanitized_item_to_edge(item, page_idx)
                if mapped is None:
                    continue
                new_edges = mapped if isinstance(mapped, list) else [mapped]
                all_edges.extend(new_edges)
                page_edges_count += len(new_edges)

            print(f"  [page {page_idx}] Estratti e sanificati {page_edges_count} elementi grafici convertiti in mm")

        doc.close()
        return all_edges

    except Exception as ex:
        raise RuntimeError(f"the PDF could not be loaded: {ex}")