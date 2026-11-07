# topo — TODO

Lo stato, non la storia: qui sta solo ciò che è aperto. Il perché di ogni
scelta è in `MAP.md` (`D##`), la cronaca nel git log. Il testo intero di questo
file prima dell'accorciamento (2 novembre) è in `TODO_ARCHIVE.md`, solo locale,
fuori da git.

---

## PIANO — ultimo tentativo (Federico, 2 novembre; D207)

Data di consegna di cui parla Federico: 1 dicembre.

Se questo piano apre cose nuove nel cancello, Federico chiude topo.
Ogni sessione parte da qui e lo dice in chat: passo, contatore.

**Regole (valgono per Claude, non si discutono a metà strada)**
1. Il cancello non cresce. Un difetto trovato strada facendo va in "Dopo la
   1.0" con una riga di fatti, mai in un G nuovo. Unica eccezione: un difetto
   causato da un nostro commit di questo piano → quel commit si revoca.
2. Nessun rifacimento del motore. Solo correzioni locali, un meccanismo per
   commit. Una modifica in `normalize`/`heal`/letture si misura prima e dopo
   su tutte le 162 letture (81 disegni × faces/outlines).
3. Cricchetto: il contatore delle letture con un salto (oggi 48) scende o
   resta, mai sale. Un commit che lo alza si revoca, non si rattoppa.
4. Ogni test nuovo si mostra rosso su un difetto vero prima di contare.
5. "Verde" non vuol dire "stabile": vuol dire solo le promesse della lista
   (D143 + D206). Ogni report dice quale promessa ha controllato.
6. Pezzi cambiati → DXF in `_debug` con cosa guardare; giudica Federico.

**Passi**
- [ ] L1 Commit del lavoro di oggi (D206, D207, `largo` +
      golden, TODO). Controllo D206 in `validate_result`, chiamato anche da
      `outlines()`: un salto → warning + `is_valid=False`. Test
      `test_closure` su 162 letture con la lista dei 48 noti scritta nel test:
      fallisce se ne compare uno nuovo o se uno guarito non viene tolto.
- [ ] L2 I 48 raggruppati per causa (salti 0,05 esatti,
      0,0032, 0,0051, 0,0087, 0,0002, sotto 1e-4…), con il commit in cui
      ciascuno è nato (17 dopo il 25 ottobre). Esce il numero di meccanismi →
      la stima del lavoro. Federico decide lì se si va avanti.
- [ ] L3 Un meccanismo per commit, dal gruppo più grande.
      Ogni commit: contatore giù, suite verde nel budget, DXF in `_debug`.
- [ ] L4 Solo se L3 è a zero: G16 (stretto, 1136 segmenti in `faces()`),
      stesse regole.
- [ ] L5 Bilancio con numeri: contatore (48 → ?), voci del
      cancello (7 → ?), voci entrate (deve essere 0). Federico decide.

**Stato (4 novembre)**: L1 fatto (`773a4e3`). `eabf73c` `join_ends`: i capi
sullo stesso nodo portati sullo stesso punto (linee spostate, archi ruotati,
spline ed ellissi no) → contatore 48 → 28, nessuno nuovo. Rossi/aperti:
`TestTangentSpike` (due linee da 74 mm spostate 0,0016 sul capo dell'arco,
area 1011,35 → 1011,29: accettare o lasciare aperto); D208 citata nel codice
ma non scritta in MAP; `join_ends` non scritto in MAP; suite 4:27 (budget 3);
regr_01 `outlines()` 0,0237 → 0,0903 (contatto linea–arco quasi tangente);
`sbagli_tratteggio_stretto.dxf` tolto dalla suite (Federico, 7 novembre): ci gira `tratteggio_stretto_piccolo.dxf` (`tests/generate_hatch_small.py`), suite 11:49 → 4:33.

