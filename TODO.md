# topo — TODO

Lo stato, non la storia: qui sta solo ciò che è aperto. Il perché di ogni
scelta è in `MAP.md` (`D##`), la cronaca nel git log. Il testo intero di questo
file prima dell'accorciamento (2 novembre) è in `TODO_ARCHIVE.md`, solo locale,
fuori da git.

---

## Fuori dal cancello: MAP e TODO corte (Federico, 1 novembre) — fatto il 2 novembre

- [x] **MAP.md** 7 464 → 400 righe: una voce `### D##` per decisione (titolo =
      la regola in una frase, al massimo 4 righe sotto); una regola superata è
      una riga ("D59 → D99, D161"). Il testo intero è in `MAP_ARCHIVE.md`
      (locale, in gitignore; lo stesso testo è in git a `67fda38:MAP.md`).
      `python scripts/check_map_shrink.py --archive MAP_ARCHIVE.md` esce 0:
      201 decisioni su 201, nessuna doppia, nessun rimando appeso.
      Da qui in poi una decisione nuova è un titolo `### D##` + al massimo 4
      righe; il perché lungo va nel commit.
- [x] **TODO.md** 1 732 → 293 righe; il testo intero in `TODO_ARCHIVE.md`
      (locale, in gitignore).

## DECISO prima della 1.0 (D202) — `heal()` ripara, `faces()`/`outlines()` leggono (2 novembre)

Deciso da Federico il 2 novembre: si fa comunque, bene, in pochi giorni.
Le misure sotto non sono più un cancello: la 1 è la verifica del lavoro
(golden cambiati classificati + DXF in `_debug`), la 3 il tetto dei tempi.
Sottopassi, uno per commit:
- [x] A. inventario (2 novembre). Le differenze sono quattro, non tre
      (`heal.py:87,110` contro `island.py:136-165`):
      1. portata dei gap: `reach(tol)` contro `reach(max(tol, max_gap))`.
         `faces()` non ne ha bisogno: nessun consumer chiede a heal() gap
         larghi (passano solo `tolerance`). B prova un numero solo (D202:
         `outlines` via `heal(doc, tolerance=max_gap)`); il rischio è che i
         nodi si decidano a `max_gap`. Se i golden di island non peggiorano
         a occhio resta uno; se peggiorano, i numeri sono due — lo dice la
         misura, non una scelta a tavolino.
      2. `keep_junctions`: True (D110) contro False (D50). Nella rete i pezzi
         restano separati (non si perde niente); `outlines()` ricompone già
         lungo il contorno (`merge_runs`, `island.py:200`). Da misurare in B.
      3. scope: tutto il disegno contro un gruppo `spatial_islands` alla
         volta. I gap si chiudono entro `max_gap` e i gruppi sono a `max_gap`,
         quindi le coppie dovrebbero essere le stesse: il raggruppamento
         diventa un passo di `outlines()`. Da misurare: risultati e tempi.
      4. `cut_crossings`: False in heal (D132, D189), True in island (D101).
         È già "lo dice la lettura" (docstring `noding.py:170`): la rete
         tiene gli incroci come dato (`crossings`), il taglio lo fa
         `outlines()`. Serve un taglio applicabile a una rete già fatta.
      Minori: il filtro dei degeneri (`island.py:163`) va nella riparazione
      comune; il secondo `decide_nodes` in `read_island` sparisce; gli errori
      di disegno vuoto (solo in heal) valgono per tutti; `label` e
      `source_file` (heal li prende, island usa `doc.source_path`) vanno
      sulla rete.
      Superficie di `Network`: `edges` (riparati), `crossings`, `free_ends`,
      `set_aside` (ruoli non strutturali), `warnings`, `errors`, `is_valid`,
      `source_file`, `label`; `faces()`, `outlines()`. `NodedEdges` resta
      interno.
