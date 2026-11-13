# topo — TODO

Solo ciò che resta da fare. Il perché di ogni scelta è in `MAP.md` (`D##`), la
cronaca nel git log. Misure, esiti e storia dei tentativi non stanno qui.

---

## Il cancello della 1.0 (D148, D249)

**Feature freeze.** Quando la lista è
vuota topo è *1.0-ready*: `python scripts/release_check.py` esce 0 e da quel
giorno ogni commit su `main` lo tiene a 0. Entra solo ciò che rompe un nome
pubblico, o rende vere e provate le invarianti di D143 sui fixture del repo,
più i documenti (D144) e la history pulita; il resto è 1.x (D158, D174).
Un difetto trovato prima della 1.0 entra nel cancello (D249); ogni test nuovo
si mostra rosso su un difetto vero prima di contare.

**Chiusi:** G1 (D150), G2 (→ 1.x, D149), G3 (D152), G4 (D145/D153/D154), G5
(D156), G6 (D103, D157), G6b (D163), G6c (D180), G6d (D189), G6e (D201), G7
(D220), G8 (D248), G9, G11, G12 (D165), G13 (D166–D168), G15 (D206/D209), G16 (D210),
G17 (D250).

**Aperti**
- [ ] **G14** Superficie allineata alle API di una libreria matura (D174,
      D175). Restano: la regola 8 (docstring pubbliche in inglese: G9 è chiuso,
      da verificare che basti) e il test di rimozione delle deprecazioni (vuoto
      finché non ce n'è una). I consumer si adeguano con le tabelle
      vecchio → nuovo di D176/D177, dalle loro sessioni (snapbend, snapdraw,
      smoother, pippo).
- [ ] **Pulizia del repo** (Federico): TODO.md, MAP.md e il resto non devono
      avere log di sessione; restano solo cose da fare e decisioni. TODO.md è
      fatto; resta MAP.md e il controllo del resto. In `tests/data/` resta solo
      ciò che un test usa: il resto si toglie.
- [ ] **Stato "alpha" via al rilascio**: `README.md:23` e `README_IT.md:23`
      ("alpha, l'API si muove ancora") diventano "stabile: i nomi pubblici non
      si rompono, si deprecano" (D174, D175); in `pyproject.toml` il
      classifier passa da `3 - Alpha` a `5 - Production/Stable`. Restano le
      frasi su `topo.experimental` e `topo_pdf`, che sono vere.
- [ ] **Licenza**: `LICENSE`, `pyproject.toml` e i due README dicono "All rights
      reserved", quindi nessuno può usare topo senza permesso scritto. Prima
      della 1.0 una licenza scelta da Federico.
- [ ] **G10** Rewrite della history (`git filter-repo` + `--message-callback`,
      un solo force-push) contro le liste di D76–D78. `audit_names --strict` è
      verde sui file di oggi. Dalla history il rewrite deve togliere: un codice
      tipo disegno scritto come riferimento in un commento di un test, già su
      GitHub e in più commit; i blocchi-logo definiti e mai usati dei fixture
      `anch_01…06` (D97); i file `tests/**/*healed*` (uscite di
      `11_batch_heal.py`, oggi fuori da git): fra quelli di `output_polylines/`
      alcuni nomi sembrano codici pezzo. Da guardare nell'audit anche i file di
      blocco AutoCAD (`.dwl*`) tracciati in `tests/data/mixed_pipeline/`: di
      solito portano nome utente e PC.
- [ ] **Tempo della suite** (D160, D212): ~3:22 seriale, sopra il tetto di
      2,5–3 min. Pesano `test_fidelity` sulle spline e le letture di
      `outlines()` (`TestScrambled` in `test_outlines_invariants`,
      `test_outlines_single_use`). Misurare il tempo prima e dopo ogni
      intervento. Da decidere:
      - `--full`: `TestScrambled` e la fedeltà sui fogli > 500 bordi solo con
        `--full` (mai scritto), più `test_outlines_single_use`;
      - `test_golden_split` su 7 padri ripete i confronti di
        `test_golden_faces` e non guarda i figli;
      - i test che provano un adapter vanno in `tests/adapters/dxf/` e
        `tests/adapters/pdf/` con un `conftest.py` che fa
        `pytest.importorskip`; dove metta `tests/golden/` è da decidere.
- [ ] **Generatore di disegni credibili**: compone forme vere (contorni con
      raccordi, cerchi e asole dentro, archi tangenti, spline, annidamenti) e le
      guasta come i file veri (piccoli buchi, ripassati, segmenti spezzati,
      versi invertiti, ordine rimescolato, rotazioni). La risposta è nota per
      costruzione: ogni disegno è un test senza golden. Nella suite pochi semi
      fissi; passate grandi a mano. Da decidere: `hypothesis` come dipendenza di
      test.
- [ ] **D208 non è in `MAP.md`**: è citata nel codice (`topo_dxf/exporter.py` e
      i test di esportazione: una polilinea non copre un salto con un vertice)
      ma la decisione non è scritta.

**Fuori dal cancello, ma prima di snapbend 1.0:** le suite dei consumer erano
rosse già prima di D150 (snapbend: 16 golden di processo con aree spostate di
~1 mm², probabilmente D145; snapdraw: 3 regressioni). Si giudicano nei loro
repo, mai rigenerando alla cieca.

## Dopo la 1.0 (1.x, additivo — non toccare finché il cancello è aperto)

**Difetti noti, fuori dal cancello (D237).** Fatti, nessuna analisi.
- `experimental.parity_faces` (D250): nei pareggi del T-join decide l'ordine
  delle coordinate; 108 dei 631 disegni di `tests/` si leggono diversi ruotati
  o specchiati (l'asola con la croce di `Multifeature.dxf`).
- `near-copy` (D237): l'avviso scatta anche su spigoli veri (coppie a 45–90°).
  Idea di Federico: alzare la soglia solo nello spicchio dei `points`
  dell'avviso; conta solo quando la lineetta serve a chiudere un esterno.
  `near_copies` (`topo/core/base/normalizer.py`) prende per copia ogni retta più
  corta coi due capi entro `distance` da una più lunga, senza chiedere parallele
  né sovrapposte.
- Una curva sola che incrocia se stessa non si taglia nell'incrocio
  (`split_at_crossings` taglia solo fra edge diversi): una spline di grado 1 a
  forma di quadrato 100×100 con un ricciolo sotto dà in `outlines()` 9900
  (l'anello intero, area con segno) invece di 10100 + il lobo in `loose`.
- Due curve chiuse semplici con il nodo dell'una sul bordo dell'altra (spline di
  grado 1, cerchi a 24 lati r 50 in (0,0) e r 40 in (90,0)): `outlines()` dà
  solo la prima (7764,6) e l'altra in `loose`; con il nodo 7e-5 dentro, un
  contorno da 12733,9.
- Un foro scritto a linee con un buco fra i capi (0,02–0,03 mm,
  `tolerance=0.1`) finisce in `loose`: `refit_tessellations` fa della catena
  aperta una spline sola e "i due capi dello stesso edge non sono mai un gap"
  (`compute_gap_fixes`). Circa 20 su 750 cerchi a caso.
- Un contatto dove una curva supera l'altra di pochi millesimi (retta oltre un
  arco di 0,003; spline oltre una retta di 0,004): l'arco si taglia
  all'incrocio, la retta no, i due punti finiscono nello stesso nodo →
  `close_contour_jumps` (D209) mette una retta nuova con un warning. Da fare: il
  capo si prolunga o accorcia lungo se stesso fino all'altra curva (come agli
  incroci); su una spline non si può prolungare, lì un segmento nuovo.
- Sweep dei disegni di snapdraw: restano da capire un disegno con un salto di
  0,84 mm negli inner (oltre la tolleranza 0,5, `is_valid=False`) e due fogli
  oltre 300 s. Il perché non è cercato.
- Rossi della forza bruta (`_debug/2026-11-06_topo_node-distance`,
  `_debug/2026-11-08_topo_forza-bruta-gruppi`): restano rossi, fuori dal
  cancello (Federico, 9 novembre). Da decidere col banco: "mosso" col bordo
  entro la tolleranza (D143) invece dell'area a 1e-5; il foro che una
  quasi-copia lascia aperto (D226) il controllo "risposta" lo conta rosso; un
  file vero con "mosso" che passa da 3 a 4 isole.
- Agganci dei testi persi con D161 (golden di `golden_anchoring/` accettati senza
  giudicarli): testi rimasti senza aggancio in anch_02 (3), anch_03 (1), anch_04
  (10), anch_05 (7), anch_07 (1); tipico un richiamo "M6 n°16 fori" legato a una
  figurina 6×3 e oggi a niente. Da guardare con snapdraw.
- D229: 18 nomi ancora doppi con contenuti diversi
  (`SAME_NAME_DIFFERENT_CONTENT` in `tests/package/test_one_copy.py`):
  `anch_01..08` in `golden_anchoring/` e `golden_outlines/` sono disegni diversi
  con lo stesso nome; gli altri 10 hanno una copia nella radice letta dai test
  unitari e una in `golden_faces/` letta dai golden. Per ognuno: quale contenuto
  resta, o un nome nuovo.
- D228: `target`/`references` sugli edge della rete, uguali per ogni lettura
  (oggi `anchor_elements`, sperimentale, non vede le curve aperte). Una forma
  nuova sola, poi promossa. I golden di aggancio sono fuori dalla suite, in
  `_archive/golden_anchoring/`: vanno bene come base dei golden futuri.
- `tests/engine/readings/test_non_structural_role.py`: righe senza ruolo
  (`unknown`) a 0,5 → `faces()` 0 cluster, `is_valid` False, 435 curve in
  `loose` su 475 edge. Con `is_structural=lambda r: True` e ruolo `x`: 0
  cluster, `loose` vuoto, warning "508 edge non di contorno esclusi dal grafo"
  → edge non consegnati da nessuna parte (D137?).

**Primo lavoro (deciso il 30 ottobre)**
- **Discretizzazione delle spline in Rust** (o almeno numpy): De Boor in Python
  è il costo singolo più grosso di `outlines()`. Numpy a blocchi scende solo da
  6,5 a 5,1 s (D169 chiede la misura per un core Rust).

**Altro**
- **Fusione delle curve quasi allineate / quasi coarcali** (D211, D226):
  funzione pubblica a parte, chiamata da chi usa topo sul risultato, con la
  soglia sua. Le letture non fondono mai due curve diverse del file. Oggi
  `outlines()` le fonde (`_contour`, `merge_runs` a 1e-3): da togliere quando
  c'è la funzione.
- **Precisioni**: in `core/` + `sanitize` ~40 soglie di coincidenza su 9 valori
  (1e-2 … 1e-12). Federico ha chiesto di uniformarle; D196 le tenne separate.
  Da decidere con una misura completa, non a tentativi.
- **`topo_dxf` e i `HATCH`**: D205 esplode già i tratteggi a pattern in `LINE`;
  restano da decidere gli altri tipi (riempimenti pieni, gradienti).
- **Ordine dei rami a un nodo in `_leaving_angle`** (D199, D201): la direzione
  si legge a `DIRECTION_SAMPLE`; una spline che lascia il nodo e passa oltre una
  retta vicina può rovesciare l'ordine, e la camminata dà un lobo per
  sporgenza (oggi lo salva l'unione di D100).
- **Togliere l'unione di D100** (`_faces_union_loop`, `_network`, `_on_nodes`,
  `UNION_GRID`, `rim.py`): rifà il noding sulle discretizzazioni e salda
  contatti che D180 esclude. Dopo la voce sopra; rifare le due misure di D199;
  `TestChordContactUnderMotion` diventa rosso.
- **Il ripiego D100 senza edge interi sul bordo dell'unione** restituisce `None`
  e vince il giro più piccolo; da sistemare in generale.
- I 3 residui della passata sui 121 disegni (D201).
- Costo accettato di D186: `heal()` raddoppia sui disegni a catene di tratti
  corti; ottimizzare, prima in Python, poi Rust.
- **Warning sui pezzi d'ingresso che coincidono** (un `CIRCLE` ripassato da una
  polilinea): difetto del disegno, topo lo dice e non ne cancella nessuno
  (D137). Oggi due cerchi r 2 a 0,05 (tol 0,1) escono 2 cluster, `is_valid`
  True. Da decidere con tutti gli avvisi: due contorni chiusi che si incrociano
  invalidano? avvisi come dati invece che frasi (D227)?
