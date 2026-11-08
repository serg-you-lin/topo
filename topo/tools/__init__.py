"""
topo/tools/
------------
Stadi opzionali e componibili su un ``Result`` già prodotto da
``topo.heal``. Ognuno lo arricchisce in-place e lo ritorna; il chiamante
sceglie quali eseguire e in che ordine.

- ``anchor_texts`` — àncora ogni testo al cluster che lo contiene

È il pattern che un interprete di disegno (progetto separato) generalizza e
orchestra dall'alto.
"""

from .anchor import anchor_texts

__all__ = ["anchor_texts"]
