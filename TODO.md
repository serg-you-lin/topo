# topo — TODO


Stato attuale: healing funzionante, export JSON/XDATA base, layer centralizzati.
Topo è un motore per comprendere geometria CAD 2D.

Nota: tutto quello che era ✅ fatto è stato tolto da qui (il record resta in
`MAP.md`, decisione per decisione). Questo file tiene solo quello che è
ancora aperto.

---

## IL CANCELLO DELLA 1.0 — si riparte da qui (D148, 22 ottobre)

**Feature freeze.** Questa lista è chiusa: può solo accorciarsi. Quando è
vuota topo è *1.0-ready*: `python scripts/release_check.py` esce 0 e da quel
giorno ogni commit su `main` lo tiene a 0 (la versione può restare 0.x; la
1.0 si pubblica quando si vuole, senza fare altro).

Entra qui solo ciò che **rompe un nome pubblico** o serve a rendere **vere e
provate le invarianti di D143** sui fixture già nel repo, più i documenti
(D144) e la history pulita. Tutto il resto va in "Dopo la 1.0" in fondo a
questa sezione. Il dettaglio di ogni punto sta più sotto o in `MAP.md`.

**Regola d'ingresso (D158, temporanea — si cancella a 1.0-ready):** dopo la
passata delle invarianti di D143 su tutti i fixture, entra qui solo ciò che
rende rossa una di quelle invarianti su un fixture del repo. Il resto è 1.x.
Le invarianti invece restano nella suite per sempre. Passata fatta il 23
ottobre (D159): i rossi sono G6c, G6d, G7 qui sotto (G6b chiuso, D163), ognuno nel
registro dei difetti noti del suo test (skip con la voce del cancello; un
caso che torna verde fa fallire il test finché non esce dalla lista).

Ordine: prima la superficie (rompe), poi la promessa (prova), poi i documenti
(si scrivono su una superficie ferma), ultima la pulizia.

**Superficie — cambia nomi, quindi prima**
- [x] **G1** Campi di `Result` — fatto, D150: via `classified_entities`
      (di snapbend), `all_arcs` (doppione di contorni + `loose`),
      `_open_shapes` (morto). snapbend adattato.
- [x] **G2** ~~Report di scostamento di `heal()` per entità~~ — spostato a
      1.x, D149 (riapre D143 su questo punto): è additivo; resta bloccante
      la prova G3.

- [x] **G13** Nessun tipo shapely nella superficie pubblica (D166, deciso con
      Federico il 25 ottobre): un contorno espone solo tipi di topo —
      `segments`, `bbox`, `area` e `centroid` esatti (con G12), `contains(p)`,
      i punti del giro discretizzato entro una tolleranza. Una conversione
      esplicita `to_shapely(contour)` fuori dal modello per overlay e buffer.
      Shapely resta dentro topo come dettaglio d'implementazione. I consumer
      si adattano loro (D140): ~120 righe `.polygon` in snapbend, snapdraw,
      snapfence, smoother — una riga per ognuno in `## Richieste a topo` non
      serve, è topo che rompe: va scritto nel loro TODO dalle loro sessioni.
      Rompe un nome: si fa per prima, insieme a G12.
      Passi (piano del 25 ottobre, MAP D166 "Implemented"): 1 fatti del giro
      sulle primitive ✅ · 2 verso e ordine dall'integrale ✅ · 3
      `to_shapely` e interno senza `.polygon` ✅ (`to_shapely(cluster)`
      pari-dispari, confermato) · 4 via `.polygon` dal modello ✅ · 5 ✅
      (`splits_contour`, `polygonize_to_curves`; controprova di
      `splits_contour`/`bridged_runs` su tutte le fixture: 4550 contorni,
      54 600 corde, 0 differenze) · 6 documenti, D168, 0.23.0 ✅.
      Chiuso 25 ottobre (MAP D168: tabella vecchio → nuovo per i consumer).
- [x] **G12** Area esatta (D165, entra nel cancello per decisione di
      Federico, 25 ottobre): `area` di un contorno è l'integrale di Green
      sui suoi `segments` (linea, arco, ellisse in forma chiusa, spline per
      polinomi), non l'area del poligono discretizzato. Non dipende più da
      `tol` e non sottostima più gli archi. Cambia il valore di un nome
      pubblico: va fatto prima della 1.0.
      Fatto 25 ottobre (`core/geometry/integrals.py`, MAP D165
      "Implemented"): golden aggiornati nei soli campi d'area. Il
      baricentro c'è (`ring_centroid`), esce come `centroid` con G13.
      Restano su `polygon.area` ordine e verso dei contorni: via con G13.

**Promessa — D143, provata sui fixture**
- [x] **G3** Test di fedeltà a due vie — `tests/real/test_fidelity.py`
      (D152): Hausdorff ≤ tolleranza (heal) / `max_gap` (island) e
      coefficienti identici dove la lettura non tocca, sul DXF riletto.
      Lungo la strada: D151 (giro senza area perso), D152 (saldatura a
      catena). Ogni disegno con la sua lettura: `golden_islands/` e
      `golden_anchoring/` → `island()`, il resto → `heal()`.
- [x] **G4** `ArcSeg`/`EllipseSeg.discretize` verificati contro la
      tolleranza come i cerchi in D145: archi già entro `tol`, ellisse sulla
      griglia del parametro (D153); curve di misura nulla rifiutate dalla
      primitiva e avvisate dall'adapter (D154).
- [x] **G5** Bug di misura trovati con D145 — fatto, D156: l'area di
      `rect_with_countersink` non era un bug (Ø10 è un'isola a depth 2,
      D89; scarto 0.47 entro tol × perimetro, ora provato da un test);
      `contour_shape` `length`/`width` di `other` misurati sulle primitive
      (prima fino a 0.016 corti, ora ≤ 4e-5 dal riferimento a 1e-6).
- [x] **G6** I 4 dubbi D103 — fatto, D157: 56 giri scartati, tutti senza
      un bordo loro a tol + max_gap (fantasmi annidati, doppioni veri, una
      scheggia, un ciclo che non è faccia); tutti in `result.loose` (bordo
      coperto al 100%), due test lo tengono. DXF da guardare:
      `_debug/2026-10-23_topo_G6_D103/`.
- [x] **G6b** Ogni pezzo d'ingresso esce una volta sola — fatto, D163: un
      edge che il bordo prende solo in parte lascia in `loose` il suo resto
      esatto (`rim.off_rim`), in `island()` (ripiego D100) e nel ripiego
      polygonize di `heal()`. `KNOWN["out once"]` e `KNOWN_TWICE` vuoti.
      DXF da guardare: `_debug/2026-10-25_topo_G6b/`.
- [ ] **G6c** `island()` dipende dall'ordine delle entità e dal sistema di
      riferimento (passata D158, 23 ottobre). Rimescolando gli edge cambiano
      gli inner su 22 dei 31 disegni d'isole; ruotando di 0.7 rad, spostando
      a (2.5e6, −1.5e6) o specchiando, su 20. Due famiglie viste: (a) inner
      persi — fessure larghe 0.5 = `max_gap` (anch_02, anch_04 col solo
      specchio, anch_01/regr_03) e un 14×14 su regr_04 anche solo
      spostato; (b) inner che cambiano forma con l'ordine (anch_05 108 mm →
      8.5, anch_08 204 → 695, anch_06, regr_01, anch_02) — un ciclo scelto
      fra più giri. `heal()` invece passa tutto: ordine, rotazione,
      traslazione, specchio, outer e inner. Causa da trovare prima del
      rimedio. **Invariante:** `TestEdgeOrder`, `TestRigidMotion` di island
      (`KNOWN["edge order"]`, `KNOWN["rigid motion"]`). Prima di G7.
- [ ] **G6d** `heal()` su `SEGNI_TRACCIATI` (tol 0.5): tre cave larghe
      0.4–0.5 mm restano nell'outer letto da solo e si riempiono quando ci
      sono le corde (`TestChordsKeepTheOuter`, `KNOWN_CHORDS`): l'esito su
      una fessura larga quanto la tolleranza dipende da edge che non la
      toccano.
- [ ] **G7** Zero `expectedFailure` e zero difetti noti: golden di island
      rifatti da zero sui `_noframe` (dopo che Federico ha guardato i DXF di
      G6), `test_text_budget` anch_02 spiegato, inner che si incrociano
      (D107: cicli fra giri accettati che non sono facce — non sono giri di
      D103, D157) — con la passata D158 sono anch_03/regr_02 e 10 disegni di
      `golden_anchoring/` (`KNOWN["inners cross"]`), più il roundtrip di
      anch_03/regr_02/anch_03_noframe (`KNOWN["roundtrip"]`).

**Documenti — D144**
- [ ] **G8** README / README_IT / `description` di pyproject / prima riga
      di CLAUDE.md: motore di geometria 2D, i disegni tecnici sono un caso.
- [ ] **G9** `docs/API.md` e `docs/ARCHITECTURE.md` in inglese; docstring
      dei nomi pubblici in inglese, con un controllo nella suite.

**Pulizia**
- [ ] **G10** Rewrite della history (`git filter-repo` + `--message-callback`,
      un solo force-push), contro le liste di D76–D78.
- [x] **G11** `scripts/release_check.py` — scritto il 22 ottobre: suite
      senza xfail, `gen_index --check`, `audit_names --strict` (file e
      history), `audit_fixtures --strict`, docstring inglesi dei nomi pubblici.
      Al primo giro: rossi suite (20 xfailed → G6/G7), history (19 sospetti
      distinti → G10) e docstring (85 nomi → G9); `audit_names` era rosso da D100 (gli id `D1xx` e gli sha
      abbreviati sembravano codici), corretto alla fonte. Il controllo
      docstring vive qui; G9 decide se spostarlo nella suite.

**Fuori dal cancello di topo, ma prima di snapbend 1.0:** le suite dei
consumer erano già rosse prima di D150 (snapbend 16 golden di processo,
aree spostate di ~1 mm² — probabilmente D145; snapdraw 3 regressioni). Si
giudicano nei loro repo, mai rigenerando alla cieca.

**Dopo la 1.0 (1.x, additivo — non toccare finché il cancello è aperto):**
report di scostamento di `heal()` per entità (D149), PDF (`topo_pdf`), modello `Curve`/`as_analytic`/firma dei contorni, viewer,
strisce (D142), D147 (estremi sui T, branch `d147-t-ends`),
criterio del punto medio di `_refine_segment`, curve da equazione, fatti di
riconoscimento, snapfence, richieste dei consumer che aggiungono nomi.
Dipendenze (D169): misurare i tempi di `heal()`/`island()` su tutte le
fixture; inventario operazione shapely/numpy → cosa la sostituisce; poi, un
pezzo alla volta e solo a pari golden: numpy diretto (`integrals`, `points`),
indice spaziale nostro, `polygonize` contro il cercatore di giri. Il noding
resta a GEOS. Un core Rust solo su una misura (tempi, o un host senza Python).
Decisi con Federico il 25 ottobre, da fare in 1.x:
- **warning sui pezzi d'ingresso che coincidono** (un `CIRCLE` ripassato da
  una polilinea, anch_06): è un difetto del disegno, topo lo dice e non ne
  cancella nessuno (D137); cosa farne è del consumer. Sostituisce "cerchi
  doppi".
- **terza lettura, la rete**: i gruppi di pezzi che si toccano o si
  incrociano, coi punti di contatto, senza contorni né dentro/fuori. È la
  domanda sotto `heal()` e `island()` (che già raggruppano e rendono piana
  la rete, solo internamente), per chi usa la geometria senza leggerla come
  pezzo o come vista.
- **da ragionare: griglia per le spline** (come D145/D153). Oggi
  `BSplineSeg.discretize` è adattiva sul proprio intervallo: un pezzo di
  spline tagliato (D163) non dà gli stessi vertici del tratto dell'intera.
  Una griglia nel parametro dell'intera lo renderebbe un pezzo del suo
  poligono. Serve solo se si vede un difetto (finti buchi/sovrapposizioni
  fra pezzi della stessa spline); nessun rosso oggi (D167).

## FATTO (23 ottobre) — shape dei pezzi chiusi in loose (D162)

D162: un pezzo che chiude da sé esce da `island()` come un `ClosedCurve` in
`loose`; `contour_shape` lo legge, `anchor_texts` lo aggancia (`"loose[k]"`).
Federico ha guardato i DXF: golden `anch_01`/`anch_08` rigenerati (17 e 1
agganci nuovi, nessuno perso). Resta a snapdraw: leggere i fori da `loose`
invece che da `cluster.inners` (da annotare nel suo TODO).