- **Terza lettura, la rete**: gruppi di pezzi che si toccano o si incrociano,
  coi punti di contatto, senza contorni né dentro/fuori.
- **In `outlines()` i pezzi dello stesso cerchio/retta si ricompongono anche in
  `loose`** (richiesta snapdraw/pippo): un cerchio attraversato da linee esce in
  archi aperti; estendere a `loose` la ricomposizione di D65, senza scegliere
  cicli (D161). Fino ad allora i consumer ricompongono da sé.
- **Griglia per le spline** (come D145/D153): `BSplineSeg.discretize` è adattiva
  sul proprio intervallo, un pezzo tagliato (D163) non dà gli stessi vertici
  dell'intera. Solo se si vede un difetto; nessun rosso oggi (D167).
- **Criterio del punto medio di `_refine_segment`**: su un tratto a S il medio
  cade sulla corda; oggi lo copre il campionamento fitto.
- **La forma dai punti, per PDF e visione**: `simplify_points` (D141) e
  `refit_tessellations` (D60) sono già geometria di topo; gli estremi ambigui di
  D185, oggi solo in un warning, come dato interrogabile sul `Result`. Il
  dettaglio del formato resta nell'adapter.
- **Report di scostamento di `heal()` per entità** (D149); **PDF** (`topo_pdf`);
  **modello `Curve`**, `as_analytic`, firma dei contorni (D121) e fatti di
  riconoscimento (si promuovono in una minor quando un secondo consumer li usa,
  D91/D118); **curve da equazione**; **strisce** (D142, promozione a
  `topo.geometry` quando un secondo chiamante le usa); **D147** (ponti sui T,
  branch `d147-t-ends`; `regr_04` peggiora); **snapfence**.
