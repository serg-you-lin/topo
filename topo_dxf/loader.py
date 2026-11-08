
"""
topo_dxf/loader.py
------------------
Punto di ingresso unico per aprire un file DXF o DWG.

Funzioni pubbliche:
    load_dxf — apre, audita, upgradia, sanitizza, traduce → Document

load_dxf è l'UNICO punto in cui ezdxf viene toccato per la lettura: dopo di essa
il documento ezdxf sorgente sparisce e heal()/write() lavorano solo sul
Document restituito.
"""

import os
import sys
import shutil
from typing import Callable, Sequence, Union

import ezdxf
from ezdxf.addons import odafc

from .sanitize import sanitize, _explode_inserts, _explode_hatches, deduplicate
from .adapter import DxfAdapter
from .text_extractor import DxfTextExtractor
from .layers import SKIP_LAYERS
from topo.model import DEFAULT_NODE_TOLERANCE, Diagnostic, Document, RoleRule

# Percorso dell'eseguibile ODA File Converter. `topo` NON legge i DWG da solo:
# il supporto DWG di ezdxf È l'addon `odafc`, che è un wrapper attorno a ODA
# File Converter (converte il DWG in DXF temporaneo, ezdxf rilegge il DXF).
# Download (gratuito): https://www.opendesign.com/guestfiles/oda_file_converter
ODA_DOWNLOAD_URL = "https://www.opendesign.com/guestfiles/oda_file_converter"
ODA_PATH = os.environ.get("ODA_PATH")

# Guida rapida alle variabili d'ambiente per SO — rimando nei messaggi d'errore.
_ENV_VAR_HELP = (
    "How to set ODA_PATH:\n"
    "  Windows (permanente): setx ODA_PATH \"C:\\Program Files\\ODA\\"
    "ODAFileConverter X.Y.Z\\ODAFileConverter.exe\"  (open a new terminal)\n"
    "  Windows (session)   : $env:ODA_PATH = \"...\\ODAFileConverter.exe\"  (PowerShell)\n"
    "  Linux / macOS       : export ODA_PATH=\"/opt/ODAFileConverter/ODAFileConverter\" "
    "in ~/.bashrc or ~/.zshrc\n"
    "  Or put the ODAFileConverter executable on the system PATH."
)

DWG_VERSIONS = {
    'AC1012': 'R13',
    'AC1014': 'R14',
    'AC1015': 'R2000',
    'AC1018': 'R2004',
    'AC1021': 'R2007',
    'AC1024': 'R2010',
    'AC1027': 'R2013',
    'AC1032': 'R2018+',
}


# ---------------------------------------------------------------------------
# DWG → doc via odafc
# ---------------------------------------------------------------------------

def _text_signature(text) -> tuple:
    return (text.source_kind, round(text.position[0], 3), round(text.position[1], 3),
            text.text)


def _merge_texts(base: list, extra: list) -> None:
    """Aggiunge a `base` i testi di `extra` non già presenti (per firma)."""
    seen = {_text_signature(t) for t in base}
    for text in extra:
        sig = _text_signature(text)
        if sig not in seen:
            seen.add(sig)
            base.append(text)


# Tipi che topo sa ri-materializzare in to_dxf(): geometria di taglio +
# testi. Tutto il resto viene perso nel write-back.
_ROUNDTRIP_TYPES = frozenset({
    "LINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE", "LWPOLYLINE", "POLYLINE",
    "POINT", "TEXT", "MTEXT", "DIMENSION", "LEADER", "MULTILEADER", "INSERT",
})


def _warn_non_roundtrip_types(msp, sink: list, verbose: bool = False) -> None:
    """Avvisa sui tipi di entità che to_dxf() non riscrive (HATCH, IMAGE, …)."""
    lost = sorted({
        e.dxftype() for e in msp if e.dxftype() not in _ROUNDTRIP_TYPES
    })
    if lost:
        _emit(sink, Diagnostic(
            "dxf-not-modeled", f"entity types topo does not model, not written back by to_dxf(): {', '.join(lost)}",
            notes=["their geometry is not in the Document"]), verbose)


