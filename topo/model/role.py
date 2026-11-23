"""
model/role.py

Topological role of a shape — the minimum the engine (core/) must know to
build the containment tree: is it an outer contour, an inner contour, or has it
no role decided yet. Full stop. **No manufacturing taxonomy lives here** (hole,
threaded hole, countersink, bend, engraving, marking, ...) — that is a
consumer's vocabulary (snapbend): topo does not know what a hole is, it only
distinguishes one contour from another.

``ContourRole`` is NOT a closed universe: a consumer (a library above topo,
snapbend, snapdraw, an agent — none is privileged) can assign a role core does
not know — ``"hole"``, ``"frame"``, ``"title_block"``, any slug — and topo
keeps it and treats it as non-structural by default. How it is drawn on output
is decided by an exporter from the role, with the caller's map — not as
garbage: that geometry is not trash. Whoever wants a role core does not know to
be treated as structural (a hole is a true part contour, not decoration)
passes their own predicate to ``heal(doc, is_structural=...)``.

``normalize_role()`` is the only point where a role string coming from the
caller enters the model: it cleans it once into a safe slug, so all the
downstream code (keys and serialized values, names and attributes of any
output format) can trust it without re-validating.

The rules with which the caller assigns a role at load live in
``model/role_rule.py``.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Dict

# Role slug: lowercase, digits, _ and -. Everything else is collapsed to "_" by
# normalize_role — it neutralizes injection payloads (`"</cluster>"`, newlines,
# characters an output format does not accept in a name): a security choice, not
# a format's.
_MAX_ROLE_LEN = 64
_ROLE_SLUG_RE = re.compile(r"[^a-z0-9_-]+")


class ContourRole(str, Enum):
    """The three roles the topology engine knows. **Not exhaustive** — a consumer
    assigns any other string to an edge/contour, see ``normalize_role``.

    It inherits from str: the value is already a plain string, so JSON/repr write
    ``"outer"`` instead of ``<ContourRole.OUTER: 'outer'>`` and comparisons with
    strings work without ``.value``."""
    UNKNOWN = "unknown"   # default — no role decided
    OUTER   = "outer"     # outer profile of the part, found by heal()
    INNER   = "inner"     # loop interno, trovato da heal()
    # Nothing else here. `hole`/`bending`/`engrave`/... are process vocabulary
    # (snapbend), `frame`/`title_block`/... snapdraw's: a consumer's slugs, outside
    # this enum, same treatment.


# --- Taxonomy: which roles are contour topology (pure engine) ---
# The single point of truth for the question "is this edge/loop/proxy OUTER or
# INNER by how heal() built it, regardless of any manufacturing meaning?".
# Whoever wants heal() to treat as structural also a role core does not know (a
# hole assigned by role_rules, say) passes their own predicate to
# `heal(doc, is_structural=...)`. Without that predicate, heal() treats any role
# outside here as non-structural by default (it leaves the graph, stays in
# `loose` with its role intact).
STRUCTURAL_ROLES = frozenset({
    ContourRole.OUTER,
    ContourRole.INNER,
})


def is_structural_role(role) -> bool:
    """True if ``role`` is OUTER or INNER for the engine (see ``STRUCTURAL_ROLES``).

    The engine's minimal predicate — it knows nothing about holes, bends or
    engravings. A pure membership test — it accepts both a ``ContourRole``
    constant and the equivalent string slug (``ContourRole`` inherits from
    ``str``). No reverse lookup on the enum."""
    return role in STRUCTURAL_ROLES


def feature_role(contour, item_role):
    """The role with which a contour of an overlay element is drawn: its own, if it
    is a consumer's; the element's, if the contour carries only an engine role
    (outer/inner/unknown: where the geometry comes from, not what it means)."""
    own = getattr(contour, "role", None)
    if own and own != ContourRole.UNKNOWN and not is_structural_role(own):
        return own
    return item_role or own


# --- work_type string → ContourRole — pure mapping, no format dependencies ---
WORK_TYPE_TO_ROLE: Dict[str, ContourRole] = {
    "outer": ContourRole.OUTER,
    "inner": ContourRole.INNER,
}


def normalize_role(value) -> str:
    """
    Cleans a role string coming from the caller (``RoleRule``,
    ``load_geometry``) and returns it as a safe slug.

    It is the only entry point: from here on ``feature.role`` is always
    either a ``ContourRole`` constant or a short ``[a-z0-9_-]`` slug, which
    the rest of topo trusts without re-checking.

    - non-string or empty → ``"unknown"``
    - lowercase, leading/trailing ``_``/``-`` removed
    - characters outside ``[a-z0-9_-]`` collapsed into ``_``
    - truncated to 64 characters
    - if it is a known role → the canonical ``ContourRole`` constant
    - otherwise → the slug as is (a consumer's role)

    Never do dynamic lookups on the enum (``ContourRole[s]``, ``getattr``,
    ``ContourRole(s)``): they raise or reach class attributes. Here it always
    goes through a dict.
    """
    if not isinstance(value, str):
        return ContourRole.UNKNOWN.value
    slug = _ROLE_SLUG_RE.sub("_", value.strip().lower()).strip("_-")
    slug = slug[:_MAX_ROLE_LEN]
    if not slug:
        return ContourRole.UNKNOWN.value
    known = WORK_TYPE_TO_ROLE.get(slug)
    return known if known is not None else slug


def role_str(role) -> str:
    """String value of a role, whether a ``ContourRole`` constant or an already pure
    string. Use it in place of ``role.value``, which blows up on a plain ``str``."""
    return role.value if isinstance(role, ContourRole) else str(role)

