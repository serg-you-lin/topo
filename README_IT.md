# topo

**Motore di geometria 2D deterministico: ripara la geometria vettoriale e ne legge la struttura — contorni chiusi, cosa sta dentro cosa, cosa è collegato.**

`topo` prende geometria 2D rotta e ne ricava un modello pulito e senza perdite —
contorni chiusi ricuciti, la loro gerarchia di contenimento, i testi del
disegno, e un overlay aperto dove un consumatore attacca la sua lettura — e lo
riscrive in uscita. Il prodotto è il modello. **topo non conosce alcun formato
di file**: lavora su geometria e ruoli. I file entrano ed escono attraverso gli
adapter, pacchetti fratelli nella stessa distribuzione.

La parte distintiva è l'**healing**: le curve che dovrebbero incontrarsi e non
lo fanno — piccoli gap, doppioni, sporgenze, pezzi disegnati uno per uno —
vengono ricucite in contorni chiusi, e niente viene scartato in silenzio.

Oggi la geometria arriva soprattutto da file CAD e disegni tecnici (DXF in
ingresso; DXF, JSON o SVG in uscita); il motore vede solo geometria, da
qualunque fonte arrivi.

topo **non è uno strumento per la lamiera**. La lamiera e la piastra sono il
contesto in cui è nato, e il suo primo consumatore, non il suo confine: il
motore non conosce materiale, processo né prodotto. Leggere un contorno come "un
foro da forare" o una linea come "una piega" è interpretazione del consumatore
(`snapbend` per la lamiera, `snapdraw` per la notazione del disegno), scritta
sopra attraverso un overlay aperto (`cluster.overlay`).

> Stato: **alpha**. In produzione, ma l'API si muove ancora. Vedi `MAP.md` per le decisioni di design correnti.

> **Scrivi codice contro topo con un assistente AI?** Dagli anche
> [`docs/LLM.md`](docs/LLM.md): ogni nome pubblico con la sua firma, in pochi
> token. Questo README è la panoramica; i nomi fuori dall'API stabile stanno in
> `topo.experimental` e si scrivono sempre con quel prefisso.

---

## Installazione

```bash
pip install -e .            # topo da solo: geometria in entrata, SVG / JSON / testo in uscita
pip install -e ".[dxf]"     # + topo_dxf: file DXF e DWG in entrata, DXF in uscita
pip install -e ".[pdf]"     # + topo_pdf: PDF in entrata (sperimentale)
```

I comandi sopra installano da un clone del repository. Da una wheel già costruita si nomina il file:
`pip install "g_topo-<versione>-py3-none-any.whl[dxf]"`. g-topo non è su PyPI.

Una distribuzione (`g-topo`), tre pacchetti importabili:

| pacchetto  | cosa                                                          |
|------------|---------------------------------------------------------------|
| `topo`     | il motore: modello, heal, le due letture, split, SVG / JSON / testo |
| `topo_dxf` | adapter di file: legge DXF e DWG, scrive DXF. Per il DWG serve [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter) installato (gratuito, `ODA_PATH`) |
| `topo_pdf` | adapter di file: legge PDF (sperimentale)                     |

`topo` non importa mai un adapter, e un adapter usa solo i nomi pubblici di topo
— un confine che il controllo dell'indice fa rispettare
(`scripts/gen_index.py --check`). Cosa legge e scrive un adapter, e le sue
opzioni, stanno in `docs/API.md` (§9, §10). Python ≥ 3.10.

---

## Avvio rapido — geometria in mano

```python
import topo

fg = topo.geometry
doc = topo.load_segments(fg.rectangle(200, 100) + fg.circle(10))   # -> Document
net = topo.heal(doc)                                              # riparato una volta -> Network
result = net.faces()                                              # -> Result

if not result.is_valid:                          # nessun contorno esterno chiuso
    print(result.errors)

cluster = result.clusters[0]                     # un pezzo: esterno 200×100, un cerchio interno
print(cluster.outer.area, len(cluster.inners))
topo.save_json(result, "part.json")              # i fatti del modello
topo.experimental.save_svg(result, "part.svg")   # un'immagine
```