def _emit(sink: list, msg: str, verbose: bool = False) -> None:
    """Aggiunge `msg` (un `Diagnostic`) al canale `sink`; lo stampa solo se verbose."""
    if sink is not None:
        sink.append(msg)
    if verbose:
        print(f"[loader] {msg}")


def _configure_odafc(sink: list = None, verbose: bool = False) -> None:
    """
    Punta l'addon `odafc` all'eseguibile ODA File Converter.

    Ordine di ricerca:
      1. variabile d'ambiente ODA_PATH (full path dell'eseguibile)
      2. `ODAFileConverter` nel PATH di sistema (odafc lo trova da solo)

    Raises:
        EnvironmentError: ODA_PATH non settato E nessun ODAFileConverter nel PATH.
                          Il messaggio include link di download e guida alle
                          variabili d'ambiente per SO.
    """
    # su Windows odafc usa "win_exec_path", su Linux/macOS "unix_exec_path"
    opt_key = "win_exec_path" if sys.platform == "win32" else "unix_exec_path"

    if ODA_PATH:
        if os.path.isfile(ODA_PATH):
            ezdxf.options.set("odafc-addon", opt_key, ODA_PATH)
            return
        _emit(sink, Diagnostic(
            "dxf-oda-path", f"ODA_PATH is set but is not a file: {ODA_PATH!r}; looking for ODAFileConverter on PATH",
            help="point ODA_PATH at the ODAFileConverter executable"), verbose)

    if shutil.which("ODAFileConverter"):
        return  # odafc lo troverà da solo

    raise EnvironmentError(
        "Cannot open the DWG: ODA File Converter not found.\n"
        "topo (like ezdxf) converts DWG files through ODA File Converter.\n\n"
        f"1. Download it (free) from: {ODA_DOWNLOAD_URL}\n"
        f"2. {_ENV_VAR_HELP}\n\n"
        "Note: if ODA is installed in a folder named after its version "
        "(e.g. 'ODAFileConverter X.Y.Z'), ODA_PATH must be the full path of "
        "the executable, not of the folder."
    )


def _read_dwg(path: str, sink: list = None, verbose: bool = False, notes: list = None):
    """
    Legge un file DWG usando ezdxf.addons.odafc (wrapper di ODA File Converter).

    Raises:
        EnvironmentError: ODA File Converter non trovato (vedi `_configure_odafc`)
        RuntimeError: la conversione DWG→DXF è fallita
    """
    from ezdxf.addons import odafc

    with open(path, 'rb') as f:
        version_code = f.read(6).decode('ascii', errors='ignore')
    version_name = DWG_VERSIONS.get(version_code, version_code)
    _emit(notes, Diagnostic("dxf-dwg-converted", f"DWG {version_name} ({version_code}) converted through odafc",
                            level="note"), verbose)

    _configure_odafc(sink=sink, verbose=verbose)

    try:
        doc = odafc.readfile(path)
    except Exception as ex:
        raise RuntimeError(
            f"DWG conversion failed ({type(ex).__name__}: {ex}).\n"
            f"If the message says 'ODAFileConverter not installed', "
            f"download it from {ODA_DOWNLOAD_URL} and set ODA_PATH.\n{_ENV_VAR_HELP}"
        )

    return doc

# ---------------------------------------------------------------------------
# Upgrade R12 → R2010
# ---------------------------------------------------------------------------

def _upgrade_to_r2010(doc, sink: list = None, verbose: bool = False, notes: list = None) -> object:
    """
    Converte un documento DXF legacy in R2010.
    Esplode INSERT e POLYLINE in place, poi copia tutto nel nuovo doc.
    Funzione privata — chiamata da load_dxf.
    """
    if doc.dxfversion >= 'AC1015':
        return doc

    _emit(notes, Diagnostic("dxf-upgraded", f"legacy file {doc.dxfversion} upgraded to R2010", level="note"),
          verbose)
    failed = []

    new_doc = ezdxf.new('R2010')
    new_msp = new_doc.modelspace()
    old_msp = doc.modelspace()

    for entity in list(old_msp.query('INSERT')):
        try:
            entity.explode()
        except Exception as ex:
            failed.append(f"INSERT: {ex}")

    for entity in list(old_msp.query('POLYLINE')):
        try:
            entity.explode()
        except Exception as ex:
            failed.append(f"POLYLINE: {ex}")
    if failed:
        _emit(sink, Diagnostic("dxf-explode-failed", f"{len(failed)} entities could not be exploded in the upgrade",
                               notes=failed[:5]), verbose)

    for entity in old_msp:
        # Le entità devono essere copiate nel nuovo documento: non è lecito
        # trasferire un'entità da un DXF all'altro tramite add_entity().
        new_msp.add_entity(entity.copy())

    return new_doc