Storia della voce:

Con D161 un foro letto da `island()` è un pezzo chiuso in `loose` (un
`CircleSeg`, un percorso che chiude da sé), non più un inner: `anchor_texts`
non lega più una quota Ø8 o una freccia al suo cerchio, e `contour_shape`
non lo classifica. Idea di Federico: esporre dall'API la shape (cerchio,
stadio, ellisse, rettangolo, poligono) dei pezzi chiusi in `loose`, così un
detector non la ricalcola e `anchor_texts` li usa come bersagli. Un pezzo
che chiude da sé non è un ciclo scelto (D161 resta): è un fatto
dell'ingresso. Da decidere (D162) e da confrontare con la detection di
snapdraw. Difetti noti finché è aperto: 5 test in
`tests/unit/test_anchor_texts.py`, `TestContourShapeSuIsole.test_island`.

Stato dei difetti noti d'isole dopo D161: G6b out once 13 → 4 (regr_01,
anch_06, regr_04, anchoring anch_06_noframe), G6c scrambled 26 → 2
(anchoring anch_08_noframe, islands anch_08), G7 roundtrip 4 → 0.

## APERTO (17 ottobre) — la strada verso la 1.0.0

Obiettivo: API stabili su cui un terzo costruisce i suoi algoritmi con le
primitive di topo.

0. ~~**topo non ha un formato** (D123)~~ — chiuso con D129–D130 (0.20.0).
   topo conosce geometria e ruoli; i layer non esistono, li sceglie un
   exporter dai ruoli. Gli adapter DXF e PDF diventano pacchetti separati
   nello stesso repo (`topo_dxf`, `topo_pdf`, extra `g-topo[dxf]`/`[pdf]`,
   confine controllato da `gen_index`, D124); `ezdxf` non è più una
   dipendenza di `topo`. In ordine:
   1. ~~**Il contratto di un adapter, pubblico.**~~ — fatto, D125:
      `Edge.of` al posto di quattro copie dell'arrotondamento, via
      `Adapter`, `load_geometry` fuori da `adapters/`; gli adapter importano
      solo `topo.model`/`topo.primitives` (regola `adapters` in pyproject).
      `layers.py` → `rules.palette` chiuso col passo 3 (D128).
   2. ~~**Vocabolario neutro nel modello.**~~ — fatto, D126: `EdgeStyle`
      con `dash` (segni con segno) e `color` RGB, `RoleRule(color=)` in RGB,
      `Annotation.layer` → `group`. `LAYER_*` in `recipes.py`/`io/exporter.py`
      vanno via col trasloco (passo 4), palette e `Trash` col passo 3.
   3. ~~**Uscita per ruolo.**~~ — fatto, D128: `RoleStyle` neutro nel
      modello; `to_dxf(layers={ruolo: nome | funzione(elemento)})`, un ruolo
      su più layer se il chiamante lo chiede; la palette è di topo, una
      per ogni formato (`topo.model.role_style`), la mappa del chiamante ci
      va sopra; i nomi dei layer (`Trash` compreso) sono il default
      dell'adapter DXF; via il registro globale (riaperto D47),
      snapbend e snapdraw pubblicano `ROLE_STYLES`/`LAYERS`; via
      `Annotation.group` (C di D127). Il salto dei layer `trash`/`annotation`
      nel lettore è diventato `skip_layers` col passo 4.
   4. ~~**Il trasloco.**~~ — fatto, D129: `topo_dxf/` e `topo_pdf/` accanto
      a `topo/`, extra `g-topo[dxf]`/`[pdf]`, `ezdxf` fuori dalle
      dipendenze; `topo.split` → `list[Result]` in `tools/split.py`;
      `load_dxf(skip_layers=SKIP_LAYERS)`; `gen_index` indicizza ogni
      package e vieta formati e adapter a `topo`, gli interni di topo agli
      adapter.
   5. ~~**I consumer.**~~ — fatto, D129: snapbend, snapdraw, i test e gli
      script di topo. smoother: riscritto nel suo lavoro in corso (non
      committato, `pipeline.py`, `webui/`, `00_image_to_dxf.py`) — va
      committato con quello.
   6. ~~**Docs e una minor che rompe.**~~ — fatto, D130: 0.20.0; README,
      API (§9 `topo_dxf`, §10 `topo_pdf`), ARCHITECTURE, LLM per i tre
      pacchetti; i README/API di snapbend e snapdraw allineati.
   7. **Il PDF, da riprendere per bene.** Il lavoro fermo nella cartella
      sorella `forge-pdf-adapter` (worktree a 0.13.1, nomi `forge`, modifiche
      non committate) non è stato portato: quando si riprende il PDF si
      parte da `topo_pdf/` e lo si porta lì, con `load_pdf` che restituisce
      un `Document` come ogni adapter (oggi `list[Edge]`, D10).
      La worktree e il suo branch `experiment/pdf-adapter` restano finché
      il PDF non si riprende (Federico, 19 ottobre): non proporre di
      cancellarli. Gli altri branch locali, copie della storia di prima
      della riscrittura, sono stati cancellati lo stesso giorno.
1. ~~**Rename `forge` → `topo` / `g-topo`**~~ — fatto, D119 (0.17.0), insieme
   a D117: via i prefissi `Forge*`, i passi di heal/island in `topo.steps`.
   Il repo GitHub è già `topo` e `origin` punta lì; la cartella locale è
   `GitHub/topo`, editable reinstallato e worktree `forge-pdf-adapter`
   riparato (18 ottobre).
