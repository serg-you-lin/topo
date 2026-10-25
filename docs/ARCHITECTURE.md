# topo — architettura

Questo documento spiega *come è fatto dentro* e *perché*. Per l'uso pratico
dell'API vedi [`API.md`](API.md).

---

## L'idea in una frase

`topo` non è una libreria DXF. È un **motore di ricostruzione topologica**
che non conosce alcun formato di file: geometria e ruoli, mai layer (MAP.md
D123). I formati entrano ed escono da adapter, pacchetti fratelli nella stessa
distribuzione (`topo_dxf`, `topo_pdf`). Prende geometria 2D rumorosa e produce un modello
geometrico consistente e senza perdite: contorni chiusi, gerarchia di
contenimento, testi, e un overlay aperto per le feature rilevate. Non
conosce nessun mestiere: dire cosa significa un contorno o una linea è
un'interpretazione, e sta nei consumatori (MAP.md D88).

Il DXF è solo il primo formato implementato, e sta fuori da topo: `topo`
non importa `ezdxf` né un adapter, e si installa senza (`pip install g-topo`;
`g-topo[dxf]` porta `topo_dxf` con `ezdxf`). Il core non sa cosa sia un arco o
una spline in quanto entità di CAD — lavora su primitive geometriche pure.

---

## Il principio: il prodotto è il modello

```
                                  ┌──────────────┐
  DXF / DWG ── topo_dxf ─────────►│              ├── topo_dxf ──► DXF (to_dxf)
  PDF ──────── topo_pdf (sperim.)►│    Result    ├──────────────► JSON / XML (save_json, save_xml)
  geometria ── load_segments ────►│  il modello  ├──────────────► view model (to_view_model)
                                  │              ├──────────────► SVG (to_svg, save_svg)
                                  │              ├──────────────► testo per un agente AI (to_text)
                                  └──────┬───────┘
                                         └── split ──► un Result per parte, poi uno qualunque dei render
```

Il `Result` è **il prodotto**. Tutti i `to_*` sono renderer del modello.
`to_dxf` **non rilegge mai il file sorgente** — disegna dal modello. Questo è il
motivo per cui `to_svg` produce la stessa identica immagine senza una riga di
codice nuova nel core.

Conseguenza pratica: **niente si perde**. Si importa tutto — quote, centerline, spazzatura. 
Perché `topo` non perda
niente, il modello è abbastanza ricco da tenere anche ciò che non ha classificato:

- geometria chiusa ricostruita → parti / contorni interni / feature (se una lettura le aggiunge)
- ogni curva che non è contorno di nessun cluster → `result.loose`
  (segmenti puri, formato-indipendenti; `cluster_ref` dice quale cluster la
  contiene, D137). Cosa sia lo decide un consumatore, che la sposta in
  `cluster.detected` con `topo.promote`
