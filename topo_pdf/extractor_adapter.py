"""
topo_pdf/extractor_adapter.py
----------------------------------
Extract raw vector graphic elements from a PDF page using PyMuPDF.

This module is the only one (together with loader.py) that knows 'fitz'. It
isolates the PDF's internal structure and returns clean data.

Public functions:
    extract_drawings_from_page — extracts the vector commands, mapping them to primitive types"""

from typing import Any, Dict, List


def extract_drawings_from_page(page: Any) -> List[Dict[str, Any]]:
    """Extract the vector drawings from the PDF page and normalize the output. It
    resolves PyMuPDF's inconsistencies and filters only the valid geometric commands.

    Args:
        page: the PyMuPDF page object (fitz.Page)

    Returns:
        A list of dicts containing the normalized graphic commands."""
    extracted_drawings = []
    
    try:
        raw_drawings = page.get_drawings()
    except Exception as ex:
        print(f"  [WARN] Estrazione disegni fallita sulla pagina: {ex}")
        return []

    for drawing in raw_drawings:
        # the stroke/fill properties, in case they are needed later for layers
        normalized_drawing = {
            "layer_hint": drawing.get("layer", ""),
            "color": drawing.get("color", None),
            "fill": drawing.get("fill", None),
            "width": drawing.get("width", 1.0),
            "items": []
        }

        for item in drawing.get("items", []):
            cmd = item[0]

            # 1. LINEA ("l") -> (cmd, point1, point2)
            if cmd == "l":
                p1, p2 = item[1], item[2]
                normalized_drawing["items"].append(("l", p1, p2))

            # 2. RETTANGOLO ("re") -> (cmd, rect_object)
            elif cmd == "re":
                rect = item[1]
                # check that the rectangle is valid and not degenerate
                if rect.x0 != rect.x1 and rect.y0 != rect.y1:
                    normalized_drawing["items"].append(("re", rect))

            # 3. QUADRILATERO ("qu") -> (cmd, list_of_4_points)
            elif cmd == "qu":
                quad = item[1]
                if len(quad) == 4:
                    normalized_drawing["items"].append(("qu", quad))

            # 4. CURVA DI BEZIER ("c") -> (cmd, p1, p2, p3, p4)
            elif cmd == "c":
                p1, p2, p3, p4 = item[1], item[2], item[3], item[4]
                normalized_drawing["items"].append(("c", p1, p2, p3, p4))
                
            # Note: any intermediate "s" (stroke) or "f" (fill) commands are ignored
            # because we handle the atomic geometry of the elements.

        # add the drawing only if it actually contains geometric elements
        if normalized_drawing["items"]:
            extracted_drawings.append(normalized_drawing)

    return extracted_drawings