- [ ] B. una riparazione sola dietro `heal()` → `Network`; golden classificati.
      Misura fatta il 2 novembre (`_debug/2026-11-02_topo_D202-network`,
      `measure.py`, solo lettura): `faces()` = `heal()` su 218/218 disegni;
      `outlines()` su una riparazione sola (tutto il disegno, keep_junctions
      True), con un numero solo o con due: geometria dei contorni identica
      su 51/51, i loose fuori da ogni isola (quelli del golden) uguali sui 15
      golden; tempi uguali o un poco sotto (52 s contro 55). Cambia una cosa
      sola: le isole che island() non legge (riquadro, isole annidate,
      gruppi senza contorno) oggi vanno in loose **come nel file**
      (docstring: "intatto"), dalla rete arrivano **riparate** (doppioni
      fusi, curve rifittate, gap chiusi): fino a 900 mm di linee doppie in
      meno su un disegno. Le isole lette già oggi danno loose riparati, e
      anche heal(). Proposta: loose sempre dalla rete (uniforme, un
      fondamento), la provenienza resta sulla rete. Controllo "fedele"
      (`tests/invariants.uncovered`) sui 51: 0,000 mm persi. Un numero o due:
      **due** (D202), con uno solo un contorno resta aperto di 0,41 mm.
      Lo sweep di snapdraw non è stato rifatto: l'hook blocca un comando che
      nomina la cartella di snapdraw.
- [ ] filo parcheggiato: `validate_result` non vede un salto di 0,41 mm fra
      due segmenti consecutivi di un contorno (`is_valid` True). Va guardato
      a parte, anche oggi senza D202.
- [ ] C. `faces()`/`outlines()` + rinomina `island`/`read_island(s)`/`IslandReading`;
- [ ] D. docs (LLM, API, README x2), `release_check`; i consumer si adattano
      nelle loro sessioni.

Testo di partenza: oggi `heal()` fa due cose (ripara con la base
comune + legge le facce annidate) e `island()` ripara e legge il bordo
esterno di ogni componente; "isola" in topo vuol dire anche la regione di
profondità 2 (D89). Proposta: `topo.heal(doc, *, tolerance, is_structural,
label, source_file) -> Network` (il disegno riparato: `edges`, `bridges`,
`free_ends`, `set_aside`, `warnings`, `is_valid`), poi `Network.faces() ->
Result` (l'heal di oggi) e `Network.outlines() -> Result` (l'island di oggi;
`max_gap` diventa la `tolerance` di heal). Via `island`, `read_island(s)`,
`IslandReading` → `read_outline(s)`, `OutlineReading`. Rompe tre nomi:
riapre G14 su questo punto, solo prima della 1.0.

Regge solo se la rete è una sola. Oggi la riparazione differisce in tre
punti (`heal.py:87`, `island.py:137,163`): portata dei gap (`tolerance` vs
`max(tolerance, max_gap)`), `keep_junctions` (True in heal, D110; False in
island), scope (tutto il disegno vs per gruppo di `spatial_islands`).
**Misura prima di aprire qualunque cosa** (solo lettura, costo annunciato):
1. una sola riparazione (stessa portata, una scelta di `keep_junctions`,
   tutto il disegno) e le due letture sopra: golden di heal e island
   cambiati? quanti, e i cambiati in DXF in `_debug` per l'occhio;
2. stesso confronto sul sweep di snapdraw (`scripts/21_sweep_invariants.py`);
3. tempo della suite e dei disegni grossi prima/dopo;
4. chiamate a `heal(`/`island(` nei consumer (prima conta: snapdraw 19,
   snapbend 8, pippo 2, forge-pdf-adapter 43 di `island` — da ricontare);
5. cosa di `Network` sarebbe pubblico senza esporre tipi interni.
Vale la pena se 1–2 non peggiorano nessuna lettura a occhio e 3 resta nel
tetto; se no, ripiego: `heal()` com'è + `island` → `outlines` (solo nome).

## IL CANCELLO DELLA 1.0 (D148, 22 ottobre)