- testi → `result.texts` (`Text`, un tipo solo, D138: la stringa, la
  polilinea che indica, i punti fra cui è stato misurato il numero, e
  l'immagine disegnata attorno come primitive)

I tipi di entità che `topo` non modella (`HATCH`, `IMAGE`, `TABLE`, `3DFACE`,
`XLINE`…) restano fuori, ma `load_dxf` emette un warning che li elenca — nessuna
perdita silenziosa.

---

## La struttura

Una distribuzione (`g-topo`), tre pacchetti importabili nella radice del repo
(MAP.md D124, D129):

```
topo/             IL MOTORE — nessun formato, nessun ezdxf / PyMuPDF
topo_dxf/         ADAPTER DXF/DWG                      (conosce ezdxf; extra [dxf])
│                     consumer di topo: solo nomi pubblici, mai topo.core (D125)
├── loader.py         load_dxf, document_from_msp       (+ adapter, parser, sanitize,
│                                                         text_extractor, mtext)
├── writer.py         to_dxf                            (+ exporter: segmenti → entità)
├── layers.py         i layer di default, SKIP_LAYERS, role_to_dxf_layer
├── xdata.py          write/read_metadata_to_dxf
├── recipes.py        split_to_files — heal + split + to_dxf + salvataggio
└── inspect.py        inspect_dxf, inspect_file
topo_pdf/         ADAPTER PDF — sperimentale, congelato (conosce fitz; extra [pdf])
```

Dentro `topo/`:

```
topo/
├── core/         MOTORE geometrico puro               (zero formato)
│   ├── primitives/   LineSeg, ArcSeg, BSplineSeg, CircleSeg, EllipseSeg + discretizzazione;
│   │                 fitting.py: primitive da una sequenza di punti (simplify_points)
│   ├── topology/     edge.py, grafo dei nodi, ricerca loop;
│   │                 noding.py (rete piana), outer_face.py (faccia esterna)
│   ├── healing/      chiusura gap, normalizzazione (+ tassellature), gerarchia,
│   │                 islands.py (isole per vicinanza), steps.py (i passi di heal)
│   ├── geometry/     LA GEOMETRIA, `topo.geometry` (D95): fatti con nomi geometrici
│   │                 — shape (forma, cerchi concentrici, archi attorno), lines
│   │                 (corde, file collineari), axis (rettangoli coperti) — e i
│   │                 mattoni measure / points / intersections
│   ├── geometry_input.py load_geometry / load_segments — geometria pura, non un
│   │                 formato: un ingresso di topo, non un adapter (D123, D125)
│   ├── heal.py       heal()             — lettura dall'interno: file → modello
│   └── island.py     island()           — lettura per isole, dall'esterno
│
├── model/        IL DOMINIO topo                     (dataclass pure + shapely)
│   ├── document.py   Document
│   ├── result.py     Result
│   ├── cluster.py    Cluster — il contenitore, `detected` è l'overlay
│   │                 di un consumatore (vocabolario aperto per nome — D44)
│   ├── detected.py   DetectedFeatures — il contenitore dell'overlay (D44, D90)
│   ├── curve.py      Curve → ClosedCurve / OpenCurve
│   ├── contour.py
│   ├── text.py       Text — i testi della sorgente (D138)
│   └── role.py       ContourRole = solo UNKNOWN/OUTER/INNER — il minimo
│                      che il motore usa. Nessun ruolo di un consumatore qui
│                      (D47, "roles out of core")
│
├── tools/        STADI opzionali su un Document/Result (il caller sceglie quali e in che ordine)
│   ├── anchor.py         anchor_texts()         — àncora i testi ai cluster
│   ├── inject.py         inject()                — testi del cluster → data_injector esterno
│   ├── non_contour.py    non_contour_candidates() — stesso criterio non-contorno
│   │                     di heal() (D49), esposto per decidere `edge.role`
│   │                     PRIMA di heal() (D55) — lavora su Document
│   ├── rotate.py         rotate_*() (sperimentale, D46)
│   ├── split.py          split() — un Result per parte, senza formato (D129)
│   └── strips.py         facing_boundaries(), link(), unconnected_regions(), open_boundaries() (D134, D142)
│
├── io/           RENDERER del modello senza dipendenze di formato
│   ├── svg.py        to_svg(), save_svg()  (fuori dalla 1.0 stabile, D133)
│   ├── view_model.py to_view_model()  (fuori dalla 1.0 stabile, D133)
│   ├── text.py       to_text(), save_text()  (sperimentale, D84)
│   └── exporter.py   build_metadata / save_json / save_xml
│
├── rules/        REGOLE di dominio                     (schema, validazione)
└── inspect.py    ispezione: inspect_document, inspect_result (il livello del
                  file è dell'adapter: topo_dxf.inspect_dxf)
```

`pipeline/` non esiste più (MAP.md D22): metteva insieme tre cose diverse —
`heal` (ora in `core/`), gli stadi opzionali (`tools/`) e i renderer
(`to_dxf`, poi in `io/` e oggi in `topo_dxf`; `split`, oggi in `tools/`). D22 diceva anche
che `heal` è "l'atto unico del motore": non è più vero (D58) — il motore ha due
letture, `heal()` e `island()`, che compongono gli stessi ingredienti del core
in modo diverso e riempiono lo stesso modello. Il prodotto è il modello, non
una delle due ricette.

**Regola di dipendenza** (controllata da `scripts/gen_index.py --check`,
in `pyproject.toml`):

- `topo` non importa mai `ezdxf`, `fitz`/`pymupdf`, `topo_dxf`, `topo_pdf`:
  non sa che gli adapter esistono (D123, D129). Un test lo prova anche a
  runtime: `import topo`, `heal`, `split` in un processo dove ezdxf e PyMuPDF
  non si possono importare.
- un adapter non importa `topo.core`/`tools`/`io`/`rules`, né l'altro
  adapter: solo i nomi pubblici (`topo`, `topo.model`, `topo.primitives`,
  D125). Quello che un adapter si trova a dover prendere da dentro è un nome
  pubblico che manca.
- dentro `topo`, `core` e `model` non importano mai `tools` né `io` (D44).
  Quando `model/` deve comunque annotare un tipo che vive in `tools/` (es.
  `Cluster.detected`), lo fa solo sotto `TYPE_CHECKING` — zero import a
  runtime, `from __future__ import annotations` rende l'annotazione una
  stringa pigra.

Il core non sa da dove viene la geometria. Spostare un adapter in un repo suo,
un giorno, è spostare una cartella: il confine è già pulito.

---

## Il flusso, passo per passo

### 1. `topo_dxf.load_dxf` → `Document`

L'adapter DXF, unico codice che legge `ezdxf`; un `Document` può venire anche
da `topo.load_segments`/`load_geometry` (geometria in mano, nessun formato).
In ordine:

1. se `.dwg` → conversione via ODA File Converter
2. `readfile`
3. `audit` (i testi vengono estratti **prima**: l'auditor di ezdxf
   cancella le quote che referenziano un blocco geometria mancante)
4. upgrade a R2010 se il file è legacy (R12/R13/R14)
5. explode degli `INSERT` (default `True` — un blocco non esploso fa sparire la
   sua geometria)
6. sanitize: normalizzazione OCS, appiattimento Z ≠ 0, deduplica
7. traduzione: ogni entità → uno o più `Edge`; ogni testo/quota → un
   `Text`. I layer che il writer usa per `loose` e testi
   (`SKIP_LAYERS`) si saltano, così un file già passato da topo si rilegge
   pulito (D129)

Dopo questa funzione l'oggetto `ezdxf` sorgente **sparisce**. Tutto il resto
lavora sul `Document`.

### 2. `heal` → `Result` (topologia)

Il passo difficile. Lavora su `doc.edges`, zero `ezdxf`. `heal()` è una
ricetta: ogni passo è una funzione pubblica in `core/healing/steps.py` (D62),
`heal()` le compone in quest'ordine e scrive i warning che le raccontano. Un
consumatore (snapdraw) compone gli stessi passi come gli serve.

1. **normalizza** (`merge_collinear_overlaps`, `merge_cocircular_overlaps`,
   `weld_degenerate_linesegs`): rette e archi tracciati a spezzoni fusi,
   `LineSeg` sotto 0.05 mm saldati in un nodo (D50, D52, D56)
2. **estrae** (`split_labeled`) gli `Edge` con ruolo deciso e non strutturale
   (qualunque ruolo che un consumatore assegna, con `role_rules` o prima di
   `heal`): non entrano nel grafo, non sono contorno. Il predicato è
   `model/role.is_structural_role` (D30); è il punto d'aggancio per un
   consumatore che marca la geometria prima di `heal` (snapdraw) —
   `topo.non_contour_candidates(doc)` (D55) espone lo stesso criterio del
   passo 4 sotto, per decidere QUALI edge marcare qui
3. **chiude i gap**: prima un arco quasi completo coi capi liberi diventa
   cerchio (`close_near_full_arcs`: gap entro `tolerance` e angolo mancante
   entro 2°), poi gli estremi liberi entro `tolerance` (`close_free_gaps`),
   accoppiati due a due per vicinanza, portati alla loro intersezione reale.
   La tolleranza misura un gap, non un lato: un elemento più corto di lei
   resta (D112)
4. **detection non-contorno** (`find_non_contour_edges`): le catene di
   `Edge` attraverso nodi di grado 2 (`Graph.chains`, D131) che finiscono su
   due nodi di branching distinti (grado > 2) e che il bordo della faccia
   esterna della loro componente non percorre una volta sola (una corda, un
   ponte) non sono contorno (D111, riapre D49) — escono dal grafo, intere,
   per non rompere la ricerca dei loop. `heal` non
   decide cosa siano: lo decide un consumatore, a modo suo
5. **ricerca loop** (`find_loops` → `LoopSearch`, che dice quale gradino ha
   chiuso), con una scala di strategie sempre meno esatte:
   - grafo esatto (uguaglianza delle tuple arrotondate)
   - se restano estremi liberi (D57): clustering degli endpoint entro
     `tolerance` per trovare gli angoli "quasi chiusi", poi chiusura vera
     all'intersezione (`repair_merged_corners`)
   - se non chiude ancora: loop sul grafo clusterizzato tollerante (con
     warning: la discrepanza sopravvive nell'output)
   - se nessun gradino chiude, `heal()` passa all'ultima spiaggia:
     `polygonize_edges` sui segmenti discretizzati, che dà già i contorni
     (`polygons_to_curves`, geometria nativa persa)
6. **loop → curva** (`structural_loops`, `loops_to_curves`): un loop con un
   edge di ruolo non strutturale non è contorno; un loop senza area (o un
   micro-cerchio) torna come curve aperte, che finiscono in `loose` (D151)
7. **costruzione gerarchia** (`build_hierarchy`): quale loop contiene quale →
   albero di contenimento `outer` / `inner`. `heal` si ferma qui: **non** dà un
   significato ai contorni interni (D15) — ogni loop contenuto è un `Contour`
   in `cluster.inners`.

Se non si forma **nessun** contorno esterno chiuso, il risultato è dichiarato
**non valido** (`is_valid = False`) — come il modelspace vuoto. `topo_dxf.to_dxf` e
`to_svg` lo disegnano lo stesso (tutto in `loose`) per farti vedere cosa ha capito
topo; rifiutarlo è scelta del chiamante che consegna a una macchina
(`allow_invalid=False`, D83).

`validate_result` viene chiamata automaticamente alla fine.

### 2b. `island` → `Result` (lettura per isole)

L'alternativa a `heal` per un disegno di **viste** (più viste su un foglio,
isometriche, 3D proiettato). `heal` cerca il pezzo dall'interno, per
connettività: su una vista proiettata più spigoli quasi coincidenti convergono
sugli stessi nodi e non c'è nessun segnale locale per scegliere quale prosegue
come contorno. `island` parte da un fatto globale, cosa sta fuori:

1. **estrae** gli `Edge` con ruolo deciso e non strutturale, come `heal` (D30):
   è così che un consumatore toglie cornice, cartiglio, cerchi di ingrandimento
2. **pezzi**: gli edge che si toccano entro `max_gap` (`spatial_islands`):
   nessuna nozione di chiusura, quindi nessuna ambiguità di grafo. Nessuna
   distanza fra le viste: quella dipendeva da come è impaginato il disegno,
   che topo non conosce (D99)
3. per ogni pezzo **normalizza** sulla griglia fine della rete: nodi dagli
   estremi reali, catene tassellate rifittate come archi/spline, merge/weld di
   `heal`, gap fino a `max_gap` senza mai spostare un estremo più di così
   (anche `max_gap` è del chiamante, D98)
4. **rete piana** (`split_at_crossings`): ogni incrocio diventa un nodo
5. **faccia esterna** (`outer_face`): si parte dal punto più a sinistra della
   geometria, a ogni nodo si gira il meno possibile in senso antiorario; un
   edge percorso andata e ritorno è una sporgenza (asse, segno)
6. **interno**: giri chiusi → `inners`, il resto in `loose`. Un'isola
   il cui contorno sta dentro quello di un'altra non è un cluster: diventa
   interno della più esterna che la contiene

Stesso contratto di `heal`: un `Result`, un `Cluster` per isola, e
`split` e i renderer non sanno quale lettura l'ha prodotto. Cosa sia
un'isola (vista, pezzo, cornice) lo decide chi chiama (D21). `island` non
chiama mai `heal`.

### 3. la lettura di un consumatore (fuori da topo)

Cosa significa un contorno o una curva è la lettura di un consumatore
(MAP.md D88): la fa sopra il `Result` e la attacca a `cluster.detected` (D44) — non a campi fissi del cluster. topo non conosce
nessun nome dell'overlay: `cluster.features(name)` legge una collezione per
nome, `[]` se `detected` è `None` o quel nome non è stato scritto. I renderer
disegnano ogni elemento dal suo `role` e dalla sua geometria (D90), e l'area
netta toglie gli elementi che si dichiarano vuoti del pezzo (`is_void`).

### 4. un Result per parte — `split`

`topo.split(result)` sceglie le parti sul modello (`min_area`, `namer`) e dà
un `Result` per parte, con le curve sciolte e i testi che le
appartengono: una curva va al cluster del suo `cluster_ref`, un testo
alla parte che lo contiene; se nessuna, alla più vicina fra tutte — niente
duplicato, niente perso (D124, D129). Nessun formato: ogni renderer prende un
`Result`, quindi una parte va in DXF, SVG o testo allo stesso modo.

### 5. render — `topo_dxf.to_dxf`

Costruisce un documento `ezdxf` **nuovo** (mai il sorgente) e ci scrive i
segmenti puri del modello, ognuno sul layer che il chiamante sceglie per il
suo ruolo, o su quello di default dell'adapter (vedi la tabella nel README e
`API.md` §9). Regole di fedeltà:

