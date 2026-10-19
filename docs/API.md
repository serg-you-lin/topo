# topo — riferimento API

Una distribuzione (`g-topo`), tre pacchetti (MAP.md D123, D124, D129):
`topo`, il motore, che non conosce alcun formato di file; `topo_dxf`, l'adapter
DXF (`pip install g-topo[dxf]`); `topo_pdf`, l'adapter PDF sperimentale
(`g-topo[pdf]`). I moduli interni non si importano direttamente. Questo
documento copre ogni nome esportato in `topo.__all__` (§1–§8),
`topo_dxf.__all__` (§9) e `topo_pdf.__all__` (§10).

Convenzioni di questo documento:

- **firma** — parametri e default reali
- **prende / ritorna** — i tipi
- **muta** — se modifica qualcosa in-place (importante: diversi stadi di
  elaborazione lavorano per effetto collaterale)
- **solleva** — le eccezioni che il chiamante deve prevedere

I tipi di dominio (`Document`, `Result`, `Cluster`, …) sono descritti
in fondo.

**Come si scrive una chiamata.** `import topo` (e `import topo_dxf` se leggi o
scrivi DXF), poi ogni nome con il suo percorso intero: `topo.heal(...)`,
`topo_dxf.load_dxf(...)`, `topo.Result`,
`topo.geometry.contour_shape(...)`, `topo.steps.find_loops(...)`. Mai
`from topo.steps import find_loops` o `from topo import steps`: un nome letto
da solo a metà di uno script non dice di chi è, `topo.steps.find_loops` sì.
Tutti gli esempi di questo documento sono scritti così (MAP.md D119).

---

## Indice