**Feature freeze.** La lista è chiusa: può solo accorciarsi (D193 l'elenco).
Quando è vuota topo è *1.0-ready*: `python scripts/release_check.py` esce 0 e
da quel giorno ogni commit su `main` lo tiene a 0. Entra solo ciò che rompe un
nome pubblico, o rende vere e provate le invarianti di D143 sui fixture del
repo, più i documenti (D144) e la history pulita; il resto è 1.x (D158, D174).

**Chiusi:** G1 (campi di `Result`, D150), G2 (→ 1.x, D149), G3 (fedeltà a due
vie, D152), G4 (discretizzazione, D145/D153/D154), G5 (misure, D156), G6 (4
dubbi D103, D157), G6b (ogni pezzo una volta, D163), G6c (contatto deciso una
volta, D180), G6d (D189), G6e (`heal()` indipendente dal riferimento: D201,
3 residui in 1.x), G11 (`release_check.py`), G12 (area esatta, D165), G13
(nessun tipo shapely nella superficie, D166–D168).

**Aperti**
- [ ] **G14** Superficie allineata alle API di una libreria matura (D174,
      D175). Fatti: la regola (D175), la passata sui nomi (D176, D177), la
      regola 1 come test (D178). Restano: la regola 8 (con G9) e il test di
      rimozione delle deprecazioni (vuoto finché non ce n'è una). Consumer da
      adeguare con le tabelle vecchio → nuovo di D176/D177: snapbend,
      snapdraw, smoother, pippo — dalle loro sessioni.
- [ ] **G7** Zero `expectedFailure` e zero difetti noti: golden di island
      rifatti da zero sui `_noframe` (dopo che Federico ha guardato i DXF);
      `test_text_budget` anch_02 (+3.7% di caratteri dal D138: capire se è
      testo legittimo prima di toccare il budget); inner che si incrociano
      su anch_03/regr_02 e 10 disegni di `golden_anchoring/`
      (`KNOWN["inners cross"]`: cicli accettati che non sono facce, D107);
      roundtrip di anch_03/regr_02/anch_03_noframe (`KNOWN["roundtrip"]`).
      Da verificare: lo snapshot di `test_golden_islands.py` confronta la
      forma di ogni inner, non solo bbox e conteggio.
- [ ] **G8** README / README_IT / `description` di pyproject / prima riga di
      CLAUDE.md: motore di geometria 2D, i disegni tecnici sono un caso.
- [ ] **G9** `docs/API.md` e `docs/ARCHITECTURE.md` in inglese; docstring dei
      nomi pubblici in inglese, con un controllo nella suite.
- [ ] **G10** Rewrite della history (`git filter-repo` + `--message-callback`,
      un solo force-push) contro le liste di D76–D78. `audit_names --strict`
      dà 5 sospetti (2 novembre, dopo l'accorciamento di MAP e TODO): un codice
      tipo disegno in `tests/unit/core/test_normalizer.py:351`, nei commit non
      ancora pushati; gli altri (`BLE001`, `SLEP009`) sono falsi positivi
      probabili. Da descrivere a parole e togliere dai commit prima di
      qualunque push. Nei commit vecchi restano anche i blocchi-logo definiti
      e mai usati di `anch_01…06` (D97).
- [ ] **Tempo della suite**: 3:23 dopo D181, sopra il tetto di 2.5–3 min.
      Restano `test_fidelity` sulle spline e le letture di `island()`.
      **Si riparte da qui** (deciso il 1 novembre): riordino dei test.
      1. Ogni test che apre un DXF con `ezdxf` o lavora sul modelspace e prova
         una lettura, non il formato, passa a geometria costruita con i
         numeri (`load_segments`, primitive, `topo.geometry`). Primo visto:
         `tests/integration/test_gap.py`; `load_msp` in `test_healer.py:36` è
         morto. Altri dei 17 file con `import ezdxf`: uno per uno.
      2. I test che provano un adapter vanno in `tests/adapters/dxf/` e
         `tests/adapters/pdf/`, con un `conftest.py` che fa
         `pytest.importorskip`. Da decidere: `tests/real/` sotto
         `adapters/dxf/` o lì con lo stesso skip.
      3. Dopo l'1: via i generatori di fixture (`generate_examples`,
         `generate_gap_examples`, `generate_rotation_fixture`,
         `generate_two_flanges`) e i .dxf che nessun test legge più; restano
         i .dxf piccoli che provano l'adapter in lettura. I `generate_golden*.py`
         restano (regola 9), al più in `tests/tools/`.
      Fuori dal cancello (solo test); misurare il tempo prima e dopo.
- [ ] **Generatore di disegni credibili** (30 ottobre): compone forme vere
      (contorni con raccordi, cerchi e asole dentro, archi tangenti, spline,
      annidamenti) e le guasta come i file veri (piccoli buchi, ripassati,
      segmenti spezzati, versi invertiti, ordine rimescolato, rotazioni). La
      risposta è nota per costruzione: ogni disegno è un test senza golden.
      Nella suite pochi semi fissi; passate grandi a mano. Da decidere:
      `hypothesis` come dipendenza di test.

**Fuori dal cancello, ma prima di snapbend 1.0:** le suite dei consumer erano
rosse già prima di D150 (snapbend 16 golden di processo, aree spostate di ~1
mm², probabilmente D145; snapdraw 3 regressioni). Si giudicano nei loro repo,
mai rigenerando alla cieca.

## Dopo la 1.0 (1.x, additivo — non toccare finché il cancello è aperto)

Primo lavoro (deciso il 30 ottobre):
- **discretizzazione delle spline in Rust** (o almeno numpy): De Boor in Python
  è il costo singolo più grosso di `island()`. Prova numpy a blocchi: scende
  solo da 6.5 a 5.1 s (D169 chiede la misura per un core Rust).

Da G6e (D199, D201) e G6c (D179):
- **ordine dei rami a un nodo in `_leaving_angle`**: la direzione si legge a
  `DIRECTION_SAMPLE`; una spline che lascia il nodo e passa oltre una retta
  vicina può rovesciare l'ordine, e la camminata dà un lobo per sporgenza
  (oggi lo salva l'unione di D100).
- **togliere l'unione di D100** (`_faces_union_loop`, `_network`, `_on_nodes`,
  `UNION_GRID`, `rim.py`): rifà il noding sulle discretizzazioni e salda
  contatti che D180 esclude. Dopo la voce sopra; rifare le due misure di D199;
  `TestChordContactUnderMotion` diventa rosso e esce dai difetti noti.
- **il ripiego D100 senza edge interi sul bordo dell'unione** restituisce
  `None` e vince il giro più piccolo; da sistemare in generale.
- i 3 residui della passata sui 121 disegni (D201).
- costo accettato di D186: `heal()` raddoppia sui disegni a catene di tratti
  corti; ottimizzare, prima in Python, poi Rust.

Additivi decisi con Federico (25–30 ottobre):
- **warning sui pezzi d'ingresso che coincidono** (un `CIRCLE` ripassato da
  una polilinea): difetto del disegno, topo lo dice e non ne cancella nessuno
  (D137). Oggi due cerchi r 2 a 0.05 (tol 0.1) escono 2 cluster, `is_valid`
  True, e l'unico avviso (D132) dà il consiglio sbagliato. Da decidere con
  tutti gli avvisi: due contorni chiusi che si incrociano invalidano? avvisi
  come dati invece che frasi?
- **terza lettura, la rete**: gruppi di pezzi che si toccano o si incrociano,
  coi punti di contatto, senza contorni né dentro/fuori.
- **in `island()` i pezzi dello stesso cerchio/retta si ricompongono anche in
  `loose`** (richiesta snapdraw/pippo): un cerchio attraversato da linee esce
  in archi aperti; estendere a `loose` la ricomposizione di D65, senza
  scegliere cicli (D161). Fino ad allora i consumer ricompongono da sé.
- **griglia per le spline** (come D145/D153): `BSplineSeg.discretize` è
  adattiva sul proprio intervallo, un pezzo tagliato (D163) non dà gli stessi
  vertici dell'intera. Solo se si vede un difetto; nessun rosso oggi (D167).
- **criterio del punto medio di `_refine_segment`**: su un tratto a S il medio
  cade sulla corda; oggi lo copre il campionamento fitto (0.00988 a tol 0.01).
- **la forma dai punti, per PDF e visione** (31 ottobre): `simplify_points`
  (D141) e `refit_tessellations` (D60) sono già geometria di topo; gli estremi
  ambigui di D185, oggi solo in un warning, come dato interrogabile sul
  `Result`. Il dettaglio del formato resta nell'adapter (regola 1).
- **report di scostamento di `heal()` per entità** (D149); **PDF** (`topo_pdf`);
  **modello `Curve`**, `as_analytic`, firma dei contorni (D121) e fatti di
  riconoscimento (si promuovono in una minor quando un secondo consumer li
  usa, D91/D118); **curve da equazione**; **viewer**; **strisce** (D142,
  promozione a `topo.geometry` quando un secondo chiamante le usa); **D147**
  (ponti sui T, branch `d147-t-ends`; `regr_04` peggiora); **snapfence**.
- **dipendenze** (D169): misurare i tempi di `heal()`/`island()` sulle
  fixture; inventario shapely/numpy → sostituto; poi un pezzo alla volta e a
  pari golden. Il noding resta a GEOS.

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
- Da fare nei consumer (non qui): snapdraw `tag_features` → `result.promote`;
  snapbend `topo.promote(result, …)` → `result.promote(…)` (D172, D173);
  smoother strisce → `link` (D142) e `simplify_points` (D141); pippo
  `cancel_on_line` → `contour_union` (D171); snapdraw legge i fori da `loose`
  (D162); avviso a snapdraw e cogo che `topo.core.healing` è diviso in
  `base/` e `readings/` (D188).

## Fili da ragionare con Federico

- **Datum** (origine e assi da cui si misura un pezzo): il sistema di
  riferimento attaccato a un contorno è di topo; quale datum scegliere è del
  consumer. Additivo; la 1.0 non deve legare niente al solo sistema mondo.
- **La scansione** (`healing/outer_scan`, raggi del lab `island_rays`): come
  farla completa e a cosa serve oltre al giro esterno.
- **Ricette di ricomposizione**: oggi `heal` (un pezzo piano) e `island` (più
  viste, per isole); se ne servono altre. Candidata: una lettura "mesh" dove
  una faccia interna chiusa è vuota per default. Legato al filo `faces()`/
  `outlines()` in cima.
- **Scelta A: faccia interna chiusa, materiale o foro?** (D131) Oggi le catene
  interne a 0 passaggi sono corde: rettangolo + quadrato interno + 4 diagonali
  → 1 pezzo pieno, 8 linee in `loose`. Federico: "corda e opzionalmente
  foro", ma la regola dell'opzione (proposta: vuota se nessun lato sul
  contorno esterno) non è decisa. Un disegno con pareti appese a una linea
  (U + barra, 26 ottobre) è un assieme di due pezzi saldati, non l'opzione
  "foro": serve una lettura che spezza lungo i bordi in comune (futuro
  snapweld). Sul pezzo piano di `heal()` il default resta pieno. DXF locali
  in `tests/lab/caso_A/`.