- **le spline** si riemettono come `SPLINE` native, ricostruite da control points
  / knots / weights / degree (D135) — **mai discretizzate a polilinea**
- **l'overlay**: un contorno chiuso (una `ClosedCurve`, un vuoto `is_void`,
  segmenti che chiudono un giro — `model.feature_closed`) si scrive chiuso, gli altri come N
  entità native (`LINE`/`ARC`/`SPLINE`/`CIRCLE`), **mai come `LWPOLYLINE`**
  (D90) — così esce una curva aperta attaccata da un consumatore
- **`loose`** si scrive sempre, sul layer del ruolo di ogni curva (`Trash`
  per `unknown`)
- **i testi** si riscrivono tutti, quelli del `Result` che riceve (con la
  loro immagine `rendered` se ce l'hanno): in un file per parte, quelli che
  `split` ha dato alla parte

### 6. export / inject

`save_json` / `save_xml` scrivono i metadati per parte secondo lo schema
(`rules/metadata_schema.py`), fondendo tre livelli (D44): `cluster.summary`
(conteggio grezzo, generico, sempre disponibile — `{nome}_count` per ogni
collezione attaccata a `cluster.detected`), `cluster.custom`, ed
`extra`/`extra_metadata` — un
dizionario o una callback esplicita del chiamante (stesso idioma di
`data_injector`) per una detection propria che topo non può conoscere.
`inject` serve solo a passare i testi dentro l'outer a un `data_injector`
esterno che restituisce codice / materiale / spessore, e a metterli in
`cluster.custom`.

---

## Due concetti che tornano ovunque

### La tolleranza

`tolerance` (default 0.05, i golden usano 0.5) è il gap più largo che topo può
chiudere. **Non** arrotonda i nodi: ogni endpoint va su una griglia unica
(`NODE_DECIMALS` = 3 decimali, MAP.md D113), la stessa per `heal()` e `island()`
e per qualunque tolleranza, così due capi diventano lo stesso nodo solo se
coincidono davvero. Serve in tre modi:

1. **gap fra nodi del grafo tollerante** (`find_loops`, ultimo gradino): capi
   entro `tolerance` fusi per distanza, mai i due capi dello stesso edge (D112)
2. **chiusura gap**: due endpoint liberi entro `tolerance` vengono congiunti
   prolungando i segmenti
3. **nodo per contatto** (`split_at_crossings`, D101): un estremo che giace
   entro `tolerance` sulla curva di un altro edge è un nodo — non solo
   estremo-su-estremo, anche estremo-su-curva (un vero contatto a T), format-
   agnostico, indipendente da come il file è stato disegnato. E due tagli
   entro `tolerance` l'uno dall'altro sono lo stesso nodo, non due: una retta
   quasi tangente a un arco incrocia in due radici matematicamente distinte
   ma vicinissime (una quasi-tangenza è numericamente instabile: una
   perturbazione minima dei dati di origine sposta parecchio il punto
   d'incrocio quando l'angolo è piccolo). Trattarle come due nodi lascia uno
   sliver fra loro che può spaccare in due una faccia che doveva restare una
   sola (MAP.md D100, la causa isolata e risolta alla radice da D101).

Un gap 4× la tolleranza **non** viene chiuso — è una scelta, non un bug: se il
file ha buchi grossi, o sono voluti o l'unità di misura è sbagliata. Workaround:
alza `tolerance`.

### Il doppio binario delle feature (role_rules / inferenza)

Ogni feature di un consumatore è raggiungibile per **due strade** (la
seconda la fa il consumatore, D88):

- **`role_rules`**: il chiamante dice "le linee del gruppo sorgente `A` hanno
  ruolo `a`", o "le tratteggiate con `constr` nel nome hanno ruolo `b`". Il ruolo è
  assegnato al load, è **autoritativo**, a valle non si rimette in discussione
  (`source="labeled"`, `confidence=1.0`). Il vocabolario dei ruoli è aperto —
  passa per `normalize_role` e non è un errore che topo (cioè il motore)
  non lo conosca. Cosa succede in `heal` dipende da `is_structural=...`
  (D47): senza, qualunque ruolo di un consumatore resta fuori dal grafo; con
  il predicato del consumatore, i ruoli che lui dichiara strutturali restano
  DENTRO il grafo (chiudono contorni del pezzo), gli altri restano fuori.
  L'output lo scrive su un layer DXF col nome dello slug (non
  `Trash` — non è spazzatura), geometria intatta (D27, D30, D31, D47).
  Una regola combina segnali neutri — nome del gruppo sorgente, tratteggio,
  colore — tutti veri insieme; le regole sono in ordine e vince la prima
  (D63). topo dà il meccanismo, il contenuto lo scrive il chiamante: nessun
  vocabolario di nomi vive in topo. Il nome resta nell'adapter, l'`Edge`
  riceve solo il ruolo. Tratteggio e colore sono quelli **effettivi**: un'entità
  `ByLayer` eredita lo stile dal layer che la contiene, e `DxfAdapter` lo
  risolve prima di consegnare un `EdgeStyle`, che non conosce parole di un
  formato (D126): tratto come segni con segno, colore in RGB. "Tratteggiata" vuol dire che il pattern ha
  almeno un vuoto — un fatto del pattern, non del nome del linetype.
