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

`RoleStyle`, nello stesso vocabolario, è l'altro verso: come si disegna un
ruolo in uscita (D128). La palette di topo (`DEFAULT_ROLE_STYLES`) dà il
colore ai ruoli che topo produce — outer verde, inner giallo, unknown rosso —
e il grigio a ogni altro; la mappa del chiamante ci si mette sopra. Ogni
exporter chiede `role_style(ruolo, mappa)` e traduce soltanto: la scelta è di
topo e del chiamante, mai di un formato.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Mapping, Optional, Tuple

from .role import ContourRole, role_str

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


@dataclass(frozen=True)
class RoleStyle:
    """
    Come il chiamante vuole disegnato un ruolo in uscita (D37, D128). Il
    chiamante ne tiene un dizionario `{ruolo: RoleStyle}` e lo passa a ogni
    exporter (`to_dxf`, `split`, `to_svg`, `to_view_model`): topo non ne
    tiene nessuno, ogni exporter ha il suo default per i campi a `None`.

    Stesso vocabolario di `EdgeStyle`, nessun formato. Dove finisce un ruolo
    (un layer DXF, un gruppo SVG) non è qui: lo decide l'exporter, con i
    suoi parametri (`to_dxf(layers=...)`).

    Campi (tutti opzionali):
        color      : (r, g, b) 0–255
        linetype   : nome del tipo di linea, per i formati che lo nominano;
                     da solo vale un tipo standard del formato ("DASHED")
        dash       : il tratto, segni con segno come in `EdgeStyle.dash`
        lineweight : spessore in mm
    """
    color:      Optional[Tuple[int, int, int]] = None
    linetype:   Optional[str]                  = None
    dash:       Optional[Tuple[float, ...]]    = None
    lineweight: Optional[float]                = None


# ---------------------------------------------------------------------------
# La palette di topo (D128): il colore dei ruoli che heal()/island()
# producono, uguale per ogni formato. Un ruolo di un consumatore che nessuna
# mappa nomina è grigio: topo non sa cos'è, ma non è spazzatura (D31).
# ---------------------------------------------------------------------------
DEFAULT_ROLE_STYLES: Mapping[str, RoleStyle] = {
    ContourRole.OUTER.value:   RoleStyle(color=(0, 255, 0)),      # verde
    ContourRole.INNER.value:   RoleStyle(color=(255, 255, 0)),    # giallo
    ContourRole.UNKNOWN.value: RoleStyle(color=(255, 0, 0)),      # rosso
}
CONSUMER_ROLE_STYLE = RoleStyle(color=(128, 128, 128))            # grigio


def role_style(role, role_styles: Optional[Mapping[str, RoleStyle]] = None) -> RoleStyle:
    """
    Come si disegna `role`: la palette di topo (o il grigio di un ruolo di
    consumatore), con sopra i campi non `None` del `RoleStyle` che il
    chiamante dà per quel ruolo in `role_styles`. Un consumatore aggiunge i
    suoi ruoli senza riscrivere quelli di topo, e può cambiarne uno.
    """
    slug = role_str(role) if role else ContourRole.UNKNOWN.value
    base = DEFAULT_ROLE_STYLES.get(slug, CONSUMER_ROLE_STYLE)
    own = (role_styles or {}).get(slug)
    if own is None:
        return base
    return replace(base, **{f.name: getattr(own, f.name)
                            for f in fields(own) if getattr(own, f.name) is not None})