**Ramo `no-join-ends` (6 novembre)**: `join_ends` tolto (revert di
`eabf73c`), saldatura dei tratti corti tolta da `normalize`. Ogni salto entro
la tolleranza rimasto in un contorno consegnato lo chiude ora una retta nuova
(`close_contour_jumps`, D206), con un warning; `test_fidelity` pretende 0 salti
ovunque. Le cause qui sotto restano: dicono quando nasce quella retta.
Ramo `node-moves-geometry`: abbandonato (spostava i capi).
Aperti, con i fatti:
- Sweep 6 novembre (`21_sweep_invariants.py` su `snapdraw/`, 121 disegni, ora
  con il controllo `jumps`): `faces()` rossa su 18 disegni contro 3 del 2
  novembre. "out once" nuovo su 17 (es. drw_0012 4,58 mm, drw_0016 fino a
  57,5 mm); drw_0016 nuovo anche in "scrambled" (inner 22 → 20); drw_0017 ha
  due salti di 0,8395 mm (oltre la tolleranza 0,5) negli inner 41 e 42 a
  (318.61, 249.23), con `is_valid=False`. `outlines()` verde ovunque.
  Riletti i 18 a ogni commit del motore da `4e5d9c0` (`per_commit.json`): "out
  once" 0 → 17 con `db780b7`; drw_0016 "scrambled" nasce con `df67722`; il
  salto 0,8395 di drw_0017 nasce con `34102bc`. Disegni con un salto 17 → 1
  (con `384aebc`). Il perché di ciascuno non è cercato. Rapporto in
  `_debug/2026-11-06_topo_sweep-jumps`.
  `db780b7` ritirato (Federico, 6 novembre): out once 17 → 0, suite verde;
  `df67722` ritirato: drw_0016 verde, suite verde (il salto di anch_01_noframe
  lo chiude `384aebc`). Restano drw_0017 (salto + scrambled), sweep #8, #79 (oltre 300 s).