- **inferenza geometrica**: il consumatore riconosce la feature dalla forma
  (`source="geometric"`, `confidence < 1.0`).

---

## Cosa NON è (ancora) pulito

Onestà sullo stato — dettagli e motivazioni sono in `MAP.md` (sezione
"Closed decisions"), non ripetuti qui:

- **`topo_pdf.load_pdf`** ritorna `list[Edge]` invece di un `Document` → non
  si aggancia a `heal()`. Congelato (MAP.md D10); il lavoro fermo nella
  cartella sorella `forge-pdf-adapter` si riprende qui (TODO, punto 0.7).
- **Il DWG** passa da ODA File Converter, un eseguibile esterno: `topo_dxf`
  lo chiama via l'addon `odafc` di `ezdxf`.
- **`heal()` con solo edge etichettati** (tutti con ruolo non strutturale):
  errore "Nessuna geometria chiusa trovata" e `loose` **vuota** — gli
  etichettati non ci arrivano, a differenza di ogni altro caso invalido.
  Comportamento di sempre, conservato tale e quale nella fase B (D62).

Tutta la storia dei refactor già chiusi (bridge/shape eliminato, dispatcher
entità→primitiva unificato, `Edge` spostato da `adapters/` a
`core/topology/`, ecc.) è nel log decisioni — vedi `MAP.md`.