I builder restituiscono segmenti di topo: `polygon(points)`, `rectangle`,
`regular_polygon`, `circle`, `ellipse`, `stadium` (con archi veri). Ogni altra
forma a lati dritti è un `polygon`.

## Da un file

```python
import topo, topo_dxf

doc = topo_dxf.load_dxf("part.dxf", tolerance=0.5)   # .dxf o .dwg -> Document
result = topo.heal(doc).faces()
topo_dxf.to_dxf(result, doc).saveas("part_healed.dxf")
```

Dopo `load_dxf` tutto lavora sul `Document`, che non sa di formati; l'adapter è
l'unico codice che conosce il file.

## Più pezzi in un disegno

```python
for part in topo.split(result):                 # un Result per pezzo, senza formato
    name = part.clusters[0].label               # _P1, _P2, ... (heal(doc, label="x") dà x_P1; oppure namer=)
    topo.experimental.save_svg(part, f"output/{name}.svg")
```

`split` è una decisione sul modello: quali pezzi (`min_area`), i loro nomi
(`namer`), quali curve sciolte e testi viaggiano con ciascuno (il pezzo che li
contiene, o il più vicino). Poi un adapter scrive ogni pezzo nel suo formato.

## Due letture di una rete ricucita

`heal()` ripara la geometria una volta (nodi, doppioni, gap fino a `max_gap`) e
restituisce un `Network`; una lettura di questo dà un `Result`.

- `faces()` legge da dentro: quali giri si chiudono, quale sta dentro quale.
  Per contorni piani separati.
- `outlines()` legge da fuori: le curve che si toccano formano un gruppo, il
  contorno esterno di ogni gruppo è la faccia esterna della sua rete planare, e
  ogni contorno esterno non contenuto in un altro è un cluster con il solo
  `outer` (quello che sta dentro va in `loose`). Per un disegno di più viste.

```python
result = topo.heal(doc, max_gap=0.5).outlines()
for cluster in result.clusters:              # una vista (o un pezzo) per contorno
    print(cluster.outer.area)
```

`max_gap` (default `tolerance`) è il gap più largo che viene chiuso. Le letture
sono ricette su passi pubblici: i passi di `heal()` sono esportati uno per uno
in `topo.experimental` (`topo.experimental.split_labeled`,
`topo.experimental.close_free_gaps`, `topo.experimental.face_loops`,
`topo.experimental.build_hierarchy`, ...), così un consumatore compone il suo
ordine — vedi `docs/API.md` (i passi di `heal()`).

## Forme: cos'è un contorno, non a cosa serve

topo dà nomi alla geometria, mai al suo uso. Un cerchio è un cerchio; a cosa
serve lo legge il consumatore (D68, D91).

```python
for cluster in result.clusters:
    for inner in cluster.inners:
        shape = topo.geometry.contour_shape(inner)     # circle / ellipse / stadium / rectangle / polygon / other
        print(shape.kind, shape.center, shape.length, shape.width)

    # cerchi con lo stesso centro, dal più piccolo (anche quelli da soli)
    for group in topo.geometry.concentric_groups(cluster.inners, tolerance=0.1):
        if len(group.items) > 1:
            print("concentrici:", group.center, group.diameters)

# archi concentrici a un cerchio e più grandi: ampiezza, rapporto dei raggi
# (un arco aperto non chiude niente, quindi sta in result.loose)
arcs = [s for c in result.loose for s in c.segments if isinstance(s, topo.primitives.ArcSeg)]
for found in topo.geometry.arcs_around((10, 20), 2.5, arcs, tolerance=0.1):
    print(found.sweep, found.radius_ratio)
```

Nessuna soglia di significato dentro: cosa vuol dire un arco di una certa
ampiezza lo decide il consumatore.

---

## La pipeline