- **Forza bruta 6-7 novembre** (banco e rapporto in
  `_debug/2026-11-06_topo_node-distance`, `RAPPORTO.md`; generatore `fuzz/gen.py`,
  controlli `fuzz/check.py` e `fuzz/sweep2.py`, lanciatore `fuzz/drive.py`). Da fare
  in una chat nuova (Federico, 7 novembre): tutte le fix qui sotto, poi di nuovo la
  forza bruta sulle stesse passate, codice vecchio contro nuovo.
  1. ~~Togliere la griglia dei nodi (D216)~~ fatto. I 2 rossi: `test_007` aveva
     la premessa fatta dalla griglia (ora il nodo unico è scritto a mano);
     `TestChordContactUnderMotion` era il difetto noto G6e, ora chiuso (5 moti, una
     risposta). I 4 DXF veri: 2 "guastati" (non giudicabili), 1 a ~5e9 mm (senza
     griglia l'area cambia meno: 0,0003% contro 0,1%), 1 è il difetto qui sotto.
     ~~Difetto delle due spline chiuse~~ fatto (D219). La diagnosi di prima era
     sbagliata: basta una spline chiusa che incrocia se stessa, con `end` scritto a
     1e-13 da `start` (`moved()` dei test, `rotate_document`): `renode` lasciava i
     nodi delle curve chiuse come scritti → `outlines()` la mandava intera in loose.
  2. ~~Cerchio scritto due volte~~ fatto (D217).
  3. ~~Foro in archi~~ fatto (D218). La voce di prima era sbagliata: r 5 con buco 0,3
     sono 3,4°, sopra i 2° di D112, e restare aperto è giusto. Il difetto vero: due
     archi con buchi sotto i 2° si chiudevano con segmenti, non col cerchio.
  Il controllo della forza bruta contava "foro mancante" anche un cerchio spezzato
  oltre i 2° (giusto per D112): corretto il 7 novembre (`fuzz/check.py`,
  `open_by_d112`; il vecchio in `check_prima_D112.py`); su 30 semi 5 → 3 rossi.
  Forza bruta (~3 ore) di notte: `bash notte.sh` nel banco, `topo_base` (`4e729d1`)
  contro `topo_new` (`a9e2d61`), uscite in `notte/`. I numeri di prima qui sotto
  sono col controllo vecchio: si confronta solo con le due copie di `notte/`.
  Prossima chat (Federico, 7 novembre): il riordino dei test, voce "Tempo della suite" nel cancello (suite 4:36, budget 3).
- Una curva sola che incrocia se stessa non si taglia nell'incrocio
  (`split_at_crossings` taglia solo fra edge diversi): spline di grado 1 a forma
  di quadrato 100×100 con un ricciolo sotto → `outlines()` 9900 (l'anello intero,
  area con segno), le stesse rette 10100 + il lobo in loose. DXF vero fuori dal
  repo (banco della forza bruta, seme 3339): spline 8 (3 lobi), 9 (6 lobi),
  silhouette di 8+9+10 ~13944, `outlines()` 10735 e la 8 in loose a pezzi.
- Due curve chiuse semplici, il nodo dell'una sul bordo dell'altra (spline di
  grado 1, cerchi a 24 lati r 50 in (0,0) e r 40 in (90,0)): `outlines()` dà solo
  la prima (7764,6) e l'altra in loose; il nodo 7e-5 dentro → un contorno da
  12733,9. Nel disegno del seme 3339 il nodo della spline 8 sta a 6,6e-5 dalla 10.
  Numeri prima delle fix (attuale / senza griglia): 3000 inventati, risposta sbagliata
  790 / 767 (fori in più: quasi sempre con un doppione nel disegno; fori mancanti: quasi
  sempre con un cerchio spezzato + un buco; 8 senza nessuno dei due; compatibile con 2 e
  3, non dimostrato). Mosso → conti diversi 123 / 21 (cause dei 21: non cercate).
  Mosso → aree diverse 876 / 862. 3551 DXF veri: mosso 46 / 29, salti 4 / 0.
- Precisioni (Federico, 2 novembre, chiese di uniformarle; D196 le tenne
  separate): in `core/` + `sanitize` ~40 soglie di coincidenza su 9 valori
  (1e-2 … 1e-12). Misurato sui 18 rossi: solo `NODE_DECIMALS` 6 → drw_0016 e
  il salto di drw_0017 guariti, +36% tempo; 9 → nulla di più, ×20 tempo.
  Tutte le soglie a un valore: 1e-3 meglio (out once 17 → 9, 0 salti, 39 s),
  1e-6 e 1e-9 peggio. Sweep 121 con tutto a 1e-3: rossi 18 → 17, 7 guariti,
  5 nuovi in "scrambled" (regr_04 e due derivati, sweep #83 e #97), #79
  finisce (279 s), 0 salti, `outlines()` sempre verde. Script `per_unified.py`
  e rapporto `unified_1e-3/` in `_debug/2026-11-06_topo_sweep-jumps`.
- un contatto dove una curva supera l'altra di pochi millesimi (anch_07: retta
  oltre un arco di 0,003; regr_01: spline oltre una retta di 0,004): l'arco si
  taglia all'incrocio, la retta no, i due punti finiscono nello stesso nodo →
  salto. Fatto per l'accorciamento in `34102bc` (anch_07 e regr_05 a 0 salti).
- `decide_nodes` salda ancora un tratto più corto di 0,01 coi due capi sullo
  stesso nodo (warning "2 LineSeg degeneri" su anch_01).
- I salti si guardano un file alla volta (DXF in `_debug`, salti cerchiati) e
  ognuno prende un nome:
  - **N1** (anch_01 faces, 0,0107; chiuso in `e15c053`). Natura: due capi
    diversi fusi in un nodo. Una lineetta di tratteggio da 0,015 taglia in
    diagonale un angolo esatto (due orizzontali e una verticale); l'angolo sta
    a 0,0075 di lato dalla lineetta, il capo della lineetta sul lato a 0,0107
    dall'angolo. `_same_contact` fondeva i due contatti della coppia (entro
    `tolerance` lungo il lato) e `merge_along_edges` misurava solo lungo la
    lineetta (0,0075), non sul piano (0,0107): angolo e capo nello stesso nodo,
    il pezzo di lato fra i due spariva. Ora due capi diversi restano due punti.
  - **N2** (anch_01_noframe outlines, 0,0040; aperto). Natura: un contatto a T
    il cui capo non tocca la curva. Tre lineette di tratteggio, una da 0,011;
    heal chiude due buchi con due segmenti suoi, uno per capo della lineetta
    corta. Il capo del primo (0,129) resta a 0,004 di lato dal secondo (0,406):
    sotto 0,01 è un T, il secondo si taglia nel suo punto più vicino, col nome
    del capo, e i due punti veri restano a 0,004. Da fare: il capo si
    prolunga o accorcia lungo se stesso fino all'altra curva (come agli incroci,
    `34102bc`); su una spline non si può prolungare, lì un segmento nuovo.
    Il contorno è un triangolino di tre lineette e due segmenti di heal.

