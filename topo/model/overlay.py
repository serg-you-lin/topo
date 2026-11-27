"""
topo/model/overlay.py
-----------------------
The open overlay of a cluster: `Cluster.overlay` is an `Overlay`, a container
written by name. topo writes nothing into it: a consumer fills it (any
recognizer of its own), all with the same
mechanism. `cluster.overlay is None` until someone has written to it.

No contract on the elements, not even at runtime ("convention, not
hierarchy"). The renderers read only the `role` and the geometry of each
element (`contours`, or `segments`; a void declares itself with `is_void`).
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
        """Replace (or create) the collection `name` with `items`."""
        self._store[name] = list(items)

    def add(self, name: str, item: Any) -> None:
        """Add an element to the collection `name`, creating it if missing."""
        self._store.setdefault(name, []).append(item)

    def get(self, name: str, default: List[Any] = None) -> List[Any]:
        """Collection `name`, or `default` (`[]` if unspecified) if absent."""
        return self._store.get(name, [] if default is None else default)

    def items(self):
        """`(name, collection)` for every attached name — for whoever wants to iterate everything."""
        return self._store.items()

    def names(self) -> List[str]:
        return list(self._store.keys())

    def __getattr__(self, name: str) -> List[Any]:
        # Fires only for absent attributes: `_store` is a real field of the dataclass,
        # never in a loop. `cluster.overlay.<name>` for any name.
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
    """True if a contour of an overlay item is drawn as a closed ring: it is a
    closed curve (`ClosedCurve` or `Contour`), its item declares itself a void of the figure (`is_void`),
    or its `segments` close a ring head to tail.
    Otherwise they are drawn as they are, one primitive each."""
    from .curve import _Ring
    if isinstance(contour, _Ring) or getattr(item, "is_void", False):
        return True
    return ring_closes(getattr(contour, "segments", None) or [])



def _feature_contours(item) -> list:
    """The contours of an overlay element as every renderer reads them: its
    `contours` if it has them, otherwise the element itself."""
    contours = getattr(item, "contours", None)
    return [item] if contours is None else list(contours)


def _feature_drawable(item) -> bool:
    """True if a renderer draws something of the element: at least one contour with
    `segments` and a role (its own or the element's). Otherwise the element
    carries no geometry."""
    from .role import feature_role
    role = getattr(item, "role", None)
    return any(getattr(c, "segments", None) and feature_role(c, role)
               for c in _feature_contours(item))