```
un adapter (un file)      ──►  Document   (edge + testi)
topo.load_segments(segs)  ──►  Document   geometria in mano
                          │
                          ▼
topo.heal(doc)  ──►  Network     riparato una volta: nodi, doppioni, gap
                          │
                          ▼   .faces() / .outlines()
                       Result      contorni chiusi, albero di contenimento outer / inner
                          │
                          ▼
  (la lettura di un consumatore)  scritta in cluster.overlay
                          │
                          ▼
   topo.split(result)                       ──►  list[Result] uno per pezzo, senza formato
   topo.save_json(result, path)                  i fatti del modello in JSON
   topo.experimental.to_svg(result)         ──►  stringa SVG  per una UI / un report (fuori dall'API stabile 1.0, D133)
   topo.experimental.to_view_model(result)  ──►  dict (geometria completa) per un renderer esterno (fuori dall'API stabile 1.0)
   un adapter                               ──►  un file
```

Ogni renderer disegna dallo stesso modello, mai dal file sorgente, quindi
mostrano tutti la stessa cosa.

## Cosa contiene un `Result`

```
Result      clusters: list[Cluster]   loose: list (curve che non sono contorno di nessun cluster)
            texts   is_valid   errors   warnings   notes
            reading ("faces" / "outlines")   tolerance   max_gap
            source_file   source_format   cluster_count
Cluster     outer: Contour   inners: list[Contour]   label   overlay (la lettura di un consumatore)
            area   bbox
Contour     segments (LineSeg / ArcSeg / CircleSeg / EllipseSeg / BSplineSeg)   role
            area   bbox   centroid   points   depth   parent   contains(...)
```

Le forme si chiedono alla geometria, non sono salvate: `topo.geometry.contour_shape(contour)`.
Schede complete in `docs/API.md` (`Result`, `Cluster`, `Contour`).

---

## Ispezione

```python
topo.inspect_document(doc)          # cos'è l'ingresso: edge, primitive, grafo dei nodi
topo.inspect_result(result)         # cosa ha fatto topo: cluster, outer/inner, overlay, curve sciolte
```

Tutto stampa su stdout. Serve quando qualcosa non torna e devi vedere in che
punto della catena si rompe. Un adapter può aggiungere un livello suo per il
file grezzo (`docs/API.md`).

---

## Cosa promette topo, e i suoi limiti

- **Millimetri**: ogni lunghezza, tolleranza e area è in mm. topo non legge l'unità che un file
  dichiara (spesso è sbagliata): un disegno in pollici va convertito in mm prima di leggerlo.
- **Fedele**: ogni contorno sta entro `tolerance` dalla geometria sorgente, nei due sensi.
- **Completo**: ogni curva è contorno di un cluster o sta in `result.loose`;
  niente viene scartato in silenzio.
- **Deterministico**: lo stesso ingresso dà lo stesso risultato, a ogni
  esecuzione. La stessa geometria spostata o ruotata *non* è promesso che dia lo
  stesso risultato: una regola sì/no su un numero misurato ha un bordo, e
  l'arrotondamento di una rotazione può spingere un valore oltre. Perché, per
  qualunque lettore: [`docs/LIMITS_IT.md`](docs/LIMITS_IT.md).
- Un gap più largo di `max_gap` non viene chiuso: le curve restano in `loose`.
- Se non si forma nessun contorno esterno chiuso, `result.is_valid` è `False`.
  I renderer disegnano comunque quello che c'è, così vedi cosa ha capito topo;
  chi consegna a una macchina passa `allow_invalid=False` e riceve
  `ValueError`. `topo.split` solleva sempre: un risultato per pezzo non ha senso
  senza pezzi.
- **I consigli sono sperimentali.** Un avviso è un `topo.Diagnostic`: cosa è
  successo (`code`, `message`), dove (`points`) e perché (`notes`) sono stabili.
  La chiamata che suggerisce per sistemarlo (`help`, `param`, `value`) è
  sperimentale: può sbagliare su un caso su cui non è stata misurata, e può
  cambiare in una minor. Leggila, giudicala, non applicarla alla cieca.

**Difetti noti dell'healing** — un risultato sbagliato che puoi incontrare oggi,
da sistemare nella 1.x. Ognuno è stato riprodotto sul codice attuale.