Fuori da questo piano: G8, G9, G10, G14 (non toccati).

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
Verifica del lavoro: golden cambiati classificati + DXF in `_debug`;
tetto dei tempi: quello della suite.
Sottopassi, uno per commit:
- [x] A. inventario (2 novembre). Le differenze sono quattro, non tre
      (`heal.py:87,110` contro `outline.py:136-165`):
      1. portata dei gap: `reach(tol)` contro `reach(max(tol, max_gap))`.
         `faces()` non ne ha bisogno: nessun consumer chiede a heal() gap
         larghi (passano solo `tolerance`). Risolto in B: i numeri sono
         **due** (D202), `tolerance` per i nodi e `max_gap` per i gap
         (default `tolerance`).
      2. `keep_junctions`: True (D110) contro False (D50). Nella rete i pezzi
         restano separati (non si perde niente); `outlines()` ricompone già
         lungo il contorno (`merge_runs`, `outline.py:200`). Da misurare in B.
      3. scope: tutto il disegno contro un gruppo `touching_groups` alla
         volta. I gap si chiudono entro `max_gap` e i gruppi sono a `max_gap`,
         quindi le coppie dovrebbero essere le stesse: il raggruppamento
         diventa un passo di `outlines()`. Da misurare: risultati e tempi.
      4. `cut_crossings`: False in heal (D132, D189), True in outlines (D101).
         È già "lo dice la lettura" (docstring `noding.py:170`): la rete
         tiene gli incroci come dato (`crossings`), il taglio lo fa
         `outlines()`. Serve un taglio applicabile a una rete già fatta.
      Minori: il filtro dei degeneri (`outline.py:163`) va nella riparazione
      comune; il secondo `decide_nodes` in `read_outline` sparisce; gli errori
      di disegno vuoto (solo in heal) valgono per tutti; `label` e
      `source_file` (heal li prende, outlines usa `doc.source_path`) vanno
      sulla rete.
      Superficie di `Network`: `edges` (riparati), `crossings`, `free_ends`,
      `set_aside` (ruoli non strutturali), `warnings`, `errors`, `is_valid`,
      `source_file`, `label`; `faces()`, `outlines()`. `NodedEdges` resta
      interno.
