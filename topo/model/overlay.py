"""
topo/model/overlay.py
-----------------------
L'overlay aperto di un cluster (MAP.md D44): `Cluster.overlay` è un
`Overlay`, un contenitore che si scrive per nome. topo non ci scrive
niente: lo riempie un consumatore (snapbend: fori, pieghe, incisioni; snapdraw;
un riconoscitore custom), tutti con lo stesso meccanismo. `cluster.overlay is
None` finché nessuno ci ha scritto.

Nessun contratto sugli elementi, nemmeno a runtime (MAP.md D5: "convenzione,
non gerarchia"). I renderer leggono
di ogni elemento solo `role` e la geometria (`contours`, oppure
`segments`; un vuoto lo dichiara con `is_void`) — MAP.md D90.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List

from topo.core.geometry.rings import ring_closes


@dataclass
class Overlay:
    """
    Container open by name: each consumer writes under the name it wants,
    with the same method.
    """
    _store: Dict[str, List[Any]] = field(default_factory=dict)

    def attach(self, name: str, items: Iterable[Any]) -> None:
        """Sostituisce (o crea) la collezione `name` con `items`."""
        self._store[name] = list(items)

    def add(self, name: str, item: Any) -> None:
        """Aggiunge un elemento alla collezione `name`, creandola se manca."""
        self._store.setdefault(name, []).append(item)

    def get(self, name: str, default: List[Any] = None) -> List[Any]:
        """Collezione `name`, o `default` (`[]` se non specificato) se assente."""
        return self._store.get(name, [] if default is None else default)

    def items(self):
        """`(nome, collezione)` per ogni nome attaccato — per chi vuole iterare tutto."""
        return self._store.items()

    def names(self) -> List[str]:
        return list(self._store.keys())

    def __getattr__(self, name: str) -> List[Any]:
        # Scatta solo per attributi assenti: `_store` è un campo vero del
        # dataclass, mai in loop. `cluster.overlay.<nome>` per qualunque nome.
        store = self.__dict__.get("_store", {})
        try:
            return store[name]
        except KeyError:
            raise AttributeError(
                f"{name!r} is not attached to this Overlay "
                f"(names present: {list(store)})"
            )

    def __repr__(self) -> str:
        counts = {k: len(v) for k, v in self._store.items()}
        return f"Overlay({counts})"


def feature_closed(contour, item) -> bool:
    """
    True if a contour of an overlay item is drawn as a closed ring: it is a
    `ClosedCurve`, its item declares itself a void of the part (`is_void`),
    or its `segments` close a ring head to tail (MAP.md D90, D166).
    Otherwise they are drawn as they are, one primitive each (a bend).
    """
    from .curve import ClosedCurve
    if isinstance(contour, ClosedCurve) or getattr(item, "is_void", False):
        return True
    return ring_closes(getattr(contour, "segments", None) or [])



def _feature_contours(item) -> list:
    """
    I contorni di un elemento dell'overlay come li legge ogni renderer: i suoi
    `contours` se li ha, altrimenti l'elemento stesso (D90).
    """
    contours = getattr(item, "contours", None)
    return [item] if contours is None else list(contours)


def _feature_drawable(item) -> bool:
    """
    Vero se un renderer disegna qualcosa dell'elemento: almeno un contorno con
    `segments` e un ruolo (suo o dell'elemento, D90). Altrimenti l'elemento non
    porta geometria (D244).
    """
    from .role import feature_role
    role = getattr(item, "role", None)
    return any(getattr(c, "segments", None) and feature_role(c, role)
               for c in _feature_contours(item))