- **Scelta E: foro con un vertice in comune col contorno esterno** (D132). Oggi
  resta foro; per Federico è `loose` con warning. Nessun golden lo contiene:
  si decide quando arriva un disegno vero.
- **`island()` e cornici**: i test girano sui disegni grezzi, la cornice
  diventa l'isola più esterna (la riconosce snapdraw, D90). Copie
  `*_noframe.dxf` fatte; un cerchio chiuso non dovrebbe cambiare natura per
  ciò che gli sta attorno (anch_07: due cerchi sono inner con la cornice,
  `loose` senza). Si chiude in G7.
- **Contatto di un giro con sé stesso deciso sul poligono discretizzato**
  (`_loop_faces`, anch_06: un cerchio D2.2 toccato da un simbolo passa da
  `circle` a `other` cambiando la discretizzazione): decidere il contatto sulle
  primitive prima di rifare i golden di island (G7).
- **Lato PDF dei fix di D101** (`_drop_redundant_meets`,
  `_drop_boundary_duplicates`): provati solo sui DXF; su un PDF Federico li ha
  visti sbagliati (12 ottobre). Ipotesi non verificata: `band = tolerance +
  max_gap` è calibrata sulla precisione DXF. Si riprende col PDF.

## Aperti minori

- `contour_minus` rifiuta i bordi che corrono uno sull'altro (`ValueError`):
  da gestire se un caso vero lo chiede (D118).