- [x] B. una riparazione sola dietro `heal()` → `Network`; golden classificati.
      Fatto: `readings/network.py` (`build_network`, `repair_edges`); heal() e
      outlines() leggono la stessa rete, firme invariate (il cambio è C). Loose
      sempre dalla rete (D203). Suite verde, nessun golden cambiato; anch_06
      rientra nel budget di testo (loose 179 → 101, doppioni fusi, 0 mm persi)
      ed esce dai fallimenti attesi. Note della misura:
      Misura fatta il 2 novembre (`_debug/2026-11-02_topo_D202-network`,
      `measure.py`, solo lettura): `faces()` = `heal()` su 218/218 disegni;
      `outlines()` su una riparazione sola (tutto il disegno, keep_junctions
      True), con un numero solo o con due: geometria dei contorni identica
      su 51/51, i loose fuori da ogni isola (quelli del golden) uguali sui 15
      golden; tempi uguali o un poco sotto (52 s contro 55). Cambia una cosa
      sola: le isole che outlines() non legge (riquadro, isole annidate,
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
- [ ] filo parcheggiato → **G15** (cancello): vedi sotto.
- [x] C. `heal()` → `Network`; `faces()`/`outlines()`; `island()` tolto;
      `read_outline(s)`/`OutlineReading` (taglio netto, D202). `source_file`
      di default da `doc.source_path`, `label` su tutte e due le letture (D204).
- [x] D. docs (LLM, API §3, README x2, CLAUDE.md regola 5, SCRIPTS, ARCHITECTURE)
      e `release_check` (3 novembre). `release_check.py` non nomina `island`:
      nessuna modifica. Suite 244 s (sopra il budget). I consumer si adattano
      nelle loro sessioni.

## IL CANCELLO DELLA 1.0 (D148, 22 ottobre)

**Feature freeze.** La lista è chiusa: può solo accorciarsi (D193 l'elenco).
Quando è vuota topo è *1.0-ready*: `python scripts/release_check.py` esce 0 e
da quel giorno ogni commit su `main` lo tiene a 0. Entra solo ciò che rompe un
nome pubblico, o rende vere e provate le invarianti di D143 sui fixture del
repo, più i documenti (D144) e la history pulita; il resto è 1.x (D158, D174).

**Chiusi:** G1 (campi di `Result`, D150), G7 (D220), G2 (→ 1.x, D149), G3 (fedeltà a due
vie, D152), G4 (discretizzazione, D145/D153/D154), G5 (misure, D156), G6 (4
dubbi D103, D157), G6b (ogni pezzo una volta, D163), G6c (contatto deciso una
volta, D180), G6d (D189), G6e (`heal()` indipendente dal riferimento: D201,
3 residui in 1.x), G11 (`release_check.py`), G12 (area esatta, D165), G13
(nessun tipo shapely nella superficie, D166–D168), G15 (contorni chiusi
esatti, D206/D209), G16 (tratteggio per ruolo, D210) — tutti e due il 6
novembre, ramo `no-join-ends` fuso in `main`.

**Aperti**
- [x] **G15** Un contorno consegnato si chiude entro tolleranza (3 novembre).
      Rende vera la regola 6 di CLAUDE.md (`is_valid` prima di una macchina);
      allarga D143 con la chiusura. Caso: `heal(doc, tolerance=0.5)` su
      `regr_02`, `anch_03`, `anch_03_noframe`: uno spigolo a 90° con
      un'obliqua a 45° sopra, interrotta di 0,41 mm sullo spigolo.
      `close_free_gaps` chiude il buco, il pezzo di chiusura taglia lo
      spigolo e nella rete compare due volte (`split_at_crossings`).
      Misurato su 25 DXF (`golden_outlines/`, `golden_anchoring/`): salto di
      0,411 mm in `faces()` su tutti e tre, in `outlines()` su `regr_02` e
      `anch_03_noframe`; `is_valid` True ovunque. A 0,05 (tolleranza del file)
      nessun buco. `validate_result` non controlla la chiusura.
      Sottopassi: 2 controllo di chiusura in `validate_result`; 3 meccanismo
      in `readings/network.py` (non il solo regr_02); 4 golden, se cambiano;
      5 decisione in MAP.md.
      Fatto il 3 (`78b460c`): `normalize` fonde i collineari due volte, prima
      (doppioni del disegno) e dopo `close_free_gaps` (le due metà allungate
      sul gap si sovrappongono). Federico (2 novembre, DXF in `_debug`):
      `sbagli_tratteggio_largo` con G15 giusto in `faces()` (12) e
      `outlines()` (10), senza G15 sbagliato in tutte e due. Lo stretto non
      ancora giudicato. Restano 2, 4, 5.
      `largo` in `tests/data/golden_faces/` con golden `faces()` (passa con G15,
      senza fallisce: area +1607 mm²). Per il 2: `outlines()` non chiama
      `validate_result`. Salti testa-coda misurati a 0,5 con G15 (81 file
      golden_outlines/anchoring, 162 letture): 72 a zero, 45 > 1e-6, 9 > 0,01
      (max 0,062 `regr_01` faces; 0,05 su regr_03, anch_01, anch_01_noframe),
      il salto G15 era 0,411. Deciso D206: chiuso esatto, ogni salto è un
      bug del motore → le 48 letture con salto > 1e-9 vanno corrette.
      Storia (stessi 81 file, faces+outlines a 0,5; letture con salto > 1e-9):
      0.23.0 `66829cb` 32 (max 0,05) · prima di D189 `6c0cca6` 36 (max 0,064)
      · D189 `f477804` 47 (9 a 0,41–0,42, tolti da G15) · oggi 48 (max 0,062).
      Dal 25 ottobre: 31 rotte allora e oggi, 1 guarita, 17 nuove.
      **Chiuso il 6 novembre**: `test_fidelity` (218 test, 162 letture)
      pretende 0 salti e passa; un salto entro tolleranza lo chiude una retta
      nuova con un warning (D209). Suite intera verde (3046, 0 falliti).
- [ ] **G14** Superficie allineata alle API di una libreria matura (D174,
      D175). Fatti: la regola (D175), la passata sui nomi (D176, D177), la
      regola 1 come test (D178). Restano: la regola 8 (con G9) e il test di
      rimozione delle deprecazioni (vuoto finché non ce n'è una). Consumer da
      adeguare con le tabelle vecchio → nuovo di D176/D177: snapbend,
      snapdraw, smoother, pippo — dalle loro sessioni.
- [x] **G16** Un tratteggio dentro un pezzo non sporca il contorno (2 novembre).
      `tests/data/sbagli_tratteggio.dxf` (non tracciato; 12 linee + un `HATCH`
      ANSI31 che `topo_dxf` non legge), con il tratteggio esploso in 2622 righe
      a 45° (0,125 mm) e un restringimento di 0,3 mm nel contorno. A tolleranza
      0,5: `faces()` ha un contorno di **1136** segmenti (dovrebbero essere 12),
      `outlines()` di 14–15; a 0,05 sono 12 tutti e due. Nato con D189
      (`f477804`): `6c0cca6`, il commit prima, dava `heal()` a 12 segmenti e 0
      inner; da `f477804` 1136 (anche `ca3cac5`, prima di D202). Dipende dalla modifica
      di G15 (misurato a 0,5, HEAD `be2d3b8` con/senza la seconda fusione):
      stretto `faces()` 1136 seg + 0/1 inner, `outlines()` 15/14; largo
      `faces()` 12/9, `outlines()` 10/9. Più indietro (`b7ca910`) era un'altra cosa: 70 cluster. I 1136 sono i 12 lati veri, nella forma giusta, spezzati in ogni punto
      in cui una riga di tratteggio li tocca (681 orizzontali, 451 verticali,
      4 altri, nessuno a 45°): la rete piana ha 7885 pezzi, il contorno non li
      rifonde. Resta da guardare lo stretto (`outlines()` dà 14–15 segmenti; quanti
      debbano essere lo stabilisce Federico). Federico:
      né `faces()` né `outlines()` vanno bene così.
      Causa: i 1136 sono i lati spezzati dai contatti del tratteggio, mai
      rifusi → `faces()` rifonde i collineari. `largo`: con G15 giusto per
      Federico (vedi G15), non fa più parte di G16.
      Ramo `no-join-ends` (6 novembre): la causa vera era `NodedEdges.whole`,
      che ricomponeva un lato solo se il giro lo percorreva tutto; agli angoli
      una riga di tratteggio lascia fuori la punta, e il lato restava a pezzi.
      Ora i pezzi di fila tornano un tratto solo della curva (`_joined_run`):
      stretto `faces()` 1136 → 14, `outlines()` 15 (12 lati + righe di
      tratteggio sugli angoli). Federico (6 novembre): il tratteggio lo toglie
      il consumer prima di `heal()`, con un ruolo non strutturale; così
      stretto dà 12 in tutte e due le letture. DXF in `_debug/2026-11-06_topo_g16-tratteggio`.
      **Chiuso il 6 novembre**: il rosso→verde del meccanismo è
      `TestPartOfACurveOnTheContour` (`test_noding.py`, rosso su `main`); la
      promessa di D210 è `tests/integration/test_non_structural_role.py`
      (righe con ruolo non strutturale che tagliano gli angoli: pezzo e area
      uguali a quelli senza righe, righe in `loose`; rosso se le righe restano
      nella rete). Riconoscere un tratteggio è del consumer (snapdraw): il
      file `stretto` resta non tracciato, per il suo test.
- [x] **G7** Zero `expectedFailure` (7 novembre, D220). Difetti noti ne restano
      (curva che incrocia sé stessa, curva chiusa che tocca col nodo, agganci persi):
      sono limiti della 1.0, scritti qui sotto, non test rossi.
      golden di outlines e di aggancio rigenerati, liste dei noti vuote,
      suite senza rossi attesi. Golden dei `_noframe` non fatti (Federico).
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
      Misura del 2 novembre: 4:07 a `fc9997e` (prima di D202 C), 4:08 dopo.
      Restano `test_fidelity` sulle spline e le letture di `outlines()`.
      Misura del 7 novembre a `43cf58a` (seriale, `--durations=0`): 4:35, 3242 test.
      Le letture di `outlines()` valgono ~159 s su 272: `test_fidelity` _outlines 81 s
      (31 test), `test_outlines_invariants` 65 s (`TestScrambled` 47), `test_outlines_single_use`
      13 s. `test_heal_invariants` 57 s (1496 test). I 17 file con `ezdxf`: 7,5 s in tutto,
      quindi il punto 1 qui sotto non accorcia la suite. Il disegno più caro: anch_02 (38 s + 18 il noframe).
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
      Nel cancello (D160, D212); misurare il tempo prima e dopo.
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

Difetti trovati il 6 novembre (fatti, nessuna analisi):
- Agganci dei testi persi con D161 (golden di `golden_anchoring/` rigenerati il 7 novembre, Federico li accetta senza giudicarli): testi rimasti senza aggancio anch_02 3, anch_03 1, anch_04 10, anch_05 7, anch_07 1; tipico un richiamo "M6 n°16 fori" che era legato a una figurina 6×3 (inner di `faces()` di prima) e oggi a niente. Da guardare con snapdraw.
- `tests/integration/test_non_structural_role.py`, stesso disegno, righe
  senza ruolo (`unknown`) a 0,5: `faces()` 0 cluster, `is_valid` False,
  435 curve in `loose` su 475 edge. Con `is_structural=lambda r: True` e
  ruolo `x`: 0 cluster, `loose` vuoto, warning "508 edge non di contorno
  esclusi dal grafo" → edge non consegnati da nessuna parte (D137?).

Primo lavoro (deciso il 30 ottobre):
- **discretizzazione delle spline in Rust** (o almeno numpy): De Boor in Python
  è il costo singolo più grosso di `outlines()`. Prova numpy a blocchi: scende
  solo da 6.5 a 5.1 s (D169 chiede la misura per un core Rust).

- **Fusione delle curve quasi allineate / quasi coarcali** (Federico, 6
  novembre): funzione pubblica a parte, chiamata da chi usa topo sul
  risultato, con la soglia sua. Le letture non fondono mai due curve diverse
  del file (sposterebbe il vertice fra le due); `merge_runs` è la base.
  Oggi `outlines()` le fonde (`_contour`, `merge_runs` a 1e-3): da togliere
  quando c'è la funzione.

- **`topo_dxf` non legge `HATCH`** (adapter, 1.x; Federico, 2 novembre): oggi
  solo un avviso in `doc.warnings`. Un tratteggio (es. ANSI31) va esploso in
  righe e dato come edge normali: topo non sa che cosa sono (regola 4), lo sa
  il consumer. `ezdxf.render.hatching.hatch_entity` le genera; sul fixture
  `tests/data/sbagli_tratteggio.dxf` (non tracciato) sono 2622 righe a 45°
  ogni 0,125 mm. Da decidere con lui: edge con ruolo `unknown`, o altro.

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
- **in `outlines()` i pezzi dello stesso cerchio/retta si ricompongono anche in
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
- **bisettrice e offset** (2 novembre; ricerca: nulla di simile in
  `topo.geometry`, vicino c'è solo `offset_from_line` = distanza con segno,
  positiva a sinistra, e le strisce D142). In due minor: (1) primitive esatte,
  senza politica, in `core/geometry/` + `topo.geometry`: `offset_segment`
  (retta traslata, arco concentrico r±d, mai un poligono discretizzato) e la
  bisettrice di due tratti come `LineSeg` con `length` richiesta (nessun
  tipo nuovo di retta infinita); stesso segno di `offset_from_line`. I due
  tratti NON devono toccarsi: il vertice è l'incrocio delle rette (con un
  raccordo o uno smusso in mezzo è fuori dal materiale); se un tratto
  contiene il vertice l'angolo è ambiguo → `ValueError`. La linea di mezzo
  fra parallele è un fatto a parte (`midline`, lista di tratti). L'offset di
  una catena aperta e quello di un contorno chiuso sono lo stesso meccanismo.
  (2) offset di contorno (giunzioni, collasso, un contorno che si divide in
  due) in `topo.experimental` finché non regge D143; mai silenzioso (regola 7).
  "Kerf" è l'uso di un consumer, non un nome di topo. Da decidere prima di
  scrivere: `side` o due funzioni; dove finisce la bisettrice (solo `length`).
- **dipendenze** (D169): misurare i tempi di `heal()`/`outlines()` sulle
  fixture; inventario shapely/numpy → sostituto; poi un pezzo alla volta e a
  pari golden. Il noding resta a GEOS.

## Catalogo dei fatti geometrici futuri (2 novembre) — 1.x, nulla deciso

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
- **Ricette di ricomposizione**: oggi `heal` (un pezzo piano) e `outlines` (più
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
- **`outlines()` e cornici**: i test girano sui disegni grezzi, la cornice
  diventa l'isola più esterna (la riconosce snapdraw, D90). Copie
  `*_noframe.dxf` fatte; un cerchio chiuso non dovrebbe cambiare natura per
  ciò che gli sta attorno (anch_07: due cerchi sono inner con la cornice,
  `loose` senza). Si chiude in G7.
- **Contatto di un giro con sé stesso deciso sul poligono discretizzato**
  (`_loop_faces`, anch_06: un cerchio D2.2 toccato da un simbolo passa da
  `circle` a `other` cambiando la discretizzazione): decidere il contatto sulle
  primitive prima di rifare i golden di outlines (G7).
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
  normalizzazione, orientamento, scheletro, decomposizione): ora nel
  "Catalogo dei fatti geometrici futuri".

## Regola da ricordare

Mai parlare di layer DXF quando si parla di `role` e di estensibilità: i
`role_rules` sono solo il modo di assegnarlo al load (D63), il meccanismo vero
è `edge.role`, per qualunque criterio, senza dipendere da layer o formato.
