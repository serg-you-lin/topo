"""
model/style.py
---------------
Aspetto visivo grezzo di un'entità sorgente — tipo di linea, tratto e colore.

Dato di dominio puro, in un vocabolario che nessun formato possiede (MAP.md
D126): niente indici colore ACI, niente BYLAYER/BYBLOCK, niente pattern nella
forma della tabella DXF. Ogni adapter traduce il suo formato in questi campi
al load, risolvendo l'ereditarietà (uno stile "del layer" è lo stile che la
linea ha davvero) e lo ritraduce in uscita. Captato al load (`Edge.style`),
sopravvive nel modello come `styles` — lista parallela a `segments` su
ClosedCurve/OpenCurve — e un exporter ne ripristina il tratto (Cluster E).
Il colore no: quello in uscita lo decide il ruolo, con la mappa del
chiamante (D123); qui resta perché `RoleRule(color=...)` lo legge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

# Forma del tratto (D64): continua, tratteggio uniforme (un solo segno ripetuto:
# tratti tutti uguali, o solo punti), catena (segni diversi alternati: tratto
# lungo + tratto corto o punto).
DASH_CONTINUOUS = "continuous"
DASH_UNIFORM    = "uniform"
DASH_CHAIN      = "chain"
VALID_DASH_KINDS = {DASH_CONTINUOUS, DASH_UNIFORM, DASH_CHAIN}

# Due segni sono "diversi" se differiscono più di questa frazione della
# lunghezza totale del pattern: relativo, così la scala del pattern non conta.
_MARK_REL_TOL = 0.05


@dataclass
class EdgeStyle:
    """
    Campi (tutti opzionali: un `EdgeStyle()` vuoto è "la sorgente non lo dice"):
        linetype      : nome del tipo di linea nella sorgente ("HIDDEN",
                        "CENTER", "CONTINUOUS"), "" se non ne ha uno
        linetype_desc : la sua descrizione, se la sorgente la porta
        dash          : il tratto, come segni con segno ripetuti — `> 0`
                        tratto, `0` punto, `< 0` vuoto (mm). `()` = continuo
                        dichiarato, `None` = non noto. Un dash-array PDF/SVG
                        `[3, 1]` è `(3, -1)`.
        color         : colore effettivo (r, g, b) 0–255, None se non noto
    """
    linetype:      str                          = ""
    linetype_desc: str                          = ""
    dash:          Optional[Tuple[float, ...]]  = None
    color:         Optional[Tuple[int, int, int]] = None

    @property
    def is_dashed(self) -> bool:
        """True se il tratto ha almeno un vuoto (D63)."""
        return any(element < 0 for element in self.dash or ())

    @property
    def dash_kind(self) -> str:
        """Forma del tratto: `continuous`, `uniform` o `chain` (D64)."""
        if not self.is_dashed:
            return DASH_CONTINUOUS
        marks = [e for e in self.dash if e >= 0]    # tratti (> 0) e punti (= 0)
        total = sum(abs(e) for e in self.dash)
        if max(marks, default=0.0) - min(marks, default=0.0) > _MARK_REL_TOL * total:
            return DASH_CHAIN
        return DASH_UNIFORM