- **Bisettrice e offset**: nulla di simile in `topo.geometry` (vicino c'è solo
  `offset_from_line` e le strisce D142). In due minor: (1) primitive esatte,
  senza politica, in `core/geometry/` + `topo.geometry`: `offset_segment`
  (retta traslata, arco concentrico r±d, mai un poligono discretizzato) e la
  bisettrice di due tratti come `LineSeg` con `length` richiesta; stesso segno
  di `offset_from_line`. I due tratti NON devono toccarsi (il vertice è
  l'incrocio delle rette); se un tratto contiene il vertice → `ValueError`. La
  linea di mezzo fra parallele è un fatto a parte (`midline`). (2) offset di
  contorno (giunzioni, collasso, un contorno che si divide) in
  `topo.experimental` finché non regge D143; mai silenzioso. "Kerf" è l'uso di
  un consumer, non un nome di topo. Da decidere prima di scrivere: `side` o due
  funzioni; dove finisce la bisettrice (solo `length`).
- **Viewer** (`to_view_model` + `to_svg`, D133: fuori dalla 1.0 stabile): da
  rifare in una sessione a parte; non scala (su un foglio di viste pesa più del
  DXF di partenza) e non deve più discretizzare archi e cerchi (riapre D12;
  coordinate a 3 decimali nelle uscite di lettura, non in `to_dxf`).
- **Dipendenze** (D169): misurare i tempi di `heal()`/`outlines()` sulle
  fixture; inventario shapely/numpy → sostituto; poi un pezzo alla volta e a
  pari golden. Il noding resta a GEOS.

## Catalogo dei fatti geometrici futuri — 1.x, nulla deciso

Un elenco di candidati, non un impegno: ognuno passa dal triage di "Richieste
dalla superficie" (D139: non entra perché esiste altrove) e, se la firma non è
sicura, da `topo.experimental`. Cosa NON c'è già (controllato su `API.md` §
geometria): `contour_shape`, `concentric_groups`, `arcs_around`,
`splits_contour`, `bridged_runs`, `intersections`, `point_on_contour`,
`nearest_point`, `cut_by`, `contour_minus`, `contour_union`, `dash_line`,
`covered_rectangles`, `segment_length`, `length_inside`, `chord_angle_deg`,
`track_*`, i costruttori (`polygon`…`stadium`), le strisce D142
(sperimentali). Da controllare prima di scrivere: `core/geometry/integrals.py`
(centroide e momenti potrebbero già esserci) e `measure.py`.

