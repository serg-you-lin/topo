"""
model/role_rule.py
-------------------
Regole con cui il chiamante assegna un ruolo alle linee in ingresso.

topo fornisce solo il meccanismo: il contenuto delle regole (quali nomi,
quali stili, quale ruolo) lo scrive chi chiama. L'adapter le valuta al load
su segnali neutri — il nome del gruppo sorgente e l'aspetto (`EdgeStyle`) —
e consegna al core solo il ruolo risultante (MAP.md D63).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

from .role import ContourRole, normalize_role
from .style import VALID_DASH_KINDS, EdgeStyle

RGB = Tuple[int, int, int]

# I colori di base per nome, con i valori RGB che un CAD dà ai suoi colori
# indicizzati (MAP.md D126). Il nero è il nero: una linea "bianca/nera" di un
# DXF (indice 7) è bianca, la legge così l'adapter.
_COLOR_NAMES: Dict[str, RGB] = {
    "red": (255, 0, 0), "yellow": (255, 255, 0), "green": (0, 255, 0),
    "cyan": (0, 255, 255), "blue": (0, 0, 255), "magenta": (255, 0, 255),
    "white": (255, 255, 255), "black": (0, 0, 0),
    "gray": (128, 128, 128), "grey": (128, 128, 128),
    "darkgray": (128, 128, 128), "darkgrey": (128, 128, 128),
    "lightgray": (192, 192, 192), "lightgrey": (192, 192, 192),
    "pink": (255, 127, 127),
}


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

@dataclass
class RoleRule:
    """
    Una regola: se TUTTE le condizioni date sono vere, la linea prende `role`.
    Le condizioni lasciate a None non contano; almeno una è obbligatoria.

    Campi:
        role          : ruolo assegnato (passa per normalize_role)
        name          : nome del gruppo sorgente, uguale (maiuscole ignorate)
        name_contains : sottostringa del nome del gruppo (maiuscole ignorate)
        dashed        : True = solo tratteggiate, False = solo continue
        dash          : forma del tratto, "continuous" / "uniform" / "chain"
        color         : colore effettivo, (r, g, b), "#rrggbb" o un nome
                        di base ("cyan", "red", ...)
    """
    role:          str
    name:          Optional[str]              = None
    name_contains: Optional[str]              = None
    dashed:        Optional[bool]             = None
    dash:          Optional[str]              = None
    color:         Optional[Union[RGB, str]]  = None

    def __post_init__(self):
        if (self.name is None and self.name_contains is None
                and self.dashed is None and self.dash is None and self.color is None):
            raise ValueError(f"RoleRule({self.role!r}) senza condizioni: matcherebbe tutto")
        self.role = normalize_role(self.role)
        if self.name is not None:
            self.name = self.name.lower()
        if self.name_contains is not None:
            self.name_contains = self.name_contains.lower()
        if self.dash is not None:
            self.dash = self.dash.lower()
            if self.dash not in VALID_DASH_KINDS:
                raise ValueError(f"RoleRule({self.role!r}): dash {self.dash!r} non valido, "
                                 f"attesi {sorted(VALID_DASH_KINDS)}")
        if self.color is not None:
            self.color = _color_rgb(self.color)

    @property
    def reads_style(self) -> bool:
        """True se la regola guarda l'aspetto (tratto o colore), non solo il nome."""
        return self.dashed is not None or self.dash is not None or self.color is not None

    def matches(self, name: str, style: Optional[EdgeStyle] = None) -> bool:
        """
        True se l'elemento (nome del gruppo sorgente + aspetto) soddisfa la
        regola. `style=None` = la sorgente non ha un aspetto da confrontare
        (un testo, D127): una regola che guarda l'aspetto non matcha.
        """
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
        return True


def resolve_role(rules: Sequence[RoleRule], name: str, style: Optional[EdgeStyle] = None) -> str:
    """Ruolo della prima regola che matcha, in ordine; `unknown` se nessuna."""
    for rule in rules:
        if rule.matches(name, style):
            return rule.role
    return ContourRole.UNKNOWN.value


def name_rules(mapping: Dict[str, str]) -> List[RoleRule]:
    """Scorciatoia: {nome: ruolo} → una RoleRule(name=...) per voce."""
    return [RoleRule(role=role, name=name) for name, role in mapping.items()]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _color_rgb(value: Union[RGB, str]) -> RGB:
    """(r, g, b) da una tupla, da "#rrggbb" o da un nome di base ("cyan")."""
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
    raise ValueError(f"colore non riconosciuto: {value!r} — attesi (r, g, b), "
                     f"'#rrggbb' o uno di {sorted(_COLOR_NAMES)}")