1. [Geometria in ingresso](#1-geometria-in-ingresso) — `load_segments`, `load_geometry`, `RoleRule`, `name_rules`, scrivere un adapter
2. [Validazione](#2-validazione) — `validate`, `validate_result`
3. [Elaborazione](#3-elaborazione) — `heal` / `island` e i suoi mattoni (core), `split`, `anchor_annotations` / `inject` (tools)
4. [Export](#4-export) — `save_json`, `to_json`, `save_xml`, `to_view_model`, `to_svg`, `save_svg`
5. [Metadati](#5-metadati) — `build_metadata`, `set_schema`
6. [Ispezione / debug](#6-ispezione--debug) — `inspect_document`, `inspect_result`
7. [Tipi di dominio](#7-tipi-di-dominio)
8. [Il flusso completo, in ordine](#8-il-flusso-completo-in-ordine)
9. [`topo_dxf` — l'adapter DXF](#9-topo_dxf--ladapter-dxf) — `load_dxf`, `document_from_msp`, `to_dxf`, `split_to_files`, XDATA, `inspect_dxf` / `inspect_file`, i layer di default
10. [`topo_pdf` — l'adapter PDF](#10-topo_pdf--ladapter-pdf) — `load_pdf` (sperimentale)

---

## 1. Geometria in ingresso

topo non apre file: un file entra da un adapter (`topo_dxf.load_dxf`, §9;
`topo_pdf.load_pdf`, §10), la geometria che hai già in mano da qui. Le
regole di ruolo (`RoleRule`, `name_rules`) sono di topo e ogni adapter le
applica.

### `RoleRule`

```python
topo.RoleRule(role, name=None, name_contains=None, dashed=None, dash=None, color=None)
```

Una regola: se **tutte** le condizioni date sono vere, la linea prende `role`.
topo fornisce il meccanismo; il contenuto (quali nomi, quali stili, quale
ruolo) lo scrive il chiamante (MAP.md D63).

| campo | significato |
|---|---|
| `role` | ruolo assegnato, ripulito da `normalize_role`. Vocabolario aperto: topo conosce solo `outer`, `inner`, `unknown`; `hole`, `bending`, `engrave`, … sono di snapbend (MAP.md D88); qualunque altro slug (`frame`, `title_block`, …) è conservato, trattato come non strutturale e scritto in output su un layer col suo nome (MAP.md D27 / D31). |
| `name` | nome del gruppo sorgente, uguale (maiuscole ignorate). |
| `name_contains` | sottostringa del nome del gruppo (maiuscole ignorate). |
| `dashed` | `True` solo tratteggiate, `False` solo continue. Tratteggiata = il pattern del linetype ha almeno un vuoto (`EdgeStyle.is_dashed`), non il nome del linetype. Vale anche per le catene. |
| `dash` | forma del tratto (`EdgeStyle.dash_kind`), letta dai segni del pattern: `"continuous"` nessun vuoto; `"uniform"` un solo segno ripetuto (tratti tutti uguali, o solo punti); `"chain"` segni diversi alternati (tratto lungo + tratto corto o punto). Due segni sono diversi se differiscono più del 5% della lunghezza del pattern. Valore sconosciuto → `ValueError`. |
| `color` | colore effettivo in RGB: `(r, g, b)`, `"#rrggbb"` o un nome di base (`red`, `yellow`, `green`, `cyan`, `blue`, `magenta`, `white`, `black`, `gray`/`grey`, `lightgray`/`lightgrey`, `pink`). Ogni adapter legge il colore della sorgente in RGB: per un DXF un indice ACI diventa il suo RGB canonico (il 7 è bianco) (MAP.md D126). Un intero è un errore. |

Metodo `matches(name, style) -> bool`. Condizioni lasciate a `None` non
contano.

**Solleva** `ValueError` se non c'è nessuna condizione (matcherebbe tutto), se
il nome del colore non è riconosciuto o se `dash` non è una delle tre forme.

```python
rules = [
    topo.RoleRule("bending", name="Piega"),         # una piega a catena resta piega
    topo.RoleRule("construction", dash="chain"),    # assi e linee di costruzione
]
```

### `name_rules`

```python
topo.name_rules(mapping: dict[str, str]) -> list[RoleRule]
```

Scorciatoia: `{nome: ruolo}` → una `RoleRule(role, name=nome)` per voce, nello
stesso ordine.

```python
rules = topo.name_rules({"Piega": "bending", "MARK": "engrave"})
rules.append(topo.RoleRule("bending", dashed=True))   # dopo i nomi
```

### `load_segments`

```python
topo.load_segments(segments, tolerance=0.05, role="unknown", source_path="") -> Document
```

Un `Document` da segmenti di topo (`LineSeg`, `ArcSeg`, `CircleSeg`, …) o
da liste di segmenti — quelle che restituiscono i costruttori di
`topo.geometry`. Tutti gli edge prendono `role`. È il modo per disegnare con
topo in mano; `load_geometry` resta per chi non importa topo (D96).

```python
fg = topo.geometry
doc = topo.load_segments(fg.rectangle(200, 100) + fg.rectangle(100, 50))
result = topo.heal(doc)     # un pezzo: outer 200×100, un inner 100×50
```

---

### `load_geometry`

```python
topo.load_geometry(
    entities,
    tolerance=0.05,
    source_path="",
) -> Document
```

Costruisce un `Document` da geometria pura — dict Python, non un file.
Stesso contratto di ritorno di `topo_dxf.load_dxf`, ma la sorgente è
chi chiama: un generatore parametrico (uno sviluppo cono/cilindro calcolato
altrove) o un ricostruttore di contorni da punti (una traccia vettorializzata da
computer vision). Chi chiama non importa nessun tipo interno di topo.

| parametro | significato |
|---|---|
| `entities` | lista di dict, uno per entità geometrica. `type` supportati: `line` (`start`, `end`), `arc` (`center`, `radius`, `start_angle`/`end_angle` **in gradi**, `ccw`), `circle` (`center`, `radius`), `polygon` (`points` — sempre chiuso, D96), `spline` (`control_points`, `knots`, `degree`, più `weights`/`fit_points`/`closed` opzionali — stessi campi di `SplineSeg`), `ellipse` (`center`, `major_axis` come **vettore** dal centro, più `ratio`/`start_param`/`end_param`/`ccw` opzionali — stessi campi di `EllipseSeg`, stessa parametrizzazione del gruppo DXF ELLIPSE; default = ellisse piena). `role` è opzionale su ogni entità — stesso vocabolario di `RoleRule.role` (`outer`, `hole`, `bending`, …); un valore diverso è conservato come slug di consumatore, non un errore. |
| `tolerance` | tolleranza di arrotondamento dei nodi topologici — stesso significato di `topo_dxf.load_dxf(tolerance=...)`. |
| `source_path` | etichetta libera per `Document.source_path`; non è un file, serve solo per diagnostica. |

```python
doc = topo.load_geometry([
    {"type": "arc",  "center": (0, 0), "radius": 50,
     "start_angle": -30, "end_angle": 30, "role": "outer"},
    {"type": "line", "start": (43.3, -25.0), "end": (34.6, -20.0), "role": "outer"},
    {"type": "arc",  "center": (0, 0), "radius": 40,
     "start_angle": -30, "end_angle": 30, "role": "outer"},
    {"type": "line", "start": (34.6, 20.0), "end": (43.3, 25.0), "role": "outer"},
])
result = topo.heal(doc, label="sviluppo_cono")
topo_dxf.to_dxf(result)
```

```python
# entità "spline" — i campi sono quelli di SplineSeg, presi 1:1
segments = topo.simplify_points(points, closed=True)
doc = topo.load_geometry([
    {
        "type": "spline",
        "control_points": seg.control_points,
        "knots": seg.knots,
        "degree": seg.degree,
        "fit_points": seg.fit_points,
        "closed": seg.closed,
        "role": "outer",
    }
    for seg in segments
])
```

Provato da un caso reale (`snapbend`, ex bendly, che lo usa per portare gli sviluppi che
genera a `Document` senza passare da un file — vedi MAP.md D32; il tipo
`spline` viene da `smoother`, che vi passa l'output di `simplify_points()` —
vedi MAP.md D35). Il tipo `ellipse` (MAP.md D45) esiste perché `EllipseSeg`
è una primitiva di topo come le altre — non serve un caso reale a parte,
segue lo stesso schema di `spline`/`circle`.

### Scrivere un adapter

Un adapter (DXF, PDF, un formato tuo) è un consumer di topo come un altro: usa
solo nomi pubblici e consegna un `Document` (MAP.md D125). `topo_dxf` e
`topo_pdf` sono scritti così, e il controllo dell'indice lo fa rispettare:
non importano `topo.core`/`tools`/`io`/`rules` (D129). Quello che gli serve:

| nome | a cosa serve |
|---|---|
| `topo.primitives.LineSeg` … `EllipseSeg` | la geometria letta dalla sorgente, nativa (mai discretizzata dall'adapter) |
| `topo.model.Edge.of(segment, role, style=None) -> Edge` | l'`Edge` di un segmento: estremi sulla griglia dei nodi di topo (D113), che l'adapter non deve conoscere; un cerchio, una spline o un'ellisse chiusi hanno un nodo solo |
| `topo.model.EdgeStyle(linetype="", linetype_desc="", dash=None, color=None)` | l'aspetto effettivo dell'entità sorgente, senza parole di un formato (D126): `dash` sono segni con segno (`> 0` tratto, `0` punto, `< 0` vuoto; `()` continuo, `None` non noto — un dash-array `[3, 1]` è `(3, -1)`), `color` è `(r, g, b)`. L'adapter risolve l'ereditarietà (uno stile "del layer") prima di consegnarlo |
| `topo.model.RoleRule`, `topo.model.resolve_role(rules, name, style) -> str` | il ruolo di un'entità dalle regole del chiamante: la prima che matcha, altrimenti `unknown` |
| `topo.model.Document`, `topo.model.DEFAULT_NODE_TOLERANCE` | il risultato dell'adapter e la tolleranza di default che `heal()` chiuderà |
| `topo.model.Annotation`, `Note`, `Dimension`, `Leader`, `RenderedGeometry`, `RenderedText` | le annotazioni lette dalla sorgente, ognuna col suo `role` (D127; il gruppo sorgente non resta nel modello, D128) |

Per riscrivere in un formato: `topo.primitives.segment_endpoints(segment)` dà i
due estremi di un segmento, `topo.model.feature_role(contour, item_role)` il
ruolo con cui si disegna un contorno di un elemento rilevato,
`topo.model.role_style(role, role_styles)` come si disegna: la palette di
topo con sopra la mappa del chiamante (D128). Un exporter non sceglie colori,
traduce quello che `role_style` gli dà nella codifica del suo formato.

```python
edges = [topo.model.Edge.of(seg, topo.model.resolve_role(rules, name, style), style)
         for seg, name, style in read_my_format(path)]
doc = topo.model.Document(edges=edges, source_path=str(path))
```

---

## 2. Validazione

### `validate`

```python
topo.validate(doc: Document) -> Result
```

Valida l'**input** prima di `heal()`. Non modifica niente. Ritorna un
`Result` con solo `warnings` / `errors` / `is_valid` (`clusters` vuoto).

- **`is_valid = False`** — il file non è lavorabile: nessuna geometria, coordinate
  NaN/inf, tutti i segmenti degeneri.
- **warning** — lavorabile ma da tenere d'occhio: `LINE`/`ARC` ancora fuori da un
  contorno chiuso, endpoint che non si toccano nemmeno alla tolleranza dichiarata,
  segmenti di lunghezza nulla. Include anche le `doc.warnings` del loader.

**Solleva** `TypeError` se non gli passi un `Document`.

```python
check = topo.validate(doc)
if not check.is_valid:
    raise SystemExit(check.errors)
for w in check.warnings:
    print("warn:", w)
```

### `validate_result`

```python
topo.validate_result(result: Result) -> Result
```

Valida l'**output** dopo `heal()`. **Muta** il `result` passato: aggiunge
`warnings` / `errors` e può mettere `is_valid = False`. Controlla, per ogni cluster:
poligono outer valido e non vuoto, area > 0, ogni inner contenuto nell'outer.

Viene **già chiamata automaticamente da `heal()`** — la usi a mano solo se
costruisci un `Result` per altre vie.

---

## 3. Elaborazione

`heal` e `island` sono le due letture del motore (`topo/core/`), una
dall'interno e una dall'esterno — il chiamante sceglie quella adatta al
disegno; `split`, `anchor_annotations` / `inject` sono stadi opzionali su un
`Result` (`topo/tools/`, il caller sceglie quali e in che ordine). Scrivere
in un formato è di un adapter: `topo_dxf.to_dxf` e `topo_dxf.split_to_files`
(§9); `to_svg`/`to_view_model`/`to_text` sono in §4. Fori, pieghe, incisioni sono
una lettura di processo, in snapbend (`snapbend.flat`, MAP.md D88). Tutto resta accessibile come `topo.<nome>`.

### `heal`

```python
topo.heal(doc: Document, tolerance=None, label="", source_file="",
           is_structural=None) -> Result
```

Il passo difficile: ricostruzione della topologia. Lavora su `doc.edges`, zero
`ezdxf`. Chiude i gap, esclude dal grafo gli edge che non chiudono un contorno
(candidati a "qualcos'altro" — `non_contour_candidates()` espone lo stesso
criterio a un consumatore, vedi sezione 8), trova i loop chiusi, costruisce
l'albero di contenimento outer / inner.

`heal()` **non classifica i fori** (D15): consegna solo `Cluster(outer,
inners=[Contour...])`. Chiamare foro un cerchio è una lettura di processo (snapbend, MAP.md D88).

| parametro | significato |
|---|---|
| `tolerance` | se `None`, ripresa da `doc.source_meta["tolerance"]` (quella passata a `topo_dxf.load_dxf`). |
| `label` | etichetta del pezzo, finisce in `cluster.label` e nei metadati. |
| `source_file` | nome file sorgente, finisce nei metadati. |
| `is_structural` | `Callable[[str], bool] \| None` — "questo ruolo è topologia di contorno di pezzo?", usato per decidere quali `Edge` già etichettati (da `role_rules`) restano nel grafo prima della ricerca loop. `heal()` da solo conosce solo `outer`/`inner`; senza questo parametro un ruolo di consumatore (`"hole"`, ...) è trattato come non strutturale ed **esce** dal grafo (heal lo segnala con un warning). Il consumatore passa il suo (snapbend: `snapbend.flat.is_structural`). |

`role_rules` **non è un parametro di `heal`** — va passato a `topo_dxf.load_dxf()`, che
assegna i ruoli agli `Edge`.

**Ritorna** un `Result`. Se non si forma nessun contorno esterno chiuso,
`result.is_valid` è `False` e `result.errors` è popolato (la `trash_entities`
resta piena per la diagnostica).

**Solleva** `TypeError` se non gli passi un `Document`.

```python
result = topo.heal(doc, tolerance=0.5, label="P-1024")
```

#### I passi di `heal()`

`heal()` è una ricetta: compone questi passi, nell'ordine sotto, e scrive i
warning che li raccontano. Esposti per chi compone la sua (snapdraw: per esempio
fermarsi prima di `build_hierarchy`, finché non ha deciso da sé cosa significa
un contorno dentro un altro — D62). Stessi pezzi di `heal()`, nessun criterio
duplicato.

```python
topo.steps.merge_collinear_overlaps(edges) -> list[Edge]
topo.steps.merge_cocircular_overlaps(edges) -> list[Edge]
topo.steps.weld_degenerate_linesegs(edges) -> list[Edge]
topo.steps.split_non_finite(edges) -> tuple[list[Edge], list[Edge]]
topo.steps.split_labeled(edges, is_structural=None) -> tuple[list[Edge], list[Edge]]
topo.steps.close_near_full_arcs(edges, tolerance, max_missing_angle=NEAR_FULL_ARC_MISSING)
    -> tuple[list[Edge], int]
topo.steps.close_free_gaps(edges, tolerance) -> list[Edge]
topo.steps.dangling_splines(edges) -> list[Edge]
topo.steps.find_non_contour_edges(edges, tolerance) -> set[int]
topo.steps.find_joining_edges(edges, candidate_ids) -> list[Edge]
topo.steps.free_ends(edges, epsilon=0.0) -> list[tuple[point, float]]
topo.steps.find_loops(edges, non_contour_ids, tolerance) -> LoopSearch
topo.steps.repair_merged_corners(edges, tolerance, exclude_ids=frozenset()) -> tuple[list[Edge], int, list]
topo.steps.structural_loops(loops, is_structural=None) -> list[loop]
topo.steps.loops_to_curves(loops) -> list[ClosedCurve]
topo.steps.polygonize_edges(edges, tolerance) -> list[Polygon]
topo.steps.polygons_to_curves(polygons) -> list[ClosedCurve]
topo.steps.edges_to_open_curves(edges, exclude_ids) -> list[OpenCurve | ClosedCurve]
topo.steps.labeled_curves(edges) -> list[OpenCurve | ClosedCurve]
topo.steps.build_hierarchy(features, label="", source_file="", is_structural=None)
    -> tuple[list[Cluster], list]
```

| passo | prende → ritorna | cosa fa |
|---|---|---|
| `split_non_finite` | `list[Edge]` → `(finiti, non finiti)` | mette da parte gli edge con una coordinata NaN/inf: heal() li conta in `errors` e il risultato non è valido (D111). |
| `merge_collinear_overlaps` | `list[Edge]` → `list[Edge]` | fonde le rette tracciate a spezzoni sovrapposti (D50). |
| `merge_cocircular_overlaps` | `list[Edge]` → `list[Edge]` | lo stesso sugli archi co-circolari (D52). |
| `weld_degenerate_linesegs` | `list[Edge]` → `list[Edge]` | salda i `LineSeg` sotto 0.05 mm in un nodo solo (D56). |
| `split_labeled` | `list[Edge]` → `(restano, etichettati)` | mette da parte gli edge con un ruolo già deciso e non strutturale (D30). Senza `is_structural`, solo `outer`/`inner` sono strutturali. |
| `close_near_full_arcs` | `list[Edge]` → `(edge, n_chiusi)` | un `ArcSeg` coi capi liberi diventa `CircleSeg` solo se il gap fra i capi è entro `tolerance` **e** l'angolo mancante è entro `max_missing_angle` (`NEAR_FULL_ARC_MISSING` = 2°): la tolleranza dice se il buco è un gap, l'angolo se l'arco è un cerchio. `tolerance=math.inf` lascia solo l'angolo, per chi conosce il suo CAD (D112). |
| `close_free_gaps` | `list[Edge]` → `list[Edge]` | chiude i gap fra estremi liberi entro `tolerance` (estensione all'intersezione reale o linea di congiunzione), accoppiati due a due per vicinanza: ogni estremo chiude al più un gap, col più vicino ancora libero, e mai con l'altro capo dello stesso edge. Un lato più corto della tolleranza resta (D112). |
| `dangling_splines` | `list[Edge]` → `list[Edge]` | le `SplineSeg` aperte con un estremo non collegato — solo diagnostica. |
| `find_non_contour_edges` | `list[Edge]` → `set[id(Edge)]` | edge che non chiudono un contorno (corde e ponti: catene fra due nodi di branching distinti, non sul bordo della faccia esterna, D111, D131), da tenere fuori dal grafo. `non_contour_candidates(doc)` è la stessa cosa su un documento. |
| `find_joining_edges` | `list[Edge]`, `set[id]` → `list[Edge]` | fra i candidati, gli edge che uniscono due forme altrimenti staccate (tolti, i due estremi non si collegano più): heal() li segnala in un warning (D111). |
| `free_ends` | `list[Edge]`, `epsilon` → `[(punto, mm)]` | gli estremi che nessun altro edge tocca, con la distanza dal nodo più vicino, dal più vicino; `epsilon` è quello del grafo su cui si sono chiusi i loop. heal() li segnala anche quando qualcosa si chiude (D111). |
| `find_loops` | `list[Edge]` → `LoopSearch` | la scala: grafo esatto → riparazione angoli se restano estremi liberi (D57) → grafo tollerante, dove un edge i cui due capi si fondono resta fuori dal giro (D112). |
| `repair_merged_corners` | `list[Edge]` → `(edge, n_riparati, cluster_saltati)` | il secondo gradino da solo: angoli fusi dal clustering portati all'intersezione reale; cluster di 3+ estremi saltati. |
| `structural_loops` | loop → loop | tiene i loop senza edge di ruolo non strutturale. |
| `loops_to_curves` | loop → `list[ClosedCurve]` | un `ClosedCurve` per loop, geometria nativa. |
| `polygonize_edges` | `list[Edge]` → `list[Polygon]` | ultima spiaggia quando `find_loops` non chiude: le facce dell'intero disegno discretizzato. |
| `polygons_to_curves` | `list[Polygon]` → `list[ClosedCurve]` | OUTER dal bordo, INNER dai buchi, a `LineSeg` (la geometria nativa è persa). |
| `edges_to_open_curves` | `list[Edge]` → feature | gli edge non assorbiti da un loop (`exclude_ids`) come feature aperte. |
| `labeled_curves` | `list[Edge]` → feature | gli etichettati di `split_labeled`, col ruolo intatto. |
| `build_hierarchy` | feature → `(cluster, trash)` | albero di contenimento: ogni radice un `Cluster`, i discendenti `inners` con `depth`/`parent`. |

Nessuno **muta** l'input: ritornano liste/oggetti nuovi.

`LoopSearch` — come `find_loops` ha chiuso (o non chiuso) i giri:

| campo | tipo | significato |
|---|---|---|
| `edges` | `list[Edge]` | gli edge dopo l'eventuale riparazione degli angoli — da usare a valle al posto di quelli in ingresso |
| `loops` | `list[loop]` | loop `[(Edge, reversed)]`, vuota se nessun gradino chiude |
| `method` | `str` | `"exact"`, `"corner_repair"`, `"tolerant"` o `"none"` |
| `repaired` | `int` | angoli chiusi all'intersezione reale |
| `skipped_corners` | `list` | cluster non riparati (3+ estremi) |
| `unrepaired_corners` | `list` | con `"tolerant"`: angoli fusi solo nel grafo, la discrepanza resta nell'output |
| `open_nodes` | `list` | con `"none"`: gli estremi liberi |

```python
# la ricetta di heal() fino ai contorni chiusi, senza gerarchia
edges, labeled = topo.steps.split_labeled(doc.edges, is_structural)
edges = topo.steps.close_free_gaps(edges, 0.1)
search = topo.steps.find_loops(edges, topo.steps.find_non_contour_edges(edges, 0.1), 0.1)
print(search.method, len(search.loops))
closed = topo.steps.loops_to_curves(topo.steps.structural_loops(search.loops, is_structural))
```

---

### `island`

```python
topo.island(doc: Document, *, max_gap: float,
             tolerance=None, is_structural=None) -> Result
```

La seconda lettura di un documento, accanto a `heal()`: **per isole**.
`heal()` ricostruisce la topologia dall'interno (chi tocca chi, quali giri si
chiudono, chi sta dentro chi) e trova il pezzo per contenimento. `island()`
legge il disegno dall'esterno:

1. separa i **pezzi**: gli edge che si toccano, entro `max_gap` (`spatial_islands`);
2. per ogni pezzo normalizza (tassellature rifittate come archi/spline,
   merge/weld di `heal`, gap fino a `max_gap`) e rende la rete **piana**
   (`split_at_crossings`);
3. il **contorno esterno** è il bordo della faccia esterna della rete
   (`outer_face`) — gli edge percorsi andata e ritorno (assi, segni che
   sporgono) non sono contorno;
4. ogni contorno esterno che non sta dentro un altro è un'**isola** (un
   cluster); un pezzo che sta dentro un'isola, col suo contorno o senza, è
   suo per contenimento (D99);
5. dentro: i giri chiusi diventano `inners`, il resto va in `trash_entities`
   col ruolo che aveva (`unknown` se nessuno l'ha deciso) e con `cluster_ref`,
   l'indice dell'isola che lo contiene o che tocca (`None` fuori da tutte).

**Quando usarla invece di `heal()`**: disegni di viste — più viste su un
foglio, viste isometriche/3D proiettate, sagome con linee quasi coincidenti
dove il grafo di `heal()` è ambiguo. Per un disegno di sagome piane (uno o più
pezzi separati, geometria esatta da cucire) resta `heal()`.

Un pezzo il cui contorno sta **dentro** quello di un altro non è un cluster:
diventa interno (`inners`) dell'isola più esterna che lo contiene. Due
contorni esterni sono due isole per quanto siano vicini: non c'è una distanza
fra le viste (D99). Con la
cornice nel disegno, quindi, l'unico cluster è la cornice: toglierla (o dare un
ruolo a cornice, cartiglio, cerchi di ingrandimento) è compito del chiamante.
Cosa sia un cluster — vista, pezzo — lo decide chi lo usa (D21).

| parametro | significato |
|---|---|
| `max_gap` | **obbligatorio**, per nome. Due edge più vicini di così (mm) si toccano; gap chiusi fra estremi liberi, mai spostando un estremo più di così. Nessun default (D98). |
| `tolerance` | se `None`, ripresa da `doc.source_meta["tolerance"]` — come `heal()`. |
| `is_structural` | come in `heal()` (D30): un `Edge` con un ruolo già deciso e non strutturale (`frame`, `title_block`, ...) resta **fuori** dalla lettura e va in `trash_entities` col suo ruolo. È così che un consumatore toglie cornice e cartiglio prima di leggere le viste. Senza, solo `outer`/`inner` sono strutturali. |

**Ritorna** un `Result` con un `Cluster` per isola,
ordinati per area del contorno esterno. Nessun giro chiuso in nessuna isola →
`is_valid=False`, `errors` popolato.

**Solleva** `TypeError` se non gli passi un `Document`, o se manca
`max_gap`.

```python
doc = topo_dxf.load_dxf("tavola.dxf")
result = topo.island(doc, max_gap=0.5)
for cluster in result.clusters:          # una vista / un pezzo per cluster
    print(cluster.outer.polygon.area, len(cluster.inners))
```

#### I mattoni di `island()`

Esposti per chi compone la sua ricetta (snapdraw: togliere cornice e cartiglio
per ruolo, poi leggere le viste) — stessi pezzi, nessun criterio duplicato.

```python
topo.read_islands(edges, tolerance, max_gap) -> list[IslandReading]
topo.read_island(edges, tolerance, max_gap) -> IslandReading
topo.steps.spatial_islands(edges, gap_tolerance) -> list[Island]
topo.steps.split_at_crossings(edges, tolerance, decimals=3) -> NodedEdges
topo.steps.outer_face(edges, epsilon=0.0) -> OuterFace | None
topo.steps.refit_tessellations(edges, max_segment=0.1, min_run=10,
                          arc_fit_tolerance=0.02, node_decimals=3) -> list[Edge]
```

| funzione | prende → ritorna | cosa fa |
|---|---|---|
| `read_islands` | `list[Edge]` → `list[IslandReading]` | pezzi a contatto + `read_island` per ognuno + annidamento (`nested_in`, anche per un pezzo senza contorno tutto dentro un'isola). È `island()` prima di diventare `Result`. |
| `read_island` | `list[Edge]` → `IslandReading` | un'isola: normalizza, rete piana, faccia esterna, classificazione dell'interno. |
| `spatial_islands` | `list[Edge]` → `list[Island]` | union-find sulle coppie di edge a distanza vera `<= gap_tolerance` (STRtree). Nessuna nozione di chiusura. |
| `split_at_crossings` | `list[Edge]` → `NodedEdges` | spezza `LineSeg`/`ArcSeg`/`CircleSeg` dove incrociano o toccano a T un altro edge, entro `tolerance`; due tagli entro `tolerance` l'uno dall'altro sono lo stesso nodo, non due (D101 — una quasi-tangenza incrocia in due radici matematicamente distinte ma vicinissime). `NodedEdges.parent_of(pezzo)` dà l'`Edge` originale. `SplineSeg`/`EllipseSeg` restano interi. |
| `outer_face` | `list[Edge]` (rete piana) → `OuterFace \| None` | bordo della faccia esterna, per componente, quella di area massima; `spurs` = edge percorsi andata e ritorno. |
| `refit_tessellations` | `list[Edge]` → `list[Edge]` | catene di `LineSeg` corti (curva scritta a punti) rifittate come arco/cerchio/spline; estremi della catena sui nodi originali. |

Nessuna **muta** l'input: ritornano liste/oggetti nuovi.

`IslandReading` — cosa è stato deciso su un'isola, pezzo per pezzo:

| campo | tipo | significato |
|---|---|---|
| `edges` | `list[Edge]` | gli edge dell'isola, come arrivano |
| `outer` | `OuterFace \| None` | contorno esterno (`polygon`, `segments`, `edges`, `spurs`) |
| `inner_loops` | `list[loop]` | giri chiusi dentro, come dal `LoopFinder` |
| `spurs` | `list[Edge]` | percorsi andata e ritorno dal contorno |
| `outside` | `list[Edge]` | pezzi dell'isola rimasti fuori dal contorno (rete staccata) |
| `non_contour` | `list[Edge]` | candidati non-contorno, stesso criterio di `heal()` (D49) |
| `unclassified` | `list[Edge]` | il resto |
| `nested_in` | `int \| None` | indice dell'isola più esterna che la contiene |

---

## La geometria — `topo.geometry`

**Costruire** (`topo.geometry.<nome>`, restituiscono una lista di segmenti,
un giro chiuso, da passare a `topo.load_segments`). Gli argomenti sono le
misure che `contour_shape` restituisce, così `contour_shape(rectangle(80, 30,
angle=20))` ridà 80, 30, 20 (D96):

| costruttore | forma |
|---|---|
| `polygon(points)` | il poligono per i punti dati, chiuso da solo; almeno 3 punti |
| `rectangle(length, width, center=(0, 0), angle=0)` | rettangolo, lato lungo a `angle` gradi |
| `regular_polygon(sides, radius, center=(0, 0), angle=0)` | poligono regolare inscritto nel cerchio di raggio `radius`, primo vertice a `angle` |
| `circle(radius, center=(0, 0))` | un `CircleSeg` |
| `ellipse(length, width, center=(0, 0), angle=0)` | un `EllipseSeg` intero, assi `length` × `width` (`length` >= `width`), asse lungo a `angle` |
| `stadium(length, width, center=(0, 0), angle=0)` | due semicerchi veri (`ArcSeg`) e due lati paralleli; fuori tutto `length` × `width` |

Rombi, trapezi e ogni altra forma con lati dritti sono un `polygon`.

**Leggere**:

I fatti geometrici stanno tutti in `topo.geometry` (il package
`topo/core/geometry/`, D95) e si chiamano per intero,
`topo.geometry.<nome>(...)`, senza importare il nome da solo (D119). Nomi
geometrici: "cerchio", mai "foro". Le misure di base (lunghezza di un
segmento, tracce aperte, tratti sugli assi, intervalli) sono pubbliche dalla
D122; quello che resta nei sottomoduli di `topo.core.geometry` (arrotondamento
dei nodi, sequenze di punti, `circular_geometry`, …) è interno, senza
garanzie. L'elenco con `file:riga` è in `docs/INDEX.md`.

### `contour_shape`

```python
topo.geometry.contour_shape(item, tolerance=0.01, angle_tolerance=1.0) -> ContourShape | None
```

La forma di un contorno chiuso (`Contour`, un oggetto con `.segments`
o la lista dei segmenti): `circle`, `ellipse`, `stadium` (stadio: due
semicerchi uguali e due rette parallele — nome geometrico, non "asola"),
`rectangle`, `polygon` (solo rette), `other`. Fatto
geometrico, non feature: `circle` non vuol dire foro, lo decide chi legge il
disegno o il processo. Vale uguale su `heal` e su `island`. I segmenti
consecutivi sulla stessa retta o circonferenza sono ricomposti prima.
`tolerance` è una frazione della dimensione del contorno.

**Elenco chiuso e stabile** (D136): `kind` è un `ShapeKind` (`str`, quindi
`kind == "circle"` funziona) e nella 1.x non nascono altri kind né un
contorno cambia kind. Una forma ha un nome solo se centro, lunghezza,
larghezza e angolo la determinano; un rettangolo raccordato, un'asola ad arco,
un esagono sono `other` o `polygon`. Le regole leggono le primitive come sono:
un'ellisse ad assi uguali è un `circle` (stessi punti, esattamente), un
cerchio fatto di spline resta `other`.

`ContourShape`: `kind`, `center`, `length` (maggiore; cerchio: diametro;
ellisse: asse maggiore; stadio: fuori tutto), `width` (minore; ellisse: asse
minore; stadio: 2 × raggio), `angle` (gradi
[0, 180) dell'asse lungo, `None` per il cerchio), `sides` (segmenti dopo la
ricomposizione), `diameter` (solo cerchio), `.to_dict()`.

**Non muta** niente.

---

### `concentric_groups`

```python
topo.geometry.concentric_groups(items, tolerance=0.1) -> list[ConcentricGroup]
```

I contorni circolari di `items` (come per `contour_shape`) raggruppati per
centro: ogni cerchio sta in un solo gruppo, anche da solo; i non circolari non
compaiono. `tolerance` è la distanza massima fra i centri, in unità del
disegno. Fatto geometrico: due cerchi concentrici non sono una svasatura,
come accoppiarli lo decide il consumatore (D91).

`ConcentricGroup`: `center` (del cerchio più piccolo), `items` e `shapes`
(`ContourShape`) dal raggio minore al maggiore, `diameters`.

**Non muta** niente.

---

### `arcs_around`

```python
topo.geometry.arcs_around(center, radius, arcs, tolerance=0.1) -> list[ArcAround]
```

Gli `ArcSeg` di `arcs` concentrici al cerchio (`center`, `radius`) entro
`tolerance` e più grandi di lui, dal più vicino al più lontano. Nessuna soglia
sull'angolo: "~270°, poco più grande" è come si disegna una cresta di filetto,
lo applica il consumatore (D91).

`ArcAround`: `arc`, `sweep` (gradi, nel verso dell'arco), `radius_ratio`
(raggio dell'arco / `radius`).

**Non muta** niente.

---

### `splits_polygon`

```python
topo.geometry.splits_polygon(polygon, start, end, reach=0.0) -> bool
```

La corda `start`-`end`, prolungata di `reach` ai due capi, divide il poligono
(shapely) in due o più parti. Fatto geometrico: che quella corda sia una piega
lo decide il consumatore (snapbend la prolunga di 1 mm, D93).

**Non muta** niente.

---

### `bridged_runs`

```python
topo.geometry.bridged_runs(segments, bridges, tolerance=0.1, angle_tolerance=1e-6) -> list[CollinearRun]
```

File di due o più tratti sulla stessa retta in cui lo spazio fra un tratto e il
successivo sta tutto dentro uno dei poligoni di `bridges` (per esempio i vuoti
di un pezzo). Un tratto è una `LineString` o una coppia `(start, end)`;
`tolerance` è la distanza massima dalla retta, `angle_tolerance` la differenza
di direzione in radianti. I tratti rimasti da soli non compaiono.

`CollinearRun`: `start`, `end` (i capi esterni della fila), `members` (indici in
`segments`, nell'ordine lungo la retta).

**Non muta** niente.

---

### `intersections`

```python
topo.geometry.intersections(a, b) -> list[Point]
```

I punti dove due primitive si incontrano: incroci e tocchi, capi compresi.
Esatti fra `LineSeg`, `ArcSeg`, `CircleSeg` (forma chiusa); su `SplineSeg` ed
`EllipseSeg` entro `CURVE_TOLERANCE` (1e-4), perché lì una forma chiusa non
c'è. Due tratti sovrapposti (stessa retta, stesso cerchio) non danno punti: il
loro incontro è un tratto (D118).

**Non muta** niente.

---

### `point_on_contour`, `ContourPoint`

```python
topo.geometry.point_on_contour(segments, point, tolerance=0.01, angle_tolerance=1e-3) -> ContourPoint | None
```

Dove cade `point` sull'anello `segments` (testa-coda, come `contour.segments`).
`ContourPoint`: `point`, `kind` (`"vertex"` due lati con un angolo, `"smooth"`
due lati che proseguono uno nell'altro — un raccordo —, `"edge"` in mezzo a un
lato), `segments` (indici: entrante e uscente per un vertice, uno solo per un
lato), `turn_deg`, `concave` (l'interno occupa più di mezzo giro). Le tangenti
sono esatte; concavo o convesso lo dice il verso dell'anello. None se `point`
dista più di `tolerance` (D118).

**Non muta** niente.

---

### `cut_by`

```python
topo.geometry.cut_by(segment, region, keep="outside") -> list
```

I pezzi di `segment` fuori (`"outside"`) o dentro (`"inside"`) la regione
chiusa `region`, nel verso di `segment`, tagliati nei punti di
`intersections`. Una regione è un anello di primitive qualunque
(`topo.geometry.circle`, `rectangle`, `polygon`, `contour.segments`). I pezzi
restano primitive dello stesso tipo: un arco tagliato è un arco (D118).

**Non muta** niente. **Solleva** `ValueError` se un pezzo corre lungo il bordo
della regione (né dentro né fuori).

---

### `contour_minus`

```python
topo.geometry.contour_minus(contour, region) -> list[list]
```

L'anello `contour` meno la regione chiusa `region`: gli anelli del bordo che
resta, ognuno testa-coda. Un anello esterno ha il verso di `contour`, un foro
(regione tutta dentro) quello opposto. `[]` se la regione copre tutto,
`[contour]` se non lo tocca. Tanti anelli quanti ne vengono: un taglio che
stacca un pezzo ne dà due, e quale tenere lo decide il chiamante. Un tocco
solo (tangenza) non cambia la forma. Da passare a `Contour.from_segments`
(D118).

**Non muta** niente. **Solleva** `ValueError` se i due bordi corrono uno
sull'altro.

---

### `dash_line`

```python
topo.geometry.dash_line(start, end, head, tail, middle=0.0, n_middle=0) -> list[tuple[Point, Point]]
```

Il segmento `start`→`end` ridotto a tratti: uno lungo `head` attaccato a
`start`, uno lungo `tail` attaccato a `end`, e `n_middle` tratti lunghi
`middle` fra i due, con tutti i vuoti uguali. Ogni tratto è `(start, end)` nel
verso del segmento; un tratto lungo zero non compare. Se i tratti coprono tutto
il segmento torna `[(start, end)]`, intero. Fatto geometrico: che quel segmento
sia una piega lo decide il consumatore (D115).

**Non muta** niente. **Solleva** `ValueError` su lunghezze o `n_middle` negativi.

---

### `covered_rectangles`

```python
topo.geometry.covered_rectangles(items, min_side, eps=0.5, cluster_tolerance=1.5, coverage=0.85) -> list[CoveredRectangle]
```

I rettangoli allineati agli assi i cui quattro lati sono coperti almeno per
`coverage` da tratti dritti (`items`: oggetti con `start`/`end`, per esempio gli
`Edge` dritti di un documento), costruiti sulle coordinate dei tratti lunghi
almeno `min_side`. Non usa `polygonize`: un bordo pieno di tacche resta un
rettangolo, una cornice a doppio bordo ne dà due. Che un rettangolo sia una
cornice o un cartiglio lo decide il consumatore (snapdraw, D94).

`CoveredRectangle`: `polygon`, `items` (i tratti sui suoi lati), `bbox`, `area`,
`long_side`, `short_side`, `ratio`.

**Non muta** niente.

---

### `spanning_lines`

```python
topo.geometry.spanning_lines(bounds, items, coverage=0.85, eps=0.5, cluster_tolerance=1.5) -> (list[float], list[float])
```

`(ys, xs)`: le linee strettamente interne a `bounds` che lo attraversano per
almeno `coverage` della larghezza (orizzontali) o dell'altezza (verticali).

**Non muta** niente.

---

### `sides_on_border`

```python
topo.geometry.sides_on_border(bounds, border, tolerance) -> list[str]
```

I lati di `bounds` (`"left"`, `"bottom"`, `"right"`, `"top"`) che stanno sul
lato omologo di `border` entro `tolerance`: un riquadro appoggiato al bordo di
un altro. Lista vuota se non ne tocca nessuno.

**Non muta** niente.

---

### `axis_aligned_share`

```python
topo.geometry.axis_aligned_share(segments, angle_tolerance) -> float | None
```

Frazione della lunghezza dei `LineSeg` orizzontale o verticale entro
`angle_tolerance` gradi; `None` senza `LineSeg`.

**Non muta** niente.

---

### `axis_lines`

```python
topo.geometry.axis_lines(items, eps=0.5) -> (list[AxisLine], list[AxisLine])
```

`(orizzontali, verticali)`: i tratti (`items`, oggetti con `start`/`end`) che
si scostano dall'asse al più di `eps`; gli altri non compaiono.
`AxisLine`: `item` (il tratto ricevuto), `lo`, `hi` (l'intervallo lungo il suo
asse: x per un orizzontale), `at` (la coordinata costante, media dei due capi).

**Non muta** niente.

---

### `items_inside`

```python
topo.geometry.items_inside(bounds, items, margin=0.0) -> list
```

I tratti con entrambi i capi dentro `bounds` = `(xmin, ymin, xmax, ymax)`
allargato di `margin`, nell'ordine dato.

**Non muta** niente.

---

### `merge_intervals`

```python
topo.geometry.merge_intervals(intervals, tolerance=0.0) -> list[tuple[float, float]]
```

Gli intervalli `(a, b)` uniti dove si sovrappongono o distano al più
`tolerance`, in ordine crescente.

**Non muta** niente.

---

### `group_collinear_lines`

```python
topo.geometry.group_collinear_lines(lines, tolerance=COLLINEAR_TOLERANCE, angle_tolerance=COLLINEAR_ANGLE_TOLERANCE) -> list[list]
```

I tratti (`start`/`end`) raggruppati per retta: `[[L1, L2], [L3], ...]`. Ogni
gruppo prende la retta del suo primo tratto, nell'ordine dato; non guarda se i
tratti si toccano (per le file attraverso dei vuoti: `bridged_runs`).

**Non muta** niente.

---

### `segment_length`, `length_inside`, `chord_angle_deg`

```python
topo.geometry.segment_length(segment) -> float
topo.geometry.length_inside(segment, bounds) -> float
topo.geometry.chord_angle_deg(a, b) -> float
```

- `segment_length`: la lunghezza di una primitiva nativa. Esatta per
  `LineSeg`, `ArcSeg`, `CircleSeg`; per `SplineSeg` ed `EllipseSeg` è la
  polilinea di `discretize()`.
- `length_inside`: quanta parte di `segment` sta dentro il rettangolo
  `bounds` = `(xmin, ymin, xmax, ymax)`, bordo compreso (le curve sulla
  polilinea di `discretize()`).
- `chord_angle_deg`: l'angolo in gradi, in `[0, 180)`, della corda da `a` a
  `b`; modulo 180 perché una linea non ha verso.

**Non mutano** niente.

---

### `track_points`, `track_length`, `track_shape_type`

```python
topo.geometry.track_points(segments, tolerance=None) -> list[Point]
topo.geometry.track_length(pts) -> float
topo.geometry.track_shape_type(pts) -> str
```

Una traccia aperta (piega, incisione, frammento non chiuso) è una catena di
segmenti nativi. `track_points` ne dà i vertici (il `discretize()` di ogni
segmento, senza ripetere il punto di giunzione); `track_length` la lunghezza
della polilinea; `track_shape_type` dice `"line"` se è un solo tratto dritto
(2 vertici), altrimenti `"curve"`.

**Non mutano** niente.

---


### `split`

```python
topo.split(
    result: Result,
    namer=None,
    min_area=50.0,               # topo.DEFAULT_MIN_CLUSTER_AREA, mm²
) -> list[Result]
```

**Un `Result` per parte**, senza formato (D124, D129): scegliere le parti è
una decisione sul modello, scriverle è di un adapter. Ogni parte è un
`Result` con un solo cluster, più le entità trash e le annotazioni che le
appartengono: quelle che contiene o, se nessuna parte le contiene, quelle più
vicine al suo contorno esterno fra **tutte** le parti (anche quelle scartate
da `min_area`). Niente viene duplicato, niente perso. Gli altri campi
(sorgente, avvisi) sono copiati. Ogni writer prende un `Result`, quindi una
parte va in DXF, SVG o testo allo stesso modo.

| parametro | significato |
|---|---|
| `namer` | `callable(i, cluster) -> str` — assegna `cluster.label`, così il nome di un file resta ricavabile (`f"{cluster.label}.dxf"`). Senza, `f"{label}_P{i+1}"`. |
| `min_area` | le parti con area sotto soglia (mm²) sono scartate con un avviso in `result.warnings`; `<= 0` nessun filtro. |

**Muta** `cluster.label` di ogni parte tenuta e `result.warnings`.
**Ritorna** le parti nell'ordine dei cluster tenuti.
**Solleva `ValueError`** se `result.is_valid` è `False`: un file per parte
non ha senso senza parti.

```python
for part in topo.split(result, min_area=100.0):
    name = part.clusters[0].label
    topo_dxf.to_dxf(part, doc).saveas(f"{name}.dxf")
    topo.save_svg(part, f"{name}.svg")
```

---

### `RoleStyle`

```python
@dataclass(frozen=True)
class RoleStyle:                                          # topo.RoleStyle, topo.model.RoleStyle
    color:      tuple[int, int, int] | None = None   # RGB 0-255
    linetype:   str | None = None                     # nome del tipo di linea; da solo, un tipo standard ("DASHED")
    dash:       tuple[float, ...] | None = None       # il tratto, segni con segno come EdgeStyle.dash
    lineweight: float | None = None                   # mm
```

Come il chiamante vuole disegnato un ruolo in uscita, nello stesso vocabolario
di `EdgeStyle` e senza formato (D37, D128). Vale per un ruolo del motore
(`"outer"`, `"inner"`, `"unknown"`) come per uno di un consumatore — snapbend
(`"hole"`, ...), snapdraw (`"frame"`, `"title_block"`, ...) — nessuno è
privilegiato. Il dizionario `{ruolo: RoleStyle}` è del chiamante e lo passa a
ogni exporter: `to_svg`, `to_view_model`, `topo_dxf.to_dxf`,
`topo_dxf.split_to_files`. Sotto c'è sempre la palette di topo; un campo
`None` resta quello della palette. Dove finisce un ruolo (un layer DXF) non è
qui: è `topo_dxf.to_dxf(layers=...)`.

**La palette di topo** (`topo.model.DEFAULT_ROLE_STYLES`, D128) dà il colore
ai ruoli che heal e island producono, uguale per ogni formato: `outer` verde
(0, 255, 0), `inner` giallo (255, 255, 0), `unknown` rosso (255, 0, 0); ogni
altro ruolo è grigio (`CONSUMER_ROLE_STYLE`, (128, 128, 128)) finché il
chiamante non gli dà un colore. `topo.model.role_style(ruolo, role_styles)`
risolve uno stile: la palette, con sopra i campi non `None` della mappa del
chiamante. Ogni exporter la chiama e traduce soltanto (ACI o true color in
DXF, hex in SVG): chi scrive un adapter non sceglie colori.

```python
topo.model.role_style("outer")                                   # verde
topo.model.role_style("hole", snapbend.flat.ROLE_STYLES)         # magenta di snapbend
topo.model.role_style("outer", {"outer": topo.RoleStyle(lineweight=0.3)})   # verde, 0.3 mm
```

In DXF: un colore della palette diventa il suo indice ACI esatto (3, 2, 1, 8);
`color` del chiamante → true color del layer; `dash` → un tipo di linea registrato
col nome `linetype` o, senza, `<RUOLO>_DASH`; un `linetype` senza `dash` deve
essere nel documento o fra gli standard, altrimenti `ValueError` (D85);
`lineweight` → centesimi di mm.

```python
topo_dxf.to_dxf(result, doc, role_styles={
    "frame":   topo.RoleStyle(color=(0, 0, 0)),          # cornice: nero
    "unknown": topo.RoleStyle(lineweight=0.05),          # trash: linea sottilissima
    "bending": topo.RoleStyle(dash=(5.0, -2.0)),         # pieghe: tratto 5, vuoto 2
})
```

---

### `anchor_annotations`

```python
topo.anchor_annotations(result: Result, snap_distance=0.0,
                         leader_distance=0.5) -> Result
```

Collega le annotazioni alla geometria. Per ogni annotazione `cluster_ref` =
indice del cluster il cui contorno esterno ne contiene la posizione (con
`snap_distance` > 0, anche il più vicino entro quella distanza). Per ogni
`Leader` con vertici anche `target` — vedi `leader_target`; per ogni
`Dimension` `references` — vedi `dimension_references`.

**Muta** le annotazioni di `result` in-place. **Ritorna** lo stesso `result`.

### `leader_target`

```python
topo.leader_target(result: Result, leader: Leader,
                    distance=0.5) -> str | None
```

L'elemento su cui cade la punta (`vertices[0]`) di `leader`, come percorso in
`result`: `"clusters[0].outer"`, `"clusters[0].inners[3]"`,
`"clusters[1].holes[2]"` — qualunque collezione di `cluster.detected`, quindi
vale dopo la lettura di un consumatore come dopo `island`.

Regola: il bordo più vicino alla punta, se entro `distance` (a parità, vince
l'elemento più piccolo); altrimenti il più piccolo elemento chiuso, non il
contorno esterno, che contiene la punta (freccia che finisce dentro un foro);
altrimenti `None` (freccia di sezione, fuori dal pezzo). Non legge il testo.

**Non muta** niente.

### `dimension_references`

```python
topo.dimension_references(result: Result, dimension: Dimension,
                           distance=0.5) -> list[str]
```

Gli elementi fra cui la quota misura, come percorsi in `result` (stesso
formato di `Leader.target`): per ogni punto di `measured_points` l'elemento
il cui bordo passa entro `distance` (a parità il più piccolo). Senza doppioni,
nell'ordine dei punti: un diametro dà il cerchio, una lineare uno o due
elementi. Non legge il testo.

**Non muta** niente.

### `resolve_target`

```python
topo.resolve_target(result: Result, target: str | None) -> Any
```

Il passo inverso: il contorno o la feature a cui punta un `target`, o `None`
se il percorso non esiste più in `result` (per esempio dopo una detection che ha
spostato i fori da `inners` a `holes`: ancorare dopo aver scelto le feature).

---

### `inject`

```python
topo.inject(
    result: Result,
    data_injector=None,
    snap_distance: float = 0.0,
) -> Result
```

Arricchimento **opzionale** dai testi. **Muta** `result.clusters[i].custom` in-place e
ritorna il `result`. Fa **una cosa**: se passi `data_injector` —
`callable(cluster, list[str]) -> dict` — gli passa i testi di
`result.annotations` che ricadono dentro l'outer di ogni parte e mette il dict
restituito in `cluster.custom` (codice pezzo, materiale, spessore, …). Senza
`data_injector`, `inject()` non fa nulla.

`snap_distance` > 0: un testo fuori da ogni parte va alla parte **più vicina**
(una sola) se dista al massimo `snap_distance` dal suo contorno esterno — il
callout scritto appena fuori dal pezzo. Stessa regola di `anchor_annotations`
(MAP.md D82). Un testo contenuto non viene mai spostato dallo snap.

I **conteggi delle feature** NON si fanno qui: `cluster.summary` dà il
conteggio grezzo per nome dell'overlay (sempre disponibile), il dettaglio per
tipo è del consumatore che le ha lette (MAP.md D44, D88). Per metterlo
nell'export passa `extra_metadata` (vedi sotto).

```python
def leggi_cartiglio(cluster, testi):
    return {"material": next((t for t in testi if t.startswith("S")), "S275JR")}

topo.inject(result, data_injector=leggi_cartiglio, snap_distance=5.0)
```

---

## 4. Export

Tutti leggono lo schema da `topo/rules/metadata_schema.py` — **una sola fonte**
per i nomi dei campi. Cambia quel file (o usa `set_schema`) per adattarti al tuo
CAM.

### `save_json` / `to_json`

```python
topo.save_json(
    result: Result, path, indent=2,
    extra_metadata: Callable[[Cluster], dict] = None,
) -> None   # scrive su file
topo.to_json(
    result: Result, indent=2,
    extra_metadata: Callable[[Cluster], dict] = None,
) -> str    # ritorna la stringa
```

Metadati per parte secondo schema — **niente coordinate**. `extra_metadata`
(D44), se passata, viene chiamata una volta per cluster e i campi che
ritorna finiscono nell'output **fuori dallo schema** — passarla è già la
scelta esplicita del chiamante, stesso idioma di `data_injector`. Serve per
una detection tua (fori per tipo, una `FlangeViewHint`) che topo non può
conoscere. Struttura:

```json
{
  "source_file": "batch.dxf",
  "is_valid": true,
  "cluster_count": 3,
  "warnings": [], "errors": [],
  "clusters": [
    {
      "label": "P-1", "source_file": "batch.dxf",
      "quantity": 1, "material": "S275JR", "thickness_mm": 0.0,
      "area_mm2": 12345.67, "inner_contours_count": 1,
      "outer_perimeter_mm": 480.0, "inner_perimeter_mm": 60.0,
      "total_perimeter_mm": 540.0,
      "bbox": {"minx": 0, "miny": 0, "maxx": 200, "maxy": 100}
    }
  ]
}
```

### `save_xml`

```python
topo.save_xml(
    result: Result, path,
    extra_metadata: Callable[[Cluster], dict] = None,
) -> None
```

Stessi campi di `save_json` (`extra_metadata` incluso), in XML
(`<topo><clusters><cluster>…`).

> **Il viewer** — `to_view_model`, `to_svg`, `save_svg` — è **fuori dalla
> 1.0 stabile** (MAP.md D133): si importa come `topo.<nome>` ma non è in
> `__all__`, e verrà rifatto (TODO, "Rifare il viewer"). Le firme qui sotto
> valgono oggi, senza garanzia che restino.

### `to_view_model`

```python
topo.to_view_model(
    result: Result,
    tolerance=0.05,
    include_trash=True,
    include_annotations=True,
) -> dict
```

`Result` → dizionario JSON **orientato al rendering**: le coordinate di
*ogni* feature + ruolo + colore hex. È il pendant geometrico di `to_json` (che dà
solo metadati). Lo consuma `to_svg` e lo consumerebbe un front-end esterno
(dashboard JS che disegna con SVG/Canvas).

> `to_text(result) -> str` / `save_text(result, path)` — la lettura per un
> modello linguistico (`<nome>.topo.md`) — è **sperimentale**, fuori da
> `__all__` finché non ha un chiamante vero (MAP.md D84). Firma e sezioni in
> `docs/LLM.md`, insieme a una tabella di cosa dà ogni uscita.

> `to_nester_input(result) -> list[dict]` esiste ancora (`label`, `bbox`,
> `outer_coords`, `holes_coords` per parte) ma è **sperimentale**, fuori da
> `__all__` — scritto per un nester mai realizzato (MAP.md D18). Per serializzare
> la geometria usa `to_view_model`.

Tutta la geometria è **discretizzata a polilinee** (`points: [[x, y], …]`):
archi, cerchi, spline appiattiti. L'overlay sta sotto `features`, per nome
(D90): una voce per contorno, con ruolo, colore, punti, `closed` e i campi
scalari del `to_dict()` dell'elemento — chi porta `center` + `diameter` si può
disegnare come cerchio vero. Coordinate nel sistema del sorgente (Y in alto).

```python
vm = topo.to_view_model(result, role_styles=None)   # {ruolo: RoleStyle} del chiamante: ne legge il colore
vm["clusters"][0]["outer"]        # {"role": "outer", "color": "#00ff00", "points": [...], "closed": true}
vm["clusters"][0]["features"]     # {"holes": [{"role": "hole", "points": [...], "diameter": ..., ...}], ...}
vm["palette"]                  # {"outer": "#00ff00", ...} + i ruoli che role_styles colora
```

Non muta `result`, non solleva su `result` non valido (torna il dict con
`is_valid=False`).

### `to_svg` / `save_svg`

```python
topo.to_svg(
    result: Result,
    tolerance=0.05,
    include_trash=True,
    include_annotations=True,
    padding=0.03,
    background="#1e1e1e",     # None = trasparente
    true_circles=True,        # una voce con center + diameter → <circle>
    stroke_width=None,        # None = auto (diagonale bbox / 400)
    size=None,                # None = niente width/height → scala al contenitore
    units=None,               # "mm" = SVG in scala reale, 1 unità = 1 mm
    allow_invalid=True,       # False → ValueError su un result non valido
    role_styles=None,         # {ruolo: RoleStyle}: il colore di ogni ruolo, come in topo_dxf.to_dxf
) -> str
topo.save_svg(result, path, **kwargs) -> None
```

Renderer SVG del modello (MAP.md D12) — per visualizzazione (UI/report/
anteprima) o per una macchina che importa SVG. Un colore per ruolo: la palette di topo, con sopra `role_styles` del
chiamante (D128). La
Y viene ribaltata (modello Y-su → SVG Y-giù). Una parte = un `<g data-cluster="…">`.
Costruito sopra `to_view_model`.

`size=None` (default) **non** scrive `width`/`height` sull'`<svg>`: l'immagine è
vettoriale e scala a riempire il contenitore (o la finestra del browser) — la
zoomi quanto vuoi. Passa `size="800"` per fissare la larghezza in px.

`units="mm"` produce un SVG **in scala reale** (`width="…mm"`, padding e sfondo a
zero) per chi importa SVG in un software che vuole 1 unità = 1 mm.
**Attenzione:** archi, cerchi e spline restano discretizzati a polilinea — quando
conta la curva esatta (cerchi lisci, quote a tolleranza) usa `topo_dxf.to_dxf`, non l'SVG.

Un `result` non valido viene disegnato lo stesso. `allow_invalid=False` →
`ValueError`, stesso contratto di `topo_dxf.to_dxf` (D83).

```python
topo.save_svg(result, "pezzo.svg")
```

---

## 5. Metadati

### `build_metadata`

```python
topo.build_metadata(cluster: Cluster, schema: dict = None, extra: dict = None) -> dict
```

I metadati di un cluster secondo lo schema attivo (`metadata_schema.py`, o
quello di `set_schema`): la fonte unica che usano `save_json`, `save_xml` e,
come XDATA in un DXF, `topo_dxf.write_metadata_to_dxf` (§9). `extra` aggiunge
campi del chiamante. Non muta niente.

### `set_schema`

```python
topo.set_schema(schema: dict) -> None
```

Sostituisce lo schema metadati attivo a runtime. Da usare quando `topo` è
installato con pip e non puoi editare `metadata_schema.py`. Struttura:
`{chiave_interna: (nome_output, default, sorgente)}` con `sorgente` ∈
`{"cluster", "custom", "calculated"}`.

---

## 6. Ispezione / debug

I due livelli di topo, in ordine di elaborazione; il primo, le entità grezze
di un file, è dell'adapter (`topo_dxf.inspect_dxf`, e `topo_dxf.inspect_file`
che stampa i tre in fila, §9). Tutti stampano su stdout.

```python
topo.inspect_document(doc, graph=True, limit=60) -> None
```
**Livello 2** — un `Document`: `source_meta`, warning del loader,
gli `Edge` (ruolo, primitiva, endpoint), le annotazioni, e il
grafo dei nodi (nodi totali, loop degeneri, nodi di branching, estremi liberi).
"Cosa ha capito l'adapter."

```python
topo.inspect_result(result, coords=False) -> None
```
**Livello 3** — un `Result`: validità, warning/errori, e per ogni parte
outer/inner, le collezioni di `cluster.detected` (quello che un consumatore ha
attaccato), custom, più `trash_entities`,
`classified_entities`, annotazioni. "Cosa ha prodotto topo."

---

## 7. Tipi di dominio

Oltre alla top-level ci sono tre namespace pubblici (MAP.md D120); quello che
sta sotto `topo.core`, `topo.tools`, `topo.io`, `topo.rules` è interno, senza
garanzie. Gli adapter sono pacchetti a parte (§9, §10):

- **`topo.primitives`** — i segmenti nativi `LineSeg`, `ArcSeg`, `CircleSeg`,
  `SplineSeg`, `EllipseSeg` (math puro, nessun ruolo) e
  `sub_segment(seg, a, b, via)`, il tratto di `seg` da `a` a `b` (`via`, un
  punto interno, serve solo su una curva chiusa).
- **`topo.model`** — i tipi qui sotto (`Document`, `Result`, `Cluster`,
  `Contour`), le curve (`Curve`, `ClosedCurve`, `OpenCurve`), `Edge` (un
  segmento con ruolo e stile), `EdgeStyle`, le annotazioni, le feature
  rilevate e i ruoli: `ContourRole`, `role_str`, `normalize_role`,
  `is_structural_role`. I quattro più usati stanno anche in `topo.<Nome>`.
- **`topo.steps`** — i passi di `heal()` e della lettura per isole (§3).

```python
import topo

side = topo.primitives.LineSeg(start=(0, 0), end=(100, 0))

class Hole(topo.model.ClosedCurve): ...
```

### `Document`

Prodotto da `topo_dxf.load_dxf` / `topo_dxf.document_from_msp`. È il contratto tra l'adapter e il
core: dopo di lui, `ezdxf` non si tocca più.

| campo | tipo | contenuto |
|---|---|---|
| `edges` | `list[Edge]` | geometria tradotta in primitive pure — input di `heal()` |
| `annotations` | `list[Annotation]` | testi e quote della sorgente |
| `source_meta` | `dict` | `$INSUNITS`, `$MEASUREMENT`, `tolerance`, `ignore_layers` |
| `source_path` | `str` | percorso del file |
| `warnings` | `list[str]` | diagnostica del loader sul file grezzo |

`node_tolerance(override=None) -> float`: la distanza sotto cui due estremi
sono lo stesso nodo — `override` se dato, altrimenti `source_meta["tolerance"]`,
altrimenti `DEFAULT_NODE_TOLERANCE` (0.05, `model/document.py`). È la lettura
che usano `heal`, `island` e `validate` quando `tolerance` non è passata (D86).

### `Annotation`

`Note` / `Dimension` / `Leader`. Comuni: `kind` (`"TEXT"` | `"MTEXT"` |
`"DIMENSION"` | `"LEADER"` | `"MULTILEADER"`), `position` `(x, y)`,
`cluster_ref`, `display_text`, `role`.

`role` dice cosa è l'annotazione per chi la usa (`"title_block"`,
`"part_code"`, ...), come il ruolo di un edge (MAP.md D127). topo non lo legge
e non lo decide: lo scrive il consumer (`Note(..., role="title_block")`,
ripulito da `normalize_role`), oppure le sue `role_rules` al load, sul nome
del gruppo sorgente (il layer di un DXF). Su un'annotazione contano solo le
regole sul nome (`name`, `name_contains`): una regola su tratto o colore non
la tocca. `unknown` se nessuno l'ha detto. Il gruppo sorgente serve solo a
questo e non resta nel modello (D128): chi vuole un testo distinto in uscita
gli dà un ruolo. `topo_dxf.to_dxf` scrive un'annotazione con un ruolo sul layer del suo
ruolo, come un edge; senza ruolo, su `annotation_layer`.

- `Note`: `text`, `height`, `rotation`.
- `Dimension`: `measured_value`, `dim_type`, `text_override` (testo
  dell'autore, `<>` = la misura), `rendered`, `measured_points` (i punti
  sulla geometria fra cui misura), `references` (percorsi degli elementi
  quotati, da `anchor_annotations`). `display_text` = override con `<>`
  sostituito dalla misura come è scritta nel disegno.
- `Leader`: `text`, `vertices` (`[0]` = punta), `target`.

### `Result`

Prodotto da `heal()`, arricchito da un consumatore / `inject()`.

| campo | tipo | contenuto |
|---|---|---|
| `clusters` | `list[Cluster]` | un elemento per contorno esterno chiuso |
| `is_valid` | `bool` | **controllalo prima di `split` o di scrivere (`topo_dxf.to_dxf`)** |
| `warnings` / `errors` | `list[str]` | diagnostica |
| `trash_entities` | `list` | geometria non classificata (proxy con `segments`, formato-indipendenti) |
| `annotations` | `list[Annotation]` | copiate da `heal()` dal `Document` |
| `classified_entities` | `list` | di un consumatore (snapbend: marking, work_type custom) |
| `all_arcs` | `list[ArcSeg]` | tutti gli archi del disegno (snapbend li usa per i fori filettati) |
| `cluster_count` | property | `len(clusters)` |

Metodo `to_dict()` → dizionario JSON-ready (usato internamente dagli export).

### `Cluster`

| campo | tipo | contenuto |
|---|---|---|
| `outer` | `Contour` | profilo esterno (ha `polygon`, `segments`, `role`, `area`, `bbox`) |
| `inners` | `list[Contour]` | contorni chiusi dentro l'outer, senza lettura (un cerchio non è un foro, D15) |
| `label` | `str` | etichetta, base del nome file |
| `custom` | `dict` | dati aggiunti da un `data_injector` esterno (materiale, spessore, codice) |
| `detected` | `Optional[DetectedFeatures]` | overlay di un consumatore — `None` finché nessuno ci ha scritto (D44, D90) |
| `features(name)` | metodo | collezione `name` da `detected` — `[]` se `detected` è `None` o `name` non è stato scritto |
| `summary` | property | conteggio **grezzo**, sempre disponibile: `{nome}_count: len(items)` per ogni collezione in `detected` — `{}` se `detected` è `None` |
| `overlay_voids` | property | gli elementi dell'overlay con `is_void = True` e un `polygon`: vuoti del pezzo letti da un consumatore (D90) |
| `area` | property | outer − vuoti dell'overlay − inner a depth dispari + inner a depth pari (D89, D90) |
| `bbox` | property | `(minx, miny, maxx, maxy)` |

Un consumatore attacca la sua detection così (`topo.DetectedFeatures`):
`cluster.detected = cluster.detected or DetectedFeatures();
cluster.detected.attach("flange_view_hint", [...])`, poi la legge con
`cluster.features("flange_view_hint")`. Nessun nome è privilegiato (D44) — `DetectedFeature` (`typing.Protocol`, `source`/`confidence`)
è il contratto minimo, non imposto a runtime.

### `Contour`

`role` (`ContourRole`), `polygon` (shapely), `segments` (primitive native, un
anello testa-coda), `depth`, `parent`, proprietà `area` e `bbox`.

```python
topo.Contour.from_segments(segments, role, depth=0, parent=None, tolerance=0.01) -> Contour
```

Contorno da un anello di primitive scritto da un chiamante (per esempio il
risultato di `geometry.contour_minus`): controlla che ogni segmento parta dove
finisce il precedente e che l'ultimo chiuda sul primo, e calcola il poligono.
**Solleva** `ValueError` se l'anello non chiude o non racchiude un poligono
valido (D118).

### `ContourRole` (ruoli del motore — vocabolario aperto)

Il motore conosce solo tre ruoli: `unknown`, `outer`, `inner` (MAP.md D47,
"roles out of core"; i ruoli di processo sono di snapbend, D88).
**Non è un universo chiuso**: chiunque può assegnare un ruolo che il motore non conosce (`hole`,
`frame`, `title_block`, `section`, …). Passa per `normalize_role()` — ripulito
in uno slug `[a-z0-9_-]` ≤ 64 char — e topo lo conserva senza sollevare; in
output l'adapter DXF lo scrive di default su un layer **col nome dello slug**,
grigio (`unknown` → `Trash`, rosso), salvo la scelta del chiamante
(`topo_dxf.to_dxf(layers=..., role_styles=...)`, D128). `role_str(role)` dà il valore stringa che il ruolo sia una
costante o uno slug (MAP.md D27 / D31).

**`topo.normalize_role(value) -> str`** e **`topo.is_structural_role(role) ->
bool`** sono pubbliche (MAP.md D30). `is_structural_role` (il predicato del
motore, solo `outer`/`inner`) è quello che `heal()` usa di default se non gli
passi `is_structural=...` — vedi `heal()` sopra. Un consumatore che marca la geometria **prima
di `heal`**: tiene i riferimenti agli `Edge` di `doc.edges`, imposta
`edge.role = topo.normalize_role("frame")` — resta fuori dal grafo per
default (nessun predicato lo riconosce strutturale), la geometria marcata
finisce in `trash_entities` col ruolo intatto e l'output la scrive sul layer
`frame`. È l'aggancio usato da `snapdraw` per cornice e cartiglio.

### `non_contour_candidates`

```python
topo.non_contour_candidates(doc: Document, tolerance=None) -> list[Edge]
```

Edge di `doc.edges` che il criterio topologico di `heal()` escluderebbe dal
grafo dei contorni (catene fra due nodi di branching distinti, e non sul bordo
della faccia esterna della loro componente connessa, MAP.md D111, D131) — **senza dire cosa siano**. `heal()` da solo
non assegna un significato a questi edge: li esclude e basta, restano in
`trash_entities` col ruolo che avevano. Un consumatore li interpreta (snapbend
`detect_flat`: dritto, estremi sul contorno esterno → `"bending"`).

Un consumatore che vuole
un'interpretazione propria (un bordo di feature in rilievo vista in pianta non
è una piega) chiama `non_contour_candidates(doc)` per ottenere la stessa lista
di candidati che `heal()` userebbe, senza duplicare il criterio, e decide da
sé come marcarli — poi assegna `edge.role` sugli `Edge` restituiti (sono
riferimenti dentro `doc.edges`, mutarli si riflette lì) **prima** di chiamare
`heal()` (vedi `ContourRole` sopra, MAP.md D55).

| parametro | significato |
|---|---|
| `tolerance` | se `None`, ripresa da `doc.source_meta["tolerance"]` — stesso fallback di `heal()`. |

Lavora su `doc.edges` così come sono, **prima** che `heal()` fonda segmenti
sovrapposti/cocircolari e chiuda i gap minuscoli (i suoi primi passi interni,
D50/D52): su un disegno con duplicati o gap sotto tolleranza il risultato può
differire di poco da quello che `heal()` escluderebbe a conti fatti. Non è un
problema per l'uso previsto — decidere `edge.role` prima di `heal()` — perché
la parola finale su cosa resta nel grafo la dice comunque `heal()` stesso.

```python
for edge in topo.non_contour_candidates(doc):
    if <la tua logica decide che è un bordo di feature in rilievo>:
        edge.role = topo.normalize_role("flange_up")

result = topo.heal(doc)   # "flange_up" è già fuori dal grafo, mai indovinato "bending"
```

---

## 8. Il flusso completo, in ordine

```python
import topo, topo_dxf

# 1. apri — l'adapter è l'unico che legge un formato
doc = topo_dxf.load_dxf("pezzo.dxf", tolerance=0.5)

# 2. valida l'input (opzionale ma consigliato)
check = topo.validate(doc)
if not check.is_valid:
    raise SystemExit(check.errors)

# 3. topologia
result = topo.heal(doc, label="P-1024")
# 4. (opzionale) una lettura di processo, fuori da topo — es. snapbend:
#   from snapbend.flat import detect_flat
#   detect_flat(result, "all")

# 5. controlla SEMPRE prima di renderizzare
if not result.is_valid:
    raise SystemExit(result.errors)

# 6. arricchimento CAM (opzionale — solo se hai un data_injector per i testi)
result = topo.inject(result, data_injector=leggi_cartiglio, snap_distance=5.0)

# 7a. render — un documento con tutte le parti
topo_dxf.to_dxf(result, doc).saveas("pezzo_healed.dxf")

# 7b. oppure render — un file per parte
for part in topo.split(result):
    topo_dxf.to_dxf(part, doc).saveas(f"output/{part.clusters[0].label}.dxf")

# 8. metadati
topo.save_json(result, "pezzo.json")
```

Se qualcosa non torna su un file reale: `topo_dxf.inspect_file("pezzo.dxf")`.

---

## 9. `topo_dxf` — l'adapter DXF

```python
import topo, topo_dxf          # pip install g-topo[dxf]
```

Un consumer di topo come un altro, nella stessa distribuzione: legge DXF/DWG
in un `Document`, scrive un `Result` in un `Drawing` `ezdxf`. Usa solo i nomi
pubblici di topo (D125, D129); senza `ezdxf` installato `import topo_dxf`
dice quale extra manca. Layer e colori sono scelte del chiamante; quello che
non dice è il default di questo adapter.

### `load_dxf`

```python
topo_dxf.load_dxf(
    path,
    upgrade=False,
    explode_inserts=True,
    flatten_z_flag=True,
    verbose=False,
    tolerance=0.05,
    role_rules=(),
    ignore_layers=None,
    skip_layers=SKIP_LAYERS,          # ("Trash", "Annotation")
) -> Document
```

Unico punto in cui `ezdxf` viene usato per **leggere**. Apre un `.dxf` o `.dwg`,
lo audita, lo porta a R2010 se legacy, esplode gli `INSERT`, sanifica (OCS, Z≠0),
traduce le entità in `Edge` puri e le annotazioni in `Annotation`. Dopo questa
funzione il documento `ezdxf` sorgente sparisce.

| parametro | significato |
|---|---|
| `path` | percorso `.dxf` o `.dwg`. Per il `.dwg` vedi la sezione **DWG** qui sotto. |
| `upgrade` | forza l'upgrade a R2010 anche se non necessario. |
| `explode_inserts` | `True` (default): esplode i blocchi in primitive. **Metti `False` solo se vuoi ignorare i blocchi di proposito** — un `INSERT` non esploso viene scartato e la sua geometria sparisce. |
| `flatten_z_flag` | riporta sul piano le entità con Z ≠ 0. |
| `tolerance` | tolleranza di arrotondamento dei nodi topologici. Viene salvata in `source_meta` e riletta da `heal()` se non gliela ripassi. |
| `role_rules` | lista di `RoleRule` — assegnano il **ruolo** agli `Edge` già in fase di traduzione. Valutate in ordine, vince la prima che matcha, nessuna → `unknown`. Il nome valutato da `name`/`name_contains` è il layer; `dashed` e `color` guardano l'aspetto **effettivo** (un'entità `ByLayer` viene risolta al linetype/colore del suo layer). Il layer non esce dall'adapter: l'`Edge` porta solo il ruolo (MAP.md D63). Vedi **`RoleRule`** sotto. |
| `ignore_layers` | lista di layer da escludere dalla geometria (per sottostringa, maiuscole ignorate). |
| `skip_layers` | layer da saltare per **nome esatto** (maiuscole ignorate). Di default `topo_dxf.SKIP_LAYERS`, i layer che il writer usa per trash e annotazioni: un file scritto da topo si rilegge pulito, e `Trash_old` si legge. `()` legge tutto (D129). |

**Ritorna** un `Document`. La diagnostica sul file grezzo (audit, INSERT non
esplosi, Z≠0, duplicati rimossi, tipi non ri-materializzabili in output) finisce
in `doc.warnings`; `topo.validate(doc)` la rilancia.

**Solleva** `FileNotFoundError`, `EnvironmentError` (DWG senza `ODA_PATH`),
`RuntimeError` (conversione DWG fallita), o le eccezioni di lettura di `ezdxf`.

```python
doc = topo_dxf.load_dxf("pezzo.dxf", tolerance=0.5,
                     role_rules=topo.name_rules({"Piega": "bending", "MARK": "engrave"}))
for w in doc.warnings:
    print("loader:", w)
```

Quando l'intenzione sta nello stile della linea, o in una combinazione di
nome e stile:

```python
doc = topo_dxf.load_dxf("pezzo.dxf", role_rules=[
    topo.RoleRule("construction", name_contains="constr", dashed=True),
    topo.RoleRule("bending", dashed=True),
    topo.RoleRule("engrave", color="cyan"),
])
```

Vedi `14_style_classification.py` per un esempio completo (una regola per
step, su un file reale in `tests/examples/`).

#### DWG

**`topo` non legge il DWG da solo, e nemmeno `ezdxf`.** Il DWG è un formato
chiuso: il "supporto DWG" di `ezdxf` è l'addon `odafc`, che è un wrapper attorno
a **ODA File Converter** — converte il `.dwg` in un `.dxf` temporaneo e `ezdxf`
rilegge quello. `topo` usa esattamente questo (`topo_dxf/loader.py`).

Per aprire un `.dwg` serve quindi:

1. **ODA File Converter** installato — download gratuito:
   <https://www.opendesign.com/guestfiles/oda_file_converter>
2. `topo` deve trovare l'eseguibile. Due modi:
   - variabile d'ambiente **`ODA_PATH`** = *full path dell'eseguibile*
     (non la cartella — se ODA è in `ODAFileConverter X.Y.Z\`, il path deve
     includere `\ODAFileConverter.exe`);
   - oppure `ODAFileConverter` raggiungibile dal `PATH` di sistema.

Impostare `ODA_PATH`:

| SO | comando |
|---|---|
| Windows, permanente | `setx ODA_PATH "C:\Program Files\ODA\ODAFileConverter X.Y.Z\ODAFileConverter.exe"` — poi **riapri il terminale** |
| Windows, solo sessione (PowerShell) | `$env:ODA_PATH = "C:\...\ODAFileConverter.exe"` |
| Windows, GUI | Impostazioni → *Modifica le variabili di ambiente relative al sistema* → *Variabili d'ambiente…* → *Nuova* |
| Linux / macOS, permanente | `export ODA_PATH="/opt/ODAFileConverter/ODAFileConverter"` in `~/.bashrc` o `~/.zshrc`, poi riapri la shell |
| Linux / macOS, solo sessione | `export ODA_PATH="/opt/ODAFileConverter/ODAFileConverter"` |

Guide di riferimento per le variabili d'ambiente:
[Windows](https://learn.microsoft.com/windows/win32/procthread/environment-variables) ·
[Linux/macOS (`export`)](https://www.gnu.org/software/bash/manual/bash.html#Environment).

Se manca tutto, `load_dxf` su un `.dwg` solleva `EnvironmentError` con il link e
questa stessa guida nel messaggio.

---


### `document_from_msp`

```python
topo_dxf.document_from_msp(
    msp,
    tolerance=0.05,
    role_rules=(),
    ignore_layers=None,
    source_path="",
    skip_layers=SKIP_LAYERS,
) -> Document
```

Costruisce un `Document` da un `modelspace` `ezdxf` **già aperto**. Utile per
i test o per geometria generata a mano. **Non** fa audit / upgrade / sanitize: si
assume che il `msp` sia già pronto. `role_rules`, `ignore_layers`,
`skip_layers` funzionano come in `load_dxf()` — vedi sopra.

```python
import ezdxf
doc_ez = ezdxf.new("R2010"); msp = doc_ez.modelspace()
msp.add_line((0, 0), (100, 0)); msp.add_line((100, 0), (100, 50))
# ...
document = topo_dxf.document_from_msp(msp, tolerance=0.5)
```

### `to_dxf`

```python
topo_dxf.to_dxf(
    result: Result,
    source_doc: Document = None,
    filter_cluster=None,
    include_annotations=True,
    include_trash=True,
    annotation_layer="Annotation",
    role_styles: dict[str, RoleStyle] = None,
    layers: dict[str, str | Callable[[object], str]] = None,
    allow_invalid: bool = True,
    exclude_types: set[str] = None,
) -> ezdxf.document.Drawing
```

Materializza il modello in un **documento DXF nuovo** (R2010). Non rilegge mai
entità dalla sorgente: `source_doc` serve solo a riportare gli header
(`$INSUNITS`, `$MEASUREMENT`). Testi e quote arrivano da `result.annotations`.

| parametro | significato |
|---|---|
| `filter_cluster` | `callable(Cluster) -> bool` — scrive solo i cluster che passano; trash e annotazioni si scrivono tutti. Per un file per parte la parte viene da `topo.split` (§3), che li ha già divisi. |
| `exclude_types` | set di `dxftype` da togliere dal documento (es. `{"TEXT"}`). |
| `include_trash` | `True` (default): la geometria non classificata va sul layer `Trash`. Chi apre il file deve poter vedere ogni entità del disegno di partenza. |
| `allow_invalid` | `True` (default): un `result` non valido viene scritto lo stesso (trash e annotazioni), come fa `to_svg`. `False` → `ValueError`: per il chiamante che consegna il file a una macchina (D83). |
| `layers` | dove va ogni ruolo: `{ruolo: "Nome"}`, o `{ruolo: funzione(elemento) -> nome}` per dividere le entità di un ruolo su più layer guardando l'elemento scritto (il `Contour`, l'elemento di `cluster.detected`, l'entità trash o l'`Annotation`). Un ruolo che non nomini resta al default dell'adapter: `OuterContour`, `InnerContour`, `Trash` per `unknown`, lo slug per ogni altro ruolo (D31, D128). |
| `role_styles` | come si disegna ogni ruolo: `{ruolo: RoleStyle}` (vedi sotto). Agisce sul layer — tutto si scrive BYLAYER — e su un layer di più ruoli vince il primo scritto. Un ruolo con uno stile ha il suo layer anche senza entità. Sotto c'è sempre la palette di topo (`DEFAULT_ROLE_STYLES`): la mappa aggiunge i ruoli del chiamante e cambia solo i campi che dà. |
| `annotation_layer` | il layer di testi e quote **senza ruolo** (default `"Annotation"`). Un'annotazione con un ruolo va sul layer del suo ruolo, come un edge (D127, D128). Nessuna annotazione viene mai scartata. |

Le mappe sono del chiamante e valgono per la sua chiamata: topo non ne tiene
nessuna (D128). Un consumatore pubblica le sue (`snapbend.flat.ROLE_STYLES`,
`snapbend.flat.LAYERS`) e chi esporta le passa, o le compone:

```python
# la cornice (ruolo "frame", assegnato da un consumatore come snapdraw) in nero, su "Cornice"
topo_dxf.to_dxf(result, doc,
            layers={"frame": "Cornice"},
            role_styles={"frame": topo.RoleStyle(color=(0, 0, 0))})

# le pieghe su due layer, secondo il verso (un'informazione dell'elemento)
topo_dxf.to_dxf(result, doc, layers={"bending": lambda bend: "BendUp" if is_up(bend) else "BendDown"})   # is_up: del chiamante
```

**L'overlay** (D70, D90): scrive ogni collezione di `cluster.detected`,
senza conoscerne nessuna per nome. Di un elemento legge solo `role` e
geometria: `item.contours` se c'è (ognuno con `segments`/`styles`/`polygon`
ed eventualmente un suo `role`), altrimenti l'elemento stesso. Un contorno
con `polygon` si scrive chiuso (LWPOLYLINE/CIRCLE), uno senza come una entità
per primitiva (LINE/ARC/SPLINE). Il `role` di un contorno vince su quello
dell'elemento solo se non è un ruolo del motore (`outer`/`inner`/`unknown`).
Senza ruolo o senza geometria si salta.

**Ritorna** un `Drawing` `ezdxf`. Sta a te fare `doc_out.saveas(...)`.

**Solleva `ValueError`** solo con `allow_invalid=False` e `result.is_valid`
`False`. Il rifiuto non è del formato, è di chi consegna il file a una macchina:
quel chiamante lo chiede esplicitamente.

```python
topo_dxf.to_dxf(result, doc).saveas("guarda.dxf")                         # sempre
topo_dxf.to_dxf(result, doc, allow_invalid=False).saveas("macchina.dxf")  # solo se valido
```

---

### `split_to_files`

```python
topo_dxf.split_to_files(
    doc: Document,
    output_folder,
    label="",
    source_file="",
    tolerance=None,
    namer=None,
    include_annotations=True,
    min_area=50.0,
    exclude_types=None,
    annotation_layer="Annotation",
    is_structural=None,
    role_styles=None,
    layers=None,
) -> Result
```

Flusso multi-pezzo + salvataggio su disco: `topo.heal → topo.split →
to_dxf + .saveas()` per parte (`is_structural` passa a `heal`;
`include_annotations`, `annotation_layer`, `role_styles`, `layers`,
`exclude_types` a `to_dxf`). È un ciclo che puoi scrivere tu (§3, `split`).
Una lettura di processo (fori, pieghe) si fa sul result con `heal` + la
detection + `split`, non qui. **È l'unica funzione che scrive su disco.**
Il nome file è `f"{cluster.label}.dxf"`, dove `cluster.label` è quello che assegna
`namer(i, cluster)`; senza `namer` diventa `f"{label}_P{i+1}"` (es. `batch_P1.dxf`).

**Ritorna** il `Result` (per poterci fare `save_json` dopo). Se il risultato
non è valido, ritorna il result senza scrivere niente.

```python
result = topo_dxf.split_to_files(doc, "output/", label="batch")
topo.save_json(result, "batch.json")
```

---

### `inspect_dxf` / `inspect_file`

```python
topo_dxf.inspect_dxf(path, entities=True, limit=40) -> None
```
**Livello 1** — entità DXF grezze: versione, header, conteggio per tipo e per
layer, dettaglio di ogni entità. Non tocca `topo`.

```python
topo_dxf.inspect_file(path, tolerance=0.05, role_rules=(),
                   run_heal=True, entities=True, coords=False) -> None
```
Orchestratore: apre il file e stampa i tre livelli in fila. `run_heal=False` per
fermarti al `Document`. `role_rules` come in
`load_dxf()`.

```python
topo_dxf.inspect_file("pezzo.dxf", role_rules=topo.name_rules({"Piega": "bending"}))
topo_dxf.inspect_file("pezzo.dxf", role_rules=[topo.RoleRule("bending", dashed=True)])
```

### `write_metadata_to_dxf` / `read_metadata_from_dxf`

```python
topo_dxf.write_metadata_to_dxf(doc, cluster: Cluster, extra: dict = None) -> None
topo_dxf.read_metadata_from_dxf(doc) -> dict
```

Scrive / rilegge i metadati (stessi campi di `save_json`, `extra` incluso —
un dict diretto qui, non una callback, perché opera già su un singolo
cluster; sotto c'è `topo.build_metadata`) come XDATA `TOPO` sull'entità del
layer `OuterContour`. `doc` è un
`Drawing` `ezdxf` (tipicamente quello restituito da `to_dxf`). `read_`
ritorna `{}` se non trova niente.

```python
doc_out = topo_dxf.to_dxf(result, doc)
topo_dxf.write_metadata_to_dxf(doc_out, result.clusters[0])
doc_out.saveas("out.dxf")
# più tardi:
meta = topo_dxf.read_metadata_from_dxf(ezdxf.readfile("out.dxf"))
```

### I layer di default

topo non ha layer (D123); questi sono i default dell'adapter, quando il
chiamante non passa `layers=`:

| nome | valore | |
|---|---|---|
| `topo_dxf.LAYER_OUTER` | `"OuterContour"` | ruolo `outer` |
| `topo_dxf.LAYER_INNER` | `"InnerContour"` | ruolo `inner` |
| `topo_dxf.TRASH_LAYER` | `"Trash"` | ruolo `unknown` |
| `topo_dxf.LAYER_ANNOTATION` | `"Annotation"` | testi e quote senza ruolo |
| `topo_dxf.DEFAULT_LAYERS` | `{ruolo: layer}` | i tre ruoli del motore |
| `topo_dxf.SKIP_LAYERS` | `("Trash", "Annotation")` | quelli che `load_dxf` salta rileggendo |

```python
topo_dxf.role_to_dxf_layer(role, element=None, layers: LayerMap = None) -> str
```

Il layer di un ruolo come lo sceglie `to_dxf`: la mappa del chiamante (un
nome, o la funzione chiamata con `element`), altrimenti il default, altrimenti
lo slug del ruolo (D31). `LayerMap` è il tipo di quella mappa:
`Mapping[str, str | Callable[[object], str]]`.

```python
topo_dxf.role_to_dxf_layer("hole", layers=snapbend.flat.LAYERS)   # "Hole"
topo_dxf.role_to_dxf_layer("frame")                               # "frame"
```

---

## 10. `topo_pdf` — l'adapter PDF

```python
topo_pdf.load_pdf(path, snap_tolerance=0.15) -> list[Edge]     # pip install g-topo[pdf]
```

**Sperimentale** (MAP.md D10): apre un PDF, estrae le geometrie vettoriali
di ogni pagina, le porta in mm con l'asse Y cartesiano e le ripulisce con uno
snap dei nodi vicini. Ritorna una lista di `Edge`, **non un `Document`**:
non si passa ancora a `topo.heal()`, e l'API può cambiare o sparire. Il lavoro
sul PDF si riprende qui (TODO.md, strada verso la 1.0, punto 0.7).