**Regole d'ingresso** (tutte, per ogni voce): (1) vale anche se la geometria
arriva da un PDF senza layer (non-negoziabile 1); (2) esatta sulle primitive,
mai su un poligono discretizzato, salvo dirlo; (3) tipo restituito dichiarato,
dati posizionali e opzioni solo per nome (D175); (4) nessuna soglia del
consumer dentro, nessuna parola di processo (foro, piega, fresa, taglio);
(5) una **proprietà** come test, senza golden (es. bisettrice: stessa
distanza dalle due rette; offset: distanza d dall'originale, Hausdorff ≤ tol);
(6) scheda in `API.md` e riga in `docs/INDEX.md`. Sigle: **P** una primitiva,
**C** catena o contorno, **R** regione (più contorni).

**Onda 1 — piccole, esatte, senza politica** (candidate per la prima minor):
- P `offset_segment` e `bisector` (voce "bisettrice e offset" sopra), `midline`
  fra parallele (lista di tratti).
- P `tangent_at(seg, point)` e `normal_at`: la direzione di una primitiva in un
  punto; oggi privata in `strips.py` (`_tangent_at`, `_normal_toward`).
- P `angle_between(a, b)`: angolo fra due rette o direzioni (diverso da
  `chord_angle_deg`, che è di una corda).
- C `corner_angles(chain)`: angolo interno e verso di svolta a ogni vertice
  (oggi `_turn`, privato); giunzione liscia (tangente) o spigolo.
- P/C `distance(a, b)` esatta fra due primitive o catene, con la coppia di
  punti: promuove `gap`/`refine_gap` delle strisce.
- C `hausdorff(a, b)`: è già l'invariante di D143 nei test
  (`tests/invariants`); renderlo un fatto pubblico.
- C `convex_hull`, `oriented_bbox` (rettangolo di area minima),
  `min_enclosing_circle`, `width_range` (larghezza minima e massima, i
  calibri): deterministici, nomi puramente geometrici.
- C `centroid`, `inertia` (assi principali) se non già in `integrals.py`.
- C `is_convex`, `concave_vertices`, `is_simple` (non si autoincrocia),
  `orientation` (area con segno).
- P `arc_through(a, b, c)`, arco da bulge: costruttori, accanto a `circle_through`.
- P/C `transform` rigida (traslazione, rotazione, specchio) esatta su tutte le
  primitive; le affini non uniformi cambiano il tipo (un arco diventa
  un'ellisse): fuori finché non è deciso cosa restituiscono.

**Onda 2 — costruzioni con una politica da decidere:**
- C `fillet(a, b, radius)` e `chamfer(a, b, distance)`: costruiscono l'arco
  tangente a due rette e tagliano i tratti; l'inverso, "arco tangente a
  entrambi i vicini" (continuità di tangente), è una lettura strutturale che
  il consumer chiama raccordo.
- P `tangent_lines(circle, circle)`, tangenti da un punto a un cerchio,
  cerchio tangente a due rette di raggio dato.
- P `trim_to` / `extend_to`: un tratto fino all'incrocio con un altro tratto
  aperto. Il taglio contro una regione chiusa c'è già: `cut_by` (D118).
- C `offset` di catena aperta e di contorno chiuso (un meccanismo solo, lista
  di contorni, giunzione `round` di default, collasso mai silenzioso).
- R `contour_intersection`, differenza simmetrica: a fianco di `contour_union`
  e `contour_minus` con la stessa convenzione di input e di tolleranza.
- R somma/differenza di Minkowski di due contorni (l'offset ne è il caso del
  cerchio).
- C/R `clearance`: la distanza minima fra due contorni o fra un contorno e il
  bordo; relazioni tipizzate tolleranti (disgiunti, si toccano, si incrociano,
  tangenti dentro/fuori), da D134/D142.
- C simmetrie: asse di simmetria, simmetria rotazionale e ordine; congruenza
  di due contorni a meno di un moto rigido (la firma dei contorni, D121).
- R famiglie di tratti paralleli (6 novembre): direzione, passo, membri;
  giudicare la direzione di un tratto corto con l'errore dei suoi capi (un
  tratteggio tagliato sul bordo esce a 44,97°–45,09°). Un tratteggio da PDF o
  SVG si riconosce solo così; "è un tratteggio" resta del consumer (D210).
- R schemi ripetuti: contorni uguali legati da passo costante in linea o su
  cerchio (traslazione/rotazione), come fatto, non come "serie di fori".

**Onda 3 — algoritmi grossi, ognuno la sua lettura (D202 lascia lo spazio):**
- R asse mediale / scheletro, e lo scheletro retto (straight skeleton).
- R spessore locale (distanza dal bordo opposto lungo l'asse mediale):
  minimo e dove; lo "spessore minimo" di un consumer è questo numero letto.
- R decomposizione: in parti convesse, in rettangoli (generalizza
  `covered_rectangles`, che è solo sugli assi), in strisce.
- R partizione di una regione lungo i lati in comune (la lettura che spezza
  un assieme, "scelta A" in "Fili da ragionare").

**Curve (con "modello `Curve`" e "curve da equazione" sopra):** lunghezza e
ascissa curvilinea, curvatura e raggio in un punto, flessi, tangente di una
`BSplineSeg`; rifitto di una catena in rette e archi (biarchi) oltre
`simplify_points`; offset di una spline (approssimato, dichiarato tale);
ellisse: lunghezza d'arco, tangenti, offset (non è un'ellisse).

**Ordine proposto:** onda 1 in blocco, una minor; poi le singole voci di onda
2 su richiesta di un secondo consumer; l'onda 3 solo con una misura di tempo
e un golden di proprietà. Le voci che riguardano più di una primitiva
(`offset`, `fillet`, `trim_to`) condividono lo stesso nodo di partenza (la
giunzione fra due tratti): costruirlo una volta.

## Richieste dalla superficie

Un prototipo può importare da `topo.core` mentre esplora; un pacchetto
pubblicato no. Ogni import dal core di un prototipo è una richiesta. Si smista,
mai in automatico: **fatto geometrico** → nome pubblico (docs, test, D##);
**pezzo dell'algoritmo** → capire cosa il prototipo ricostruiva e offrire
quello; **scelta del chiamante** → resta nel prototipo. Un "no" si scrive qui
col perché. Dopo la 1.0 un nome utile ma non sicuro passa da
`topo.experimental`. Le richieste arrivano da `## Richieste a topo` nei
`TODO.md` dei consumer (`grep -n -A20 "## Richieste a topo" ../*/TODO.md`);
nemmeno il codice già scritto entra perché c'è (D139).

Aperte:
- **snapdraw `lab/`** (D122): `LoopFinder`, `segments_from_loop`,
  `edge_styles_from_loop`, `build_node_graph`, `split_at_crossings`,
  `edge_geometry`, `_outer_face_walk`, `_normalize`/`GRAPH_EPSILON`, i pezzi di
  `healing/outer_scan`, `HealStep`/`_loop_is_structural`,
  `loop_to_closed_feature`, `build_polygon`, `DEFAULT_TOLERANCE`,
  `_configure_odafc`. Quale fatto stava ricostruendo il lab (giro esterno?
  facce?), e se diventa un passo di `topo.steps` o un fatto di
  `topo.geometry`. Va insieme alle ricette (sotto).
- **Due misure del cerchio** (D122): `circular_geometry` (interna, usata da
  `healing/hierarchy.py`) e `contour_shape` (esatta). Da unificare su
  `contour_shape`, provando i golden come in snapbend D66.
- **snapdraw/pippo, cerchio attraversato da altre linee** → 1.x (sopra).
- **snapbend, vaschetta** (un anello che tocca l'outer nei 4 vertici concavi
  esce inner in `faces()`): topo non cambia, è geometria giusta (D250: tutti i
  nodi pari, l'unica lettura con ogni linea contorno). snapbend usa
  `topo.experimental.gap(inner, cluster.outer).distance == 0` per trattarlo come
  suo (`tests/data/golden_faces/vaschetta_input.dxf`: distanza 0 in (200, 0)).
- Da fare nei consumer (non qui): snapdraw `tag_features` → `result.promote`;
  snapbend `topo.promote(result, …)` → `result.promote(…)` (D172, D173);
  smoother strisce → `link` (D142) e `simplify_points` (D141); pippo
  `cancel_on_line` → `contour_union` (D171); snapdraw legge i fori da `loose`
  (D162); avviso a snapdraw e cogo che `topo.core.healing` è diviso in
  `base/` e `readings/` (D188).


## Fili da ragionare con Federico

- **Riferimenti D## nel codice e nelle docstring pubbliche** (D239): 484 nel codice,
  58 in 22 docstring pubbliche, che `help()` mostra. Federico ne parla col forum;
  fino ad allora restano.
- **`Text.source_kind`** (`"MTEXT"`, `"DIMENSION"`, …) è un fatto del formato nel
  modello, tenuto da D138 per riscrivere il testo fedele. Federico non decide ora.
- **snapbend dopo D230**: `snapbend/flat/detect.py` scrive `cluster.custom` e i
  suoi test chiamano `topo.inject`; con D230 non esistono più. Va adattato in una
  sessione aperta in snapbend.
- **Datum** (origine e assi da cui si misura un pezzo): il sistema di riferimento
  attaccato a un contorno è di topo; quale datum scegliere è del consumer.
  Additivo; la 1.0 non deve legare niente al solo sistema mondo.
- **La scansione** (`healing/outer_scan`, raggi del lab `island_rays`): come
  farla completa e a cosa serve oltre al giro esterno.
- **Ricette di ricomposizione**: oggi `faces()` (un pezzo piano) e `outlines()`
  (più viste); se ne servono altre. Candidata: una lettura "mesh" dove una
  faccia interna chiusa è vuota per default.
- **Scelta A: faccia interna chiusa, materiale o foro?** (D131) Oggi le catene
  interne a 0 passaggi sono corde: rettangolo + quadrato interno + 4 diagonali
  → 1 pezzo pieno, 8 linee in `loose`. Federico: "corda e opzionalmente foro",
  ma la regola dell'opzione (proposta: vuota se nessun lato sul contorno
  esterno) non è decisa. Un disegno con pareti appese a una linea (U + barra) è
  un assieme di due pezzi saldati, non l'opzione "foro": serve una lettura che
  spezza lungo i bordi in comune. Sul pezzo piano di `heal()` il default resta
  pieno.
- **Scelta E: foro con un vertice in comune col contorno esterno** (D132). Oggi
  resta foro; per Federico è `loose` con warning. Nessun golden lo contiene: si
  decide quando arriva un disegno vero.
- **`outlines()` e cornici**: i test girano sui disegni grezzi, la cornice
  diventa l'isola più esterna (la riconosce snapdraw, D90). Un cerchio chiuso
  non dovrebbe cambiare natura per ciò che gli sta attorno (`anch_07`: due
  cerchi sono inner con la cornice, `loose` senza). Esistono le copie
  `*_noframe.dxf`; i loro golden non ci sono (D220).
- **Contatto di un giro con sé stesso deciso sul poligono discretizzato**
  (`_loop_faces`, `anch_06`: un cerchio toccato da un simbolo passa da `circle`
  a `other` cambiando la discretizzazione): decidere il contatto sulle primitive.
- **Lato PDF dei fix di D101** (`_drop_redundant_meets`,
  `_drop_boundary_duplicates`): provati solo sui DXF; su un PDF Federico li ha
  visti sbagliati. Ipotesi non verificata: `band = tolerance + max_gap` è
  calibrata sulla precisione DXF. Si riprende col PDF.

## Aperti minori

- `HierarchyBuilder._collect_loose` (`hierarchy.py:217`) toglie da `loose` le
  curve con ruolo OUTER/INNER: una curva così che non entra nella gerarchia
  sparisce, contro D137. Letto nel codice, non misurato se succede.
- `closed-touch` (D241) non scatta su un anello che tocca l'outer in un punto
  solo (quadrato 100 con un triangolo che ha un vertice a metà di un lato):
  da capire perché.
- `load_dxf` sbaglia in silenzio cerchi, archi ed ellissi su un piano inclinato
  (estrusione diversa da (0,0,±1), o asse maggiore con Z). Misurato su un DXF
  generato, un caso per layer: un cerchio r=8 inclinato di 45° con centro WCS
  (110,60) diventa `CircleSeg(center=(110, 42.43), r=8)` (prende il centro OCS
  come XY), la proiezione vera è un'ellisse centrata in (110,60) con semiassi 8
  e 5.66; scarto massimo 15.2 mm (arco uguale), ellisse con asse inclinato
  2.07 mm. Nessuna nota, solo `dxf-flattened`. Corretti (scarto ≤ 0.002):
  LINE, LWPOLYLINE/POLYLINE con quota, POLYLINE 3D, SPLINE, cerchi/archi a Z≠0
  o con estrusione (0,0,-1).
- `heal(max_gap=0.5)` chiude gli angoli aperti di 0.3 mm di un rettangolo di
  4 linee (ogni lato accorciato di 0.3 a un capo) senza nessuna nota: `notes`
  vuoto, outer di 4 `LineSeg`, area 7200 esatta. Con 4 archi e gap 0.2 dà
  `arc-joined`. Da capire se è un "silently" di D137/D206.
- `topo/core/readings/outer_scan.py` lo usava solo `scripts/18_outer_scan.py`,
  tolto con D247: ora lo chiama solo il suo test (`test_outer_scan.py`).
- `docs/LLM.md`: `geometry.circle(radius, center)` scritto posizionale, ma
  `center` è solo keyword (`circle(10, (-50, 0))` → `TypeError`).
- Il consiglio di `near-gap` può essere falso (D240: sperimentale, ma non deve
  mentire). Misurato con `faces()` e la tolleranza di default:
  - `tests/data/golden_faces/rect_gap.dxf` e `rect_overlap.dxf`: dice
    "max_gap=0.1 closes them all", ma un angolo ha un buco di 0.141; con 0.1 il
    risultato resta non valido (`no-loop`).
  - `golden_faces/spline_line_gap.dxf`, `arc_arc_gap.dxf`, `arc_open.dxf` e
    `spline_line_gap_qcad.dxf`: buchi di 0.2–0.245, nessun consiglio, solo
    `no-closed-outer`; con `max_gap=0.5` si chiudono tutti.
- `import topo_pdf` dà l'avviso di PyMuPDF "The `fitz` API is deprecated".
- `contour_minus` rifiuta i bordi che corrono uno sull'altro (`ValueError`):
  da gestire se un caso vero lo chiede (D118).
- `load_geometry`: gli angoli dell'arco sono ancora in gradi "per convenzione
  CAD" (resto di D96); `ArcSeg` usa i radianti. Passare ai radianti tocca la
  matematica di cono e sezione di snapbend.
- Fitting ellisse da punti grezzi (5 gradi di libertà, per smoother): rimandato
  dopo D45.
- `rotate_result`/`rotate_cluster` non ruotano `Document.annotations` né
  `cluster.overlay`/`custom` (schema libero, D44): l'overlay va scritto dopo la
  rotazione.
- **PDF da riprendere** (D10): `load_pdf` oggi restituisce `list[Edge]`; deve
  restituire un `Document` come ogni adapter, portando in `topo_pdf/` il lavoro
  fermo nella worktree `forge-pdf-adapter` (branch `experiment/pdf-adapter`: non
  cancellarli).
- Estrazione dei loop planari (half-edge/DCEL): ricorrente sui fogli densi
  (grafo con il 91% dei nodi a grado > 2, un file Creo quasi tutto SPLINE). Da
  riverificare con la lettura di oggi (D189) prima di riaprire.
- `anonymize` è ora `dxf-anonymize` (D80, repo privata, `pipx`). Regola: la
  marcatura (testo che ripete il numero del pezzo, la scrive Advance Steel) non è
  dato cliente, si tiene. Aperti lì: loghi senza retini; 6 disegni dove snapdraw
  non è sicuro del cartiglio; una cartella sotto `tests/examples/` il cui nome
  è da guardare.
- Fogli A e C di "outer che non si chiude" (D49): non riverificati con la
  lettura di oggi. Foglio C: 1682 pezzi in `loose` con catene di tratti
  ~0,3–0,5 mm; il foglio A è un assieme con archi e linee di costruzione.
- `compute_gap_fixes` scarta ogni coppia arco/arco oltre `tolerance` anche
  quando i cerchi si intersecano davvero; un'altra scelta di design solo con un
  file reale.
- Backlog: `DxfAnalyzer.summary_stats()` anche in CSV; fingerprint geometrica
  per validare una parte; "meccanismo anti-rotazione di un pezzo staccato" (un
  ponticello su un contorno singolo, nome non deciso: non "microjoint").

## Regola da ricordare

Mai parlare di layer DXF quando si parla di `role` e di estensibilità: i
`role_rules` sono solo il modo di assegnarlo al load (D63), il meccanismo vero
è `edge.role`, per qualunque criterio, senza dipendere da layer o formato.
