"""
topo/tools/
------------
Optional, composable stages on a ``Result`` already produced by
``topo.heal``. Each enriches it in place and returns it; the caller chooses
which to run and in what order.

- ``anchor_texts`` — anchors every text to the cluster that contains it

It is the pattern that a drawing interpreter (a separate project)
generalizes and orchestrates from above.
"""

from .anchor import anchor_texts

__all__ = ["anchor_texts"]
