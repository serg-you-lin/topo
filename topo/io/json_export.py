"""
topo/io/json_export.py
----------------------
The `Result` as JSON, geometry only. The only source of the fields is
`Result.to_dict()`; here a consumer's fields are added and it is written.
"""

import json
from typing import Callable, Optional

from ..model import Cluster, Result


def _with_extra(result: Result, extra: Optional[Callable[[Cluster], dict]]) -> dict:
    """`result.to_dict()` with the fields of `extra(cluster)` merged into every
    cluster; a key topo already writes is an error, never a replacement."""
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
    The result as a JSON string, geometry only.

    Top level: `source_file`, `source_format`, `reading`,
    `max_gap`, `is_valid`, `warnings`, `errors`, `loose_count`, `text_count`,
    `clusters`. Each cluster: `label`, `area`, `outer_perimeter`,
    `inner_perimeter`, `inner_count`, `bbox`, `overlay` (items per
    collection). In mm, exact on the primitives, no coordinates
    (an adapter's writer carries the curves).

    `extra(cluster) -> dict` adds a consumer's fields (anything topo cannot
    know) to each cluster. A key topo already writes
    raises `ValueError`.
    """
    return json.dumps(_with_extra(result, extra), indent=indent, ensure_ascii=False)


def save_json(result: Result, path: str, *, indent: int = 2,
              extra: Optional[Callable[[Cluster], dict]] = None) -> None:
    """Write `to_json(result, indent=indent, extra=extra)` to `path` (UTF-8)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_json(result, indent=indent, extra=extra))