- `load_geometry`: gli angoli dell'arco sono ancora in gradi "per convenzione
  CAD" (resto di D96); `ArcSeg` usa i radianti. Passare ai radianti tocca la
  matematica di cono e sezione di snapbend.
- Fitting ellisse da punti grezzi (5 gradi di libertà, per smoother):
  rimandato dopo D45.
- `rotate_result`/`rotate_cluster` non ruotano `Document.annotations` né
  `cluster.detected`/`custom` (overlay a schema libero, D44): la detection
  va fatta dopo la rotazione.
- **PDF da riprendere** (D10): `load_pdf` oggi restituisce `list[Edge]`; deve
  restituire un `Document` come ogni adapter, portando in `topo_pdf/` il
  lavoro fermo nella worktree `forge-pdf-adapter` (branch
  `experiment/pdf-adapter`: non proporre di cancellarli).
- **Viewer** (`to_view_model` + `to_svg`, D133: fuori dalla 1.0 stabile) da
  rifare in una sessione a parte: non scala (su un foglio di viste pesa più
  del DXF di partenza), e non deve più discretizzare archi e cerchi (riapre
  D12; coordinate a 3 decimali nelle uscite di lettura, non in `to_dxf`).
- `to_text` (D84) sperimentale: la prova del valore sta in snapdraw.
- Estrazione dei loop planari (half-edge/DCEL): ricorrente sui fogli densi
  (grafo con il 91% dei nodi a grado > 2, un file Creo quasi tutto SPLINE).
  Da riverificare con la lettura di oggi (D189) prima di riaprire.