2. ~~**Superficie pubblica esplicita**~~ — fatta: prima metà D120 (0.18.0),
   seconda metà D122 (0.19.0). Misure e fatti sugli assi in `topo.geometry`;
   `"*"` attivo in snapbend e snapdraw. Fuori dalla 1.0 stabile, apposta: le
   strisce fra regioni annidate (`tools.strips`, D142, sperimentali) e la tabella dei layer
   DXF (un `topo.layers` pubblico provato e tolto: topo non ha layer, D123).
   Restano: `gen_index` in smoother (non ce l'ha), i lab di snapdraw come
   richieste (sotto).
3. ~~**Le primitive di D109**~~ — fatte, D118. Criterio: un algoritmo esterno
   (le scantonature a disco del prototipo) tiene private solo le scelte di
   processo — quali spigoli, che raggio, come raggruppare — e nessuna
   geometria che un altro consumer riscriverebbe uguale (cerchio × arco
   esatto, contorno meno disco, anello di segmenti).
4. ~~**Ordine degli edge**~~ — fatto, D131 (0.20.1): il criterio
   non-contorno giudica la catena fra due nodi di branching, non l'edge;
   `TestEdgeOrder` prova il contrario e 5 rimescolamenti a seed fisso,
   `KNOWN_ORDER_DEPENDENT` vuota.
5. ~~**Viewer**~~ — deciso, D133: fuori dalla 1.0 stabile (`to_view_model`,
   `to_svg`, `save_svg` importabili ma non in `__all__`); il rifacimento resta
   il punto 9 dei vecchi fili, dopo.
6. **Audit dati cliente della 1.0** (più sotto): i blocchi nei commit vecchi.
7. **Fedeltà a due vie** (D121) — la condizione perché il tool sia
   affidabile: il pezzo prodotto da topo è sovrapponibile all'originale.
   Oggi `TestNothingDropped` prova solo un verso (ogni ingresso sta entro la
   tolleranza da un'uscita), e solo sul modello. Manca l'altro verso (ogni
   uscita sta entro la tolleranza da un ingresso: niente geometria inventata
   o spostata più del dovuto) e la prova sul DXF scritto e riletto, non sul
   modello in memoria. Distanza di Hausdorff nei due versi ≤ tolleranza di
   heal; dove heal non è intervenuto, coefficienti identici (stesso centro,
   raggio, punti di controllo). Più un DXF di overlay (originale + uscita +
   punti oltre soglia) da guardare a occhio.
   Non solo test: `heal()` misura e riporta nel risultato lo scostamento
   massimo che ha introdotto e dove (per entità), così su un disegno
   disastrato nessuno deve verificare a mano — il file dice di quanto è
   stato toccato. Le spline non toccate escono con gli stessi punti di
   controllo (lo stesso problema già visto in D41, reso invariante).
8. **Modello `Curve` e firma dei contorni** (D121) — cambia nomi pubblici,
   quindi prima della 1.0: protocollo comune per le cinque primitive
   (`point_at`, `tangent_at`, `length`, `bbox`, `reversed`, `sub_curve`,
   `closest_point`, `discretize(tol)`), `as_analytic(tol)` (riconoscimento
   come domanda, la geometria originale resta la verità), `SplineSeg` →
   nome matematico (`BSpline`, con pesi opzionali), `to_biarcs(tol)` solo
   predisposto (oggi biarchi li fa il CAM). Firma pubblica di un contorno:
   sequenza canonica di primitive con misure, invariante a punto di
   partenza e verso — primo candidato `_canonical` di
   `snapbend/rules/read_section.py`. I pattern (svasature, sezioni, …)
   restano codice nei consumer.
   Da fissare insieme (18 ottobre): l'elenco di `contour_shape.kind`
   (circle/stadium/rectangle/polygon/other). Aggiungere un tipo dopo la 1.0
   cambia il risultato di chi oggi conta su `other` (snapdraw). Proposta:
   chiuso a quelle forme elementari, dichiarato stabile; ogni forma in più
   arriva dalla firma, nel consumer. Oggi costruire una forma è già del
   chiamante (`topo.geometry.rectangle`/…/`polygon`, `Contour.from_segments`);
   riconoscerla no: si rifà a mano la ricomposizione dei lati e il punto di
   partenza, che è proprio quello che la firma deve dare.
   Accanto, additivo (può essere 1.x): i **fatti di riconoscimento** che un
   consumer usa per dire "questa è roba mia", come già `concentric_groups`
   (svasature) e `arcs_around` (filetti), D91. Federico, 18 ottobre: non dime
   (la L, l'omega), ma i segnali di una lamiera. Oggi snapbend li calcola a
   mano in `rules/read_section.py` (forge-free per D43, "da riguardare quando
   l'interprete è vero"): coppie di rette parallele (distanza, sovrapposizione
   delle proiezioni, angolo) e coppie di archi concentrici fra loro (differenza
   di raggio, sovrapposizione angolare). Sono geometria, quindi prima o poi
   `topo.geometry` (D93-D95); lo spessore dalla tabella e "è piegata" restano
   di snapbend. Non bloccano niente: si promuovono in una minor quando un
   secondo consumer ne ha bisogno (snapdraw, lo spessore in una vista), così
   il fatto si disegna su due usi veri. Vale per ogni fatto nuovo dopo la
   1.0 (i dischi di cogo, D118, sono il precedente).

   **Deciso il 19 ottobre (D135–D137), da fare prima della 1.0:**
   - ~~**D135** `SplineSeg` → `BSplineSeg`~~ — fatto il 19 ottobre: campi
     solo geometrici, `closed`/`periodic` ricavati, fit points convertiti in
     lettura; tolto il tetto di 400 punti di `_refine_segment`.
   - ~~**Tetto di 128 lati su `CircleSeg.discretize`**~~ — fatto il 19
     ottobre, D145: tolto, e cerchi e archi su una griglia per cerchio.
     **Lasciati rossi apposta:** `test_golden_anchoring` anch_02–07 e
     `test_text_budget` anch_06 (golden di `island()`, congelati dai dubbi
     D103; anch_06 cambia topologia, vedi "Trovati con D145" più sotto).
     Nota originale: (trovato con D135): la
     tolleranza è una freccia assoluta, quindi i lati devono crescere con il
     raggio (~π·√(r/2·tol)); oltre r ≈ 33 a tol 0.01 il tetto la viola (r 500
     → freccia 0.15). Stessa cura del tetto delle spline; cambia golden,
     da giudicare a parte. Guardare anche `ArcSeg`/`EllipseSeg`.
   - **Criterio del punto medio in `_refine_segment`** (nota, non urgente):
     guarda solo il punto medio di ogni tratto; su un tratto a S il medio
     cade sulla corda mentre i lobi escono, e la suddivisione si ferma
     presto. Oggi lo copre il campionamento iniziale fitto (misurato: 0.00988
     a tol 0.01 su `quadro_fori_spline`).
   - ~~**D136** `contour_shape.kind`~~ — fatto il 19 ottobre: sei kind,
     `ShapeKind`, `ellipse()`, `TestShapeKindStabile`.
   - ~~**D137** `trash_entities` → `result.loose`~~ — fatto il 19 ottobre:
     `cluster_ref` su ogni curva, `topo.promote`, `split` per `cluster_ref`;
     snapbend usa `cluster_ref` e `promote`. Il layer DXF resta `Trash`.
   - ~~**D138** `Annotation`/`Note`/`Dimension`/`Leader` → `Text`~~ — fatto
     il 19 ottobre; golden convertiti chiave per chiave, stessi valori.
   - **Rassegna dei campi di `Result`/`Cluster`** (sono API): `List[Any]`,
     `all_arcs`, `classified_entities` (di un consumer, D88), `_open_shapes`.
   - ~~**Cosa promette la 1.0**~~ — deciso il 19 ottobre, D143: nomi e
     firme *e* la geometria, come invarianti (fedele nei due versi, completa,
     deterministica), non come numeri dei golden. Ne seguono, bloccanti:
     la fedeltà a due vie (punto 7), il tetto di 128 lati qui sopra, i 4
     dubbi su D103 verificati (non esclusi), e il giro scartato come
     duplicato che va in `result.loose`, mai in un bucket di scarto.
   - **Documenti del lettore in inglese** (D144, bloccante): `docs/API.md`
     (1843 righe) e `docs/ARCHITECTURE.md` (405) tradotti; docstring dei nomi
     pubblici (`__all__` di `topo`, `topo.geometry`, `topo_dxf`) in inglese,
     corte. L'interno resta in italiano. Un controllo (in `gen_index` o un
     test) che lo verifichi sui nomi pubblici, invece di ricordarlo.
   - **README fuorviante** (Federico, 19 ottobre, bloccante): sembra una
     libreria solo per disegni tecnici, a partire dal titolo ("for
     technical drawings and CAD geometry") e dagli esempi. Va riscritto per
     quello che topo è: un motore di geometria 2D (contorni chiusi,
     contenimento, le due letture) di cui i disegni tecnici sono un caso.
     Con `README_IT.md` e la prima riga di `CLAUDE.md` / `pyproject`
     (description), che dicono la stessa cosa.

   Restano 1.x: modello `Curve`, `as_analytic`, firma dei contorni, i fatti
   di riconoscimento, le strisce di D134. Le nervature: tutto il resto
   (l'opzione "foro" della scelta A, fatti nuovi) è additivo e viene dopo.
9. **Dopo la 1.0, additivo (non blocca):** curve da equazione. Una `Curve`
   costruita da una parametrizzazione esatta (`x(t), y(t)` su `[t0, t1]`)
   che ricorda la sua origine (`curve.source`: "generata da questa
   equazione"), valutata esatta nel modello; nel DXF esce come LINE/ARC
   quando lo è, altrimenti come spline o polilinea entro `tol` — il CAD
   resta solo al confine, nello scrittore. Primo cliente vero: sviluppi
   che non sono archi (cilindro tagliato obliquo → sinusoide, innesti tra
   tubi) in snapbend.

10. **snapfence, in beta, prima della release** (Federico, 18 ottobre): un
    nuovo consumer che genera cancelli velocemente "da varie cose". Scopo per
    topo: vedere se un terzo consumer chiede qualcosa che la superficie
    pubblica non dà (ogni richiesta va in "richieste dalla superficie"). Beta,
    senza esagerare: progetto a parte accanto a snapbend/snapdraw, setup come
    gli altri (`python-project-setup`, `gen_index`).
    **Avviato il 19 ottobre** (`../snapfence`, 0.1.0, solo scheletro). Ingressi:
    misure del vano + un motivo da un disegno qualunque (logo, numero civico,
    decoro) che diventa la lamiera di tamponamento traforata; uscita: DXF di
    taglio dei pezzi piani (snapfence MAP D2). Le richieste attese (scalare e
    spostare un documento, strisce fra regioni annidate — ora `tools.strips`, D142, la politica è di snapfence —,
    scritte lasciate come TEXT) stanno nel TODO di snapfence e arrivano qui
    solo quando uno script le chiede davvero.

Poi topo 1.0.0, e snapbend 1.0.0 dietro.

- **Disegni di `island()` senza cornice** (Federico, 19 ottobre). I test di
  island girano sui disegni grezzi senza regole di ruolo: la cornice diventa
  l'isola più esterna e ogni vista un suo inner. Nessun consumer chiama
  island così — la cornice la riconosce snapdraw prima (notazione di disegno,
  significato del consumer, D90) — quindi i golden provano due cose insieme
  e una non è di topo. Federico toglie le cornici; proposta: copie senza
  cornice per i golden di island, gli originali restano per i testi e per
  snapdraw (gli `anch_*` servono anche ad `anchor_texts`, e i testi del
  cartiglio sparirebbero). Poi i golden di island si rifanno da zero su
  quelle (G7; i dubbi D103 sono chiusi, D157). Fino ad allora: `KNOWN_FAILING` in
  `test_golden_anchoring` (anch_02–07) e `test_text_budget` (anch_02, anch_06),
  fallimenti attesi, mai rigenerati.
  Non è una richiesta a topo la "provenienza" dei pezzi tagliati (quale
  entità del file erano): è un fatto di come il file è stato disegnato
  (regola 1); il fatto geometrico — stessa retta, stesso nodo — c'è già.
  Fatte le copie `golden_anchoring/anch_NN_noframe.dxf` (19 ottobre): cornice,
  fascia e cartiglio rilevati da snapdraw (`detect_frame`), tolte dal DXF
  originale le entità che coincidono con quegli edge; il resto è intatto.
  Il cartiglio snapdraw lo trova solo in anch_07 e anch_08: negli altri, se
  c'è, è rimasto. Confronto di `island()` con e senza cornice: nessun contorno
  nuovo, sparisce solo geometria tolta, **tranne anch_07**: due cerchi chiusi
  (simboli di rugosità, cerchio + due linee che toccano un rettangolo) sono
  `inner` dell'isola-cornice con la cornice, e `loose` dell'isola-rettangolo
  senza. Un cerchio chiuso non può cambiare natura per ciò che gli sta
  attorno: i loop chiusi di un pezzo fuori dall'outer scelto (D71 lo copre
  solo per un'isola annidata). DXF in `_debug/anch_07_island_*_cornice.dxf`.
- **Entità sovrapposte in `island()`** (Federico, 19 ottobre: "inner con una
  parte in trash"). Misurato sui `_noframe`: tratti di `loose` interamente
  sopra un contorno. Tre cause:
  1. ✅ lati dell'outer contati anche come sporgenze (D146).
  2. ⏸ **Ponti sui T** (D147, **sospeso**, codice sul branch `d147-t-ends`,
     annullato su `main`). Regola: un estremo sull'interno di un altro edge
     non è libero, salvo un altro estremo libero entro tolleranza. Decisione
     che resta: i giri con un lato sul contorno che li contiene sono trash
     (Federico). **Punto di ripresa:** `regr_04` è peggio dopo — l'outer
     della vista 3D era giusto prima, dopo perde una tasca di 30.8 mm² sul
     bordo sinistro (x 808–816, y 434–445;
     `_debug/regr_04_island_D147_prima/dopo.dxf`). Capire quale estremo, ora
     non più chiuso, teneva in piedi quell'outer, e se la regola deve
     distinguerlo; poi rimisurare tutti i disegni di island (vecchio contro
     nuovo) e riguardare i DXF prima di rimettere il codice su `main`.
  3. **Cerchi doppi**: CIRCLE + la stessa circonferenza tassellata
     (anch_06): `refit_tessellations` la rifà cerchio, ma
     `merge_cocircular_overlaps` prende solo `ArcSeg`, quindi due cerchi
     coincidenti (o un arco su un cerchio intero) non si fondono — anche in
     `heal()`. Da proporre a Federico (tocca heal e i suoi golden).
  Federico, stesso giorno: "un paio di imprecisioni sull'outer in una vista
  in anch_08" — da riprendere sui `_noframe`.
- **Trovati con D145 (griglia degli archi), 19 ottobre — tutti per la
  promessa geometrica di D143:**
  - ~~`rect_with_countersink`: `cluster.area`~~ — non un bug (D156): il
    Ø10 sta dentro il Ø30, depth 2, isola per D89.
  - `island()` decide il contatto di un giro con sé stesso sul poligono
    discretizzato (`_loop_faces`: `make_valid`, lobi, `face_segments`
    rilegge i segmenti dal bordo del lobo): la topologia cambia sotto la
    tolleranza. `anch_06`: un cerchio D2.2 toccato dalle linee di un simbolo
    passa da `circle` a `other` (2 linee + arco) cambiando solo la
    discretizzazione dell'arco, e l'estremo di una linea si sposta di 0.023
    (> 0.01). Il contatto va deciso sulle primitive (intersezioni esatte),
    prima di rifare i golden di island (G7).
  - ~~`contour_shape` di `other` sul poligono~~ — fatto, D156.
- **`test_text_budget::test_anch_02` rosso già su `0d5a512` (D138)**: `to_text`
  di anch_02 fa 200.435 caratteri contro un budget di 193.366 (+3.7%). Visto il
  19 ottobre lavorando a D140, non causato da D140 (rosso anche sull'HEAD
  pulito). Capire se D138 ha aggiunto testo legittimo prima di toccare il
  budget (regola: mai rigenerare per far passare).

## APERTO (17 ottobre) — richieste dalla superficie

Un prototipo (script, lab, pipeline di terzi) può importare da `topo.core`
mentre esplora; un pacchetto pubblicato no (regola `"*" = ["topo.core"]` di
`gen_index` nel suo pyproject). Ogni import dal core di un prototipo è una
richiesta: una riga qui (chi, cosa, perché). Quando l'idea è stabile si
smista, mai in automatico:

- **fatto geometrico** (esisterebbe anche in un topo riscritto, anche in
  Rust) → nome pubblico in topo, con docs, test e un D##;
- **pezzo dell'algoritmo** (`LoopFinder`, `_outer_face_walk`, …) → capire
  cosa il prototipo stava ricostruendo e offrire quello, al livello giusto;
- **processo o scelta del chiamante** → resta nel prototipo.

Dopo la 1.0, un nome utile ma non ancora sicuro può passare da
`topo.experimental` (pubblico, dichiarato instabile, come le API
"provisional" di PEP 411) prima del suo posto definitivo.

Da D140 le richieste arrivano anche scritte: ogni consumer le mette nel suo
`TODO.md`, sezione `## Richieste a topo` (da una sessione nel consumer topo è
in sola lettura). Raccoglierle: `grep -n -A20 "## Richieste a topo" ../*/TODO.md`.
Chiedere non basta per entrare: ogni richiesta passa dai tre esiti qui sopra,
e un "no, resta nel consumer" si scrive qui col perché, così il consumer lo
trova e non la richiede. Nemmeno il codice già scritto entra perché c'è: D139
è entrata così (scritta in topo da smoother prima del blocco) e resta
sperimentale finché la riscrittura di D134 non la giudica.

Richieste aperte:

- ~~**pippo, trasformazioni di segmenti**~~ — fatto, D170: `mirrored(origin,
  angle)` su qualunque retta (default l'asse x di prima) e `scaled(factor,
  origin)` uniforme, su tutte le primitive, esatti. **No**: scala non
  uniforme e affine generica (un arco diventerebbe un'ellisse); il moto
  rigido è la catena `mirrored(...).rotated(...).translated(...)`.
- ~~**pippo, unione di contorni con un bordo in comune**~~ — fatto, D171:
  `geometry.contour_union` (26 ottobre). `cancel_on_line` in
  `lab/flat_L.py` di pippo si può togliere.
- ~~**smoother, linguette a click** (D139/D140) e **linguette che non
  attraversano niente** (19 ottobre)~~ — fatto, D142: `tools.tabs` è
  diventato `tools.strips`, i quattro fatti di D134 più la costruzione.
  Entrato: bordi affacciati, distanza, striscia in un punto (anche fra
  sorelle, rifiutata col perché se attraversa un bordo o un'altra striscia),
  regioni non collegate, bordi aperti in catene di primitive. **No, resta a
  smoother** (scelte sue): quali regioni ricevono strisce (`is_tab_island`,
  `min_island_size`), quante e dove (`tab_count` attorno al centroide), a
  quale isola va un click (`_anchors_by_island`). Da fare in smoother:
  `bridge_parent_tabs`/`bridge_nested_tabs` → un `link` per punto con
  `placed=` + `open_boundaries`; `_crossing_islands` sparisce (lo fa `link`);
  i tratti sono catene di `LineSeg` (punti: gli `start` più l'ultimo `end`),
  i fianchi `opened.sides`.
- ~~**smoother, spigoli per svolta / linee dove è dritto / arco per gli
  estremi / spline con tolleranza**~~ — fatto, D141 (`simplify_points`
  riscritta). Resta a smoother: buttare `smoother/fitting.py` e chiamare
  `topo.simplify_points(pts, tolerance, scale, closed, corner_turn_deg, arcs)`.

- **snapdraw `lab/`** (D122): `LoopFinder`, `segments_from_loop`,
  `edge_styles_from_loop`, `build_node_graph`, `split_at_crossings`,
  `edge_geometry`, `_outer_face_walk`, `_normalize`/`GRAPH_EPSILON`
  (`core.island`), i pezzi di `healing/outer_scan` (`_pieces`, `_extent`,
  `_intersections`), `HealStep`/`_loop_is_structural`,
  `loop_to_closed_feature`, `build_polygon`, `DEFAULT_TOLERANCE`,
  `_configure_odafc`. Quasi tutti sono il grafo e i giri: la domanda è quale
  fatto il lab stava ricostruendo (il giro esterno di un grafo? le facce?) e
  se diventa un passo di `topo.steps` o un fatto di `topo.geometry`. Va
  insieme alle ricette (filo sotto).
- **Due misure del cerchio** (D122): `circular_geometry` (bounding box del
  poligono discretizzato) resta interna e la usa `healing/hierarchy.py`;
  `contour_shape` dà quella esatta. Da unificare su `contour_shape`, provando
  i golden come in snapbend D66.

## APERTO (18 ottobre) — tre fili da ragionare con Federico

- **Datum** (riferimenti di un pezzo: origine e assi da cui si misura). Il
  fatto geometrico è di topo — un sistema di riferimento attaccato a un
  contorno (uno spigolo, il centro di un foro, un lato) e le coordinate
  espresse in quel riferimento; quale datum scegliere (A/B/C, "si quota dalla
  piega") è del consumatore (framer). Additivo: può arrivare in una 1.x,
  purché la 1.0 non leghi niente al solo sistema mondo.
- **La scansione** (`healing/outer_scan`, i raggi del lab `island_rays`):
  come farla completa, e a cosa serve oltre al giro esterno — da capire
  prima di decidere se diventa pubblica.
- **Ricette di ricomposizione topologica**: oggi `heal` (un pezzo piano,
  geometria da riparare) e `island` (un disegno con più viste, per isole). Se
  ce ne possono essere altre e che senso hanno; sono la cosa che i lab di
  snapdraw stanno già provando a comporre con i pezzi interni. Candidata
  emersa il 18 ottobre: una lettura "mesh" dove una faccia interna chiusa è
  vuota per default (scelta A qui sotto).
- **Scelta A: faccia interna chiusa, materiale o foro?** (D131, pagina dei
  criteri). Oggi le catene interne a 0 passaggi sono corde: rettangolo +
  quadrato interno + 4 diagonali angolo-angolo → 1 pezzo pieno, 8 linee nel
  trash, e `detect_flat` non ci trova niente (le diagonali non hanno i due
  capi sul contorno esterno). Federico: su una lamiera quelle diagonali non
  possono essere pieghe (un flat così non si piega); l'unica lettura sensata
  è irrigidimento (le crocette di pressione su pannelli larghi e sottili,
  cancelli, sponde), quindi pieno. Federico: "corda e opzionalmente
  foro", ma la regola per l'opzione (quali facce sono vuote: proposta
  "nessun lato sul contorno esterno") non è decisa. DXF locali in
  `tests/lab/caso_A/` (fuori da git).
  Un secondo esempio, visto il 26 ottobre verificando D171: piastra 9×11
  attraversata da una linea a y=9, con tre pareti appese che chiudono un
  foro 3×6 contro quella linea. Oggi `heal()` dà l'esterno, nessun foro, e
  linea e pareti in `loose`. Il foro non ha lati sul contorno esterno,
  quindi con la regola proposta sarebbe vuoto. Nota: `heal()` non mette un
  nodo nei T (D131), quindi le pareti oggi non toccano neanche la linea.
  Con la sola regola A, a T nodati, le catene a 0 passaggi sarebbero corde
  e il risultato sarebbe lo stesso. Prova: `load_segments` + `heal`, DXF in
  `_debug/2026-10-26_topo_contour_union/caso4_U_barra.dxf` (pannello 3).
  Non è l'opzione "foro" (Federico, 26 ottobre). Un disegno così è un
  assieme, pezzi saldati o multipezzo (il futuro snapweld; i fili sono in
  `snapdraw/TODO.md` e `pippo/TODO.md`): U e barra sono **due pezzi**, la
  linea a y=9 è il bordo dove si toccano, e il vuoto 3×6 è lo spazio fra
  loro, non il foro di nessuno. Quella lettura spezza in pezzi lungo i bordi
  in comune, e serve di sicuro. Sul pezzo piano di `heal()` il default resta
  pieno.
- **Scelta E: un foro con un vertice in comune col contorno esterno** (D132).
  Oggi resta un foro (la sua catena è chiusa su un nodo, mai corda).
  Federico: per lui è trash (con warning). Nessun golden di heal e nessun
  DXF di snapbend lo contiene: si decide quando arriva un disegno vero.

## CHIUSO (18 ottobre, MAP.md D111, D131) — invarianti di heal

D111 ha chiuso il criterio non-contorno sui lati concavi e il crash su NaN, e
messo le invarianti di `heal()` (`tests/unit/core/test_heal_invariants.py`).
L'ultimo filo, l'ordine degli edge su `linee_di_piegatura_interne`, è chiuso
da D131: il criterio giudica la catena, non l'edge.

## CHIUSO (17 ottobre, MAP.md D118) — contorno meno regione, traccia × contorno

Fatte: `intersections`, `point_on_contour`, `cut_by`, `contour_minus`,
`Contour.from_segments`, più l'invariante "i segmenti di un contorno sono
un anello". Resta: `contour_minus` rifiuta i bordi che corrono uno sull'altro
(`ValueError`): da gestire se un caso vero lo chiede.

## CHIUSO (12 ottobre, MAP.md D106) — `.polygon` vs `.segments`; resta un filo, dentro D103

Risolto: i segmenti di una faccia si leggono dal suo bordo (`topology/rim.py`,
taglio esatto delle primitive in `primitives/trim.py`, spline comprese); un
giro che tocca se stesso è una faccia per lobo (prima `buffer(0)` buttava i
lobi minori in silenzio); una faccia più stretta della tolleranza di nodo non
è una faccia. La pista di D105 (rigrafo a banda larga) è smentita dai numeri:
metà del bordo stava su edge solo in parte sul bordo, nessun ordine e nessuna
banda li recupera. Coerenza verde su 15/15, round-trip su 13/15. DXF prima/dopo
da guardare a occhio: `_debug/*_D106_prima.dxf` / `*_D106_dopo.dxf`
(anch_02, anch_03, anch_06, drw_0011, regr_01, regr_02, regr_04).

Due invarianti nuove (D107): `TestNothingDropped` (verde 15/15) e
`TestInnersDontCross` (rosso apposta su anch_03/regr_02, il filo qui sotto).
Golden delle isole: **si rigenerano tutti insieme quando i dubbi D103 sono
chiariti** (lo sono, D157), guardando prima i DXF — deciso con Federico il
12 ottobre. Si fa in G7.

**Filo rimasto, in G7 (non è D103, D157):** round-trip di
`anch_03`/`regr_02`, l'isola da 5806 mm² passa da 28 a 15 inner. Già rosso
su `06b89b1`. Causa: giri inner che si **sovrappongono in parte** fra loro
(es. 18.7 + 71.1 mm², unione 76.6): cicli di LoopFinder che non sono facce;
rileggendo, i contorni sovrapposti si fondono. Nessuno di questi giri è
scartato da D103 (verificato in D157): 27 coppie
sovrapposte su anch_03, 25 su anch_02, quasi tutte contenimento pieno.

## CHIUSO (23 ottobre, MAP.md D157) — 4 dubbi su D103

Verificati uno a uno: ogni giro scartato ha tutto il bordo entro tol +
max_gap da un contorno già tenuto (non ha un bordo suo alla distanza di
contatto di `island()`), lo scarto segue `max_gap` e i suoi edge sono in
`loose`. DXF con i giri scartati in rosso: `_debug/2026-10-23_topo_G6_D103/`.
Restano per G7 gli inner che si incrociano su anch_03/regr_02.

---

## RIPARTENZA — D101 (nodo a T / quasi-tangenza), branch `topology/t-junction-noding`

**Fatto, verde** (MAP.md D101): `_split_params` (`noding.py`) fonde due tagli
entro `tolerance` in un nodo solo, non due — la causa isolata di D100. Suite
810 (809 verdi). Nuovo test: `test_noding.py::test_quasi_tangenza_e_un_nodo_
solo_non_due`. Branch creato da `main` a `108b74c` (prima dello stash del
lavoro PDF in corso, sotto).

Lo stash dell'esperimento scartato di D101 è stato tolto il 12 ottobre, con
l'ok di Federico. Resta solo lo stash del lavoro PDF in corso (`On main: WIP
pre topology-noding branch`).

**Nuovo filo aperto (11 ottobre, non ancora capito a fondo) — inner "fantasma" vicino
alle asole/forellini, anche con l'albero committato (non è un residuo dello stash
PDF):** su `tests/data/golden_islands/anch_02.dxf` (vista isometrica, cluster[1]),
confermato da Federico guardando `_debug/anch_02_3D_from_dxf_CLEAN_TREE.dxf` (`island()`
sul codice committato di questo branch, nessuno stash applicato):

1. L'asola grande (`inner[0]`, area 1011 mm², bbox 1421–1507 × 101–158) ha una punta
   arrotondata rovinata da una spike di 0.33 mm: il bordo liscio arriva a
   (1506.30, 105.58), scatta fuori a (1506.63, 105.39) e torna a (1506.30, 105.19)
   prima di richiudersi. Tre punti a 0.3–0.4 mm l'uno dall'altro che dovrebbero
   essere un nodo solo non si sono fusi — stessa famiglia di D100/D101
   (quasi-tangenza) ma **non risolta da D101**: il fix di D101 è già committato su
   questo branch e il difetto resta. Sembra un punto reale (fit-point della spline
   di raccordo) che non coincide con la curva healed, non un duplicato banale.
2. **Sistematico, non isolato**: nello stesso cluster, circa 20 forellini del
   pattern di foratura (bbox ~3.5mm, es. 1540–1544×128–134 e 1540–1544×104–109)
   hanno **due** inner quasi sovrapposti nello stesso punto: uno pulito (l'ellisse
   proiettata vera, 2 BSplineSeg che chiudono da estremo a estremo, area ~16 mm²) e
   uno "fantasma" annidato dentro, fatto di 2 ArcSeg + 4-7 BSplineSeg minuscoli e
   seghettati (area ~11 mm², non zero come i fantasmi di `regr_04`/D101 — qui è
   un'area reale, sbagliata). Pattern: `cluster[1].inners[26,28,30,32,...64]` su
   `anch_02.dxf` (script di ispezione non salvato, rifare con `topo.island()`
   + `max_gap=0.5` se serve riprodurre).
3. Federico non si fida più dei golden su questa classe di fogli: **confermato**
   che il motivo è reale — `test_golden_islands.py` confronta solo bbox outer e
   **conteggio** inners (non la forma), `test_golden_anchoring.py` solo il testo
   delle annotazioni: nessuno dei due avrebbe mai potuto vedere né la spike né gli
   inner fantasma, a differenza di `tests/real/test_golden.py` (`heal()`, parti
   piatte) che confronta la forma via WKT/shapely con tolleranze stette.
4. **Bisecato (11 ottobre) su worktree a commit vecchi, stesso `anch_02.dxf`, stesso
   `max_gap=0.5` — due bug distinti, non uno:**
   - **Fantasmi (punto 2 sopra): preesistenti**, identici su `1b5b02e` (D99, prima
     di tutto il lavoro di questa sessione). `fitting.py`/`points.py` non sono mai
     stati toccati per il PDF nella storia committata (solo spostati, D95) — non è
     una contaminazione del lavoro PDF. Raw edge nel punto caldo (1538–1546 ×
     127–135, prima di `island()`): 2 `ArcSeg` + 13 `BSplineSeg`, un'unica rete
     connessa — e tornano spalmati esattamente sui due inner (2 spline nel pulito,
     2 arc + 11 spline nel fantasma). Quindi non è il source duplicato: è
     `island()` che da una rete sola trova due giri chiusi (uno vero, uno fantasma)
     e li riporta entrambi come inner (D71 dice "tutti i giri chiusi" — corretto
     per isole scollegate, probabilmente non per questo caso).
   - **Spike (punto 1 sopra): introdotta da D100.** Pulita su `1b5b02e` (D99, punta
     a x=1506.30 netta), già rotta su `091970a` (D100, "the outer face is the
     boundary of the union of the closed faces", x=1506.63) — **non è D101**, il
     fix di questa sessione è innocente qui. Riapre di fatto la domanda del punto 3
     di "Resta da chiudere prima di mergiare" sotto: non è solo "forse ridondante",
     D100 **regredisce** un caso quasi-tangente sul bordo dell'unione.

**Piano di fix (deciso l'11 ottobre):**

1. ✅ **Fatto (11 ottobre) — test di regressione PRIMA del fix, rossi apposta.**
   Due fixture ritagliate dal foglio reale (non costruite a mano/analiticamente:
   i bug coinvolgono spline vere, 62 nella seconda — minimizzarle a mano non
   valeva l'effort), salvate con l'API di topo (`OpenFeature`+`Result`+
   `topo.to_dxf`, mai `ezdxf` diretto) — **attenzione**: il ruolo dev'essere
   un slug qualunque tipo `"geometry"`, **non** `"unknown"` — `role_to_dxf_layer`
   manda `unknown` sul layer `Trash`, e `DxfAdapter.to_edges()` scarta `Trash` a
   lettura (`_NON_STRUCTURAL_LAYERS`, `adapter.py:40`) — ci si casca dentro,
   verificato sul roundtrip prima di fissare le fixture:
   - `tests/data/regressions/island_ghost_loop.dxf` (15 edge: 2 `ArcSeg` + 13
     `BSplineSeg`, il foro col giro fantasma)
   - `tests/data/regressions/island_tangent_spike.dxf` (71 edge, l'asola con la
     spike)
   - `tests/unit/core/test_island_regressions.py` — `TestGhostLoop` e
     `TestTangentSpike`, caricano le fixture via `topo.load_dxf` +
     `topo.core.island.read_island(edges, tolerance=0.05, max_gap=0.5)`.
   Stato suite confermato: 809 passed, 3 failed (i 2 nuovi + `regr_04`, già
   rosso e noto, punto 1 sotto — nessun'altra rottura, `gen_index.py --check` ok).
2. ✅ **Fatto (11 ottobre, stessa sessione del punto 1) — i due fix.** La prima
   ipotesi (punto 3 di sotto, sede del bug in `outer_face.py`) era **sbagliata**:
   verificato con un giro-passo-passo che `outer_face()` da sola, su `doc.edges`
   crudi, già dà il risultato giusto (1011.26, nessuna spike) — il bug si
   manifesta solo dopo `_normalize()` (gap-fix), prima ancora che `outer_face`
   veda la rete. Entrambi i fix stanno quindi in `topo/core/island.py`, non in
   `outer_face.py`. Suite dopo i due fix: 810 passed, 10 failed — i 10 sono
   TUTTI golden islands/text-budget preesistenti impattati dal fix fantasmi
   (vedi "Impatto sui golden" sotto), **nessuna rottura nuova**: i 2 test di
   regressione (punto 1) sono verdi, `regr_04` resta nella stessa famiglia di
   rottura già nota (D101), `gen_index.py --check` ok.

3. ✅ **Fix spike — causa reale: `_normalize()` salda due estremi liberi che
   non sono un gap vero (`topo/core/island.py`).** La spike non nasce nel
   walk né nell'union di `outer_face.py` (quelli restano INTOCCATI): nasce
   prima, in `_normalize()`. Due `LineSeg` indipendenti (edge di un'altra
   faccia della vista isometrica, non il raccordo del contorno) hanno ciascuno
   un estremo libero a ~0.4mm dalla curva del raccordo (2 `BSplineSeg` già
   chiusi fra loro, la vera punta arrotondata) — entro `max_gap=0.5`, quindi
   `compute_gap_fixes` li tratta come un gap e li prolunga (retta-retta) fino
   alla loro intersezione reale, 0.33mm **oltre** la curva vera: una spike,
   non un gap chiuso. Il segno che lo tradisce: quei due estremi erano **già
   nella stessa componente connessa del grafo** (collegati altrove dal
   raccordo stesso) — saldarli apre un secondo percorso parallelo spurio
   (sliver) accanto al contorno che si chiude già da solo, non chiude niente
   che fosse aperto. Fix: `_drop_redundant_meets()` in `island.py` scarta un
   fix "incontro" (`MoveEndpoint` di retta/arco prolungata fino
   all'intersezione) quando i suoi due estremi di partenza sono già nella
   stessa componente connessa — un gap vero collega sempre due componenti
   diverse. Verificato: rigetta *solo* la coppia spuria del fixture
   (`TestTangentSpike` verde); su `anch_03`/`anch_08`/`regr_02` (golden reali
   con gap-fix legittimi, estremi in componenti diverse) non scarta nulla —
   la prima versione (filtro per prossimità a un'altra curva, non per
   componente) scartava anche questi per errore, scoperta e corretta
   confrontando i due casi fianco a fianco prima di fissare il criterio.
4. ✅ **Fix fantasmi — non è `split_at_crossings`/noding: è D71 troppo largo
   su un giro che duplica il bordo di un altro (`topo/core/island.py`).** Le
   15 edge sono **due componenti connesse separate** (13 e 2), ognuna già un
   giro chiuso per conto suo — non c'è autoincrocio numerico da correggere.
   Il giro fantasma (11.3 mm², 2 `ArcSeg`+11 `BSplineSeg`) sta **interamente
   dentro** il giro vero (16.25 mm², 2 `BSplineSeg`) e il suo bordo intero resta
   entro ~0.51mm dal bordo del giro vero (tipicamente la parete visibile di un
   foro in una vista isometrica, quasi sovrapposta alla sua stessa apertura).
   D71 ("ogni giro chiuso è un inner") è corretto per isole scollegate ma non
   per un giro che segue quasi lo stesso bordo di un altro già tenuto. Fix:
   `_drop_boundary_duplicates()` in `read_island()` — dato l'outer trovato
   (o un altro giro già accettato, in ordine di area decrescente), scarta un
   giro il cui bordo intero sta entro `tolerance + max_gap` dal bordo di un
   giro più grande già accettato (`big.exterior.buffer(band).contains(small.
   exterior)`); la soglia riusa i due parametri esistenti (nessuna costante
   nuova) — misurata sul fixture: 0.51mm, oltre `max_gap` da solo (0.5) ma
   dentro `tolerance+max_gap` (0.55). Gli edge del giro scartato non si
   perdono (non-negoziabile 7): ricadono su `NonContourEdgeDetector` come
   `non_contour` o `unclassified`, non più falsi "inner".

   **Impatto sui golden, verificato caso per caso ma NON rigenerato
   (non-negoziabile 9 — Federico deve giudicare a occhio):** 8 golden islands
   (`anch_02/03/06/07`, `regr_01/02/04/05`) e 2 text-budget (`anch_02/06`)
   ora falliscono per questo fix — perdono un inner a testa (o più su
   `anch_03`/`regr_02`, 32→28: lì il pattern è sistematico, non un caso
   isolato). Controllati a mano tre casi, tutti coerenti con lo stesso bug,
   nessun falso positivo trovato:
   - `anch_02` isola più piccola: perde un inner di area 3.10 mm² annidato
     dentro un inner pulito di 19.57 mm² alla stessa posizione (bbox quasi
     identico) — stesso pattern descritto sopra per `anch_02.dxf` nelle note
     dell'11 ottobre (punto 2), sui ~20 forellini del pattern di foratura.
   - `regr_04` isola[1]: il golden aveva già, da D101, un giro fantasma ad
     area quasi-zero (9.8e-13 mm², mai rigenerato — "il golden è letto dalla
     lettura vecchia e bacata", MAP.md D101); questo fix lo scarta anche lui
     (4→1 invece di 4→2), stessa famiglia di garbage, non un nuovo problema.
   - `anch_07` isola[0]: perde un giro minuscolo (0.076 mm², quasi un punto)
     che era un inner diretto dell'outer del pezzo stesso (non di un foro),
     col bordo a 0.51mm dal contorno esterno — stesso meccanismo, comparso
     accanto al contorno principale invece che dentro un foro.
   `test_text_budget.py` cresce di riflesso (gli edge del giro scartato
   finiscono in `non_contour`/`unclassified`, resi diversamente da `to_text`).

   **Prossimo passo per Federico:** guardare questi 10 casi a occhio (DXF
   aperti, non i numeri del golden) e confermare — poi, solo dopo, punto 5.

   **Nuovo filo aperto (12 ottobre) — stesso fix, lato PDF: completamente
   sbagliato, confermato da Federico a occhio.** I due fix sopra (punto 3 e 4,
   `_drop_redundant_meets` e `_drop_boundary_duplicates`) sono stati pensati e
   verificati solo sui golden **DXF**. Sul lato PDF (`_debug/anch_02_ALL_
   ISLANDS_from_pdf_BEFORE_FIX.dxf` vs `..._FIXED.dxf`, 11 ottobre 18:00-18:04,
   stesso pomeriggio del fix) Federico ha guardato i DXF e confermato: il
   risultato è completamente sbagliato, non un caso isolato. Non ancora
   root-causato — ipotesi non verificata: `band = tolerance + max_gap` in
   `_drop_boundary_duplicates` è calibrato sulla precisione DXF, e il residuo
   di un cerchio/arco PDF (fit ai punti Bezier campionati, non esatto come un
   `ARC` DXF — stessa causa di D102/D103 nello stash dell'adapter PDF) cade
   probabilmente proprio nella fascia che il filtro tratta come "duplicato da
   scartare", portandosi via inner veri. Da investigare con numeri reali
   prima di assumere questa causa, non solo a occhio.
5. **Solo dopo la conferma di Federico sopra:** rigenerare i golden islands e
   text-budget impattati, **poi** estendere `snapshot()` in
   `tests/real/test_golden_islands.py` a confrontare anche la **forma** di
   ogni inner (non solo bbox esterno + conteggio), sul modello di
   `test_golden.py` (WKT/shapely, tolleranza stretta) — così la prossima
   regressione di questa classe non passa inosservata.

**Resta da chiudere prima di mergiare:**

1. **`regr_04` — golden da far giudicare a Federico, non ancora rigenerato.**
   `island[0].inners` passa da 4 a 2: i due persi hanno area 1.85e-15 /
   1.88e-15 mm² alla stessa posizione — loop fantasma da zero area, non buchi
   veri (vedi MAP.md D101 per i numeri). Prima di rigenerare: fargli vedere
   (un DXF della zona, se lo vuole) e fargli confermare — non rigenerare da
   solo nemmeno con la prova in mano (CLAUDE.md non-negoziabile 9).
2. **Collisione di numerazione `D##` con `main`.** Questo branch numera la
   nuova decisione **D101** da `108b74c` (l'ultimo commit prima di questa
   sessione). Nella working tree di `main`, però, c'è ancora stashato (non
   committato) il lavoro dell'adapter PDF della sessione precedente, che
   numerava le sue decisioni **D101–D103** dallo stesso punto (vedi lo stash
   `"WIP pre topology-noding branch (pdf adapter circle-fit + naming note)"`
   su `main`, o `git stash list`). Quando l'uno o l'altro lavoro arriva a
   `main` per primo, il secondo deve rinumerare le proprie decisioni per non
   avere due D101 diversi nella storia. Non toccato qui: i due lavori sono
   indipendenti e nessuno dei due è stato fuso.
3. Non ancora valutato se il patch D100 (`_faces_union_loop`, union delle
   facce chiuse) sia reso ridondante dal criterio generale di D101 su qualche
   file — non è stato rimosso, D100 resta una decisione chiusa (va riaperta
   esplicitamente se si vuole toglierlo, non assunto qui).

---

0. **`load_geometry`: gli angoli dell'arco sono ancora in gradi** "per
   convenzione CAD" (resto di D96: `polygon` al posto di `polyline` fatto,
   costruttori e `load_segments` fatti). `ArcSeg` usa i radianti; passare lo
   schema ai radianti tocca la matematica di cono e sezione di snapbend
   (`core/cone.py`, `model/section.py`, lo scambio x/y di `model/geometry.py`).
1. ✅ **fatto (D93)** — **La geometria rimasta in `snapbend/flat/detect.py` torna in topo**
   (Federico, 4 ottobre: "tutto quello che è calcolo e geometria l'avrei messo
   in topo"). Su 828 righe la geometria pura è poca, ~70 righe; il resto è
   significato (ruoli, `Hole`, pieghe, incisioni) e lì resta. Ma due pezzi
   sono già doppioni di topo: `_point_line_distance` = `_point_to_line_distance`,
   `_same_line` = `are_collinear` (`core/geometry.py`). Da portare in topo con
   nomi geometrici: "una corda, prolungata di `reach`, divide il poligono in
   due" (`_cuts_part`) e "tratti sulla stessa retta, uniti dove lo spazio fra
   loro sta dentro un poligono dato" (`_bridged_runs`). La soglia `reach`
   (1 mm, snapbend D52) resta a snapbend come parametro.

1. **Pushare.** ✅ fatto insieme al rewrite (D81), 2 ottobre.
2. **`anonymize`** — **si prosegue in snapdraw** (deciso il 2 ottobre): il lavoro
   sul cartiglio e sui loghi è lettura del disegno, quindi è di snapdraw. Lo
   stato lasciato qui sotto vale come punto di partenza.
    — ✅ costruito (D77) e ✅ **uscito da topo (D80)**: non è più
   `topo.tools.anonymize`, è un progetto a sé (`dxf-anonymize`, repo privata,
   locale in `GitHub/dxf-anonymize/`), perché una dipendenza dichiarata in
   `pyproject.toml` di un consumer (snapbend, snapdraw) esporrebbe comunque nome
   e scopo dello strumento a chi guarda quella repo, anche con `dxf-anonymize`
   stessa privata. Dipende da topo (oracolo `heal()`), mai il contrario; si
   installa una volta con `pipx` e si lancia da terminale, nessun progetto lo
   nomina nei suoi file tracciati. `scan` aggregato su più disegni e `--find
   PAROLA...` ci sono già (fatti prima dell'estrazione, portati con sé).
   **Manca ancora:** installarla con `pipx` sul sistema (la repo privata è già
   su GitHub). **Aperto dal primo lotto vero (33 disegni, 2 ottobre):**
   `dxf-anonymize` ora legge i DWG (via ODA), scrive sul posto solo dopo che
   `heal()` ha verificato, e il conteggio con `whole_value` è corretto — tutto
   **non committato** in quella repo, insieme a `remove_title_logos` (dato il
   riquadro del cartiglio da snapdraw: toglie i retini lì dentro, svuota i
   blocchi logo — inseriti nel cartiglio, con retini, ≤ metà del cartiglio — e
   rifiuta di scrivere se cambia un solo edge di topo fuori dal riquadro) —
   ora **committato** in `dxf-anonymize`.
   Lotto pulito in `anonimizzati/drw_0001…0033.dxf`, originali intatti, fatto
   con `dxf-anonymize batch CARTELLA --rules regole.json --out ...` (le
   regole con i nomi del cliente in un JSON locale, accanto ai disegni).
   Cancellare *tutto* dentro il cartiglio: provato e **scartato** (toglieva il
   cartiglio). **Ancora aperto:** loghi senza retini (solo archi/cerchi, due
   disegni), e i 6 disegni dove snapdraw non è sicuro del cartiglio.
   **snapdraw `read_titleblock` alla prova del lotto:** trova il cartiglio in
   27/33, ma i campi letti sono quasi tutti sbagliati — `drawn_by` aggancia
   "DISEGNO DI PROPRIETÀ", `date` prende le etichette vicine o "PEZZA",
   `drawing_number` ha letto "Group" in 8 disegni. Nomi e date li hanno trovati
   le regole sul testo, non il cartiglio.
3. **I 32 disegni che la suite usa e non ha in git** — ✅ **IN GIT, D79 risolto**
   `anonymize scan` aggregato su 261 stringhe distinte (D78): zero percorsi
   assoluti, un nome di persona, una sigla sui tre stili di quota, ripuliti su
   8 file, `heal()` identica, suite 887.
   
   Non con un `git add -f` in una cartella ignorata: `tests/data/` è diventata
   la radice tracciata (D79, `.gitignore` la dichiara da anni inutilizzata). Un
   disegno è pubblicabile **perché sta lì**, non perché qualcuno si ricorda una
   flag. `tests/examples/` resta locale (originali cliente, `islands/`,
   `111-23/`). 534 spostati con `git mv`, 32 nuovi + 2 golden, suite 887 dopo
   il move.
4. **Il rewrite della history** — ✅ **fatto (D81)**, 2 ottobre: un force-push,
   albero di oggi identico, `audit_names.py --history` pulito.
5. **`detect_flat()` → snapbend** — ✅ **fatto (D88, D89, D90)**: golden divisi,
   detection in `snapbend/flat/`, renderer di topo generici sull'overlay.
   **Da decidere (Federico):** 10 golden `golden_multipli/process/` (ora in
   snapbend) hanno il summary vuoto (era `custom` prima del refactor di
   inject). Per i fori non manca un controllo (sono nei layer `Hole`); restano
   3 pieghe mai controllate: `staffa_scarto_doppia` pezzi 2 e 3 (30 mm) e
   `quattro_sviluppi_un_foglio` pezzo 2 (8.5 mm). La 8.5 mm non è più una
   piega: regola nuova "una piega taglia il pezzo" (snapbend MAP D52). Le due
   da 30 mm restano da guardare nei DXF in
   `snapbend/tests/data/flat/golden_multipli/detected/`. **Aperto:** un righino
   messo di traverso in un angolo passa ancora — serve una misura minima, da
   decidere (snapbend MAP D52).
6. **Estrazione dei loop planari (half-edge/DCEL)** — l'unica cosa in lista che
   cambia di categoria il motore; dettaglio nei "limiti geometrici noti".
7. **Due cose piccole dalla roadmap del preventivo** (step 0 e 1 di
   `ROADMAP.md`): `snap_distance` anche su `inject()` — ✅ fatto (D82). Il
   controllo quota-vs-geometria misurata **non è di topo** (D69): topo dà già
   `measured_value`, `display_text` e `references`, il confronto col numero
   scritto si fa in snapdraw — da portare nel TODO di snapdraw.
   Lo script di produzione dello split (ex `scripts/13_…`) importa ancora
   `extract_topo_texts`, che non esiste più: è rotto. **Spostato in snapbend**
   (Federico, 4 ottobre: alla radice, non versionato), da riscrivere lì
   su `inject(snap_distance=...)` — vedi il TODO di snapbend.
8. ~~Il rename `topo` → `snapforge`~~ — superato da D108: il package diventa
   `topo`, distribuito come `g-topo` (Federico, 17 ottobre).
9. **Rifare il viewer (`to_view_model` + `to_svg`), in una sessione a parte.**
   Federico, 3 ottobre: "ora è davvero bruttino e limitato, non scalabile, fa
   cose che dovrebbe fare il consumer e non fa cose che dovrebbe fare lui".
   Già visto, da cui partire (l'analisi vera è il lavoro di quella sessione):
   - ~~**fa cose da consumer**~~ e ~~le altre collezioni sono solo contate~~ —
     risolti da D90: il view-model disegna ogni collezione di `detected` sotto
     `features`, dal ruolo e dalla geometria, senza nomi privilegiati; archi e cerchi diventano
     punti (sotto);
   - **non scala**: su un foglio di viste pesa più del DXF di partenza.
   Il resto del punto, scritto prima, vale come parte di questo lavoro:
   **il view-model non discretizza più archi e cerchi** (Federico, 3 ottobre:
   "è ridicolo") — **riapre D12**, che li appiattiva in polilinee. Un cerchio
   resta cerchio (centro + raggio), un arco resta arco (centro, raggio, angoli):
   l'SVG ha `<circle>` e gli archi nei `path`, quindi `to_svg` non perde niente,
   e un renderer esterno disegna l'entità vera. Misurato: su `anch_07`/`anch_08`
   la discretizzazione rende `to_view_model` **più grande del DXF sorgente**
   (≈300k token contro 79k). Le spline restano da decidere: l'SVG ha solo
   Bézier cubiche, una NURBS qualsiasi non ci entra esatta.
   **Coordinate arrotondate al terzo decimale** nelle uscite di lettura
   (view-model, SVG, la futura lettura per un agente). Non in `to_dxf`, che va
   a una macchina e resta esatto — da confermare con Federico.
   Quando si fa, diventa un `D##` in `MAP.md`.
10. **`to_text`: la lettura per un agente AI** — ✅ **fatto, sperimentale
   (D84)**, 3 ottobre. Resta aperto: la prova del valore, in snapdraw dopo la
   sua detection (è nel TODO di snapdraw); se sopravvive, entra in `__all__` e
   in `API.md`. Sui fogli di viste il peso è ancora quasi tutto cornice,
   tacche e retini non classificati: si abbassa quando snapdraw li etichetta.
11. **Doppioni trovati da `gen_index.py` (D72)** — ✅ **tutti sistemati** il
   3 ottobre (D85): `_geometry` fuso in `noding.edge_geometry`,
   `_ensure_linetype` fuso in `exporter.ensure_linetype` (un linetype ignoto
   in `RoleStyle` ora solleva), gli omonimi rinominati.
   Limite del controllo: trova solo lo **stesso nome**. Per lo stesso lavoro
   sotto nomi diversi c'è ora `gen_index.py --similar` (punto 12).
12. **Stesso lavoro con nomi diversi** — ✅ **chiuso** il 3 ottobre: D86 (pezzi
   comuni trovati con `gen_index.py --similar`) e D87 (merge collineare e
   cocircolare su un motore unico, identico al vecchio su 611 disegni).
13. **La scala delle isole** — ✅ **chiuso** il 5 ottobre. Fatto: il default
   di `island_gap` e `max_gap` è tolto, ogni chiamante dice la sua distanza
   (D98; in snapdraw un posto solo, `sheet_islands`, snapdraw D29). Scartato:
   la scala (le distanze a cui le isole si uniscono) come strada per scegliere
   la distanza — Federico: "la scala non c'entra e non c'entrerà mai con la
   detection delle isole". Non si porta in `topo.geometry`. Le misure e i
   giudizi a occhio del 4-5 ottobre sono riassunti in D98.

14. **Isole: D99-D100 chiusi il 5 ottobre.** Il punto della situazione e i
   prossimi passi (detection sulle isole, lettura delle viste) stanno nel TODO
   di snapdraw, "Dove siamo". Golden delle isole: `tests/real/test_golden_islands.py`.

---

## `anonymize` — ripulire un disegno cliente per farne un fixture

**Costruito (D77).** `topo/tools/anonymize.py` + `topo/adapters/dxf/tags.py`,
11 test in `tests/unit/test_anonymize.py`. Quello che segue è il perché, che
resta valido come guida all'uso; quello che resta da fare è passarci i 32
fixture del punto 3.

```
python -m topo.tools.anonymize scan  disegno.dxf [--all]
python -m topo.tools.anonymize clean disegno.dxf --map mappa.json \
        [--out fixture.dxf] [--also golden1.json golden2.json] [--whole-value]
```

Il bisogno vale per topo **e per tutti i consumer**: i test si fanno per forza
con disegni di clienti, quindi serve un passaggio che li renda pubblicabili. Vive
in `topo/tools/anonymize.py` con la lettura/scrittura del formato in
`adapters/dxf/tags.py`; fuori da `topo.__all__`, i consumer lo importano da
`topo.tools.anonymize`.

**Perché non un round-trip attraverso topo.** `load_dxf` → `heal` → `to_dxf`
restituisce la *lettura* di topo, non il file: spline strane, entità fuori
contorno, il `Trash` — cioè esattamente ciò che rende quel disegno un caso di
prova — non tornerebbero uguali. Il fixture deve restare il file, byte per byte,
tranne le stringhe che identificano.

**Quindi passata testuale diretta sul DXF, non `ezdxf`.** Un DXF ASCII è una
sequenza di coppie (codice, valore), una per riga: si riscrivono solo i valori
stringa, i numeri non si toccano mai e la struttura resta allineata. I gruppi che
possono portare un'identità: `1`/`3`/`304` (testi), `2` (nomi di tabella e di
blocco, compresi gli stili di quota), `6`/`7`/`8` (linetype, stile, layer),
`300`-`309` e `1000` (testo arbitrario e XDATA), `9` (variabili d'intestazione
tipo `$LASTSAVEDBY`, `$PROJECTNAME`, `$HYPERLINKBASE`), `999` (commenti).

**topo è l'oracolo.** Dopo la pulitura: `heal()` prima e dopo, e numero di
cluster, aree, perimetri, bbox e `trash` devono coincidere. Se cambia un numero
lo strumento ha sbagliato e si rifiuta di scrivere.

Due trappole viste sul campo, da gestire dentro lo strumento:

- una stringa si **sostituisce, non si cancella**: togliere il testo del
  cartiglio cambia quello che vedono `annotations` e `inject()`;
- se un golden cita quel testo (`"display_text": …`) va riallineato nello stesso
  passaggio, altrimenti il test rompe; e un layer rinominato va rinominato in
  *tutti* i posti dove compare (record di tabella, blocchi, gruppo 8 di ogni
  entità).

Due modalità:

```
python -m topo.tools.anonymize scan  disegno.dxf
python -m topo.tools.anonymize clean disegno.dxf --out fixture.dxf --map mappa.json
```

`scan` stampa tutto quello che è scritto dentro, da leggere con l'occhio: è la
parte che non si può automatizzare, perché un **codice** ha una forma e un
pattern lo trova, un **nome** no. Prova che serve: il nome di uno studio usato
come nome di uno stile di quota in uno dei disegni, trovato solo dumpando 576
stringhe e leggendole una per una (ora sostituito). `clean` applica una mappa (sigle inventate generate,
o scritta a mano) e dice cosa ha sostituito. **La mappa resta locale**: è l'unico
file che lega il fixture all'originale.

Quello che NON è dato cliente, verificato con Federico: la **marcatura** — il
testo dentro il disegno che ripete il numero del pezzo — la scrive Advance Steel
per ogni pezzo tagliato, è il nome del normalino e può stare in git. In D76 era
stata sostituita per eccesso di zelo; non è un danno (ora il marchio coincide col
nome del fixture) ma la regola per il futuro è: la marcatura si tiene.

---

## Due cose decise a voce e mai scritte

### `to_dxf` su un `Result` non valido — ✅ fatto (D83)

`allow_invalid=True` su `to_dxf` **e** `to_svg` (alcune macchine prendono SVG):
di default si vede tutto, chi consegna a una macchina passa `False`. snapbend lo
fa già nei tre `topo.to_dxf` di `snapbend/io/dxf.py` (modifica locale, **non
committata**: quel file è ancora non tracciato in snapbend). In snapbend 3 test
falliscono da prima, non per questo: `tests/test_to_dxf_integration.py` usa
`cluster.bending_lines`, che non esiste più.

### il "pnger": topo sa già mostrare, solo non in raster

Sono due cose diverse. **Renderizzare il modello** — che geometria c'è, con
ruoli e colori — è di topo, e topo lo fa già due volte: `to_svg` e
`to_view_model`. Un SVG lo apre qualsiasi browser, è scalabile, e per un umano è
meglio di un PNG. **Comporre un'immagine per un lettore preciso** — ritagliare,
togliere le quote perché un modello leggerebbe i numeri invece delle forme — è
del consumatore: quelle scelte hanno bisogno di `ViewLayout` e dei ruoli
`FRAME`/`TITLE_BLOCK`/`CONSTRUCTION`, che topo non ha.

Quindi: il raster serve quando il lettore è una macchina, non quando sei tu.
`to_svg` resta la via umana di topo e **non** si aggiunge `to_png` adesso; in
snapdraw il pnger si riscrive su Pillow (una ventina di righe, e matplotlib esce
di scena con la sua dipendenza non dichiarata). Se un domani il raster serve
anche a topo, è un `to_png` sottile sopra lo stesso view-model, nell'extra
`raster` che il `pyproject` già dichiara. L'interattivo è un viewer, cioè un'app
a parte (MAP.md D16).

---

## Audit dati cliente prima della 1.0.0 — resta il rewrite della history

**4 ottobre — ✅ fatto (D97):** la storia pubblicata citava ancora disegni cliente per nome; riscritta e ripubblicata con `dxf-anonymize repo`, verificata pulita su un clone preso da GitHub.

D76 ha rifatto l'audit e il "zero sospetti" di D73/D75 era cieco in tre punti
(path quotati da git, `\b` che non scatta dentro gli underscore, e il contenuto
dei disegni mai letto). Ora `python scripts/audit_names.py --strict` controlla
quattro cose — nomi, prosa e codice, **dentro i disegni**, nomi di sole cifre —
ed esce 0. Dentro i DXF tracciati c'erano un percorso di rete con nome cliente e
commessa, il nome di una stampante d'ufficio e cinque codici pezzo come nomi di
layer e testi di cartiglio: tutto sostituito, suite ferma a 876. Il dettaglio
sta in MAP.md D76.

**3 ottobre — blocchi definiti e mai usati.** `anch_01…06` portavano ancora la
*definizione* di un logo cancellato a mano (geometria del logo e nome di una
ditta nel nome del blocco), invisibile in CAD, leggibile nel testo. `audit_names`
non l'ha visto perché il nome non ha la forma di un codice. Tolti con il nuovo
`dxf-anonymize purge` (`heal()` e golden di ancoraggio identici). **Solo
nell'HEAD:** i commit vecchi li hanno ancora, e Federico ha deciso di **non**
riscrivere la storia per questo adesso — da riconsiderare nell'audit della
1.0.0.

Restano due cose:

1. ~~**Mettere in git i 32 disegni che la suite usa e non ha.**~~ — fatto:
   `audit_fixtures.py --strict` dice "tutti in git" (verificato il 19 ottobre). Letti e puliti in
   D78 — `anonymize scan` su tutti e 32, aggregato in un elenco unico di 261
   stringhe distinte, lette a occhio: zero percorsi assoluti, un nome di persona
   in `$LASTSAVEDBY` e una sigla di tre lettere su tre stili di quota,
   sostituiti su **otto** file (gli stessi disegni stanno in più cartelle, e la
   pulitura segue la stringa, non la lista dell'audit). `heal()` identica su
   tutti, suite 887.

   `python scripts/audit_fixtures.py` li elenca (3,2 MB, tutti puliti secondo
   l'audit): senza di loro 61 golden su 114 fanno `skipTest` su un clone pulito,
   e la suite resta verde mentre gira meno di quello che mostra. Decisione presa
   (i golden devono girare anche da chi scarica il progetto), manca solo lo
   `git add -f` — `tests/examples/` e' ignorato in blocco, quindi serve il
   `-f`:

   ```
   python scripts/audit_fixtures.py --list > fixtures.txt
   git add -f --pathspec-from-file=fixtures.txt
   python scripts/audit_fixtures.py --strict   # deve dire "tutti in git"
   ```

   `--pathspec-from-file` e non `$(cat ...)`: un fixture ha uno spazio nel nome
   (`flangia semplice.DXF`) e la sostituzione di shell lo spezzerebbe in due
   percorsi che non esistono. `fixtures.txt` si cancella subito dopo.

2. **Il rewrite della history** (il punto 6 del piano). I codici sono nei commit
   gia' pushati: `git filter-repo` su tutta la history + un solo force-push,
   dopo che tutto il resto e' committato. Cambia ogni SHA, quindi un eventuale
   clone va riclonato; GitHub puo' tenere gli oggetti vecchi raggiungibili per
   SHA per un po'. Da rifare contro la lista di D76 e D77, non solo contro i nomi
   di file: nei commit vecchi ci sono i codici che stavano **dentro** i disegni,
   le due sigle ripulite in D77 e la sigla ripulita in D78 — quest'ultima stava
   in tre disegni **già tracciati e pushati**, e `audit_names.py --strict` li
   dava per puliti perché cerca codici e quella è un nome. E non basta riscrivere
   il contenuto dei file: almeno un **messaggio di commit** porta un codice pezzo
   nell'oggetto, quindi serve anche un `--message-callback`.

Due cose viste di passaggio, da decidere quando capita:

- `tests/examples/cartella_3/` — il nome della cartella non e' un codice pezzo e
  l'audit non lo segnala, ma non e' neanche un nome inventato. La cartella non
  e' tracciata e nessun test la usa (il `la_104.DXF` che i test usano e' quello
  in `tests/examples/`), quindi non e' un problema di git: e' da guardare.
- Lo script di produzione dello split (ex `scripts/13_…`, ora in snapbend, non
  versionato) ha un percorso assoluto con un codice pezzo. Finche' resta non
  versionato non entra in git, ma se un giorno lo si porta alla nuova API quel
  percorso va via prima.

## RIPARTENZA — stato a fine sessione 2026-09-18 (seconda parte), da qui la prossima chat

Chiuso: `refactor/ellipse-primitive` (docs cleanup + `EllipseSeg`, due
commit) mergiato `--ff-only` in `main`, bump a `0.6.19`.

Primo pezzo di "funzioni geometriche" (MAP.md D46) — **rivisto una volta
dopo la prima versione**, su correzione di Federico: la prima stesura
ruotava il `Document` grezzo e chiedeva un secondo `heal()`, e aveva
"outer" cablato nel nome della funzione invece che parametrico. Corretto:
una rotazione rigida non cambia la topologia, quindi `rotate_result`/
`rotate_cluster` ruotano DIRETTAMENTE un `Result`/`Cluster` già
sano (poligoni, segmenti, `all_arcs`) — zero `heal()` di troppo, e
`rotate_cluster` è economico/ripetibile (pensato per un futuro nester che
prova molti angoli sulla stessa parte). "Quale entità allineare" è
`include_inners: bool` (outer di ogni cluster, più gli inner se True) — non
un filtro per `role` (verificato che `role` non è affidabile: un inner senza
ruolo proprio eredita quello del padre, `hierarchy._make_inner`). Dettaglio
completo, incluso perché la prima versione è stata scartata, in MAP.md D46.

`topo/tools/rotate.py`: `.rotated(angle, origin)` su ogni primitiva,
`segment_length`/`longest_segment`/`chord_angle_deg` in `core/geometry.py`,
`structural_segments`/`longest_structural_segment`/`rotate_cluster`/
`rotate_result`/`rotate_document`/`rotate_to_longest` — sperimentale, non
ancora in `topo.__init__`. Script dimostrativo
`scripts/17_rotate_to_longest_outer.py` su `tests/examples/try_for_rotation.dxf`,
un solo `heal()`, verificato manualmente (outer più lungo passa da 90° a 0°,
la diagonale interna resta intatta e ruota con tutto il resto). Suite verde:
722 passed.

Branch `refactor/rotate-result-primitive` mergiato `--ff-only` in `main`,
bump a `0.6.21`. `main` è la verità corrente, niente da committare.

Resta aperto, discusso ma non affrontato:
- **Pippo che vuole sapere l'inclinazione di una flangia piegata** resta
  ambiguo fra due misure diverse: (a) l'orientamento 2D della bending line
  sullo sviluppo piatto (ora misurabile con `chord_angle_deg`) vs (b) il vero
  angolo di piega fisico, che in genere non si legge dalla sola direzione
  della linea — o è scritto altrove sul disegno, o si ricava per
  trigonometria confrontando la lunghezza vera (sviluppo) con quella
  proiettata in una vista che mostra la flangia piegata
  (`arccos(proiettata/vera)`) — ma questo richiede sapere quale edge dello
  sviluppo corrisponde a quale edge della vista, che è lavoro di
  snapdraw/interprete, non di topo.
- **Idea collegata ma volutamente NON la stessa cosa**: "ruotare" una vista
  per farla combaciare con un'altra vista proiettata (per trasferire feature
  da una faccia allo sviluppo) è un problema di matching/registrazione fra
  due insiemi di punti (tipo ICP), non una semplice rotazione — molto più
  grosso, legato al "raggruppamento viste" di `snapdraw` — non deciso se/come affrontarlo.
- Le annotazioni (`Document.annotations`/`Result.annotations`) non
  sono ancora ruotate (nessun caso reale l'ha ancora richiesto) — se/quando
  serve, ogni sottoclasse di `Annotation` (`Note`, `Dimension`, `Leader`, ...)
  ha campi diversi da ruotare, non è un'estensione da un rigo.
- `cluster.detected`/`cluster.custom` non sono ruotati da `rotate_result` —
  overlay a schema libero (D44), topo non sa cosa contengono. Se un
  consumatore ha già fatto la sua detection prima di ruotare, quei dati restano
  nelle coordinate vecchie — la detection va fatta DOPO aver ruotato.

**Fitting ellisse da punti grezzi** (generalizzare `arc_fit_tolerance` in
`core/primitives/fitting.py` a un fit ellittico 5-DOF, per Smoother):
deliberatamente rimandato dopo D45 — la primitiva `EllipseSeg` ora esiste,
il fitting da una sequenza di punti grezzi è il "secondo passo" di cui
parlavamo, non ancora iniziato.

Per ripartire in una chat nuova: leggere questa sezione + `MAP.md` D45, poi
proseguire dall'inventario sopra.

---

## Limiti geometrici noti (da fixture reali, non bloccanti)

Quello che resta aperto dal vecchio triage regressioni (`REGRESSION_PLAN.md` /
`file_test_status.md`, cancellati: tutto il resto lì era già ✅ risolto e
committato — la storia sta nel git log e in `MAP.md`).

- **archi_si_no.dxf** — riconoscere gli archi come outer romperebbe le bending
  line (il grafo gira prima di quella decisione). Accettato così com'è; in
  futuro potrebbe diventare un comportamento opzionale.
- **rect_special_countersink.dxf** — l'anello esterno del countersink
  potrebbe opzionalmente uscire su un layer a parte per un trattamento CAM
  diverso. Non bloccante.
- **rect_with_threaded_holes_geometric.dxf** — ipotesi: unificare a livello
  di disegno l'arco esterno di una filettatura rilevata geometricamente con
  il foro (reverse-geometric feature). Non bloccante, forse non necessario.
- **two_rects_with_bend.dxf** — una bending line con endpoint a ~10mm
  dall'outer non viene mai detectata: il filtro sulla distanza dal bordo è
  hard-coded a <1.0mm, alzare `bending_tolerance` non basta (quel parametro
  filtra solo la lunghezza minima).
- **senza_linea_piega.dxf** (fixture cliente reale) — due bug noti:
  (a) il pezzo `_1` genera 1 sola bending line dove ce ne sono di più, causa
  non ancora indagata; (b) il cartiglio (`Cartiglio_sviluppo` esploso) viene
  rilevato come un cluster a sé. Il punto (b) non è più "da risolvere in
  topo": è esattamente il caso d'uso che motiva `snapdraw`, che
  lo elimina marcando `role="title_block"` prima di `heal`.
- **arc/arc oltre tolleranza** — `compute_gap_fixes` scarta ogni coppia con
  `distance > tolerance` anche per gli archi; esentarli quando i loro cerchi
  si intersecano davvero è una scelta di design da rivedere con un file
  reale (workaround oggi: alzare `tolerance`).
- **outer che non si chiude su viste vere, ricorrente** — non più un caso
  isolato: tre disegni reali indipendenti, stesso sintomo in superficie
  ("outer vero, tutto in trash") ma **cause diverse** — non era un bug solo:
  - **foglio A** (snapdraw MAP D5, mesi fa): pezzi veri non chiudono in `heal`,
    tanti archi e linee di costruzione — causa non ancora ri-analizzata con
    gli strumenti di oggi.
  - **foglio B** ✅ **risolto, MAP.md D49** — non era un gap né una
    duplicazione da fondere: il file ha due viste indipendenti sullo stesso
    foglio (il piano e, sopra, una vista sottile dello spessore), e
    `NonContourEdgeDetector` calcolava il convex hull su TUTTO il documento
    invece che per singola forma connessa — la vista piccola perdeva 3 dei
    suoi 4 lati veri, scambiati per corde interne perché "dentro" l'hull
    dominato dalla vista grande. Fix: hull per componente connessa
    (`Graph.connected_components()`, nuovo). Ora chiude in 2 cluster puliti.
  - **foglio di rilievo C** (snapdraw, survey reale): di 3 viste sullo stesso
    foglio, 1 sana, 2 no. Sintomo diverso dal **foglio B**: `result.trash_entities` qui non
    sono ~10 frammenti ma **1682**, con lunghe catene di segmenti minuscoli
    (~0.3-0.5mm ciascuno) che sembrano un profilo curvo scomposto in tanti
    tratti retti che non richiudono l'anello — non ancora capito se manchi
    un singolo anello di congiunzione in fondo alla catena o se la
    frammentazione stessa sia il problema. Non ancora riverificato con gli
    strumenti di oggi (D49/D50) — segmenti di un profilo curvo hanno
    direzioni leggermente diverse l'uno dall'altro, quindi `D50` (che
    richiede la STESSA retta esatta) probabilmente non li tocca; da
    verificare comunque su un file reale prima di escluderlo.

  Non ancora deciso se/quando riaprire un'indagine dedicata sui fogli **A**
  e **C** — `refactor/heal-branch-topology` (D49, D50) ha chiuso il
  caso più semplice dei tre, non gli altri due.

- **linea tracciata a spezzoni sovrapposti** ✅ **risolto, MAP.md D50** —
  pattern distinto dal precedente (non viste multiple, una singola riga
  ridisegnata più volte quasi sullo stesso tratto). Trovato e riprodotto su
  `tests/examples/dedup.dxf`: un trapezio coi lati tracciati a 3-4 frammenti
  sovrapposti mandava tutto in `polygonize` invece di chiudere.
  `core/healing/normalizer.merge_collinear_overlaps()` (nuovo, gira in
  `heal()` prima di tutto il resto) fonde 2 o più frammenti che si toccano
  o si sovrappongono sulla stessa retta esatta, mai fra edge con un ruolo
  già assegnato — quel filtro sul ruolo resta l'unica vera protezione,
  perché decide qualcosa che la geometria da sola non può decidere (un
  ruolo da role_rules è dato di dominio, D30). Il dettaglio di due giri di
  falsi positivi prima di arrivare qui (e del bug di arrotondamento che
  in realtà li causava, non il contatto o il numero di frammenti) è in
  MAP.md D50, non ripetuto qui.

- **outer che non chiude su un grafo densamente ramificato — causa distinta
  dal punto precedente, non va nello stesso branch** — trovato su
  `tests/lab/3d_1.dxf` (una vista isolata da un disegno con più viste,
  export Creo via ODA File Converter, 259/423 entità sono SPLINE). Qui non
  c'è nessun gap: la componente connessa più grande ha 70 nodi, zero
  estremi liberi anche a 1mm di tolleranza (provato 0.1/0.3/0.5/1.0, zero
  differenza sul risultato), ma **64 di quei 70 nodi sono a grado>2**.
  L'euristica di `loop_finder.py` ("prosegui nella direzione più collineare
  all'arrivo") regge i bivi isolati visti finora, ma non un grafo dove il
  91% dei nodi è un bivio: il perimetro vero finisce interamente in
  `Trash` (bounding box del Trash identica a quella dell'intero disegno),
  mentre le feature interne (fori, bozze), chiudendosi bene da sole,
  emergono come cluster di primo livello invece che come inner — non è un
  bug di hierarchy, è che l'outer che dovrebbe contenerle non viene mai
  costruito.
  Trovato anche perché il dedup esistente non l'ha già ripulita:
  `sanitize.py::_key_for` (usato da `core/healing/normalizer.
  find_duplicates`) copre solo LINE/LWPOLYLINE/POLYLINE/CIRCLE/ARC — SPLINE
  produce `key=None` e viene ignorata da `find_duplicates`, quindi su un
  file quasi tutto SPLINE il dedup di fatto non gira. Anche dove si applica,
  la chiave è un'uguaglianza esatta a 2 decimali: due entità quasi
  coincidenti ma scostate di qualche decimo di mm (come le tracciature
  doppie viste sia qui che nel foglio B) hanno chiavi diverse e non vengono
  mai considerate duplicate — è un dedup per copie esatte, non per
  prossimità.
  Non è la stessa causa degli altri punti: lì servirebbe riconoscere
  geometria doppia/quasi-coincidente; qui servirebbe un'estrazione loop
  planare corretta (es. half-edge/DCEL con una regola di svolta coerente),
  che è un algoritmo diverso, non un'estensione dell'euristica attuale — va
  affrontato a parte. `merge_collinear_overlaps` (MAP.md D50, fatto dopo
  questa nota) non aiuta qui: lavora solo su `LineSeg`, e questo file è quasi
  tutto SPLINE.

---

## PRIORITÀ MEDIA — migliora la qualità


### Apertura files

I files splittati non vengono aperti in Autocad, vengono aperti in sigmanest senza problemi e anche in edrawing. Se si aprono in autocad è meglio, perhcè così a lavoro posso guardarli e se i colleghi vogliono guardarli non rompono il cazzo che non si aprono.

### Hashing

creare una fingerprint geometrica per validare na topo part.

### Analisi

- [ ] **`DxfAnalyzer` — output CSV**
  - Esportare `summary_stats()` anche in CSV per analisi batch
  - Utile per misurare qualità dei fornitori

---

## PRIORITÀ BASSA — futuro


### Implementazione nuovo formato:
Al momento in input posso avere solo dxf, ma mi sono messo in condizione di poter prendere anche svg o pdf. Da capire se implementare ad esempio almeno i pdf.



# I tools possibili sul motore geometrico:
Interrogazione (query)

measure() — distanze, aree, perimetri, bounding box
classify() — aperto/chiuso, convesso/concavo, presenza fori
compare() — similarity tra due parti (base per l'hashing/fingerprint che hai in lista)
validate() — check topologico: ci sono gap? self-intersections? geometrie degeneri?

Trasformazione

heal() — già ce l'hai
simplify() — riduzione punti, merge di segmenti collineari
offset() — kerf compensation, inset/outset contours
normalize() — porta tutto in coordinate canoniche (utile per comparison e hashing)

Analisi

nest_hint() — bounding box ottimale, orientamento suggerito per nesting
grain_direction() — suggerisce orientamento rispetto alla fibra del materiale
engrave_detect() — quello che hai in lista come "feature di tracciatura"

Decomposizione

split() — già ce l'hai
skeleton() — asse mediano (utile per bend detection avanzato)
region_decompose() — divide parti complesse in regioni semantiche


### Cos'è in poche parole:

Questa libreria è tipo un “riparatore di disegni tecnici”: legge un file DXF, controlla se le linee e le forme sono rotte o confuse, le sistema, trova le parti e gli spazi vuoti, e poi salva un disegno più pulito e ordinato.

In pratica
Ora: utile per CAD/CAM e automazione industriale.
Domani: può diventare un sistema di “interpretazione visiva di disegni” se aggiungi:
classificazione robusta,
feature detection,
model di topologia,
regole di business,
eventualmente ML/vision.


---

# strisce fra regioni annidate — fatto (MAP.md D40, D134, D142)

## ~~APERTO (19 ottobre, MAP.md D134) — regioni annidate unite da strisce~~

Fatto il 19 ottobre, D142: `topo.tools.strips` (i quattro fatti e la
costruzione, nomi geometrici). smoother non è stato aggiornato nello stesso
cambio come diceva D134: da D140 si adegua dalla sua sessione (voce sopra in
"richieste dalla superficie"). Resta aperto: promuovere a `topo.geometry`
quando un secondo chiamante (snapfence) li usa davvero.

## Cosa resta parcheggiato, non toccare senza motivo

- ~~**Problema 2**~~ — risolto da D47, poi la tassonomia di processo è uscita
  da topo (D90, in snapbend).
- ~~**Idea "detect dovrebbe usare il suo stesso contratto"**~~ — risolta da
  D90: la detection sta in snapbend e usa gli stessi ganci di qualunque
  consumatore (`role`, `register_role_style`, `heal(is_structural=...)`,
  l'overlay).
- **Meccanismo anti-rotazione pezzo staccato** (diverso da `tab`/`bridge_tabs`):
  un ponticello su un contorno singolo per evitare che un pezzo che si stacca
  giri libero e l'ugello ci sbatta contro — non collega un inner a un inner
  più annidato, è tutta un'altra cosa. Non ancora costruito, non ancora
  disegnato. Nome non deciso: forse "joint", di sicuro non "microjoint"
  (Federico l'ha escluso esplicitamente).

## Regola da ricordare per tutta questa roba

Mai parlare di layer DXF quando si parla di `role`/estensibilità di topo —
`role_rules` sono solo il modo di assegnarlo al load (D63), il
meccanismo vero è `edge.role`, assegnabile per qualunque criterio
(raggio, posizione, geometria...), senza nessuna dipendenza da layer o
formato. In questa conversazione è già capitato di spiegare una cosa così a
Federico usando "layer" invece di "role", e si è arrabbiato parecchio — vedi
memoria `discuss-forge-in-role-terms-not-layer-terms`.
