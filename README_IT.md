# topo

**Motore di geometria 2D deterministico per il disegno tecnico e la geometria CAD.**

`topo` prende un disegno 2D disordinato e ne ricava un modello pulito e senza
perdite — contorni chiusi ricuciti, la loro gerarchia di contenimento, le
annotazioni del disegno, e un overlay aperto dove si attaccano le feature
rilevate — poi lo riscrive in DXF (un documento, o uno per pezzo), JSON/XML, SVG,
un view model per una UI, o (sperimentale) una lettura testuale compatta per un
modello linguistico. Il prodotto è il
modello; un formato CAD è solo una porta di entrata o di uscita. **topo stesso
non conosce alcun formato di file**: geometria e ruoli, mai layer. Le porte sono
adapter, pacchetti fratelli nella stessa distribuzione — `topo_dxf` (DXF, DWG
via ODA) e `topo_pdf` (sperimentale) — che usano solo i nomi pubblici di topo;
tutto ciò che sta a valle lavora sul modello neutro rispetto al formato.

La parte che nessun altro strumento fa per te è l'**healing**: ricucire la
geometria rotta — matasse di `LINE`/`ARC` da un export CAM, il DXF di un cliente,
un vecchio file R12 — in contorni chiusi.

**Non è una libreria DXF** e **non è uno strumento per la lamiera**. La lamiera
e la piastra sono il contesto in cui topo è nato, e il suo primo consumatore, non
il suo confine: il motore non conosce materiale, processo né prodotto. Leggere la
geometria come "un foro da forare" o "una piega" è interpretazione del
consumatore (`snapbend` per la lamiera, `snapdraw` per la notazione del disegno):
topo non ha letture di quel tipo dentro, così un consumatore di qualunque
dominio ottiene la stessa geometria e ci mette sopra il suo vocabolario
attraverso un overlay aperto (`cluster.detected`).

> Stato: **alpha**. In produzione, ma l'API si muove ancora. Vedi `MAP.md` per le decisioni di design correnti.

---

## Installazione

```bash
pip install -e ".[dxf]"     # da un clone: topo + topo_dxf (DXF/DWG in entrata e in uscita)
pip install -e .            # topo da solo: geometria in entrata, SVG / JSON / testo in uscita
pip install -e ".[pdf]"     # + topo_pdf, input PDF sperimentale
```

Una distribuzione (`g-topo`), tre pacchetti importabili:

| pacchetto  | cosa                                   | extra   | porta   |
|------------|----------------------------------------|---------|---------|
| `topo`     | il motore: modello, heal, island, split, SVG/JSON/testo | —       | `shapely`, `numpy` |
| `topo_dxf` | lettore e scrittore DXF/DWG, XDATA, `inspect_dxf` | `[dxf]` | `ezdxf` |
| `topo_pdf` | lettore PDF (sperimentale)             | `[pdf]` | `PyMuPDF` |

`topo` non importa mai un adapter, e un adapter solo i nomi pubblici di topo —
un confine che fa rispettare il controllo dell'indice (`scripts/gen_index.py
--check`). Python ≥ 3.10.

---

## Esempio — file singolo

```python
import topo, topo_dxf

doc    = topo_dxf.load_dxf("pezzo.dxf", tolerance=0.5)   # -> Document
result = topo.heal(doc)                                  # topologia: contorni chiusi, outer/inner
#   fori, pieghe, incisioni sono una lettura di processo sopra: snapbend.flat.detect_flat

if not result.is_valid:                                  # nessun contorno esterno chiuso
    print(result.errors)                                  # si disegna lo stesso, vedi "Limiti noti"

doc_out = topo_dxf.to_dxf(result, doc)                   # -> ezdxf Drawing
doc_out.saveas("pezzo_healed.dxf")

topo.save_json(result, "pezzo.json")                 # metadati
cerchi = [c for cl in result.clusters for c in cl.inners
          if topo.geometry.contour_shape(c).kind == "circle"]
print(f"{result.cluster_count} cluster, {len(cerchi)} cerchi interni")
```

## File multi-pezzo

```python
import topo, topo_dxf

doc    = topo_dxf.load_dxf("batch.dxf")
result = topo.heal(doc, label="batch")

for part in topo.split(result):                 # un Result per pezzo, senza formato
    name = part.clusters[0].label               # batch_P1, batch_P2, ... (o namer=...)
    topo_dxf.to_dxf(part, doc).saveas(f"output/{name}.dxf")
    topo.save_svg(part, f"output/{name}.svg")   # lo stesso pezzo, un altro formato

topo_dxf.split_to_files(doc, "output/", label="batch")   # heal + split + salvataggio, in una chiamata
topo.save_json(result, "batch.json")
```

`split` è una decisione sul modello: quali pezzi (`min_area`), come si chiamano
(`namer`), quale trash e quali testi viaggiano con ognuno (il pezzo che li
contiene, o il più vicino). Ogni adapter scrive poi un pezzo nel suo formato.

## Un disegno di viste (più viste, isometrica)

```python
import topo, topo_dxf