- `anonymize`: ora è `dxf-anonymize` (D80, repo privata, `pipx`). Regola: la
  marcatura (testo che ripete il numero del pezzo, la scrive Advance Steel)
  non è dato cliente, si tiene. Aperti lì: loghi senza retini, 6 disegni dove
  snapdraw non è sicuro del cartiglio, `tests/examples/cartella_3/` (nome da
  guardare).
- Fogli A e C di "outer che non si chiude" (D49): non riverificati con la
  lettura di oggi. Foglio C: 1682 pezzi in `loose` con catene di tratti
  ~0.3–0.5 mm; il foglio A è un assieme con archi e linee di costruzione.
- Limiti geometrici di vecchi fixture, non bloccanti: `compute_gap_fixes`
  scarta ogni coppia arco/arco oltre `tolerance` anche quando i cerchi si
  intersecano davvero; un'altra scelta di design solo con un file reale.
- Backlog: `DxfAnalyzer.summary_stats()` anche in CSV; fingerprint geometrica
  per validare una parte; "meccanismo anti-rotazione di un pezzo staccato"
  (un ponticello su un contorno singolo, nome non deciso: non "microjoint").
- Idee di tool sul motore (misura, classificazione, confronto, validazione,
  offset/kerf, normalizzazione, orientamento per nesting, scheletro,
  decomposizione in regioni): nessuna decisa, ognuna passa dal triage sopra.

## Regola da ricordare

Mai parlare di layer DXF quando si parla di `role` e di estensibilità: i
`role_rules` sono solo il modo di assegnarlo al load (D63), il meccanismo vero
è `edge.role`, per qualunque criterio, senza dipendere da layer o formato.
