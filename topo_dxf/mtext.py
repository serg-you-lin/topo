"""
topo_dxf/mtext.py
-----------------
Decoding of DXF formatted text: MTEXT inline codes and MULTILEADER text.

`clean_mtext` is a string → string function (the MTEXT formatting codes are a
text format, not DXF entities) and is re-exported by ``topo`` as a generic
utility. `mleader_text` instead reads an ezdxf entity.
"""

from __future__ import annotations

from typing import Optional

from ezdxf.tools.text import plain_mtext


def clean_mtext(txt) -> str:
    """Plain text from a raw MTEXT string: removes the formatting codes (font,
    colour, alignment, …). Edge spaces stay: they take room in the drawn string.
    It also accepts an entity with a ``.text`` attribute for convenience.
    Returns "" for empty strings or placeholders ("<>")."""
    if not txt:
        return ""
    if not isinstance(txt, str):
        try:
            txt = txt.text
        except Exception:
            txt = str(txt)

    result = plain_mtext(txt)
    return "" if result.strip() in ("<>", "") else result


def mleader_text(entity) -> Optional[str]:
    """Raw text of a MULTILEADER (before cleaning), None if absent."""
    try:
        mtext = entity.context.mtext
        if mtext and hasattr(mtext, "default_content"):
            return mtext.default_content
    except Exception:
        pass
    return None