doc    = topo_dxf.load_dxf("tavola.dxf")   # cornice / cartiglio marcati per ruolo, o tolti
result = topo.island(doc, max_gap=0.5)
for cluster in result.clusters:              # una vista (o un pezzo) per isola
    print(cluster.outer.polygon.area, len(cluster.inners))
```

`heal()` legge un disegno di sagome piane separate dall'interno (quali giri si chiudono, chi sta
dentro chi). `island()` legge un disegno di viste dall'esterno: gli edge che si
toccano fanno un pezzo, il contorno esterno di ogni pezzo è la faccia esterna
della sua rete piana, e ogni contorno esterno che non sta dentro un altro è
un'isola; quello che sta dentro è suo per contenimento. Non c'è una distanza
fra le viste. Quali buchi del disegno chiudere (`max_gap`) dipende dal disegno,
quindi lo dice sempre chi chiama: topo non ha default. Stesso `Result` in uscita — vedi `docs/API.md` (`island`).

Tutte e due sono ricette su passi pubblici. I passi di `heal()` (`split_labeled`,
`close_free_gaps`, `find_loops`, `build_hierarchy`, ...) sono esportati uno per
uno, così un consumatore compone il suo ordine — vedi `docs/API.md` (i passi di
`heal()`).

## Disegnare con topo

```python
import topo, topo_dxf

fg = topo.geometry
doc = topo.load_segments(fg.rectangle(200, 100) + fg.rectangle(100, 50))
result = topo.heal(doc)                # un pezzo: outer 200×100, un inner 100×50
topo.save_svg(result, "due_rettangoli.svg")             # senza adapter
topo_dxf.to_dxf(result, doc).saveas("due_rettangoli.dxf")
```

I costruttori restituiscono segmenti di topo: `polygon(punti)`, `rectangle`,
`regular_polygon`, `circle`, `stadium` (con archi veri). Ogni altra forma a lati
dritti è un `polygon`.

## Forme: cos'è un contorno, non a cosa serve

topo dà nomi alla geometria, mai al suo uso. Un cerchio è un cerchio; se sia un
foro da forare, una sede o il puntino di un logo lo legge un consumatore
(snapbend per il pezzo, snapdraw per la notazione del disegno — D68, D91).

```python
for cluster in result.clusters:
    for inner in cluster.inners:
        shape = topo.geometry.contour_shape(inner)     # circle / stadium / rectangle / polygon / other
        print(shape.kind, shape.center, shape.length, shape.width)

    # cerchi con lo stesso centro, dal più piccolo (anche quelli da soli)
    for group in topo.geometry.concentric_groups(cluster.inners, tolerance=0.1):
        if len(group.items) > 1:
            print("concentrici:", group.center, group.diameters)

# archi concentrici a un cerchio e più grandi: angolo in gradi, rapporto dei raggi
for found in topo.geometry.arcs_around((10, 20), 2.5, result.all_arcs, tolerance=0.1):
    print(found.sweep, found.radius_ratio)
```

Dentro non ci sono soglie di significato: "~270° e poco più grande" è come un
disegno mostra un filetto, e quella regola sta nel consumatore.

## Linee di piega / incisione che sai già riconoscere

Se sai come la sorgente segna pieghe o incisioni — per nome, per tratteggio,
per colore o una combinazione — dillo a `topo_dxf.load_dxf` con delle regole, così
assegna il ruolo subito invece di indovinarlo. Le regole si valutano in
ordine, vince la prima che matcha:

```python
doc = topo_dxf.load_dxf("pezzo.dxf", role_rules=[
    *topo.name_rules({"Piega": "bending", "MARK": "engrave"}),
    topo.RoleRule("construction", name_contains="constr", dashed=True),
    topo.RoleRule("bending", dashed=True),
])
```

---

## La pipeline

```
topo_dxf.load_dxf(path)   ──►  Document   (edge + annotazioni + source_meta)
topo.load_segments(segs)  ──►  Document   l'adapter è l'unico codice che legge un formato
                          │
                          ▼
     heal(doc)  ──►  Result      topologia: gap chiusi, giri trovati,
                          │            albero di contenimento outer / inner
                          ▼
  (la lettura di un consumatore)       es. snapbend: tipo di foro, linee di piega, incisioni,
                          │            attaccate a cluster.detected
                          ▼
   split(result)                 ──►  list[Result]     uno per pezzo, senza formato
   topo_dxf.to_dxf(result, doc)  ──►  ezdxf Drawing    render — un Result intero o un pezzo
   to_svg(result)                ──►  stringa SVG      render — per una UI / un report
   to_view_model(result)         ──►  dict (geometria completa) per un renderer esterno
   to_text(result)               ──►  Markdown         sperimentale: una lettura per un modello linguistico (D84)
   save_json / save_xml                                export del modello (metadati)
   inject(result, ...)                                 arricchimento opzionale dai testi
