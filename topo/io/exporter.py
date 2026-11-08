"""
topo/io/exporter.py
-------------------
Il `Result` come JSON, solo geometria (D230). La sola fonte dei campi è
`Result.to_dict()`; qui si aggiungono i campi di un consumatore e si scrive.
"""

import json
from typing import Callable, Optional

from ..model import Cluster, Result


def _with_extra(result: Result, extra: Optional[Callable[[Cluster], dict]]) -> dict:
    """`result.to_dict()` con i campi di `extra(cluster)` uniti a ogni cluster;
    una chiave che topo scrive già è un errore, mai una sostituzione (D230)."""
    data = result.to_dict()
    if extra is None:
        return data
    for cluster, fields in zip(result.clusters, data["clusters"]):
        added = extra(cluster) or {}
        clash = sorted(set(added) & set(fields))
        if clash:
            raise ValueError(
                f"extra() returned keys topo already writes for cluster {cluster.label!r}: {clash}"
            )
        fields.update(added)
    return data


def to_json(result: Result, *, indent: int = 2,
            extra: Optional[Callable[[Cluster], dict]] = None) -> str:
    """
    The result as a JSON string, geometry only (D230, D231).

    Top level: `source_file`, `source_format`, `reading`, `tolerance`,
    `max_gap`, `is_valid`, `warnings`, `errors`, `loose_count`, `text_count`,
    `clusters`. Each cluster: `label`, `area`, `outer_perimeter`,
    `inner_perimeter`, `inner_count`, `bbox`, `detected` (items per
    collection). Drawing units, exact on the primitives, no coordinates
    (`topo_dxf.to_dxf` carries the curves).

    `extra(cluster) -> dict` adds a consumer's fields (material, a part code,
    anything topo cannot know) to each cluster. A key topo already writes
    raises `ValueError`.
    """
    return json.dumps(_with_extra(result, extra), indent=indent, ensure_ascii=False)


def save_json(result: Result, path: str, *, indent: int = 2,
              extra: Optional[Callable[[Cluster], dict]] = None) -> None:
    """Write `to_json(result, indent=indent, extra=extra)` to `path` (UTF-8)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_json(result, indent=indent, extra=extra))