# ---------------------------------------------------------------------------
# Entry point pubblico
# ---------------------------------------------------------------------------

def load_dxf(
    path: str,
    *,
    upgrade: bool = False,
    explode_inserts: bool = True,
    flatten_z: bool = True,
    verbose: bool = False,
    tolerance: float = DEFAULT_NODE_TOLERANCE,
    role_rules: Sequence[RoleRule] = (),
    skip_layers: Union[Sequence[str], Callable[[str], bool]] = SKIP_LAYERS,
) -> Document:
    """
    Apre un documento DXF o DWG e lo traduce in un Document.

    Sequenza:
        1. se DWG → conversione via odafc (ODA File Converter)
        2. readfile
        3. audit (stampa solo se ci sono errori)
        4. upgrade R2010 se necessario o richiesto
        5. explode INSERT se richiesto
        6. sanitize (normalize_ocs + flatten_z)
        7. traduzione: DxfAdapter.to_edges() + DxfTextExtractor.extract()

    Args:
        path:            percorso del file .dxf o .dwg
        upgrade:         se True, forza upgrade a R2010
        explode_inserts: se True (default), esplode gli INSERT in entità
                         primitive. Passa False solo se vuoi ignorare i blocchi
                         di proposito: un INSERT non esploso viene scartato e la
                         sua geometria sparisce dall'output.
        flatten_z:       se True (default), riporta sul piano le entità con Z != 0
        verbose:         se True, stampa dettaglio entità in sanitize
        tolerance:       tolleranza di arrotondamento dei nodi topologici;
                         viene ripresa da heal() se non specificata lì
        role_rules:      regole del chiamante che assegnano il ruolo agli
                         Edge in fase di traduzione (RoleRule, D63); il nome
                         valutato da `name`/`name_contains` è il layer
        skip_layers:     layer la cui geometria si salta (D176): nomi esatti,
                         senza distinguere maiuscole, oppure una funzione
                         `nome -> bool` (una parte del nome, una regex,
                         quello che serve). Di default `SKIP_LAYERS`, quelli
                         che il writer usa per `loose` e testi, così un file
                         scritto da topo si rilegge pulito; `()` legge tutto

    Returns:
        Document (edges + texts + source_meta + warnings) — pronto
        per heal(). Quello che va guardato sul file grezzo (audit, INSERT
        non esplosi, tipi non modellati) finisce in `doc.warnings`, quello che
        l'adapter ha fatto da sé (INSERT esplosi, duplicati tolti, Z sul
        piano) in `doc.notes`, tutti `Diagnostic` (D233); con verbose=True
        anche stampati. `topo.validate_document(doc)` li rilancia.
    """
    warnings: list = []
    notes: list = []

    if str(path).lower().endswith('.dwg'):
        doc = _read_dwg(path, sink=warnings, verbose=verbose, notes=notes)
    else:
        doc = ezdxf.readfile(path)

    if upgrade or doc.dxfversion < 'AC1015':
        doc = _upgrade_to_r2010(doc, sink=warnings, verbose=verbose, notes=notes)

    # I testi vanno estratti PRIMA di doc.audit(): l'auditor di ezdxf
    # cancella le DIMENSION che referenziano un blocco geometria non definito
    # (dims salvate senza pre-rendering) — sono comunque testi validi da
    # riportare in output. `_dimension_text()` / `virtual_entities()` non hanno
    # bisogno del documento auditato.
    texts = DxfTextExtractor(doc.modelspace(), role_rules).extract()

    auditor = doc.audit()
    if auditor.errors:
        _emit(warnings, Diagnostic(
            "dxf-audit", f"{len(auditor.errors)} problems found by the ezdxf audit",
            notes=[str(err) for err in auditor.errors[:5]]), verbose)

    msp = doc.modelspace()

    inserts_found = list(msp.query("INSERT"))
    if inserts_found:
        if explode_inserts:
            n = _explode_inserts(msp, sink=warnings)
            if n:
                _emit(notes, Diagnostic("dxf-inserts-exploded", f"{n} INSERT exploded into their entities",
                                        level="note"), verbose)
        else:
            _emit(warnings, Diagnostic(
                "dxf-inserts-ignored", f"{len(inserts_found)} INSERT not exploded, their geometry ignored",
                points=[tuple(i.dxf.insert)[:2] for i in inserts_found],
                help="topo_dxf.load_dxf(path, explode_inserts=True) reads them"), verbose)

    n = _explode_hatches(msp, sink=warnings)
    if n:
        _emit(notes, Diagnostic("dxf-hatches-exploded", f"{n} HATCH exploded into their pattern lines (D205)",
                                level="note"), verbose)

    removed = deduplicate(msp)
    if removed > 0:
        _emit(notes, Diagnostic("dxf-duplicates-removed", f"{removed} duplicate entities removed", level="note"),
              verbose)

    flattened = sanitize(msp, flatten_z_flag=flatten_z, verbose=verbose)
    if flattened:
        _emit(notes, Diagnostic("dxf-flattened", f"{flattened} entities with Z != 0 brought onto the plane",
                                level="note"), verbose)

    adapter = DxfAdapter(msp, role_rules=role_rules, skip_layers=skip_layers)
    edges = adapter.to_edges()
    for msg in adapter.warnings:
        _emit(warnings, msg, verbose)

    # Dopo explode possono affiorare TEXT/MTEXT che stavano dentro i blocchi:
    # le aggiungiamo a quelle catturate pre-audit, senza duplicare.
    if inserts_found and explode_inserts:
        _merge_texts(texts, DxfTextExtractor(msp, role_rules).extract())

    _warn_non_roundtrip_types(msp, warnings, verbose)

    meta = {
        "$INSUNITS":     doc.header.get("$INSUNITS", 4),
        "$MEASUREMENT":  doc.header.get("$MEASUREMENT", 1),
        "tolerance":     tolerance,
    }

    return Document(
        edges=edges,
        texts=texts,
        source_meta=meta,
        source_path=str(path),
        source_format="dwg" if str(path).lower().endswith(".dwg") else "dxf",
        warnings=warnings,
        notes=notes,
    )