```

Il prodotto è il modello. `to_dxf` non rilegge mai il file sorgente — ogni renderer
(DXF, SVG, view model) disegna dallo stesso modello, quindi mostrano tutti la stessa cosa.

---

## Layer del DXF in uscita

topo non ha layer: l'adapter DXF scrive ogni ruolo sul layer che sceglie il
chiamante (`topo_dxf.to_dxf(layers=..., role_styles=...)`, un nome o una funzione
dell'elemento per ruolo). Quando il chiamante non dice niente, questi sono i
suoi default:

| Layer          | Significato                                 |
|----------------|---------------------------------------------|
| `OuterContour` | profilo esterno del pezzo                   |
| `InnerContour` | contorno chiuso dentro l'outer              |
| `Annotation`   | testi e quote della sorgente (non è un layer di taglio) |
| *nome del ruolo* | geometria con il ruolo di un consumatore (`frame`, `hole`, `bending`, …): un layer col nome del ruolo, grigio — o nome e colore che passa il chiamante |
| `Trash`        | tutto ciò che `topo` non ha saputo classificare — tenuto, mai buttato |

Niente della sorgente si perde in silenzio: la geometria non classificata va in
`Trash`, testi e quote in `Annotation`. I tipi di entità che `topo` non modella
(`HATCH`, `IMAGE`, `TABLE`, …) li segnala `load_dxf` con un warning, non li butta.
Rileggendo un file scritto da topo, `load_dxf` salta i layer `Trash` e
`Annotation` (`skip_layers=topo_dxf.SKIP_LAYERS`; `()` per leggere tutto).

---

## Ispezionare un file reale

Tre livelli, come la pipeline:

```python
import topo, topo_dxf

topo_dxf.inspect_dxf("pezzo.dxf")   # 1 — entità DXF grezze: cosa c'è nel file
topo.inspect_document(doc)          # 2 — edge, primitive, grafo dei nodi: cosa ha capito l'adapter
topo.inspect_result(result)         # 3 — il modello: cluster, outer/inner, quello che un consumatore ha attaccato, trash

topo_dxf.inspect_file("pezzo.dxf", role_rules=topo.name_rules({"Piega": "bending"}))   # tutti e tre, in fila
```

Tutto stampa su stdout. Serve quando qualcosa su un file vero non esce giusto e
devi vedere dove si rompe la catena.

---

## Geometria in ingresso supportata

- **Come contorni strutturali:** `LWPOLYLINE`, `POLYLINE`, `CIRCLE`, `SPLINE` chiusa, `ELLIPSE` chiusa
- **Da ricostruire in contorni:** `LINE`, `ARC`, `SPLINE`/`ELLIPSE` aperte collegate ad altre entità
- **Come annotazioni:** `TEXT`, `MTEXT`, `DIMENSION`, `LEADER`, `MULTILEADER`
- **Blocchi:** gli `INSERT` si esplodono al caricamento, di default
- **Legacy:** i file R12/R13/R14 si aggiornano a R2010
- **DWG:** né `topo` né `ezdxf` leggono il DWG direttamente — passa da
  [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter)
  (gratuito). Installalo e indica a `topo` l'eseguibile con la variabile
  d'ambiente `ODA_PATH` (percorso completo dell'eseguibile), o metti
  `ODAFileConverter` nel `PATH`. Vedi `docs/API.md` → *load_dxf → DWG* per i
  singoli sistemi operativi.

---

## Limiti noti

- **Spline ed ellissi** escono native sui layer di taglio (`to_dxf`) ma
  **discretizzate** in `to_svg` / `to_view_model` (polilinee: usa `to_dxf`
  quando conta la curva esatta).
- **`topo_pdf.load_pdf`** esiste ma è sperimentale — ritorna edge grezzi, non
  un `Document`, quindi non si aggancia ancora a `heal()`.
- **Gap arco/arco oltre la tolleranza** non si chiudono da soli — alza `tolerance`.
- Se non si riesce a formare un contorno esterno chiuso, `result.is_valid` è
  `False`. `to_dxf` / `to_svg` disegnano comunque quello che c'è (tutto su
  `Trash`), così vedi cosa ha capito topo; chi manda l'output a una macchina
  passa `allow_invalid=False` e riceve `ValueError`. `topo.split` solleva sempre:
  un file per pezzo non ha senso senza pezzi.

---

## Documentazione

- **[`docs/API.md`](docs/API.md)** — ogni funzione pubblica: firma, cosa prende,
  cosa ritorna, cosa muta, quando solleva. Con esempi copiabili.
- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** — com'è fatto dentro e
  perché: gli strati, il flusso, "il prodotto è il modello".
- **`MAP.md`** — le decisioni di design, in ordine cronologico.
- **[`docs/LLM.md`](docs/LLM.md)** — riferimento compatto per un'AI che scrive
  codice contro topo: stesso contenuto di `API.md`, meno token possibile.
- **`SCRIPTS.md`** — gli script numerati in `scripts/`, uno per passo della pipeline.

---

## Licenza

Tutti i diritti riservati — vedi [`LICENSE`](LICENSE). Copyright (c) 2026
Federico Sidraschi. Non è open source; per provarlo o usarlo, scrivimi:
smia4punto6@gmail.com.
