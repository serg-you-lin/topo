"""
model/role_rule.py
-------------------
Rules with which the caller assigns a role to the incoming lines.

topo provides only the mechanism: the content of the rules (which names, which
styles, which role) is written by the caller. The adapter evaluates them at
load on neutral signals — the source group's name and the appearance
(`EdgeStyle`) — and hands the core only the resulting role.
"""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

from .role import ContourRole, normalize_role
from .style import VALID_DASH_KINDS, EdgeStyle

RGB = Tuple[int, int, int]

# The basic colours by name, with the RGB values a CAD gives its indexed
# colours. Black is black: a "white or black depending on the background" colour
# of a format is translated by its adapter.
_COLOR_NAMES: Dict[str, RGB] = {
    "red": (255, 0, 0), "yellow": (255, 255, 0), "green": (0, 255, 0),
    "cyan": (0, 255, 255), "blue": (0, 0, 255), "magenta": (255, 0, 255),
    "white": (255, 255, 255), "black": (0, 0, 0),
    "gray": (128, 128, 128), "grey": (128, 128, 128),
    "darkgray": (128, 128, 128), "darkgrey": (128, 128, 128),
    "lightgray": (192, 192, 192), "lightgrey": (192, 192, 192),
    "pink": (255, 127, 127),
}


# --- Public API ---

@dataclass
class RoleRule:
    """A rule: if ALL the given conditions are true, the line takes `role`.
    Conditions left as None do not count; at least one is required.

    Fields:
        role          : the assigned role (goes through normalize_role)
        name          : source group name, equal (case ignored)
        name_contains : substring of the group name (case ignored)
        dashed        : True = dashed only, False = continuous only
        dash          : stroke shape, "continuous" / "uniform" / "chain"
        color         : effective color, (r, g, b), "#rrggbb" or a basic
                        name ("cyan", "red", ...)
        filled        : True = sides of a filled area only, False = the
                        others (`EdgeStyle.filled`)"""
    role:          str
    _: KW_ONLY
    name:          Optional[str]              = None
    name_contains: Optional[str]              = None
    dashed:        Optional[bool]             = None
    dash:          Optional[str]              = None
    color:         Optional[Union[RGB, str]]  = None
    filled:        Optional[bool]             = None

    def __post_init__(self):
        if (self.name is None and self.name_contains is None and self.dashed is None
                and self.dash is None and self.color is None and self.filled is None):
            raise ValueError(f"RoleRule({self.role!r}) has no condition: it would match everything")
        self.role = normalize_role(self.role)
        if self.name is not None:
            self.name = self.name.lower()
        if self.name_contains is not None:
            self.name_contains = self.name_contains.lower()
        if self.dash is not None:
            self.dash = self.dash.lower()
            if self.dash not in VALID_DASH_KINDS:
                raise ValueError(f"RoleRule({self.role!r}): dash {self.dash!r} is not valid, "
                                 f"expected one of {sorted(VALID_DASH_KINDS)}")
        if self.color is not None:
            self.color = _color_rgb(self.color)

    @property
    def reads_style(self) -> bool:
        """True if the rule looks at the appearance (stroke, colour, fill), not only the name."""
        return (self.dashed is not None or self.dash is not None or self.color is not None
                or self.filled is not None)

    def matches(self, name: str, *, style: Optional[EdgeStyle] = None) -> bool:
        """True if the element (source group name + appearance) satisfies the rule.
        `style=None` = the source has no appearance to compare (a text): a rule that
        looks at the appearance does not match."""
        if style is None and self.reads_style:
            return False
        name = (name or "").lower()
        if self.name is not None and name != self.name:
            return False
        if self.name_contains is not None and self.name_contains not in name:
            return False
        if self.dashed is not None and style.is_dashed != self.dashed:
            return False
        if self.dash is not None and style.dash_kind != self.dash:
            return False
        if self.color is not None and style.color != self.color:
            return False
        if self.filled is not None and style.filled != self.filled:
            return False
        return True


def resolve_role(rules: Sequence[RoleRule], name: str, style: Optional[EdgeStyle] = None) -> str:
    """Role of the first rule that matches, in order; `unknown` if none."""
    for rule in rules:
        if rule.matches(name, style=style):
            return rule.role
    return ContourRole.UNKNOWN.value


def name_rules(mapping: Dict[str, str]) -> List[RoleRule]:
    """Shortcut: a {name: role} dict becomes one RoleRule(name=...) for each entry."""
    return [RoleRule(role=role, name=name) for name, role in mapping.items()]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _color_rgb(value: Union[RGB, str]) -> RGB:
    """(r, g, b) from a tuple, from "#rrggbb" or from a basic name ("cyan")."""
    if isinstance(value, (tuple, list)) and len(value) == 3:
        return tuple(int(c) for c in value)
    key = str(value).strip().lower()
    if key.startswith("#") and len(key) == 7:
        try:
            return tuple(int(key[k:k + 2], 16) for k in (1, 3, 5))
        except ValueError:
            pass
    if key in _COLOR_NAMES:
        return _COLOR_NAMES[key]
    raise ValueError(f"unknown colour: {value!r}; expected (r, g, b), "
                     f"'#rrggbb' or one of {sorted(_COLOR_NAMES)}")