def document_from_msp(
    msp,
    *,
    tolerance: float = DEFAULT_NODE_TOLERANCE,
    role_rules: Sequence[RoleRule] = (),
    source_path: str = "",
    skip_layers: Union[Sequence[str], Callable[[str], bool]] = SKIP_LAYERS,
) -> Document:
    """
    Costruisce un Document da un modelspace ezdxf già aperto.

    Utile quando il msp non viene da un file (test, geometria generata a mano)
    o è già stato preparato altrove. Non fa audit/upgrade/sanitize: si assume
    che il msp sia già pronto.

    `role_rules`, `skip_layers`: vedi `load_dxf()`.
    """
    adapter = DxfAdapter(msp, role_rules=role_rules, skip_layers=skip_layers)
    edges = adapter.to_edges()
    texts = DxfTextExtractor(msp, role_rules).extract()

    header = getattr(getattr(msp, "doc", None), "header", None)
    meta = {
        "$INSUNITS":     header.get("$INSUNITS", 4) if header else 4,
        "$MEASUREMENT":  header.get("$MEASUREMENT", 1) if header else 1,
        "tolerance":     tolerance,
    }
    return Document(
        edges=edges, texts=texts,
        source_meta=meta, source_path=source_path, source_format="dxf",
        warnings=list(adapter.warnings),
    )