- *Curva che incrocia se stessa.* Una curva sola che incrocia se stessa non
  viene tagliata nel suo incrocio: tutte e due le letture danno l'anello intero
  come un contorno (un quadrato con un ricciolo dà l'area con segno
  dell'anello, non il quadrato più un lobo in `loose`). Lo dice
  l'avviso `self-crossing`.
- *Un nodo su un'altra curva chiusa.* Due curve chiuse semplici dove un vertice
  dell'una sta esattamente sul bordo dell'altra: `outlines()` dà la prima e
  mette la seconda in `loose`; lo dice l'avviso `closed-touch`.
- *Un cerchio disegnato a tante rette corte con una piccola apertura.* Viene
  rifatto in una curva aperta sola, i cui due capi non sono mai trattati come un
  gap, quindi resta in `loose` invece di chiudersi (circa il 6% di questi
  anelli in un campione a caso); lo dice la nota `open-spline`.
- *Edge esclusi dal grafo.* Con un `is_structural` su misura che accetta ogni
  ruolo, `faces()` può non consegnare da nessuna parte gli edge messi da parte
  come non di contorno (nessun cluster, niente in `loose`) — un'eccezione a
  *completo* qui sopra. L'avviso `non-contour` li conta; `outlines()` li
  consegna.
- *Consiglio di quasi-copia su spigoli veri.* Una retta corta con i due capi
  entro `tolerance` da una più lunga viene segnalata come quasi-copia anche dove
  le due si incontrano in uno spigolo vero (45–90°), e il consiglio propone una
  fusione che aprirebbe il contorno. La geometria è letta giusta; sbaglia solo
  il consiglio.

**Comportamenti voluti**, da sapere:

- *I pezzi minuscoli si saldano.* Un gruppo di tratti entro 0,05 viene saldato
  su un nodo solo (nota `welded`): un pezzo più corto di così non si distingue
  da un nodo.
- *Un salto si chiude, non si sposta.* Dove una curva supera un'altra di pochi
  millesimi, la lettura aggiunge un tratto dritto corto fra i due capi (nota
  `gap-closed`) invece di spostare una delle due curve: le curve del disegno
  restano come sono disegnate. Accorciare il capo lungo se stesso fino all'altra
  curva, come a un incrocio, è previsto nella 1.x.
- *`outlines()` unisce i pezzi che continuano uno nell'altro* (allineati o
  sullo stesso cerchio, entro 1e-3) in una curva sola; `faces()` tiene ogni
  pezzo come è disegnato. Tutte e due restano entro `tolerance` dalla sorgente.
- *Due curve chiuse che si incrociano* (lo stesso cerchio disegnato due volte,
  a 0,05) sono due cluster e il risultato resta valido, con l'avviso
  `crossing`. Se dei contorni che si incrociano debbano rendere il risultato
  non valido non è ancora deciso.

**Costi e parti sperimentali**

- I disegni fatti di lunghe catene di tratti cortissimi costano circa il doppio
  da ricucire; la discretizzazione delle spline è il costo singolo più grande
  di `outlines()`; due fogli grandi di viste misurati oltre 300 s.
- I testi legati alla geometria (`topo.experimental`) mancano alcuni legami che
  un lettore traccerebbe.

---

## Documentazione

- **[`docs/LLM.md`](docs/LLM.md)** — riferimento compatto per un'AI che scrive
  codice contro topo: stesso contenuto di `API.md`, meno token possibile. È quello
  da dare a un LLM.
- **[`docs/API.md`](docs/API.md)** — ogni funzione pubblica: firma, cosa prende,
  cosa ritorna, cosa muta, quando solleva. Con esempi copiabili. Anche gli adapter.
- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** — com'è fatto dentro e
  perché: gli strati, il flusso, "il prodotto è il modello".
- **[`docs/LIMITS_IT.md`](docs/LIMITS_IT.md)** — cosa topo non può promettere, e perché.
- **`MAP.md`** — le decisioni di design, in ordine cronologico.
- **[`tutorial/`](tutorial/README.md)** — lezioni numerate (in inglese), da un pezzo disegnato in codice a una cartella di disegni tuoi.
- **`SCRIPTS.md`** — gli strumenti di manutenzione in `scripts/`.

---

## Licenza

Tutti i diritti riservati — vedi [`LICENSE`](LICENSE). Copyright (c) 2026
Federico Sidraschi. Non è open source; per provarlo o usarlo, scrivimi:
smia4punto6@gmail.com.
