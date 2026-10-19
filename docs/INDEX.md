# topo, topo_dxf, topo_pdf — code index

**Generated file — do not edit by hand.** Regenerate with:

```
python scripts/gen_index.py
```

What this is: the lookup table of *what already exists* in the package, down to internal helpers. `docs/API.md` documents the public surface (`topo, topo_dxf, topo_pdf.<name>`) with full cards; this file lists every module-level function and class so nothing gets rewritten because it was not found. Signatures and docstring lines come straight from the source, so they cannot drift.

`79` modules · `441` module-level functions · `58` classes · `14747` lines of code.

Sections: [Lookup](#lookup) · [Duplicate names](#duplicate-names) · [Dependency rule](#dependency-rule) · [By module](#by-module) · [Internal dependencies](#internal-dependencies)

---

## Lookup

Every module-level name in the package, alphabetically. **Search here before writing a new helper.**

| name | kind | location | what |
|---|---|---|---|
| `_adaptive_polyline` | func | `topo/core/primitives/segments.py:316` | Discretizza una curva parametrica valutata da `evaluate(t) -> Point` fra |
| `_add` | func | `topo/tools/tabs.py:58` |  |
| `_add_ellipse` | func | `topo_dxf/exporter.py:152` | Materializza una EllipseSeg come ELLIPSE nativa — mai una spline: topo |
| `_add_spline` | func | `topo_dxf/exporter.py:124` | Materializza una BSplineSeg come SPLINE nativa, ricostruita dalla primitiva |
| `AddSegment` | class | `topo/core/healing/gap_solver.py:84` | Istruzione: aggiungi un segmento retto tra pt_a e pt_b. |
| `anchor_texts` | func | `topo/tools/anchor.py:30` | Assegna ``cluster_ref`` a ogni testo di ``result.texts``. |
| `_angle_diff` | func | `topo/core/geometry/shape.py:212` | Differenza fra due direzioni modulo 180, in [0, 90]. |
| `angle_from_start` | func | `topo/core/primitives/segments.py:102` | Angolo, in [0, 2π), da percorrere partendo da `start_angle` nel verso |
| `_angle_of` | func | `topo/core/primitives/trim.py:93` | Angolo (o parametro dell'ellisse) di `pt` visto dal centro della curva. |
| `_angular` | func | `topo/core/primitives/trim.py:104` |  |
| `_angular_deviation` | func | `topo/core/topology/graph.py:378` |  |
| `_angular_sweep` | func | `topo/core/primitives/segments.py:83` | Angolo spazzato in radianti, sempre positivo, percorrendo da `start` a |
| `apply_gap_fixes` | func | `topo/core/healing/gap_solver.py:340` | Applica i GapFix restituendo una NUOVA lista di Edge — `edges` non viene mutata. |
| `_apply_role_style` | func | `topo_dxf/writer.py:358` | Un `RoleStyle` (D37, D128) sul layer: colore in true color (l'ACI non ha |
| `approximate_bspline` | func | `topo/core/geometry/points.py:324` | La B-spline di grado `degree` con meno punti di controllo che passa per il |
| `_Arc` | class | `topo/core/healing/outer_scan.py:104` |  |
| `_arc_chains` | func | `topo/core/healing/normalizer.py:363` | Catene angolari di un gruppo sullo stesso cerchio. Se l'ultima catena |
| `_arc_key` | func | `topo/core/healing/normalizer.py:336` | Chiave del cerchio (centro+raggio) a precisione fissa — v. `_line_key`. |
| `_arc_point` | func | `topo/core/healing/outer_scan.py:131` |  |
| `_arc_s` | func | `topo/core/topology/noding.py:132` |  |
| `arc_seg_to_bulge` | func | `topo_dxf/exporter.py:85` |  |
| `_arc_through_ends` | func | `topo/core/primitives/fitting.py:111` | L'arco che passa esattamente per il primo e l'ultimo punto (e per quello a |
| `ArcAround` | class | `topo/core/geometry/shape.py:269` | Un arco concentrico a un cerchio e più grande di lui. |
| `arcs_around` | func | `topo/core/geometry/shape.py:282` | Gli archi di `arcs` col centro entro `tolerance` da `center` e raggio |
| `ArcSeg` | class | `topo/core/primitives/segments.py:129` |  |
| `are_collinear` | func | `topo/core/geometry/lines.py:45` | I tratti `a` e `b` stanno sulla stessa retta infinita: direzioni uguali |
| `_arrival_direction` | func | `topo/core/topology/graph.py:369` |  |
| `_assign` | func | `topo/tools/anchor.py:171` |  |
| `_assign` | func | `topo/tools/split.py:88` | id(cluster) → gli elementi che gli appartengono. Con `covering` vince la |
| `assign_cluster_refs` | func | `topo/core/healing/hierarchy.py:218` | Scrive su ogni curva di `curves` (`result.loose`) `cluster_ref`: l'indice |
| `_assign_loose` | func | `topo/tools/split.py:111` | id(cluster) → le curve sciolte che gli vanno, nell'ordine di |
| `_at` | func | `topo/core/geometry/regions.py:87` |  |
| `axis_aligned_share` | func | `topo/core/geometry/axis.py:238` | Frazione della lunghezza dei `LineSeg` di `segments` orizzontale o |
| `axis_lines` | func | `topo/core/geometry/axis.py:87` | (orizzontali, verticali): i tratti che si scostano dall'asse al più di `eps`; gli altri non compaiono. |
| `AxisLine` | class | `topo/core/geometry/axis.py:73` | Un tratto orizzontale o verticale. |
| `_bbox_center` | func | `topo_dxf/text_extractor.py:497` |  |
| `_bbox_of` | func | `topo/io/view_model.py:121` |  |
| `_bridge_at` | func | `topo/tools/tabs.py:303` | Una linguetta nel punto `anchor`, scelto dal chiamante. Si proietta sul |
| `bridge_nested_tabs` | func | `topo/tools/tabs.py:408` | Cammina `cluster.inners` (che porta `depth`/`parent` per ogni contorno, |
| `bridge_parent_tabs` | func | `topo/tools/tabs.py:351` | Collega le isole di UN genitore (`island_anchors`: coppie isola, punti) |
| `bridge_tabs` | func | `topo/tools/tabs.py:101` | Costruisce UNA linguetta fra `child_points` (contorno chiuso, il figlio |
| `bridged_runs` | func | `topo/core/geometry/lines.py:106` | File di due o più tratti sulla stessa retta in cui lo spazio fra un tratto |
| `BridgeTab` | class | `topo/tools/tabs.py:87` | Risultato di un singolo ponte. `*_cut_{a,b}` sono `(punto, indice_lato)` |
| `_bspline_basis_row` | func | `topo/core/geometry/points.py:113` | Le n+1 funzioni di base N_i,p(u) (Cox-de Boor, Piegl & Tiller A2.2). |
| `_bspline_find_span` | func | `topo/core/primitives/segments.py:258` | Indice `i` tale che `knots[i] <= t < knots[i+1]` (ricerca binaria, "The |
| `BSplineSeg` | class | `topo/core/primitives/segments.py:337` | B-spline (NURBS se `weights` è impostato): grado, punti di controllo, |
| `build_hierarchy` | func | `topo/core/healing/steps.py:373` | Albero di contenimento sui ClosedCurve: ogni radice è un Cluster |
| `build_metadata` | func | `topo/io/exporter.py:24` | Costruisce il dict dei metadati per un Cluster |
| `build_node_graph` | func | `topo/core/topology/graph.py:301` | Costruisce il Graph da list[Edge]. |
| `build_polygon` | func | `topo/core/primitives/polygon_builder.py:19` | Costruisce un Polygon shapely da una lista di primitive geometriche. |
| `_build_tree` | func | `topo/core/healing/hierarchy.py:79` |  |
| `_chain` | func | `topo/core/geometry/regions.py:309` | Pezzi orientati incatenati testa-coda in anelli chiusi. |
| `_chain` | func | `topo/core/healing/normalizer.py:234` | Ordina per `lo` e incatena gli span che si toccano o si sovrappongono: |
| `chord_angle_deg` | func | `topo/core/geometry/measure.py:135` | Angolo (gradi, 0-180°) della corda da `a` a `b`. Modulo 180 perché una |
| `_chord_params` | func | `topo/core/geometry/points.py:286` |  |
| `circle` | func | `topo/core/geometry/build.py:52` | Il cerchio di raggio `radius` in `center`. |
| `_circle` | func | `topo/core/geometry/shape.py:118` |  |
| `_circle_as_arc` | func | `topo/core/topology/noding.py:162` | Un cerchio come arco di 360° da `start_angle`: stessa matematica degli archi. |
| `_circle_circle_intersections` | func | `topo/core/geometry/intersections.py:71` | Intersezioni tra due circonferenze. Restituisce 0, 1 o 2 punti. |
| `_circle_line_intersections` | func | `topo/core/geometry/intersections.py:40` | Intersezioni tra la circonferenza (cx, cy, r) e la retta infinita (p1, p2). |
| `circle_through` | func | `topo/core/geometry/points.py:271` | Il cerchio per tre punti: `(center, radius)`, None se sono allineati. |
| `CircleSeg` | class | `topo/core/primitives/segments.py:541` | Cerchio geometrico puro. |
| `circular_geometry` | func | `topo/core/geometry/measure.py:157` | (diameter, center) se il contorno è ~circolare, altrimenti (None, None). |
| `_clamp` | func | `topo/core/primitives/trim.py:86` | Un punto appena oltre un estremo (entro tolleranza) sta su quell'estremo. |
| `clean_mtext` | func | `topo_dxf/mtext.py:18` | Testo semplice da una stringa MTEXT grezza: rimuove i codici di |
| `close_free_gaps` | func | `topo/core/healing/steps.py:134` | Chiude i gap fra estremi liberi entro `tolerance` col gap solver |
| `close_near_full_arcs` | func | `topo/core/healing/steps.py:97` | Un ArcSeg coi due capi liberi diventa CircleSeg (stesso centro e raggio) |
| `_close_self_loop` | func | `topo/core/topology/graph.py:285` | ArcSeg il cui sviluppo (raggio*sweep) supera epsilon -> CircleSeg (loop degenere vero). Altrimenti `None` (sl… |
| `ClosedCurve` | class | `topo/model/curve.py:48` | Curva chiusa: ha un polygon e una lista di segmenti. |
| `closest_point_on_track` | func | `topo/core/geometry/measure.py:76` | Il punto della traccia `pts` più vicino a `point`: `nearest_point` sui suoi lati. |
| `_closest_to` | func | `topo/core/geometry/intersections.py:95` | Restituisce il punto più vicino a ref tra i candidati. |
| `_cluster` | func | `topo/core/island.py:292` |  |
| `Cluster` | class | `topo/model/cluster.py:15` |  |
| `cluster_passes_min_area` | func | `topo/tools/split.py:83` | True se la parte supera la soglia di area minima (min_area <= 0 = nessun filtro). |
| `cluster_points` | func | `topo/core/topology/graph.py:222` | Raggruppa punti 2D entro `epsilon` e restituisce {punto -> rappresentante}. |
| `cluster_values` | func | `topo/core/geometry/axis.py:55` | I valori ordinati, tenendo per ogni gruppo il più piccolo: un valore entro |
| `_collect_inners` | func | `topo/core/healing/hierarchy.py:113` | Appiattisce l'albero di contenimento in `cluster.inners` (ogni discendente |
| `CollinearRun` | class | `topo/core/geometry/lines.py:94` | Tratti sulla stessa retta, in fila lungo di essa. |
| `_color` | func | `topo/io/view_model.py:29` | Hex CSS di un ruolo: la palette di topo con sopra la mappa del |
| `color_for_role` | func | `topo_dxf/layers.py:79` | Il colore della palette di topo per `role` (D128) come indice ACI: |
| `_color_rgb` | func | `topo/model/role_rule.py:123` | (r, g, b) da una tupla, da "#rrggbb" o da un nome di base ("cyan"). |
| `_color_rgb` | func | `topo_dxf/adapter.py:62` | Il colore effettivo in RGB: il true color se c'è, altrimenti l'indice |
| `compute_gap_fixes` | func | `topo/core/healing/gap_solver.py:174` | Calcola i GapFix fra gli endpoint liberi entro tolerance. I due capi |
| `concentric_groups` | func | `topo/core/geometry/shape.py:246` | Partizione dei contorni circolari di `items` per centro: ogni cerchio sta |
| `ConcentricGroup` | class | `topo/core/geometry/shape.py:229` | Contorni circolari con lo stesso centro, dal raggio minore al maggiore. |
| `_configure_odafc` | func | `topo_dxf/loader.py:107` | Punta l'addon `odafc` all'eseguibile ODA File Converter. |
| `_continues` | func | `topo/core/geometry/shape.py:329` | `seg` prosegue `prev` sulla stessa curva, nello stesso verso? |
| `_contour` | func | `topo/core/island.py:387` | Il poligono resta quello dei pezzi della rete piana; i segmenti sono |
| `Contour` | class | `topo/model/contour.py:36` |  |
| `_contour_entry` | func | `topo/io/view_model.py:53` |  |
| `contour_minus` | func | `topo/core/geometry/regions.py:326` | L'anello `contour` meno la regione chiusa `region` (tutti e due anelli di |
| `_contour_role` | func | `topo_dxf/writer.py:295` | Il ruolo di contorno nel grafo: outer/inner se lo porta, `default` se |
| `contour_shape` | func | `topo/core/geometry/shape.py:90` | Forma di un contorno chiuso (`Contour`, o qualunque oggetto con |
| `ContourPoint` | class | `topo/core/geometry/regions.py:216` | Dove cade un punto su un contorno. |
| `ContourRole` | class | `topo/model/role.py:44` | I tre ruoli che il motore topologico conosce. **Non esaustivo** — un |
| `ContourShape` | class | `topo/core/geometry/shape.py:61` | kind:   un `ShapeKind` (circle \| ellipse \| stadium \| rectangle \| polygon \| other) |
| `_covered_at` | func | `topo/core/geometry/axis.py:100` |  |
| `covered_rectangles` | func | `topo/core/geometry/axis.py:144` | I rettangoli allineati agli assi con ogni lato coperto almeno per |
| `CoveredRectangle` | class | `topo/core/geometry/axis.py:109` | Un rettangolo allineato agli assi i cui quattro lati sono coperti da tratti. |
| `_crossing` | func | `topo/core/primitives/fitting.py:155` |  |
| `_crossing_warnings` | func | `topo/core/heal.py:209` | Lati di contorno che si attraversano senza un nodo (D132): il disegno è |
| `_crossings` | func | `topo/core/topology/noding.py:184` | Incroci reali (non sul prolungamento) fra `seg` e un cutter. |
| `_cumulative_lengths_closed` | func | `topo/tools/tabs.py:161` | `cum[i]` = distanza cumulata da `points[0]` a `points[i]` (lato i-1->i). |
| `Curve` | class | `topo/model/curve.py:38` | Radice della gerarchia. Porta solo identità semantica e traceability. |
| `cut_by` | func | `topo/core/geometry/regions.py:284` | I pezzi di `segment` fuori (`keep="outside"`) o dentro (`keep="inside"`) |
| `_cutters` | func | `topo/core/topology/noding.py:172` |  |
| `dangling_splines` | func | `topo/core/healing/steps.py:149` | BSplineSeg aperte con almeno un estremo non collegato a nient'altro. |
| `dash_line` | func | `topo/core/geometry/lines.py:143` | Il segmento `start`→`end` ridotto a tratti: uno lungo `head` che parte da |
| `deduplicate` | func | `topo_dxf/sanitize.py:243` | Shortcut: estrae chiavi, trova duplicati, li elimina. |
| `delete_entities` | func | `topo_dxf/sanitize.py:210` | Elimina le entità dal msp in-place. |
| `_describe_dxf_entity` | func | `topo_dxf/inspect.py:77` |  |
| `_describe_segment` | func | `topo/inspect.py:112` |  |
| `DetectedFeature` | class | `topo/model/detected.py:23` | Contratto minimo di un elemento attaccato a `DetectedFeatures`: la |
| `DetectedFeatures` | class | `topo/model/detected.py:34` | Contenitore aperto per nome: ogni consumatore scrive sotto il nome che |
| `_dict_to_xml` | func | `topo/io/exporter.py:231` | Converte ricorsivamente un dict in sotto-elementi XML. |
| `_dimension_anchor` | func | `topo_dxf/text_extractor.py:129` | Def-point di una DIMENSION. |
| `_dimension_measurement` | func | `topo_dxf/text_extractor.py:560` |  |
| `_dimension_override` | func | `topo_dxf/text_extractor.py:277` | Override esplicito del testo quota, o None se la quota mostra la misura. |
| `_dimension_semantics` | func | `topo_dxf/text_extractor.py:259` | (dim_type, valore misurato) di una DIMENSION. |
| `_dimension_text` | func | `topo_dxf/text_extractor.py:541` | Testo visualizzato della quota, quando l'immagine non è espandibile. |
| `_dimension_text_of` | func | `topo_dxf/text_extractor.py:193` |  |
| `_discretize_closed` | func | `topo/tools/tabs.py:227` | Punti grezzi chiusi di un `Contour` (senza il punto di chiusura duplicato). |
| `_distance` | func | `topo/core/geometry/intersections.py:36` |  |
| `Document` | class | `topo/model/document.py:37` | Documento di dominio prodotto da load_dxf() / load_svg() / load_pdf(). |
| `document_from_msp` | func | `topo_dxf/loader.py:349` | Costruisce un Document da un modelspace ezdxf già aperto. |
| `_dot` | func | `topo/tools/tabs.py:66` |  |
| `douglas_peucker` | func | `topo/core/geometry/points.py:174` | Indici dei vertici che Douglas-Peucker tiene sulla polilinea aperta |
| `_drop_boundary_duplicates` | func | `topo/core/island.py:218` | Scarta un giro chiuso il cui intero bordo sta entro `band` dal bordo di |
| `drop_duplicate_points` | func | `topo/core/geometry/points.py:33` | Rimuove punti consecutivi coincidenti entro `tolerance`. |
| `_drop_redundant_meets` | func | `topo/core/island.py:262` | Scarta un fix "incontro" (due `MoveEndpoint` sullo stesso punto, la |
| `dxf_pattern` | func | `topo_dxf/exporter.py:49` | Il tratto di topo (segni con segno) nel pattern della tabella DXF, che |
| `DxfAdapter` | class | `topo_dxf/adapter.py:222` | Adapter DXF che traduce entità DXF in Edge del dominio Topo. |
| `DxfEntityDispatcher` | class | `topo_dxf/parser.py:20` | Centralizza il routing per tipo di entità DXF. |
| `DxfTextExtractor` | class | `topo_dxf/text_extractor.py:43` | Traduce le entità di testo di un msp in list[Text]. |
| `Edge` | class | `topo/core/topology/edge.py:31` | Layer intermedio tra l'entità sorgente grezza (di qualsiasi formato) e il |
| `_edge_coords` | func | `topo/core/topology/graph.py:355` |  |
| `edge_geometry` | func | `topo/core/topology/noding.py:291` | L'edge come geometria shapely: LineString discretizzata, Point se degenere. |
| `edge_styles_from_loop` | func | `topo/core/topology/loop_finder.py:187` | Stili grezzi (linetype/colore) di un loop, allineati 1:1 con |
| `edges_to_open_curves` | func | `topo/core/topology/loop_finder.py:220` | Converte gli Edge non assorbiti da un loop strutturale in OpenCurve. |
| `EdgeStyle` | class | `topo/model/style.py:45` | Campi (tutti opzionali: un `EdgeStyle()` vuoto è "la sorgente non lo dice"): |
| `_elements` | func | `topo/tools/anchor.py:143` | (percorso, geometria shapely, è chiuso) per contorni e feature di ogni cluster. |
| `ellipse` | func | `topo/core/geometry/build.py:57` | L'ellisse di assi `length` × `width` centrata in `center`, asse lungo a |
| `_ellipse` | func | `topo/core/geometry/shape.py:133` | Pezzi della stessa ellisse (centro, semiassi, direzione dell'asse) per un giro intero. |
| `EllipseSeg` | class | `topo/core/primitives/segments.py:587` | Ellisse (o arco ellittico) geometrico puro — stessa parametrizzazione del |
| `_emit` | func | `topo_dxf/loader.py:99` | Aggiunge `msg` al canale warnings; lo stampa solo se verbose. |
| `_emit_rendered` | func | `topo_dxf/writer.py:205` | Ri-materializza l'immagine appiattita (DIMENSION / LEADER di un DXF). I testi in |
| `_emit_string` | func | `topo_dxf/writer.py:179` |  |
| `_emit_text` | func | `topo_dxf/writer.py:168` | Con un'immagine (`rendered`: quote e richiami della sorgente) si |
| `enclosing` | func | `topo/core/geometry/regions.py:378` | Per ogni traccia (una sequenza di punti), l'indice in `outers` del |
| `_endpoint_meta` | func | `topo/core/healing/gap_solver.py:253` | Dati che il solver usa per calcolare l'intersezione, per tipo di segmento. |
| `_ends` | func | `topo/core/geometry/lines.py:27` | I due capi di un tratto: `LineString` (primo e ultimo punto) o `(start, end)`. |
| `_ends` | func | `topo/core/geometry/regions.py:112` |  |
| `ensure_linetype` | func | `topo_dxf/exporter.py:23` | Garantisce che il linetype `name` esista in `doc` e ne ritorna il nome; |
| `_entity_style` | func | `topo_dxf/adapter.py:73` | Cattura l'aspetto EFFETTIVO (linetype/colore) di un'entità DXF in un |
| `even_spacing` | func | `topo/core/geometry/points.py:142` | I punti con altri aggiunti dove due vicini distano più del passo mediano. |
| `_exact_parts` | func | `topo/core/geometry/intersections.py:146` | Retta, arco, cerchio restano se stessi; spline ed ellisse diventano |
| `_explode_inserts` | func | `topo_dxf/sanitize.py:106` | Esplode tutti gli INSERT (blocchi) nel modelspace in entità primitive. |
| `_extent` | func | `topo/core/healing/outer_scan.py:135` | (min, max) del pezzo lungo la coordinata `a` (0 = x, 1 = y). |
| `_extract_content` | func | `topo_dxf/text_extractor.py:153` | Testo pulito dell'entità, stringa vuota se non ne ha. |
| `extract_drawings_from_page` | func | `topo_pdf/extractor_adapter.py:23` | Estrae i disegni vettoriali dalla pagina PDF e normalizza l'output. |
| `extract_keyed_entities` | func | `topo_dxf/sanitize.py:201` | Produce la lista (key, entity) per tutte le entità del msp. |
| `_f` | func | `topo_dxf/text_extractor.py:570` |  |
| `face_segments` | func | `topo/core/topology/rim.py:29` | (segments, styles) lungo il bordo esterno di `polygon`, in senso |
| `_faced` | func | `topo/core/island.py:332` | (giri con almeno una faccia, pezzi dei loro edge fuori da ogni faccia): |
| `_faces_union_loop` | func | `topo/core/topology/outer_face.py:176` | (loop, segments, styles, polygon) sul bordo dell'unione delle facce |
| `_fallback_anchor` | func | `topo_dxf/text_extractor.py:137` | Cerca un qualsiasi attributo-punto usabile. |
| `_feature_entries` | func | `topo/io/view_model.py:61` | Un elemento dell'overlay (MAP.md D90) → una voce per contorno: ruolo, |
| `feature_role` | func | `topo/model/role.py:91` | Il ruolo con cui si disegna un contorno di un elemento dell'overlay (D90): |
| `_features` | func | `topo/io/view_model.py:91` | `cluster.detected` per nome → lista di voci disegnabili. |
| `_find_duplicates` | func | `topo_dxf/sanitize.py:216` | Restituisce i ref delle entità duplicate (seconda occorrenza in poi). |
| `find_joining_edges` | func | `topo/core/healing/steps.py:169` | Gli Edge fra `candidate_ids` (di solito i non-contorno) che uniscono due |
| `find_loops` | func | `topo/core/healing/steps.py:243` | La scala di heal() per chiudere i giri, esclusi `non_contour_ids`: |
| `find_non_contour_edges` | func | `topo/core/healing/steps.py:158` | id(edge) degli Edge che non chiudono un contorno (catene fra due nodi di |
| `_first_coord` | func | `topo/core/topology/graph.py:362` |  |
| `_first_point` | func | `topo/io/text.py:152` | Un punto che sta sul segmento, per dire in quale pezzo cade. |
| `_first_step` | func | `topo/core/topology/outer_face.py:133` | L'edge che contiene il punto più a sinistra del componente, percorso |
| `fit_circle_kasa` | func | `topo/core/geometry/points.py:47` | Fit algebrico (Kasa) ai minimi quadrati di un cerchio su `points`: minimizza |
| `_fit_curve` | func | `topo/core/primitives/fitting.py:132` | Un pezzo curvo: arco per gli estremi se basta (e `arcs`), altrimenti spline entro `tolerance` per gli estremi. |
| `_flatten_virtual` | func | `topo_dxf/text_extractor.py:471` | Espande `virtual_entities()` ricorsivamente sugli INSERT (frecce a blocco). |
| `flatten_z` | func | `topo_dxf/sanitize.py:29` | Porta a 0 tutte le coordinate Z != 0 per LINE, ARC, CIRCLE, |
| `_flattened_points` | func | `topo_dxf/text_extractor.py:509` | Punti di un ARC o CIRCLE appiattito alla sagitta `_ARC_SAGITTA`. |
| `_fmt` | func | `topo/io/svg.py:24` | Lista di [x, y] → stringa 'x0,y0 x1,y1 …' per points= di polyline/polygon. |
| `free_endpoints_from_edges` | func | `topo/core/healing/gap_solver.py:273` | Estrae gli endpoint liberi (grado < 2 nel grafo) dagli Edge. |
| `free_ends` | func | `topo/core/healing/steps.py:197` | (estremo, distanza dal nodo più vicino) per ogni estremo che nessun altro |
| `_full_arc` | func | `topo/core/geometry/regions.py:178` | Un cerchio come arco di 360°: un arco si inverte, un CircleSeg no (è |
| `_gap_endpoints` | func | `topo/core/healing/gap_solver.py:302` | GapEndpoint per gli estremi di LINE / ARC / SPLINE il cui nodo (arrotondato) |
| `gap_endpoints_at_nodes` | func | `topo/core/healing/gap_solver.py:285` | GapEndpoint per gli endpoint che cadono su uno dei `nodes` — tuple di |
| `GapEndpoint` | class | `topo/core/healing/gap_solver.py:46` | Endpoint libero nel grafo topologico. |
| `_generic` | func | `topo/core/geometry/shape.py:193` |  |
| `GeometryReader` | class | `topo/core/geometry_input.py:46` | Traduce descrizioni geometriche pure (dict) in Edge del dominio topo. |
| `_get_solver` | func | `topo/core/healing/gap_solver.py:162` |  |
| `__getattr__` | func | `topo/model/__init__.py:54` |  |
| `_graph` | func | `topo/core/healing/steps.py:390` |  |
| `Graph` | class | `topo/core/topology/graph.py:59` | Grafo topologico interrogabile. |
| `group_collinear_lines` | func | `topo/core/geometry/lines.py:61` | Tratti raggruppati per retta: [[L1, L2], [L3], ...]. Ogni gruppo prende la |
| `_h` | func | `topo/inspect.py:36` |  |
| `_header` | func | `topo_dxf/inspect.py:28` |  |
| `heal` | func | `topo/core/heal.py:43` | Legge `doc` dall'interno: un Cluster per contorno esterno chiuso, |
| `HierarchyBuilder` | class | `topo/core/healing/hierarchy.py:150` |  |
| `inject` | func | `topo/tools/inject.py:39` | Arricchisce i Cluster con i dati estratti da un `data_injector` esterno. |
| `_inners` | func | `topo/core/island.py:300` | Un Contour inner per faccia di ogni giro chiuso; un giro senza |
| `_insert_to_degree` | func | `topo/core/primitives/trim.py:165` | Inserisce `t` nel vettore dei nodi finché compare `p` volte (agli |
| `inspect_document` | func | `topo/inspect.py:56` | Stampa un Document prodotto da un adapter (`topo_dxf.load_dxf`, …) o da |
| `inspect_dxf` | func | `topo_dxf/inspect.py:37` | Apre un DXF/DWG con ezdxf e stampa cosa contiene, senza toccare topo. |
| `inspect_file` | func | `topo_dxf/inspect.py:114` | Apre un file e stampa i tre livelli in fila: |
| `inspect_result` | func | `topo/inspect.py:141` | Stampa un Result dopo heal(): il prodotto vero di topo. |
| `interior_crossings` | func | `topo/core/topology/noding.py:98` | I punti dove due edge si attraversano senza che nessuno dei due finisca |
| `interpolate_bspline` | func | `topo/core/geometry/points.py:79` | B-spline di grado `degree` che passa per tutti i `points` (interpolazione |
| `intersections` | func | `topo/core/geometry/intersections.py:184` | I punti dove due primitive si incontrano: incroci e tocchi, capi compresi. |
| `_intersections` | func | `topo/core/healing/outer_scan.py:150` | Punti del pezzo con coordinata `a` == level. |
| `interval_coverage` | func | `topo/core/geometry/axis.py:47` | Frazione di [lo, hi] coperta dall'unione degli intervalli. |
| `_is_near_full_arc` | func | `topo/core/healing/steps.py:119` |  |
| `is_structural_role` | func | `topo/model/role.py:79` | True se ``role`` è OUTER o INNER per il motore (vedi ``STRUCTURAL_ROLES``). |
| `is_tab_island` | func | `topo/tools/tabs.py:246` | `contour` è un'isola da collegare al genitore diretto: profondità pari |
| `Island` | class | `topo/core/healing/islands.py:36` | Gruppo di Edge vicini, con la bbox che li contiene tutti. |
| `island` | func | `topo/core/island.py:76` | Legge `doc` per isole. Un Cluster per ogni contorno esterno che non |
| `IslandReading` | class | `topo/core/island.py:58` | Cosa island() ha deciso su un'isola, pezzo per pezzo. |
| `_item_geometry` | func | `topo/tools/anchor.py:158` |  |
| `items_inside` | func | `topo/core/geometry/axis.py:221` | I tratti con entrambi i capi dentro `bounds` allargato di `margin`, nell'ordine dato. |
| `_join_seam` | func | `topo/core/primitives/fitting.py:220` | Un contorno senza spigoli si apre in un punto qualunque: se il primo e |
| `_joined` | func | `topo/core/geometry/shape.py:348` |  |
| `_key_for` | func | `topo_dxf/sanitize.py:154` | Restituisce una chiave hashable che identifica univocamente |
| `labeled_curves` | func | `topo/core/healing/steps.py:351` | Gli Edge messi da parte da split_labeled() come curve col loro ruolo |
| `_largest_loop` | func | `topo/core/topology/outer_face.py:202` | (loop, segments, styles, polygon) del giro di area massima. |
| `_Layers` | class | `topo_dxf/writer.py:302` | I layer di un documento in scrittura (D128): il nome viene dalla scelta |
| `_leader_text` | func | `topo_dxf/text_extractor.py:378` |  |
| `_leader_vertices` | func | `topo_dxf/text_extractor.py:415` |  |
| `_least_squares` | func | `topo/core/geometry/points.py:299` | Spline di grado `degree` con `count` punti di controllo ai minimi quadrati |
| `_leaving_angle` | func | `topo/core/topology/outer_face.py:155` | Direzione con cui `edge` lascia `node`, letta a DIRECTION_SAMPLE (o a |
| `_length` | func | `topo/core/geometry/regions.py:104` |  |
| `_length` | func | `topo/core/geometry/shape.py:208` |  |
| `_length` | func | `topo/core/primitives/fitting.py:164` |  |
| `length_inside` | func | `topo/core/geometry/measure.py:110` | Quanta parte di `segment` (qualunque primitiva nativa) sta dentro il |
| `_Line` | class | `topo/core/healing/outer_scan.py:97` |  |
| `_line_fit` | func | `topo/core/primitives/fitting.py:144` | Retta ai minimi quadrati sui punti: (punto, direzione unitaria). |
| `_line_intersection` | func | `topo/core/geometry/intersections.py:22` | Intersezione tra retta (p1,p2) e retta (p3,p4). None se parallele. |
| `_line_key` | func | `topo/core/healing/normalizer.py:62` | Chiave della retta infinita per p1->p2: (angolo canonico, offset). |
| `_line_spans` | func | `topo/core/healing/normalizer.py:183` | Span lungo la retta comune: `t` è la proiezione sulla direzione del |
| `_line_turn` | func | `topo/core/primitives/fitting.py:168` | Di quanti gradi svolta chi passa dalla linea `a` alla linea `b`. |
| `_lines` | func | `topo/core/island.py:369` |  |
| `LineSeg` | class | `topo/core/primitives/segments.py:44` |  |
| `load_dxf` | func | `topo_dxf/loader.py:219` | Apre un documento DXF o DWG e lo traduce in un Document. |
| `load_geometry` | func | `topo/core/geometry_input.py:161` | Costruisce un Document da una lista di descrizioni geometriche pure — |
| `load_pdf` | func | `topo_pdf/loader.py:22` | Apre un documento PDF, estrae le geometrie vettoriali da tutte le pagine, |
| `load_segments` | func | `topo/core/geometry_input.py:206` | Un Document da segmenti di topo (`LineSeg`, `ArcSeg`, `CircleSeg`, |
| `_local` | func | `topo/tools/split.py:127` | Copie di `items` con `cluster_ref` riferito al Result di una parte sola. |
| `local_gap_fixes` | func | `topo/core/healing/gap_solver.py:229` | Solo i fix che non spostano un estremo più di `max_move`: due rette quasi |
| `longest_segment` | func | `topo/core/geometry/measure.py:122` | `(segment, length)` del segmento più lungo in `segments` — `(None, 0.0)` |
| `longest_structural_segment` | func | `topo/tools/rotate.py:89` | `(segment, length, angle_deg)` del segmento più lungo fra |
| `_loop_faces` | func | `topo/core/island.py:307` | (segmenti, stili, poligono) per ogni faccia di un giro chiuso: una se |
| `loop_geometry` | func | `topo/core/topology/loop_finder.py:206` | (segmenti, stili, poligono) di un loop; None se i segmenti non chiudono |
| `loop_to_closed_curve` | func | `topo/core/healing/hierarchy.py:22` |  |
| `LoopFinder` | class | `topo/core/topology/loop_finder.py:28` |  |
| `loops_to_curves` | func | `topo/core/healing/steps.py:298` | Un ClosedCurve per loop, col ruolo del primo edge; senza poligono valido, niente. |
| `LoopSearch` | class | `topo/core/healing/steps.py:41` | Come find_loops() ha chiuso (o non chiuso) i giri, gradino per gradino. |
| `_loose_ends_warnings` | func | `topo/core/heal.py:190` | Quello che resta aperto anche quando qualcosa si chiude (D111): gli |
| `_loose_entry` | func | `topo/io/view_model.py:101` |  |
| `_make_inner` | func | `topo/core/healing/hierarchy.py:92` |  |
| `_make_polygon` | func | `topo/core/primitives/polygon_builder.py:48` |  |
| `map_sanitized_item_to_edge` | func | `topo_pdf/graph_adapter.py:12` |  |
| `_measured_points` | func | `topo_dxf/text_extractor.py:302` | I punti sulla geometria fra cui la quota misura, dai def-point: |
| `measured_references` | func | `topo/tools/anchor.py:97` | Gli elementi su cui cadono i ``measured_points`` di ``text``, come |
| `_meet` | func | `topo/core/geometry/intersections.py:171` |  |
| `_meet_or_bridge` | func | `topo/core/healing/gap_solver.py:262` | Se le due geometrie si incontrano in `ix`, porta lì entrambi gli estremi; |
| `merge_cocircular_overlaps` | func | `topo/core/healing/normalizer.py:345` | `merge_collinear_overlaps` per gli ArcSeg: fonde gruppi co-circolari |
| `merge_collinear_overlaps` | func | `topo/core/healing/normalizer.py:89` | Fonde gruppi di LineSeg collineari (stessa retta infinita, `_line_key`) |
| `merge_intervals` | func | `topo/core/geometry/axis.py:36` | Unisce gli intervalli che si sovrappongono o distano al più `tolerance`, in ordine. |
| `_merge_on_carrier` | func | `topo/core/healing/normalizer.py:254` | Raggruppa per supporto (`key`) gli edge di `segment_type` con ruolo |
| `merge_runs` | func | `topo/core/geometry/shape.py:297` | Segmenti consecutivi di un giro chiuso sulla stessa circonferenza (o |
| `_merge_texts` | func | `topo_dxf/loader.py:68` | Aggiunge a `base` i testi di `extra` non già presenti (per firma). |
| `_merged_arc` | func | `topo/core/healing/normalizer.py:389` | Il fuso di una catena cocircolare: un arco, o un cerchio se chiude il |
| `_merged_line` | func | `topo/core/healing/normalizer.py:207` | Il fuso di una catena collineare: nodi arrotondati, segmento a piena |
| `_middle` | func | `topo/core/geometry/regions.py:116` |  |
| `_mleader_anchor` | func | `topo_dxf/text_extractor.py:117` | Primo vertice della direttrice di un MULTILEADER. |
| `mleader_text` | func | `topo_dxf/mtext.py:37` | Testo grezzo di un MULTILEADER (prima della pulizia), None se assente. |
| `_moved_segment` | func | `topo/core/healing/gap_solver.py:322` | Nuovo segmento con l'endpoint `role` spostato su `new_pt`. None se non gestito. |
| `MoveEndpoint` | class | `topo/core/healing/gap_solver.py:73` | Istruzione: sposta l'endpoint role di ref al punto new_pt. |
| `name_rules` | func | `topo/model/role_rule.py:114` | Scorciatoia: {nome: ruolo} → una RoleRule(name=...) per voce. |
| `nearest_point` | func | `topo/core/geometry/regions.py:263` | Il punto delle primitive `segments` più vicino a `point`: anche a metà di |
| `_nearest_within` | func | `topo/tools/anchor.py:180` | L'indice della parte più vicina a ``probe``, se entro ``snap_distance`` (> 0). |
| `NestedBridgeResult` | class | `topo/tools/tabs.py:218` | Risultato per UNA coppia isola/genitore-diretto trovata nella gerarchia. |
| `NodedEdges` | class | `topo/core/topology/noding.py:51` | La rete piana: i pezzi, e per ognuno l'Edge da cui viene. |
| `non_contour_candidates` | func | `topo/tools/non_contour.py:41` | Edge di `doc.edges` che il criterio topologico di `heal()` escluderebbe dal |
| `NonContourEdgeDetector` | class | `topo/core/topology/non_contour_edges.py:45` |  |
| `_normalize` | func | `topo/core/island.py:246` | Stessi passi di heal, ma sulla griglia fine della rete piana: prima i |
| `normalize_ocs` | func | `topo_dxf/sanitize.py:19` | Normalizza il vettore di estrusione di tutte le entità OCS nel modelspace. |
| `normalize_role` | func | `topo/model/role.py:113` | Ripulisce una stringa-ruolo che arriva dal chiamante (``RoleRule``, |
| `num_segments_for_bulge` | func | `topo/core/geometry/measure.py:34` | Numero di segmenti per discretizzare un arco dato il suo bulge. |
| `_off_faces` | func | `topo/core/island.py:346` | I tratti degli edge di `loop` lontani più di `band` dal bordo di ogni |
| `offset_from_line` | func | `topo/core/geometry/points.py:166` | Distanza con segno di `p` dalla retta a->b (positiva a sinistra). |
| `_on_arc` | func | `topo/core/geometry/intersections.py:164` |  |
| `_on_arc` | func | `topo/core/healing/outer_scan.py:127` |  |
| `_on_border` | func | `topo/core/geometry/axis.py:186` |  |
| `_on_boundary` | func | `topo/tools/anchor.py:115` | L'elemento col bordo più vicino a ``point``, se entro ``distance``. |
| `_on_line` | func | `topo/core/geometry/intersections.py:155` |  |
| `_on_line` | func | `topo/core/primitives/trim.py:47` | Proiezione di `pt` sulla retta, dentro i suoi due estremi. |
| `_open` | func | `topo/core/island.py:395` |  |
| `OpenCurve` | class | `topo/model/curve.py:74` | Curva aperta: ha segmenti ma non un polygon. |
| `outer_candidate_edges` | func | `topo/core/healing/outer_scan.py:72` | Per ogni asse, una quota rappresentativa (punto medio) fra ogni coppia |
| `_outer_entity` | func | `topo_dxf/xdata.py:17` | L'entità su layer OuterContour che porta gli XDATA: prima una polilinea, |
| `outer_face` | func | `topo/core/topology/outer_face.py:59` | Contorno esterno della rete `edges` (già piana: split_at_crossings). I |
| `outer_face_passes` | func | `topo/core/topology/outer_face.py:88` | {id(edge): quante volte il bordo della faccia esterna di `component` |
| `_outer_face_walk` | func | `topo/core/topology/outer_face.py:103` | [(edge, dal nodo, al nodo)] lungo il bordo della faccia esterna. |
| `_outer_polygons` | func | `topo/tools/split.py:151` | (cluster, poligono dell'outer) per ogni cluster che ne ha uno. |
| `OuterCandidates` | class | `topo/core/healing/outer_scan.py:54` | Edge candidati a bordo esterno, con i raggi che li hanno scelti. |
| `OuterFace` | class | `topo/core/topology/outer_face.py:42` | Il contorno esterno trovato, e cosa il percorso ha scartato. |
| `OuterHit` | class | `topo/core/healing/outer_scan.py:45` | Un raggio per cui l'Edge è stato l'estremo. |
| `_outward_normal` | func | `topo/tools/tabs.py:255` | Normale unitaria uscente dal contorno chiuso `points` nel suo punto |
| `_p` | func | `topo/inspect.py:40` | Formatta un punto (x, y) con nd decimali. |
| `_palette_dict` | func | `topo/io/view_model.py:189` | role (stringa) → colore hex, per la legenda di un renderer: i tre ruoli |
| `_param` | func | `topo/core/geometry/regions.py:64` |  |
| `_param` | func | `topo/core/topology/noding.py:136` | (parametro, distanza del punto dal segmento). |
| `_param_range` | func | `topo/core/topology/noding.py:152` |  |
| `ParentBridgeResult` | class | `topo/tools/tabs.py:338` | Risultato di `bridge_parent_tabs` per UN genitore e le sue isole. Se |
| `_parse_arc` | func | `topo_dxf/parser.py:57` |  |
| `_parse_circle` | func | `topo_dxf/parser.py:101` |  |
| `_parse_ellipse` | func | `topo_dxf/parser.py:108` | Un'ELLIPSE DXF è sempre percorsa CCW da `start_param` a `end_param` |
| `_parse_line` | func | `topo_dxf/parser.py:47` |  |
| `_parse_polyline` | func | `topo_dxf/parser.py:126` |  |
| `_parse_spline` | func | `topo_dxf/parser.py:72` | Solo la geometria (MAP.md D135): grado, punti di controllo, nodi, pesi |
| `_Part` | class | `topo/core/primitives/fitting.py:44` | Un pezzo della sequenza: `kind` "line" o "curve", coi punti che copre (estremi condivisi coi vicini). |
| `_perp` | func | `topo/tools/tabs.py:77` | Ruota `v` di 90° (verso arbitrario, coerente fra le due chiamate). |
| `_piece` | func | `topo/core/geometry/regions.py:120` | Il tratto di `seg` fra i parametri `s0` < `s1`, stessa primitiva. |
| `_piece_length` | func | `topo/core/topology/noding.py:156` |  |
| `_pieces` | func | `topo/core/healing/outer_scan.py:113` |  |
| `_place` | func | `topo/core/geometry/build.py:21` | Ruota di `angle` gradi attorno all'origine e trasla in `center`. |
| `_place` | func | `topo/core/healing/hierarchy.py:70` |  |
| `_point` | func | `topo_dxf/inspect.py:32` | Formatta un punto (x, y) con nd decimali. |
| `_point_at` | func | `topo/core/geometry/points.py:207` | Punto della polilinea `points` all'ascissa curvilinea `s` (troncata agli estremi). |
| `point_line_distance` | func | `topo/core/geometry/lines.py:36` | Distanza di `point` dalla retta infinita per `a`, `b`; da `a` se i due coincidono. |
| `point_on_circle` | func | `topo/core/primitives/segments.py:97` | Punto della circonferenza (`center`, `radius`) all'angolo dato (radianti). |
| `point_on_contour` | func | `topo/core/geometry/regions.py:235` | Dove cade `point` sull'anello `segments` (testa-coda): su un vertice, su |
| `_point_to_segment_distance` | func | `topo/core/primitives/segments.py:276` | Distanza perpendicolare di `p` dal segmento `a`-`b` (0 se `a == b`). |
| `pointer_target` | func | `topo/tools/anchor.py:69` | L'elemento indicato dalla punta (``pointer[0]``) di ``text``, come |
| `_poly_points` | func | `topo/io/view_model.py:41` | Vertici dell'anello esterno di un polygon shapely come lista di [x, y]. |
| `polygon` | func | `topo/core/geometry/build.py:27` | Il poligono per i `points` dati, chiuso: l'ultimo lato torna al primo punto. Almeno 3 punti. |
| `_polygon` | func | `topo/core/geometry/regions.py:196` |  |
| `polygonize_edges` | func | `topo/core/healing/steps.py:314` | Ultima spiaggia quando nessun grafo chiude: le facce dell'intero disegno |
| `_polygons` | func | `topo/core/island.py:381` |  |
| `polygons_to_curves` | func | `topo/core/healing/steps.py:330` | Per poligono un ClosedCurve OUTER dal bordo esterno e uno INNER per |
| `_polyline` | func | `topo/core/geometry/regions.py:49` |  |
| `polyline_line_intersections` | func | `topo/core/geometry/intersections.py:102` | Intersezioni fra la retta infinita (p1, p2) e la spezzata `points` (ogni |
| `_polyline_points` | func | `topo_dxf/text_extractor.py:517` |  |
| `_probe_point` | func | `topo/tools/split.py:137` | Punto rappresentativo di una curva, per darla alla parte più vicina. |
| `promote` | func | `topo/tools/promote.py:20` | Toglie `curve` da `result.loose` e mette `item` (la curva stessa se |
| `_radius` | func | `topo/core/geometry/shape.py:109` | Raggio di un pezzo di cerchio; un'ellisse ad assi uguali è un cerchio, esattamente. |
| `_raw_linetype_pattern` | func | `topo_dxf/adapter.py:39` | Pattern grezzo (lunghezza totale + tratti con segno, `+` = tratto, |
| `_ray_exit_point` | func | `topo/tools/tabs.py:235` | Punto in cui il raggio da `center` verso `direction` esce dal contorno chiuso `points`. |
| `_read_dwg` | func | `topo_dxf/loader.py:148` | Legge un file DWG usando ezdxf.addons.odafc (wrapper di ODA File Converter). |
| `read_island` | func | `topo/core/island.py:169` | Un'isola: normalizza (nodi dagli estremi reali, tassellature rifittate, |
| `read_islands` | func | `topo/core/island.py:146` | I pezzi a contatto (`spatial_islands` a `max_gap`) + `read_island` per |
| `read_metadata_from_dxf` | func | `topo_dxf/xdata.py:57` | Legge i metadati TOPO XDATA dall'entità OuterContour. |
| `rectangle` | func | `topo/core/geometry/build.py:37` | Rettangolo `length` × `width` centrato in `center`, lato lungo a `angle` gradi. |
| `_rectangle` | func | `topo/core/geometry/shape.py:176` |  |
| `_refine_segment` | func | `topo/core/primitives/segments.py:288` | Suddivide `[t0, t1]` finché il punto medio (valutato con `evaluate(t)`) |
| `refit_tessellations` | func | `topo/core/healing/normalizer.py:461` | Una catena di almeno `min_run` LineSeg (`role == UNKNOWN`) più corti di |
| `regular_polygon` | func | `topo/core/geometry/build.py:43` | Poligono regolare di `sides` lati inscritto nel cerchio di raggio `radius`; il primo vertice a `angle` gradi. |
| `_remove_excluded_entities` | func | `topo_dxf/writer.py:289` |  |
| `_render_block` | func | `topo_dxf/text_extractor.py:432` | Espande l'immagine dell'entità in strokes/fills/texts puri. |
| `RenderedGeometry` | class | `topo/model/text.py:44` | L'immagine che la sorgente disegna attorno a una stringa (linee, frecce, |
| `RenderedText` | class | `topo/model/text.py:35` | Una stringa dentro l'immagine appiattita di un testo (`Text.rendered`). |
| `renode` | func | `topo/core/topology/noding.py:64` | Nodi di ogni Edge ricalcolati dal punto reale del segmento a |
| `repair_merged_corners` | func | `topo/core/healing/steps.py:217` | Chiude gli angoli che il grafo esatto vede aperti e il clustering degli |
| `resolve_role` | func | `topo/model/role_rule.py:106` | Ruolo della prima regola che matcha, in ordine; `unknown` se nessuna. |
| `resolve_target` | func | `topo/tools/anchor.py:122` | L'oggetto (contorno o feature) a cui punta un ``target``, o ``None``. |
| `_restore_corners` | func | `topo/core/primitives/fitting.py:176` | Gli spigoli vivi che il campionamento ha smussato. Un pezzo curvo più |
| `Result` | class | `topo/model/result.py:12` | Risultato completo di una sessione topo su un file DXF. |
| `_result_bbox_center` | func | `topo/tools/rotate.py:224` | Centro del bbox unito degli outer di tutti i cluster — vedi `rotate_to_longest`. |
| `_reversed` | func | `topo/core/geometry/regions.py:192` |  |
| `_rim_runs` | func | `topo/core/topology/rim.py:87` | [((edge, verso), primo vertice, ultimo vertice)] lungo l'anello: copertura greedy |
| `_ring_segments` | func | `topo/core/healing/steps.py:396` |  |
| `_role` | func | `topo/inspect.py:47` | Nome del ruolo come stringa piatta ('outer'), non 'ContourRole.OUTER'. |
| `_role_from` | func | `topo/core/geometry_input.py:38` | work_type stringa (stesso vocabolario di RoleRule.role) → ruolo. Un work_type |
| `role_str` | func | `topo/model/role.py:143` | Valore stringa di un ruolo, che sia una costante ``ContourRole`` o una |
| `role_style` | func | `topo/model/style.py:117` | Come si disegna `role`: la palette di topo (o il grigio di un ruolo di |
| `role_to_dxf_layer` | func | `topo_dxf/layers.py:57` | Nome del layer DXF per `role`. La scelta del chiamante (`layers`, chiavi |
| `RoleRule` | class | `topo/model/role_rule.py:41` | Una regola: se TUTTE le condizioni date sono vere, la linea prende `role`. |
| `RoleStyle` | class | `topo/model/style.py:80` | Come il chiamante vuole disegnato un ruolo in uscita (D37, D128). Il |
| `rotate_cluster` | func | `topo/tools/rotate.py:117` | Nuovo `Cluster` con `outer`/`inners` ruotati di `angle_rad` (radianti, |
| `_rotate_contour` | func | `topo/tools/rotate.py:108` |  |
| `rotate_document` | func | `topo/tools/rotate.py:187` | Nuovo `Document` con ogni `edge.segment` ruotato di `angle_rad` |
| `_rotate_point` | func | `topo/core/primitives/segments.py:71` | Ruota `pt` di `angle` radianti (CCW) attorno a `origin`. |
| `rotate_result` | func | `topo/tools/rotate.py:147` | Nuovo `Result` con ogni cluster (`rotate_cluster`), `loose` |
| `rotate_to_longest` | func | `topo/tools/rotate.py:240` | Ruota `result` (già sano, da un `heal()` già fatto dal chiamante) in modo |
| `round_point` | func | `topo/core/geometry/measure.py:26` |  |
| `_round_points` | func | `topo/io/view_model.py:36` | Lista di punti (2D o 3D) → lista di [x, y] arrotondati. |
| `_sagitta_step` | func | `topo/core/primitives/segments.py:112` | Angolo massimo di una corda che dista al più `tolerance` dall'arco di |
| `sample_bezier_cubic` | func | `topo_pdf/geometry_adapter.py:37` | Campiona una curva di Bezier cubica in un set di punti lineari (poligonale). |
| `sanitize` | func | `topo_dxf/sanitize.py:88` | Esegue tutti i sanitizer in sequenza sul modelspace ricevuto. |
| `sanitize_pdf_geometries` | func | `topo_pdf/sanitize.py:12` | Prende gli item geometrici grezzi estratti dall'extractor, applica la conversione |
| `save_json` | func | `topo/io/exporter.py:118` | Salva i metadati in JSON secondo lo schema di metadata_schema.py. |
| `save_svg` | func | `topo/io/svg.py:173` | Scrive `to_svg(result, **kwargs)` su file. |
| `save_text` | func | `topo/io/text.py:267` | Scrive `to_text(result)` su `path` (per convenzione `<nome>.topo.md`). |
| `save_xml` | func | `topo/io/exporter.py:171` | Salva i metadati in XML secondo lo schema di metadata_schema.py. |
| `_scale` | func | `topo/tools/tabs.py:62` |  |
| `_scan_axis` | func | `topo/core/healing/outer_scan.py:184` |  |
| `_scan_bbox` | func | `topo/io/svg.py:180` | bbox da tutti i punti del view model — fallback quando vm['bbox'] è None. |
| `_search_warnings` | func | `topo/core/heal.py:221` | Cosa racconta heal() dei gradini della scala di find_loops(). |
| `_seg_end_point` | func | `topo_dxf/exporter.py:101` |  |
| `segment_endpoints` | func | `topo/core/primitives/segments.py:503` | (start, end) di un segmento primitivo, in coordinate XY non arrotondate. |
| `segment_is_closed` | func | `topo/core/primitives/segments.py:529` | True se gli endpoint del segmento coincidono entro ``tolerance``. |
| `_segment_key` | func | `topo_dxf/adapter.py:168` | Chiave univoca per deduplicazione. |
| `segment_length` | func | `topo/core/geometry/measure.py:93` | Lunghezza reale di una primitiva nativa singola (`LineSeg`/`ArcSeg`/ |
| `segments_from_loop` | func | `topo/core/topology/loop_finder.py:161` | Segmenti nativi di un loop, orientati nel verso di percorrenza. |
| `segments_to_pts_with_bulge` | func | `topo_dxf/exporter.py:109` |  |
| `_sense` | func | `topo/core/topology/rim.py:77` | +1 se il lato p→q va nel verso di `geom` vicino a `mid`, -1 se contro. |
| `set_schema` | func | `topo/io/exporter.py:101` | Imposta uno schema esterno come schema attivo. |
| `_shape` | func | `topo/io/svg.py:29` |  |
| `ShapeKind` | class | `topo/core/geometry/shape.py:30` | Le sei forme di `contour_shape`, elenco chiuso e stabile (MAP.md D136). |
| `_short_runs` | func | `topo/core/healing/normalizer.py:514` | Catene massimali: percorsi fra nodi di grado != 2, o anelli. |
| `_shown_text` | func | `topo_dxf/text_extractor.py:236` | La stringa che la quota mostra: l'override con ``<>`` sostituito dalla |
| `_shown_value` | func | `topo_dxf/text_extractor.py:249` | La misura come la mostra il disegno (precisione, virgola), o calcolata. |
| `_side` | func | `topo/core/geometry/regions.py:203` | +1 dentro, -1 fuori, 0 sul bordo. |
| `_side_cover` | func | `topo/core/topology/rim.py:60` | Per ogni lato dell'anello, gli (edge, verso) che distano meno di `band` |
| `sides_on_border` | func | `topo/core/geometry/axis.py:231` | I lati di `bounds` ("left", "bottom", "right", "top") che stanno sul |
| `_signed_area` | func | `topo/core/geometry/regions.py:187` |  |
| `_signed_turn` | func | `topo/core/primitives/fitting.py:56` | Svolta con segno (gradi) in `b` andando da `a` a `c`: positiva a sinistra. |
| `simplify_points` | func | `topo/core/primitives/fitting.py:249` | Primitive (LineSeg/ArcSeg/CircleSeg/BSplineSeg) per la sequenza di punti |
| `_size` | func | `topo/tools/anchor.py:166` | A parità di distanza vince l'elemento più piccolo: un foro sul bordo del pezzo. |
| `_slug` | func | `topo_dxf/layers.py:85` |  |
| `_solid_points` | func | `topo_dxf/text_extractor.py:529` | SOLID/TRACE: 4 vertici in ordine 'a farfalla' → poligono convesso. |
| `_solve_arc_arc` | func | `topo/core/healing/gap_solver.py:126` |  |
| `_solve_arc_line` | func | `topo/core/healing/gap_solver.py:112` |  |
| `_solve_line_line` | func | `topo/core/healing/gap_solver.py:100` |  |
| `_solve_spline_any` | func | `topo/core/healing/gap_solver.py:138` |  |
| `_span` | func | `topo/core/geometry/regions.py:53` |  |
| `_Span` | class | `topo/core/healing/normalizer.py:218` | Un edge come intervallo [lo, hi] sul suo supporto (posizione lungo la |
| `spanning_lines` | func | `topo/core/geometry/axis.py:199` | (ys, xs): le coordinate delle linee strettamente interne a `bounds` (bordo |
| `spatial_islands` | func | `topo/core/healing/islands.py:54` | Union-find sulle coppie di Edge a distanza <= gap_tolerance (STRtree, |
| `_spline_param` | func | `topo/core/primitives/trim.py:145` | Parametro del punto della spline più vicino a `pt`: campioni, poi |
| `_split` | func | `topo/core/geometry/regions.py:136` | `seg` spezzato nei `points` che gli stanno sopra, nel suo verso. |
| `_split` | func | `topo/core/topology/noding.py:245` |  |
| `split` | func | `topo/tools/split.py:26` | Un `Result` per parte, nell'ordine delle parti tenute. |
| `split_at_crossings` | func | `topo/core/topology/noding.py:72` | Spezza ogni LineSeg/ArcSeg/CircleSeg nei punti dove incrocia un altro |
| `_split_at_junctions` | func | `topo/core/healing/normalizer.py:308` | Spezza una catena dove due span consecutivi si toccano SOLO (nessuna |
| `_split_circle` | func | `topo/core/topology/noding.py:270` |  |
| `_split_closed_polyline_at_cuts` | func | `topo/tools/tabs.py:169` | Spezza il contorno chiuso `points` sui tagli in `cuts` — ognuno |
| `split_labeled` | func | `topo/core/healing/steps.py:77` | Separa gli Edge con un ruolo già deciso e non strutturale (cornice, |
| `split_non_finite` | func | `topo/core/healing/steps.py:56` | Separa gli Edge con una coordinata non finita (NaN, inf): ritorna |
| `_split_pair` | func | `topo/tools/tabs.py:282` | Spezza isola e genitore sui tagli di tutte le `bridges` della coppia, insieme. |
| `_split_params` | func | `topo/core/topology/noding.py:209` |  |
| `_split_stretch` | func | `topo/core/primitives/fitting.py:62` | Un tratto senza spigoli: tutto entro `tolerance` dalla corda -> una linea; |
| `split_to_files` | func | `topo_dxf/recipes.py:25` | Pipeline multi-pezzo + salvataggio su disco: heal → `topo.split` → |
| `splits_polygon` | func | `topo/core/geometry/lines.py:82` | La corda `start`-`end`, prolungata di `reach` ai due capi, divide `polygon` in due o più parti. |
| `stadium` | func | `topo/core/geometry/build.py:70` | Stadio fuori tutto `length` × `width` (due semicerchi di raggio |
| `_stadium` | func | `topo/core/geometry/shape.py:150` |  |
| `structural_loops` | func | `topo/core/healing/steps.py:287` | I loop in cui ogni edge con ruolo deciso è strutturale: un solo edge non |
| `structural_segments` | func | `topo/tools/rotate.py:73` | Segmenti nativi dei contorni strutturali di ogni cluster: sempre |
| `_style_attribs` | func | `topo_dxf/exporter.py:57` | dxfattribs per una entità in output: layer + linetype della sorgente, se |
| `_sub` | func | `topo/tools/tabs.py:54` |  |
| `_sub_angular` | func | `topo/core/primitives/trim.py:61` |  |
| `_sub_part` | func | `topo/inspect.py:189` |  |
| `sub_segment` | func | `topo/core/primitives/trim.py:26` | Il tratto di `seg` da `a` a `b` (punti sulla curva, o a una tolleranza |
| `_sub_spline` | func | `topo/core/primitives/trim.py:115` |  |
| `_synthesize_dimension` | func | `topo_dxf/text_extractor.py:320` | Ricostruisce l'immagine di una DIMENSION lineare dai def-point, quando il |
| `TabbedIsland` | class | `topo/tools/tabs.py:331` | Un'isola collegata da `bridge_parent_tabs`: i suoi tratti fra una linguetta e l'altra. |
| `_tangent` | func | `topo/core/geometry/regions.py:163` | Direzione di percorrenza di `seg` nel suo capo iniziale o finale. |
| `Text` | class | `topo/model/text.py:62` | Un testo della sorgente. ``position`` è il punto d'ancoraggio — dove un |
| `text_anchor` | func | `topo_dxf/text_extractor.py:98` | Punto d'ancoraggio XY di un'entità di testo. |
| `_text_entry` | func | `topo/io/view_model.py:111` |  |
| `_text_item` | func | `topo_dxf/text_extractor.py:480` |  |
| `_text_signature` | func | `topo_dxf/loader.py:63` |  |
| `_texts_by_part` | func | `topo/tools/inject.py:74` | Testi di `result.texts` per indice di parte. Un testo coperto da più |
| `_thinner_than` | func | `topo/core/island.py:375` | Larghezza media (2·area/perimetro: per una striscia, la sua |
| `to_dxf` | func | `topo_dxf/writer.py:35` | Crea un documento DXF nuovo (R2010) e vi materializza il Result. |
| `to_json` | func | `topo/io/exporter.py:148` | Restituisce i metadati come stringa JSON secondo schema. Vedi `save_json` per `extra_metadata`. |
| `to_nester_input` | func | `topo/io/exporter.py:245` | Produce l'input per il nester: coordinate grezze + metadati base. |
| `_to_primitives` | func | `topo/core/primitives/fitting.py:238` |  |
| `to_svg` | func | `topo/io/svg.py:46` | `Result` → stringa SVG completa (`<svg>…</svg>`). |
| `to_text` | func | `topo/io/text.py:171` | Il `Result` come testo per un modello linguistico (`.topo.md`). |
| `_to_text` | func | `topo_dxf/text_extractor.py:61` |  |
| `to_view_model` | func | `topo/io/view_model.py:133` | `Result` → dizionario JSON-ready con la geometria di ogni feature. |
| `_track` | func | `topo/io/view_model.py:48` | Traccia aperta (lista di segmenti nativi) discretizzata a lista di [x, y]. |
| `track_length` | func | `topo/core/geometry/measure.py:68` | Lunghezza totale di una polilinea (somma delle corde). |
| `track_points` | func | `topo/core/geometry/measure.py:49` | Vertici di una traccia aperta come catena di segmenti nativi. |
| `track_shape_type` | func | `topo/core/geometry/measure.py:82` | `"line"` se la traccia è un solo segmento retto (2 vertici), altrimenti `"curve"`. |
| `transform_point` | func | `topo_pdf/geometry_adapter.py:27` | Converte un punto da punti PDF (pt) a millimetri (mm) |
| `_trimmed` | func | `topo/core/topology/rim.py:142` | `seg` da `a` a `b`: un capo entro `band` da un estremo di `seg` è |
| `_turn` | func | `topo/core/geometry/points.py:196` | Di quanto gira (gradi, 0..180) chi va da `back` ad `at` e poi a `forward`. |
| `turn_corners` | func | `topo/core/geometry/points.py:225` | Indici degli spigoli di una sequenza campionata: vertici Douglas-Peucker |
| `_uniform_knots` | func | `topo/io/text.py:160` | Nodi bloccati agli estremi e passo interno costante: non serve scriverli. |
| `_unit_vector` | func | `topo/tools/tabs.py:70` |  |
| `_upgrade_to_r2010` | func | `topo_dxf/loader.py:180` | Converte un documento DXF legacy in R2010. |
| `validate` | func | `topo/rules/validator.py:29` | Valida l'input prima di heal(). |
| `validate_result` | func | `topo/rules/validator.py:128` | Valida i Cluster dentro un Result già popolato da heal(). |
| `_warn_non_roundtrip_types` | func | `topo_dxf/loader.py:86` | Avvisa sui tipi di entità che to_dxf() non riscrive (HATCH, IMAGE, …). |
| `weld_degenerate_linesegs` | func | `topo/core/healing/normalizer.py:409` | Salda (non cancella) i LineSeg `role == UNKNOWN` di lunghezza reale |
| `_width_factor` | func | `topo_dxf/text_extractor.py:163` | Stretch orizzontale effettivo del testo (1.0 = nessuno). |
| `_with_nodes` | func | `topo/core/topology/noding.py:239` |  |
| `_within` | func | `topo/core/primitives/fitting.py:50` | Tutti i punti entro `tolerance` dalla corda primo-ultimo. |
| `_write_attached_features` | func | `topo_dxf/writer.py:257` | Ogni collezione di `cluster.detected` (D70, D90): topo non sa cosa siano. |
| `_write_loose` | func | `topo_dxf/writer.py:234` | Materializza `result.loose`, tutte: in un file per parte le ha |
| `write_metadata_to_dxf` | func | `topo_dxf/xdata.py:28` | Scrive i metadati come XDATA sull'entità OuterContour. |
| `write_native_segments` | func | `topo_dxf/exporter.py:258` | Materializza segmenti aperti come geometria NATIVA, una entità DXF per |
| `write_open_segments` | func | `topo_dxf/exporter.py:316` | Materializza una lista di segmenti puri come geometria APERTA su msp. |
| `write_segments` | func | `topo_dxf/exporter.py:179` | Materializza una lista di segmenti puri su msp. |
| `_write_texts` | func | `topo_dxf/writer.py:147` | Riscrive i testi della sorgente nel documento di output, tutti: quale |
| `_Writer` | class | `topo/io/text.py:42` | Numeri arrotondati e id dei contorni per una sola chiamata di `to_text`. |
| `_xy` | func | `topo_dxf/text_extractor.py:505` |  |

## Duplicate names

Same name defined at module level in different modules. Not automatically a bug — but each one is either two implementations of one job (merge them) or two different jobs sharing a name (rename one).

| name | defined in |
|---|---|
| `_assign` | `topo/tools/anchor.py:171` · `topo/tools/split.py:88` |
| `_chain` | `topo/core/geometry/regions.py:309` · `topo/core/healing/normalizer.py:234` |
| `_color_rgb` | `topo/model/role_rule.py:123` · `topo_dxf/adapter.py:62` |
| `_ends` | `topo/core/geometry/lines.py:27` · `topo/core/geometry/regions.py:112` |
| `_length` | `topo/core/geometry/regions.py:104` · `topo/core/geometry/shape.py:208` · `topo/core/primitives/fitting.py:164` |
| `_on_arc` | `topo/core/geometry/intersections.py:164` · `topo/core/healing/outer_scan.py:127` |
| `_on_line` | `topo/core/geometry/intersections.py:155` · `topo/core/primitives/trim.py:47` |
| `_param` | `topo/core/geometry/regions.py:64` · `topo/core/topology/noding.py:136` |
| `_place` | `topo/core/geometry/build.py:21` · `topo/core/healing/hierarchy.py:70` |
| `_split` | `topo/core/geometry/regions.py:136` · `topo/core/topology/noding.py:245` |

## Dependency rule

- `core` never imports `tools`, `io`
- `model` never imports `tools`, `io`
- `topo` never imports `ezdxf`, `fitz`, `pymupdf`, `topo_dxf`, `topo_pdf`
- `topo_dxf` never imports `topo.core`, `topo.tools`, `topo.io`, `topo.rules`, `topo_pdf`
- `topo_pdf` never imports `topo.core`, `topo.tools`, `topo.io`, `topo.rules`, `topo_dxf`

`TYPE_CHECKING`-only imports count as violations here and must be verified by hand.

**Clean** — no violation found.

## By module

### `topo/` (root)

#### `topo/__init__.py` — 180 lines

_topo_

No module-level function or class.

### `topo/core/`

#### `topo/core/geometry/__init__.py` — 56 lines

_topo/core/geometry/__init__.py_

No module-level function or class.

#### `topo/core/geometry/axis.py` — 253 lines

_topo/core/geometry/axis.py_

- `merge_intervals(intervals: Iterable[Interval], tolerance: float=0.0) -> List[Interval]` — L36 — Unisce gli intervalli che si sovrappongono o distano al più `tolerance`, in ordine.
- `interval_coverage(intervals: Iterable[Interval], lo: float, hi: float) -> float` — L47 — Frazione di [lo, hi] coperta dall'unione degli intervalli.
- `cluster_values(values: Iterable[float], tolerance: float=CLUSTER_TOLERANCE) -> List[float]` — L55 — I valori ordinati, tenendo per ogni gruppo il più piccolo: un valore entro
- **class** `AxisLine` — L73 — Un tratto orizzontale o verticale.
- `axis_lines(items: Iterable, eps: float=AXIS_EPS) -> Tuple[List[AxisLine], List[AxisLine]]` — L87 — (orizzontali, verticali): i tratti che si scostano dall'asse al più di `eps`; gli altri non compaiono.
- `_covered_at(lines: Sequence[AxisLine], at: float, lo: float, hi: float, tol: float) -> float` — L100
- **class** `CoveredRectangle` — L109 — Un rettangolo allineato agli assi i cui quattro lati sono coperti da tratti.
  - methods: `bbox`, `area`, `long_side`, `short_side`, `ratio`
- `covered_rectangles(items: Sequence, min_side: float, eps: float=AXIS_EPS, cluster_tolerance: float=CLUSTER_TOLERANCE, coverage: float=SIDE_COVERAGE) -> List[CoveredRectangle]` — L144 — I rettangoli allineati agli assi con ogni lato coperto almeno per
- `_on_border(x_lo, y_lo, x_hi, y_hi, items, tol) -> list` — L186
- `spanning_lines(bounds: Bounds, items: Iterable, coverage: float=SIDE_COVERAGE, eps: float=AXIS_EPS, cluster_tolerance: float=CLUSTER_TOLERANCE) -> Tuple[List[float], List[float]]` — L199 — (ys, xs): le coordinate delle linee strettamente interne a `bounds` (bordo
- `items_inside(bounds: Bounds, items: Iterable, margin: float=0.0) -> list` — L221 — I tratti con entrambi i capi dentro `bounds` allargato di `margin`, nell'ordine dato.
- `sides_on_border(bounds: Bounds, border: Bounds, tolerance: float) -> List[str]` — L231 — I lati di `bounds` ("left", "bottom", "right", "top") che stanno sul
- `axis_aligned_share(segments: Iterable, angle_tolerance: float) -> Optional[float]` — L238 — Frazione della lunghezza dei `LineSeg` di `segments` orizzontale o

#### `topo/core/geometry/build.py` — 87 lines

_topo/core/geometry/build.py_

- `_place(points: Sequence[Point], center: Point, angle: float) -> List[Point]` — L21 — Ruota di `angle` gradi attorno all'origine e trasla in `center`.
- `polygon(points: Sequence[Point]) -> List[LineSeg]` — L27 — Il poligono per i `points` dati, chiuso: l'ultimo lato torna al primo punto. Almeno 3 punti.
- `rectangle(length: float, width: float, center: Point=(0.0, 0.0), angle: float=0.0) -> List[LineSeg]` — L37 — Rettangolo `length` × `width` centrato in `center`, lato lungo a `angle` gradi.
- `regular_polygon(sides: int, radius: float, center: Point=(0.0, 0.0), angle: float=0.0) -> List[LineSeg]` — L43 — Poligono regolare di `sides` lati inscritto nel cerchio di raggio `radius`; il primo vertice a `angle` gradi.
- `circle(radius: float, center: Point=(0.0, 0.0)) -> List[CircleSeg]` — L52 — Il cerchio di raggio `radius` in `center`.
- `ellipse(length: float, width: float, center: Point=(0.0, 0.0), angle: float=0.0) -> List[EllipseSeg]` — L57 — L'ellisse di assi `length` × `width` centrata in `center`, asse lungo a
- `stadium(length: float, width: float, center: Point=(0.0, 0.0), angle: float=0.0) -> list` — L70 — Stadio fuori tutto `length` × `width` (due semicerchi di raggio

#### `topo/core/geometry/intersections.py` — 198 lines

_topo/core/geometry/intersections.py_

- `_line_intersection(p1: Point, p2: Point, p3: Point, p4: Point) -> Optional[Point]` — L22 — Intersezione tra retta (p1,p2) e retta (p3,p4). None se parallele.
- `_distance(p1: Point, p2: Point) -> float` — L36
- `_circle_line_intersections(cx: float, cy: float, r: float, p1: Point, p2: Point) -> List[Point]` — L40 — Intersezioni tra la circonferenza (cx, cy, r) e la retta infinita (p1, p2).
- `_circle_circle_intersections(cx1: float, cy1: float, r1: float, cx2: float, cy2: float, r2: float) -> List[Point]` — L71 — Intersezioni tra due circonferenze. Restituisce 0, 1 o 2 punti.
- `_closest_to(candidates: List[Point], ref: Point) -> Optional[Point]` — L95 — Restituisce il punto più vicino a ref tra i candidati.
- `polyline_line_intersections(points: List[Point], closed: bool, p1: Point, p2: Point) -> List[Tuple[Point, int]]` — L102 — Intersezioni fra la retta infinita (p1, p2) e la spezzata `points` (ogni
- `_exact_parts(seg) -> list` — L146 — Retta, arco, cerchio restano se stessi; spline ed ellisse diventano
- `_on_line(seg: LineSeg, pt: Point) -> bool` — L155
- `_on_arc(seg, pt: Point) -> bool` — L164
- `_meet(a, b) -> List[Point]` — L171
- `intersections(a, b) -> List[Point]` — L184 — I punti dove due primitive si incontrano: incroci e tocchi, capi compresi.

#### `topo/core/geometry/lines.py` — 170 lines

_topo/core/geometry/lines.py_

- `_ends(item) -> Tuple[Point, Point]` — L27 — I due capi di un tratto: `LineString` (primo e ultimo punto) o `(start, end)`.
- `point_line_distance(point: Point, a: Point, b: Point) -> float` — L36 — Distanza di `point` dalla retta infinita per `a`, `b`; da `a` se i due coincidono.
- `are_collinear(a, b, tolerance: float=COLLINEAR_TOLERANCE, angle_tolerance: float=COLLINEAR_ANGLE_TOLERANCE) -> bool` — L45 — I tratti `a` e `b` stanno sulla stessa retta infinita: direzioni uguali
- `group_collinear_lines(lines: list, tolerance: float=COLLINEAR_TOLERANCE, angle_tolerance: float=COLLINEAR_ANGLE_TOLERANCE) -> list` — L61 — Tratti raggruppati per retta: [[L1, L2], [L3], ...]. Ogni gruppo prende la
- `splits_polygon(polygon, start: Point, end: Point, reach: float=0.0) -> bool` — L82 — La corda `start`-`end`, prolungata di `reach` ai due capi, divide `polygon` in due o più parti.
- **class** `CollinearRun` — L94 — Tratti sulla stessa retta, in fila lungo di essa.
- `bridged_runs(segments: Sequence, bridges: Sequence, tolerance: float=COLLINEAR_TOLERANCE, angle_tolerance: float=COLLINEAR_ANGLE_TOLERANCE) -> list[CollinearRun]` — L106 — File di due o più tratti sulla stessa retta in cui lo spazio fra un tratto
- `dash_line(start: Point, end: Point, head: float, tail: float, middle: float=0.0, n_middle: int=0) -> list[Tuple[Point, Point]]` — L143 — Il segmento `start`→`end` ridotto a tratti: uno lungo `head` che parte da

#### `topo/core/geometry/measure.py` — 186 lines

_topo/core/geometry/measure.py_

- `round_point(pt, decimals: int=NODE_DECIMALS) -> Tuple` — L26
- `num_segments_for_bulge(bulge: float) -> int` — L34 — Numero di segmenti per discretizzare un arco dato il suo bulge.
- `track_points(segments, tolerance: Optional[float]=None) -> List[Point]` — L49 — Vertici di una traccia aperta come catena di segmenti nativi.
- `track_length(pts) -> float` — L68 — Lunghezza totale di una polilinea (somma delle corde).
- `closest_point_on_track(pts, point: Point, closed: bool=False) -> Point` — L76 — Il punto della traccia `pts` più vicino a `point`: `nearest_point` sui suoi lati.
- `track_shape_type(pts) -> str` — L82 — `"line"` se la traccia è un solo segmento retto (2 vertici), altrimenti `"curve"`.
- `segment_length(segment) -> float` — L93 — Lunghezza reale di una primitiva nativa singola (`LineSeg`/`ArcSeg`/
- `length_inside(segment, bounds: Tuple[float, float, float, float]) -> float` — L110 — Quanta parte di `segment` (qualunque primitiva nativa) sta dentro il
- `longest_segment(segments) -> Tuple[Optional[object], float]` — L122 — `(segment, length)` del segmento più lungo in `segments` — `(None, 0.0)`
- `chord_angle_deg(a: Point, b: Point) -> float` — L135 — Angolo (gradi, 0-180°) della corda da `a` a `b`. Modulo 180 perché una
- `circular_geometry(polygon, segments=None)` — L157 — (diameter, center) se il contorno è ~circolare, altrimenti (None, None).

#### `topo/core/geometry/points.py` — 358 lines

_topo/core/geometry/points.py_

- `drop_duplicate_points(points: List[Point], tolerance: float=DEFAULT_DUPLICATE_TOLERANCE) -> List[Point]` — L33 — Rimuove punti consecutivi coincidenti entro `tolerance`.
- `fit_circle_kasa(points: List[Point]) -> Optional[Tuple[Point, float, float]]` — L47 — Fit algebrico (Kasa) ai minimi quadrati di un cerchio su `points`: minimizza
- `interpolate_bspline(points: List[Point], degree: int=3) -> Tuple[List[Point], List[float]]` — L79 — B-spline di grado `degree` che passa per tutti i `points` (interpolazione
- `_bspline_basis_row(u: float, p: int, knots: List[float], n: int) -> List[float]` — L113 — Le n+1 funzioni di base N_i,p(u) (Cox-de Boor, Piegl & Tiller A2.2).
- `even_spacing(points: List[Point], closed: bool) -> List[Point]` — L142 — I punti con altri aggiunti dove due vicini distano più del passo mediano.
- `offset_from_line(p: Point, a: Point, b: Point) -> float` — L166 — Distanza con segno di `p` dalla retta a->b (positiva a sinistra).
- `douglas_peucker(points: List[Point], tolerance: float) -> List[int]` — L174 — Indici dei vertici che Douglas-Peucker tiene sulla polilinea aperta
- `_turn(back: Point, at: Point, forward: Point) -> float` — L196 — Di quanto gira (gradi, 0..180) chi va da `back` ad `at` e poi a `forward`.
- `_point_at(points: List[Point], cum: List[float], s: float) -> Point` — L207 — Punto della polilinea `points` all'ascissa curvilinea `s` (troncata agli estremi).
- `turn_corners(points: List[Point], closed: bool, turn_deg: float, scale: float, tolerance: float) -> List[int]` — L225 — Indici degli spigoli di una sequenza campionata: vertici Douglas-Peucker
- `circle_through(a: Point, m: Point, b: Point) -> Optional[Tuple[Point, float]]` — L271 — Il cerchio per tre punti: `(center, radius)`, None se sono allineati.
- `_chord_params(points: List[Point]) -> List[float]` — L286
- `_least_squares(points: np.ndarray, t: List[float], degree: int, count: int)` — L299 — Spline di grado `degree` con `count` punti di controllo ai minimi quadrati
- `approximate_bspline(points: List[Point], degree: int, tolerance: float) -> Tuple[List[Point], List[float]]` — L324 — La B-spline di grado `degree` con meno punti di controllo che passa per il

#### `topo/core/geometry/regions.py` — 406 lines

_topo/core/geometry/regions.py_

- `_polyline(seg) -> List[Point]` — L49
- `_span(seg) -> float` — L53
- `_param(seg, pt: Point) -> float` — L64
- `_at(seg, s: float) -> Point` — L87
- `_length(seg, s0: float, s1: float) -> float` — L104
- `_ends(seg) -> Tuple[Point, Point]` — L112
- `_middle(seg) -> Point` — L116
- `_piece(seg, s0: float, s1: float)` — L120 — Il tratto di `seg` fra i parametri `s0` < `s1`, stessa primitiva.
- `_split(seg, points: Sequence[Point]) -> list` — L136 — `seg` spezzato nei `points` che gli stanno sopra, nel suo verso.
- `_tangent(seg, at_end: bool) -> Tuple[float, float]` — L163 — Direzione di percorrenza di `seg` nel suo capo iniziale o finale.
- `_full_arc(seg)` — L178 — Un cerchio come arco di 360°: un arco si inverte, un CircleSeg no (è
- `_signed_area(ring: Sequence) -> float` — L187
- `_reversed(ring: Sequence) -> list` — L192
- `_polygon(ring: Sequence)` — L196
- `_side(polygon, pt: Point) -> int` — L203 — +1 dentro, -1 fuori, 0 sul bordo.
- **class** `ContourPoint` — L216 — Dove cade un punto su un contorno.
- `point_on_contour(segments: Sequence, point: Point, tolerance: float=DEFAULT_TOLERANCE, angle_tolerance: float=TANGENT_TOLERANCE) -> Optional[ContourPoint]` — L235 — Dove cade `point` sull'anello `segments` (testa-coda): su un vertice, su
- `nearest_point(segments: Sequence, point: Point) -> Point` — L263 — Il punto delle primitive `segments` più vicino a `point`: anche a metà di
- `cut_by(segment, region: Sequence, keep: str='outside') -> list` — L284 — I pezzi di `segment` fuori (`keep="outside"`) o dentro (`keep="inside"`)
- `_chain(pieces: list) -> List[list]` — L309 — Pezzi orientati incatenati testa-coda in anelli chiusi.
- `contour_minus(contour: Sequence, region: Sequence) -> List[list]` — L326 — L'anello `contour` meno la regione chiusa `region` (tutti e due anelli di
- `enclosing(tracks: Sequence[Sequence[Point]], outers: Sequence, tolerance: float) -> List[Optional[int]]` — L378 — Per ogni traccia (una sequenza di punti), l'indice in `outers` del

#### `topo/core/geometry/shape.py` — 352 lines

_topo/core/geometry/shape.py_

- **class** `ShapeKind(str, Enum)` — L30 — Le sei forme di `contour_shape`, elenco chiuso e stabile (MAP.md D136).
- **class** `ContourShape` — L61 — kind:   un `ShapeKind` (circle \| ellipse \| stadium \| rectangle \| polygon \| other)
  - methods: `diameter`, `to_dict`
- `contour_shape(item, tolerance: float=SHAPE_TOLERANCE, angle_tolerance: float=ANGLE_TOLERANCE_DEG) -> Optional[ContourShape]` — L90 — Forma di un contorno chiuso (`Contour`, o qualunque oggetto con
- `_radius(seg, tol) -> Optional[float]` — L109 — Raggio di un pezzo di cerchio; un'ellisse ad assi uguali è un cerchio, esattamente.
- `_circle(segments, tol, _angle_tol)` — L118
- `_ellipse(segments, tol, angle_tol)` — L133 — Pezzi della stessa ellisse (centro, semiassi, direzione dell'asse) per un giro intero.
- `_stadium(segments, tol, angle_tol)` — L150
- `_rectangle(segments, tol, angle_tol)` — L176
- `_generic(segments)` — L193
- `_length(line: LineSeg) -> float` — L208
- `_angle_diff(a: float, b: float) -> float` — L212 — Differenza fra due direzioni modulo 180, in [0, 90].
- **class** `ConcentricGroup` — L229 — Contorni circolari con lo stesso centro, dal raggio minore al maggiore.
  - methods: `diameters`
- `concentric_groups(items, tolerance: float=CONCENTRIC_TOLERANCE) -> list[ConcentricGroup]` — L246 — Partizione dei contorni circolari di `items` per centro: ogni cerchio sta
- **class** `ArcAround` — L269 — Un arco concentrico a un cerchio e più grande di lui.
- `arcs_around(center: Point, radius: float, arcs, tolerance: float=CONCENTRIC_TOLERANCE) -> list[ArcAround]` — L282 — Gli archi di `arcs` col centro entro `tolerance` da `center` e raggio
- `merge_runs(segments: list, styles: list)` — L297 — Segmenti consecutivi di un giro chiuso sulla stessa circonferenza (o
- `_continues(prev, prev_style, seg, style) -> bool` — L329 — `seg` prosegue `prev` sulla stessa curva, nello stesso verso?
- `_joined(prev, seg)` — L348

#### `topo/core/geometry_input.py` — 232 lines

_topo/core/geometry_input.py_

- `_role_from(entity: Dict[str, Any]) -> str` — L38 — work_type stringa (stesso vocabolario di RoleRule.role) → ruolo. Un work_type
- **class** `GeometryReader` — L46 — Traduce descrizioni geometriche pure (dict) in Edge del dominio topo.
  - methods: `__init__`, `to_edges`, `_line_edge`, `_arc_edge`, `_circle_edge`, `_spline_edge`, `_ellipse_edge`, `_polygon_edges`
- `load_geometry(entities: List[Dict[str, Any]], tolerance: float=DEFAULT_NODE_TOLERANCE, source_path: str='') -> Document` — L161 — Costruisce un Document da una lista di descrizioni geometriche pure —
- `load_segments(segments, tolerance: float=DEFAULT_NODE_TOLERANCE, role: str='unknown', source_path: str='') -> Document` — L206 — Un Document da segmenti di topo (`LineSeg`, `ArcSeg`, `CircleSeg`,

#### `topo/core/heal.py` — 240 lines

_core/heal.py_

- `heal(doc: Document, tolerance: Optional[float]=None, label: str='', source_file: str='', is_structural: Optional[Callable[[str], bool]]=None) -> Result` — L43 — Legge `doc` dall'interno: un Cluster per contorno esterno chiuso,
- `_loose_ends_warnings(edges: list, non_contour_ids: set, epsilon: float) -> list[str]` — L190 — Quello che resta aperto anche quando qualcosa si chiude (D111): gli
- `_crossing_warnings(contour: list, tolerance: float) -> list[str]` — L209 — Lati di contorno che si attraversano senza un nodo (D132): il disegno è
- `_search_warnings(search: LoopSearch, tolerance: float) -> list[str]` — L221 — Cosa racconta heal() dei gradini della scala di find_loops().

#### `topo/core/healing/__init__.py` — 0 lines

No module-level function or class.

#### `topo/core/healing/gap_solver.py` — 385 lines

_core/healing/gap_solver.py_

- **class** `GapEndpoint` — L46 — Endpoint libero nel grafo topologico.
- **class** `MoveEndpoint` — L73 — Istruzione: sposta l'endpoint role di ref al punto new_pt.
- **class** `AddSegment` — L84 — Istruzione: aggiungi un segmento retto tra pt_a e pt_b.
- `_solve_line_line(ep_a: GapEndpoint, ep_b: GapEndpoint) -> List[GapFix]` — L100
- `_solve_arc_line(ep_arc: GapEndpoint, ep_line: GapEndpoint) -> List[GapFix]` — L112
- `_solve_arc_arc(ep_a: GapEndpoint, ep_b: GapEndpoint) -> List[GapFix]` — L126
- `_solve_spline_any(ep_a: GapEndpoint, ep_b: GapEndpoint) -> List[GapFix]` — L138
- `_get_solver(kind_a: str, kind_b: str)` — L162
- `compute_gap_fixes(endpoints: List[GapEndpoint], tolerance: float, pairwise: bool=True) -> List[GapFix]` — L174 — Calcola i GapFix fra gli endpoint liberi entro tolerance. I due capi
- `local_gap_fixes(fixes: List[GapFix], max_move: float) -> List[GapFix]` — L229 — Solo i fix che non spostano un estremo più di `max_move`: due rette quasi
- `_endpoint_meta(segment) -> dict` — L253 — Dati che il solver usa per calcolare l'intersezione, per tipo di segmento.
- `_meet_or_bridge(ix: Optional[Point2D], ep_a: GapEndpoint, ep_b: GapEndpoint) -> List[GapFix]` — L262 — Se le due geometrie si incontrano in `ix`, porta lì entrambi gli estremi;
- `free_endpoints_from_edges(edges: List[Edge], graph) -> List[GapEndpoint]` — L273 — Estrae gli endpoint liberi (grado < 2 nel grafo) dagli Edge.
- `gap_endpoints_at_nodes(edges: List[Edge], nodes: set) -> List[GapEndpoint]` — L285 — GapEndpoint per gli endpoint che cadono su uno dei `nodes` — tuple di
- `_gap_endpoints(edges: List[Edge], keep: Callable[[Point2D], bool]) -> List[GapEndpoint]` — L302 — GapEndpoint per gli estremi di LINE / ARC / SPLINE il cui nodo (arrotondato)
- `_moved_segment(segment, role: str, new_pt: Point2D)` — L322 — Nuovo segmento con l'endpoint `role` spostato su `new_pt`. None se non gestito.
- `apply_gap_fixes(edges: List[Edge], fixes: List[GapFix]) -> List[Edge]` — L340 — Applica i GapFix restituendo una NUOVA lista di Edge — `edges` non viene mutata.

#### `topo/core/healing/hierarchy.py` — 231 lines

- `loop_to_closed_curve(loop, role: ContourRole=ContourRole.UNKNOWN, polygon=None, segments: list=None, styles: list=None) -> Optional[ClosedCurve]` — L22
- `_place(proxy: ClosedCurve, nodes: list) -> bool` — L70
- `_build_tree(proxies: list) -> list` — L79
- `_make_inner(proxy: ClosedCurve, parent_role: ContourRole=ContourRole.UNKNOWN, depth: int=1, parent: Optional[Contour]=None) -> Contour` — L92
- `_collect_inners(children: list, inners: list, classified_proxies: set, parent_role: ContourRole=ContourRole.UNKNOWN, depth: int=1, parent: Optional[Contour]=None)` — L113 — Appiattisce l'albero di contenimento in `cluster.inners` (ogni discendente
- **class** `HierarchyBuilder` — L150
  - methods: `__init__`, `build`, `_build_parts`, `_collect_loose`
- `assign_cluster_refs(curves: list, clusters: list, tolerance: float) -> None` — L218 — Scrive su ogni curva di `curves` (`result.loose`) `cluster_ref`: l'indice

#### `topo/core/healing/islands.py` — 95 lines

_core/healing/islands.py_

- **class** `Island` — L36 — Gruppo di Edge vicini, con la bbox che li contiene tutti.
  - methods: `width`, `height`
- `spatial_islands(edges: Iterable[Edge], gap_tolerance: float) -> List[Island]` — L54 — Union-find sulle coppie di Edge a distanza <= gap_tolerance (STRtree,

#### `topo/core/healing/normalizer.py` — 542 lines

_core/healing/normalizer.py_

- `_line_key(p1, p2) -> Tuple[float, float]` — L62 — Chiave della retta infinita per p1->p2: (angolo canonico, offset).
- `merge_collinear_overlaps(edges: Iterable[Edge], keep_junctions: bool=False) -> List[Edge]` — L89 — Fonde gruppi di LineSeg collineari (stessa retta infinita, `_line_key`)
- `_line_spans(group: List[Edge]) -> List[_Span]` — L183 — Span lungo la retta comune: `t` è la proiezione sulla direzione del
- `_merged_line(lo: _Span, hi: _Span)` — L207 — Il fuso di una catena collineare: nodi arrotondati, segmento a piena
- **class** `_Span` — L218 — Un edge come intervallo [lo, hi] sul suo supporto (posizione lungo la
- `_chain(spans: List[_Span]) -> List[List[_Span]]` — L234 — Ordina per `lo` e incatena gli span che si toccano o si sovrappongono:
- `_merge_on_carrier(edges: Iterable[Edge], segment_type: type, key: Callable[[Any], Hashable], chains_of: Callable[[List[Edge]], List[List[_Span]]], merged: Callable[[_Span, _Span], Tuple[Point, Point, Any]], keep_junctions: bool=False) -> List[Edge]` — L254 — Raggruppa per supporto (`key`) gli edge di `segment_type` con ruolo
- `_split_at_junctions(chain: List[_Span], junction: Callable[[Point], bool]) -> List[List[_Span]]` — L308 — Spezza una catena dove due span consecutivi si toccano SOLO (nessuna
- `_arc_key(center, radius) -> Tuple[float, float, float]` — L336 — Chiave del cerchio (centro+raggio) a precisione fissa — v. `_line_key`.
- `merge_cocircular_overlaps(edges: Iterable[Edge]) -> List[Edge]` — L345 — `merge_collinear_overlaps` per gli ArcSeg: fonde gruppi co-circolari
- `_arc_chains(group: List[Edge]) -> List[List[_Span]]` — L363 — Catene angolari di un gruppo sullo stesso cerchio. Se l'ultima catena
- `_merged_arc(lo: _Span, hi: _Span)` — L389 — Il fuso di una catena cocircolare: un arco, o un cerchio se chiude il
- `weld_degenerate_linesegs(edges: Iterable[Edge]) -> List[Edge]` — L409 — Salda (non cancella) i LineSeg `role == UNKNOWN` di lunghezza reale
- `refit_tessellations(edges: Iterable[Edge], max_segment: float=0.1, min_run: int=10, tolerance: float=0.02, node_decimals: int=3) -> List[Edge]` — L461 — Una catena di almeno `min_run` LineSeg (`role == UNKNOWN`) più corti di
- `_short_runs(short_edges: List[Edge]) -> list` — L514 — Catene massimali: percorsi fra nodi di grado != 2, o anelli.

#### `topo/core/healing/outer_scan.py` — 217 lines

_core/healing/outer_scan.py_

- **class** `OuterHit` — L45 — Un raggio per cui l'Edge è stato l'estremo.
- **class** `OuterCandidates` — L54 — Edge candidati a bordo esterno, con i raggi che li hanno scelti.
  - methods: `ids`, `hits_of`
- `outer_candidate_edges(edges: Iterable[Edge]) -> OuterCandidates` — L72 — Per ogni asse, una quota rappresentativa (punto medio) fra ogni coppia
- **class** `_Line` — L97
- **class** `_Arc` — L104
- `_pieces(edge: Edge) -> list` — L113
- `_on_arc(arc: _Arc, pt: Point) -> bool` — L127
- `_arc_point(arc: _Arc, angle: float) -> Point` — L131
- `_extent(piece, a: int) -> Tuple[float, float]` — L135 — (min, max) del pezzo lungo la coordinata `a` (0 = x, 1 = y).
- `_intersections(piece, a: int, level: float) -> List[Point]` — L150 — Punti del pezzo con coordinata `a` == level.
- `_scan_axis(pieces: list, axis: str, hits: Dict[int, List[OuterHit]]) -> int` — L184

#### `topo/core/healing/steps.py` — 398 lines

_core/healing/steps.py_

- **class** `LoopSearch` — L41 — Come find_loops() ha chiuso (o non chiuso) i giri, gradino per gradino.
- `split_non_finite(edges: List[Edge]) -> Tuple[List[Edge], List[Edge]]` — L56 — Separa gli Edge con una coordinata non finita (NaN, inf): ritorna
- `split_labeled(edges: List[Edge], is_structural: Optional[Callable[[str], bool]]=None) -> Tuple[List[Edge], List[Edge]]` — L77 — Separa gli Edge con un ruolo già deciso e non strutturale (cornice,
- `close_near_full_arcs(edges: List[Edge], tolerance: float, max_missing_angle: float=NEAR_FULL_ARC_MISSING) -> Tuple[List[Edge], int]` — L97 — Un ArcSeg coi due capi liberi diventa CircleSeg (stesso centro e raggio)
- `_is_near_full_arc(edge: Edge, graph, tolerance: float, max_missing_angle: float) -> bool` — L119
- `close_free_gaps(edges: List[Edge], tolerance: float) -> List[Edge]` — L134 — Chiude i gap fra estremi liberi entro `tolerance` col gap solver
- `dangling_splines(edges: List[Edge]) -> List[Edge]` — L149 — BSplineSeg aperte con almeno un estremo non collegato a nient'altro.
- `find_non_contour_edges(edges: List[Edge], tolerance: float) -> Set[int]` — L158 — id(edge) degli Edge che non chiudono un contorno (catene fra due nodi di
- `find_joining_edges(edges: List[Edge], candidate_ids: Set[int]) -> List[Edge]` — L169 — Gli Edge fra `candidate_ids` (di solito i non-contorno) che uniscono due
- `free_ends(edges: List[Edge], epsilon: float=0.0) -> List[Tuple[Tuple, float]]` — L197 — (estremo, distanza dal nodo più vicino) per ogni estremo che nessun altro
- `repair_merged_corners(edges: List[Edge], tolerance: float, exclude_ids: FrozenSet[int]=frozenset()) -> Tuple[List[Edge], int, list]` — L217 — Chiude gli angoli che il grafo esatto vede aperti e il clustering degli
- `find_loops(edges: List[Edge], non_contour_ids: Set[int], tolerance: float) -> LoopSearch` — L243 — La scala di heal() per chiudere i giri, esclusi `non_contour_ids`:
- `structural_loops(loops: List[list], is_structural: Optional[Callable[[str], bool]]=None) -> List[list]` — L287 — I loop in cui ogni edge con ruolo deciso è strutturale: un solo edge non
- `loops_to_curves(loops: List[list]) -> List[ClosedCurve]` — L298 — Un ClosedCurve per loop, col ruolo del primo edge; senza poligono valido, niente.
- `polygonize_edges(edges: List[Edge], tolerance: float) -> List[Polygon]` — L314 — Ultima spiaggia quando nessun grafo chiude: le facce dell'intero disegno
- `polygons_to_curves(polygons: List[Polygon]) -> List[ClosedCurve]` — L330 — Per poligono un ClosedCurve OUTER dal bordo esterno e uno INNER per
- `labeled_curves(edges: List[Edge]) -> list` — L351 — Gli Edge messi da parte da split_labeled() come curve col loro ruolo
- `build_hierarchy(curves: list, label: str='', source_file: str='', is_structural: Optional[Callable[[str], bool]]=None) -> Tuple[List[Cluster], list]` — L373 — Albero di contenimento sui ClosedCurve: ogni radice è un Cluster
- `_graph(edges: List[Edge], exclude_ids: FrozenSet[int], epsilon: float=0.0)` — L390
- `_ring_segments(coords) -> List[LineSeg]` — L396

#### `topo/core/island.py` — 397 lines

_core/island.py_

- **class** `IslandReading` — L58 — Cosa island() ha deciso su un'isola, pezzo per pezzo.
- `island(doc: Document, *, max_gap: float, tolerance: Optional[float]=None, is_structural: Optional[Callable[[str], bool]]=None) -> Result` — L76 — Legge `doc` per isole. Un Cluster per ogni contorno esterno che non
- `read_islands(edges: List[Edge], tolerance: float, max_gap: float) -> List[IslandReading]` — L146 — I pezzi a contatto (`spatial_islands` a `max_gap`) + `read_island` per
- `read_island(edges: List[Edge], tolerance: float, max_gap: float) -> IslandReading` — L169 — Un'isola: normalizza (nodi dagli estremi reali, tassellature rifittate,
- `_drop_boundary_duplicates(loops: list, reference: Optional[Polygon], band: float) -> list` — L218 — Scarta un giro chiuso il cui intero bordo sta entro `band` dal bordo di
- `_normalize(edges: List[Edge], tolerance: float, max_gap: float) -> List[Edge]` — L246 — Stessi passi di heal, ma sulla griglia fine della rete piana: prima i
- `_drop_redundant_meets(fixes: list, graph) -> list` — L262 — Scarta un fix "incontro" (due `MoveEndpoint` sullo stesso punto, la
- `_cluster(reading: IslandReading, source_file: str, tolerance: float) -> Cluster` — L292
- `_inners(loops, parent: Contour, tolerance: float) -> List[Contour]` — L300 — Un Contour inner per faccia di ogni giro chiuso; un giro senza
- `_loop_faces(loop, tolerance: float) -> list` — L307 — (segmenti, stili, poligono) per ogni faccia di un giro chiuso: una se
- `_faced(loops: list, tolerance: float)` — L332 — (giri con almeno una faccia, pezzi dei loro edge fuori da ogni faccia):
- `_off_faces(loop, faces) -> List[Edge]` — L346 — I tratti degli edge di `loop` lontani più di `band` dal bordo di ogni
- `_lines(geometry) -> list` — L369
- `_thinner_than(polygon: Polygon, width: float) -> bool` — L375 — Larghezza media (2·area/perimetro: per una striscia, la sua
- `_polygons(geometry) -> List[Polygon]` — L381
- `_contour(segments, styles, polygon, role, parent) -> Contour` — L387 — Il poligono resta quello dei pezzi della rete piana; i segmenti sono
- `_open(edges: List[Edge]) -> list` — L395

#### `topo/core/primitives/__init__.py` — 11 lines

No module-level function or class.

#### `topo/core/primitives/fitting.py` — 311 lines

_topo/core/primitives/fitting.py_

- **class** `_Part` — L44 — Un pezzo della sequenza: `kind` "line" o "curve", coi punti che copre (estremi condivisi coi vicini).
- `_within(points: List[Point], tolerance: float) -> bool` — L50 — Tutti i punti entro `tolerance` dalla corda primo-ultimo.
- `_signed_turn(a: Point, b: Point, c: Point) -> float` — L56 — Svolta con segno (gradi) in `b` andando da `a` a `c`: positiva a sinistra.
- `_split_stretch(points: List[Point], tolerance: float, scale: float, corner_turn_deg: float, arcs: bool) -> List[_Part]` — L62 — Un tratto senza spigoli: tutto entro `tolerance` dalla corda -> una linea;
- `_arc_through_ends(points: List[Point], tolerance: float) -> Optional[ArcSeg]` — L111 — L'arco che passa esattamente per il primo e l'ultimo punto (e per quello a
- `_fit_curve(points: List[Point], tolerance: float, arcs: bool, degree: int) -> List[Primitive]` — L132 — Un pezzo curvo: arco per gli estremi se basta (e `arcs`), altrimenti spline entro `tolerance` per gli estremi.
- `_line_fit(points: List[Point]) -> Tuple[Point, Point]` — L144 — Retta ai minimi quadrati sui punti: (punto, direzione unitaria).
- `_crossing(l1, l2) -> Optional[Point]` — L155
- `_length(points: List[Point]) -> float` — L164
- `_line_turn(a: _Part, b: _Part) -> float` — L168 — Di quanti gradi svolta chi passa dalla linea `a` alla linea `b`.
- `_restore_corners(parts: List[_Part], closed: bool, tolerance: float, scale: float, corner_turn_deg: float) -> List[_Part]` — L176 — Gli spigoli vivi che il campionamento ha smussato. Un pezzo curvo più
- `_join_seam(prims: List[Primitive], tolerance: float) -> List[Primitive]` — L220 — Un contorno senza spigoli si apre in un punto qualunque: se il primo e
- `_to_primitives(parts: List[_Part], tolerance: float, arcs: bool, degree: int) -> List[Primitive]` — L238
- `simplify_points(points: Sequence[Point], tolerance: float, scale: float, closed: bool=True, corner_turn_deg: float=DEFAULT_CORNER_TURN_DEG, arcs: bool=True, spline_degree: int=DEFAULT_SPLINE_DEGREE) -> List[Primitive]` — L249 — Primitive (LineSeg/ArcSeg/CircleSeg/BSplineSeg) per la sequenza di punti

#### `topo/core/primitives/polygon_builder.py` — 60 lines

_core/primitives/polygon_builder.py_

- `build_polygon(primitives: List[LineSeg \| ArcSeg \| BSplineSeg \| CircleSeg \| EllipseSeg], tolerance: float=0.01) -> Optional[Polygon]` — L19 — Costruisce un Polygon shapely da una lista di primitive geometriche.
- `_make_polygon(pts: list) -> Optional[Polygon]` — L48

#### `topo/core/primitives/segments.py` — 691 lines

_topo/core/primitives/segments.py_

- **class** `LineSeg` — L44
  - methods: `discretize`, `reversed`, `rotated`
- `_rotate_point(pt: Point, angle: float, origin: Point) -> Point` — L71 — Ruota `pt` di `angle` radianti (CCW) attorno a `origin`.
- `_angular_sweep(start: float, end: float, ccw: bool) -> float` — L83 — Angolo spazzato in radianti, sempre positivo, percorrendo da `start` a
- `point_on_circle(center: Point, radius: float, angle: float) -> Point` — L97 — Punto della circonferenza (`center`, `radius`) all'angolo dato (radianti).
- `angle_from_start(center: Point, start_angle: float, ccw: bool, pt: Point) -> float` — L102 — Angolo, in [0, 2π), da percorrere partendo da `start_angle` nel verso
- `_sagitta_step(radius: float, tolerance: float) -> Optional[float]` — L112 — Angolo massimo di una corda che dista al più `tolerance` dall'arco di
- **class** `ArcSeg` — L129
  - methods: `_sweep`, `discretize`, `_point_at`, `reversed`, `rotated`, `from_chord`
- `_bspline_find_span(t: float, degree: int, knots: List[float], n: int) -> int` — L258 — Indice `i` tale che `knots[i] <= t < knots[i+1]` (ricerca binaria, "The
- `_point_to_segment_distance(p: Point, a: Point, b: Point) -> float` — L276 — Distanza perpendicolare di `p` dal segmento `a`-`b` (0 se `a == b`).
- `_refine_segment(evaluate, t0: float, t1: float, p0: Point, p1: Point, tolerance: float, out: List[Point], depth: int, max_depth: int=8) -> None` — L288 — Suddivide `[t0, t1]` finché il punto medio (valutato con `evaluate(t)`)
- `_adaptive_polyline(evaluate, t_min: float, t_max: float, n_initial: int, tolerance: float) -> List[Point]` — L316 — Discretizza una curva parametrica valutata da `evaluate(t) -> Point` fra
- **class** `BSplineSeg` — L337 — B-spline (NURBS se `weights` è impostato): grado, punti di controllo,
  - methods: `clamped`, `closed`, `periodic`, `endpoints`, `reversed`, `rotated`, `_evaluate`, `discretize`, `_discretize`
- `segment_endpoints(segment) -> Tuple[Point, Point]` — L503 — (start, end) di un segmento primitivo, in coordinate XY non arrotondate.
- `segment_is_closed(segment, tolerance: float=DEFAULT_TOLERANCE) -> bool` — L529 — True se gli endpoint del segmento coincidono entro ``tolerance``.
- **class** `CircleSeg` — L541 — Cerchio geometrico puro.
  - methods: `reversed`, `rotated`, `discretize`
- **class** `EllipseSeg` — L587 — Ellisse (o arco ellittico) geometrico puro — stessa parametrizzazione del
  - methods: `_sweep`, `_point_at`, `discretize`, `reversed`, `rotated`

#### `topo/core/primitives/trim.py` — 185 lines

_topo/core/primitives/trim.py_

- `sub_segment(seg, a: Point, b: Point, via: Point)` — L26 — Il tratto di `seg` da `a` a `b` (punti sulla curva, o a una tolleranza
- `_on_line(seg: LineSeg, pt: Point) -> Point` — L47 — Proiezione di `pt` sulla retta, dentro i suoi due estremi.
- `_sub_angular(seg, a: Point, b: Point, via: Point)` — L61
- `_clamp(offset: float, sweep: float) -> float` — L86 — Un punto appena oltre un estremo (entro tolleranza) sta su quell'estremo.
- `_angle_of(seg, pt: Point) -> float` — L93 — Angolo (o parametro dell'ellisse) di `pt` visto dal centro della curva.
- `_angular(seg, lo: float, hi: float, ccw: bool)` — L104
- `_sub_spline(seg: BSplineSeg, a: Point, b: Point) -> Optional[BSplineSeg]` — L115
- `_spline_param(seg: BSplineSeg, pt: Point, lo: float, hi: float) -> float` — L145 — Parametro del punto della spline più vicino a `pt`: campioni, poi
- `_insert_to_degree(p: int, knots: List[float], cpw: List[Tuple[float, float, float]], t: float)` — L165 — Inserisce `t` nel vettore dei nodi finché compare `p` volte (agli

#### `topo/core/topology/edge.py` — 79 lines

_core/topology/edge.py_

- **class** `Edge` — L31 — Layer intermedio tra l'entità sorgente grezza (di qualsiasi formato) e il
  - methods: `of`

#### `topo/core/topology/graph.py` — 388 lines

_graph.py_

- **class** `Graph` — L59 — Grafo topologico interrogabile.
  - methods: `canonical`, `degree`, `branching_nodes`, `chains`, `merged_clusters`, `connected_components`, `open_nodes`, `pruned`, `items`, `get`
- `cluster_points(points: list, epsilon: float) -> Dict[Tuple, Tuple]` — L222 — Raggruppa punti 2D entro `epsilon` e restituisce {punto -> rappresentante}.
- `_close_self_loop(edge: Edge, epsilon: float)` — L285 — ArcSeg il cui sviluppo (raggio*sweep) supera epsilon -> CircleSeg (loop degenere vero). Altrimenti `None` (sl…
- `build_node_graph(edges: list, epsilon: float=0.0) -> Graph` — L301 — Costruisce il Graph da list[Edge].
- `_edge_coords(edge: Edge, reversed_flag: bool) -> list` — L355
- `_first_coord(edge: Edge)` — L362
- `_arrival_direction(edge: Edge, rev: bool)` — L369
- `_angular_deviation(arrival_dir, edge: Edge, rev: bool)` — L378

#### `topo/core/topology/loop_finder.py` — 253 lines

_loop_finder.py_

- **class** `LoopFinder` — L28
  - methods: `find`, `_loop_to_points`, `_deduplicate_loops`
- `segments_from_loop(loop) -> list` — L161 — Segmenti nativi di un loop, orientati nel verso di percorrenza.
- `edge_styles_from_loop(loop) -> list` — L187 — Stili grezzi (linetype/colore) di un loop, allineati 1:1 con
- `loop_geometry(loop) -> Optional[Tuple[list, list, Polygon]]` — L206 — (segmenti, stili, poligono) di un loop; None se i segmenti non chiudono
- `edges_to_open_curves(edges: list, exclude_ids: set) -> list` — L220 — Converte gli Edge non assorbiti da un loop strutturale in OpenCurve.

#### `topo/core/topology/noding.py` — 296 lines

_core/topology/noding.py_

- **class** `NodedEdges` — L51 — La rete piana: i pezzi, e per ognuno l'Edge da cui viene.
  - methods: `parent_of`
- `renode(edges: List[Edge], decimals: int=NODE_DECIMALS) -> List[Edge]` — L64 — Nodi di ogni Edge ricalcolati dal punto reale del segmento a
- `split_at_crossings(edges: List[Edge], tolerance: float, decimals: int=NODE_DECIMALS) -> NodedEdges` — L72 — Spezza ogni LineSeg/ArcSeg/CircleSeg nei punti dove incrocia un altro
- `interior_crossings(edges: List[Edge], tolerance: float) -> List[tuple]` — L98 — I punti dove due edge si attraversano senza che nessuno dei due finisca
- `_arc_s(seg, pt)` — L132
- `_param(seg, pt)` — L136 — (parametro, distanza del punto dal segmento).
- `_param_range(seg)` — L152
- `_piece_length(seg, p0, p1)` — L156
- `_circle_as_arc(circle, start_angle=0.0)` — L162 — Un cerchio come arco di 360° da `start_angle`: stessa matematica degli archi.
- `_cutters(edge)` — L172
- `_crossings(seg, cutter)` — L184 — Incroci reali (non sul prolungamento) fra `seg` e un cutter.
- `_split_params(edge, near, tol)` — L209
- `_with_nodes(edge, seg, decimals)` — L239
- `_split(edge, params, decimals)` — L245
- `_split_circle(edge, near, tol, decimals)` — L270
- `edge_geometry(edge: Edge)` — L291 — L'edge come geometria shapely: LineString discretizzata, Point se degenere.

#### `topo/core/topology/non_contour_edges.py` — 87 lines

_non_contour_edges.py_

- **class** `NonContourEdgeDetector` — L45
  - methods: `__init__`, `detect`

#### `topo/core/topology/outer_face.py` — 210 lines

_core/topology/outer_face.py_

- **class** `OuterFace` — L42 — Il contorno esterno trovato, e cosa il percorso ha scartato.
  - methods: `edges`
- `outer_face(edges: List[Edge], epsilon: float=0.0) -> Optional[OuterFace]` — L59 — Contorno esterno della rete `edges` (già piana: split_at_crossings). I
- `outer_face_passes(graph: Graph, component, n_edges: int) -> dict` — L88 — {id(edge): quante volte il bordo della faccia esterna di `component`
- `_outer_face_walk(graph: Graph, component, n_edges: int) -> list` — L103 — [(edge, dal nodo, al nodo)] lungo il bordo della faccia esterna.
- `_first_step(graph: Graph, component)` — L133 — L'edge che contiene il punto più a sinistra del componente, percorso
- `_leaving_angle(edge: Edge, node, graph: Graph) -> float` — L155 — Direzione con cui `edge` lascia `node`, letta a DIRECTION_SAMPLE (o a
- `_faces_union_loop(edges: List[Edge], epsilon: float)` — L176 — (loop, segments, styles, polygon) sul bordo dell'unione delle facce
- `_largest_loop(edges: List[Edge], epsilon: float)` — L202 — (loop, segments, styles, polygon) del giro di area massima.

#### `topo/core/topology/rim.py` — 154 lines

_topo/core/topology/rim.py_

- `face_segments(edges: List[Edge], polygon: Polygon, band: float)` — L29 — (segments, styles) lungo il bordo esterno di `polygon`, in senso
- `_side_cover(pts: list, geoms: list, band: float) -> List[set]` — L60 — Per ogni lato dell'anello, gli (edge, verso) che distano meno di `band`
- `_sense(geom, mid, p, q, step: float) -> int` — L77 — +1 se il lato p→q va nel verso di `geom` vicino a `mid`, -1 se contro.
- `_rim_runs(pts: list, geoms: list, cover: List[set]) -> list` — L87 — [((edge, verso), primo vertice, ultimo vertice)] lungo l'anello: copertura greedy
- `_trimmed(seg, a, b, via, band: float)` — L142 — `seg` da `a` a `b`: un capo entro `band` da un estremo di `seg` è

### `topo/` (root)

#### `topo/inspect.py` — 212 lines

_topo/inspect.py_

- `_h(title: str) -> None` — L36
- `_p(x, nd: int=2) -> str` — L40 — Formatta un punto (x, y) con nd decimali.
- `_role(r) -> str` — L47 — Nome del ruolo come stringa piatta ('outer'), non 'ContourRole.OUTER'.
- `inspect_document(doc, graph: bool=True, limit: Optional[int]=60) -> None` — L56 — Stampa un Document prodotto da un adapter (`topo_dxf.load_dxf`, …) o da
- `_describe_segment(seg) -> str` — L112
- `inspect_result(result, coords: bool=False) -> None` — L141 — Stampa un Result dopo heal(): il prodotto vero di topo.
- `_sub_part(i: int, cluster, coords: bool) -> None` — L189

### `topo/io/`

#### `topo/io/exporter.py` — 260 lines

_exporter.py_

- `build_metadata(cluster: Cluster, schema: dict=None, extra: dict=None) -> dict` — L24 — Costruisce il dict dei metadati per un Cluster
- `set_schema(schema: dict)` — L101 — Imposta uno schema esterno come schema attivo.
- `save_json(result: Result, path: str, indent: int=2, extra_metadata: Optional[Callable[[Cluster], dict]]=None)` — L118 — Salva i metadati in JSON secondo lo schema di metadata_schema.py.
- `to_json(result: Result, indent: int=2, extra_metadata: Optional[Callable[[Cluster], dict]]=None) -> str` — L148 — Restituisce i metadati come stringa JSON secondo schema. Vedi `save_json` per `extra_metadata`.
- `save_xml(result: Result, path: str, extra_metadata: Optional[Callable[[Cluster], dict]]=None)` — L171 — Salva i metadati in XML secondo lo schema di metadata_schema.py.
- `_dict_to_xml(d: dict, parent: ET.Element)` — L231 — Converte ricorsivamente un dict in sotto-elementi XML.
- `to_nester_input(result: Result) -> list` — L245 — Produce l'input per il nester: coordinate grezze + metadati base.

#### `topo/io/svg.py` — 200 lines

_io/svg.py_

- `_fmt(pts) -> str` — L24 — Lista di [x, y] → stringa 'x0,y0 x1,y1 …' per points= di polyline/polygon.
- `_shape(entry: dict, stroke_w: float, true_circles: bool) -> str` — L29
- `to_svg(result: Result, tolerance: float=0.05, include_loose: bool=True, include_texts: bool=True, padding: float=0.03, background: Optional[str]='#1e1e1e', true_circles: bool=True, stroke_width: Optional[float]=None, size: Optional[str]=None, units: Optional[str]=None, allow_invalid: bool=True, role_styles: Optional[Mapping[str, RoleStyle]]=None) -> str` — L46 — `Result` → stringa SVG completa (`<svg>…</svg>`).
- `save_svg(result: Result, path: str, **kwargs) -> None` — L173 — Scrive `to_svg(result, **kwargs)` su file.
- `_scan_bbox(vm: dict) -> Optional[list]` — L180 — bbox da tutti i punti del view model — fallback quando vm['bbox'] è None.

#### `topo/io/text.py` — 270 lines

_io/text.py_

- **class** `_Writer` — L42 — Numeri arrotondati e id dei contorni per una sola chiamata di `to_text`.
  - methods: `__init__`, `num`, `pt`, `deg`, `label`, `segment`, `spline`, `contour`, `detected_item`
- `_first_point(s) -> Optional[tuple]` — L152 — Un punto che sta sul segmento, per dire in quale pezzo cade.
- `_uniform_knots(knots, degree: int) -> bool` — L160 — Nodi bloccati agli estremi e passo interno costante: non serve scriverli.
- `to_text(result: Result, source_name: str='', decimals: int=3, spline_data: bool=False) -> str` — L171 — Il `Result` come testo per un modello linguistico (`.topo.md`).
- `save_text(result: Result, path: str \| Path, source_name: str='', decimals: int=3, spline_data: bool=False) -> None` — L267 — Scrive `to_text(result)` su `path` (per convenzione `<nome>.topo.md`).

#### `topo/io/view_model.py` — 196 lines

_io/view_model.py_

- `_color(role, role_styles: Mapping[str, RoleStyle]) -> str` — L29 — Hex CSS di un ruolo: la palette di topo con sopra la mappa del
- `_round_points(seq) -> list` — L36 — Lista di punti (2D o 3D) → lista di [x, y] arrotondati.
- `_poly_points(polygon) -> list` — L41 — Vertici dell'anello esterno di un polygon shapely come lista di [x, y].
- `_track(segments, tolerance: float) -> list` — L48 — Traccia aperta (lista di segmenti nativi) discretizzata a lista di [x, y].
- `_contour_entry(contour, tolerance: float, role_styles: Mapping[str, RoleStyle]) -> dict` — L53
- `_feature_entries(item, tolerance: float, role_styles: Mapping[str, RoleStyle]) -> list` — L61 — Un elemento dell'overlay (MAP.md D90) → una voce per contorno: ruolo,
- `_features(cluster, tolerance: float, role_styles: Mapping[str, RoleStyle]) -> dict` — L91 — `cluster.detected` per nome → lista di voci disegnabili.
- `_loose_entry(curve, tolerance: float, role_styles: Mapping[str, RoleStyle]) -> dict` — L101
- `_text_entry(text) -> dict` — L111
- `_bbox_of(clusters) -> Optional[list]` — L121
- `to_view_model(result: Result, tolerance: float=0.05, include_loose: bool=True, include_texts: bool=True, role_styles: Optional[Mapping[str, RoleStyle]]=None) -> dict` — L133 — `Result` → dizionario JSON-ready con la geometria di ogni feature.
- `_palette_dict(role_styles: Mapping[str, RoleStyle]) -> dict` — L189 — role (stringa) → colore hex, per la legenda di un renderer: i tre ruoli

### `topo/model/`

#### `topo/model/__init__.py` — 60 lines

_topo/model/__init__.py_

- `__getattr__(name)` — L54

#### `topo/model/cluster.py` — 119 lines

_model/cluster.py_

- **class** `Cluster` — L15
  - methods: `features`, `overlay_voids`, `polygon_with_holes`, `bbox`, `area`, `summary`, `to_dict`

#### `topo/model/contour.py` — 66 lines

_model/contour.py_

- **class** `Contour(ClosedCurve)` — L36
  - methods: `from_segments`, `to_dict`

#### `topo/model/curve.py` — 80 lines

_model/curve.py_

- **class** `Curve` — L38 — Radice della gerarchia. Porta solo identità semantica e traceability.
- **class** `ClosedCurve(Curve)` — L48 — Curva chiusa: ha un polygon e una lista di segmenti.
  - methods: `area`, `bbox`
- **class** `OpenCurve(Curve)` — L74 — Curva aperta: ha segmenti ma non un polygon.

#### `topo/model/detected.py` — 74 lines

_topo/model/detected.py_

- **class** `DetectedFeature(Protocol)` — L23 — Contratto minimo di un elemento attaccato a `DetectedFeatures`: la
- **class** `DetectedFeatures` — L34 — Contenitore aperto per nome: ogni consumatore scrive sotto il nome che
  - methods: `attach`, `add`, `get`, `items`, `names`

#### `topo/model/document.py` — 54 lines

_model/document.py_

- **class** `Document` — L37 — Documento di dominio prodotto da load_dxf() / load_svg() / load_pdf().
  - methods: `node_tolerance`

#### `topo/model/result.py` — 60 lines

- **class** `Result` — L12 — Risultato completo di una sessione topo su un file DXF.
  - methods: `cluster_count`, `has_issues`, `to_dict`

#### `topo/model/role.py` — 150 lines

_model/role.py_

- **class** `ContourRole(str, Enum)` — L44 — I tre ruoli che il motore topologico conosce. **Non esaustivo** — un
- `is_structural_role(role) -> bool` — L79 — True se ``role`` è OUTER o INNER per il motore (vedi ``STRUCTURAL_ROLES``).
- `feature_role(contour, item_role)` — L91 — Il ruolo con cui si disegna un contorno di un elemento dell'overlay (D90):
- `normalize_role(value) -> str` — L113 — Ripulisce una stringa-ruolo che arriva dal chiamante (``RoleRule``,
- `role_str(role) -> str` — L143 — Valore stringa di un ruolo, che sia una costante ``ContourRole`` o una

#### `topo/model/role_rule.py` — 136 lines

_model/role_rule.py_

- **class** `RoleRule` — L41 — Una regola: se TUTTE le condizioni date sono vere, la linea prende `role`.
  - methods: `reads_style`, `matches`
- `resolve_role(rules: Sequence[RoleRule], name: str, style: Optional[EdgeStyle]=None) -> str` — L106 — Ruolo della prima regola che matcha, in ordine; `unknown` se nessuna.
- `name_rules(mapping: Dict[str, str]) -> List[RoleRule]` — L114 — Scorciatoia: {nome: ruolo} → una RoleRule(name=...) per voce.
- `_color_rgb(value: Union[RGB, str]) -> RGB` — L123 — (r, g, b) da una tupla, da "#rrggbb" o da un nome di base ("cyan").

#### `topo/model/style.py` — 130 lines

_model/style.py_

- **class** `EdgeStyle` — L45 — Campi (tutti opzionali: un `EdgeStyle()` vuoto è "la sorgente non lo dice"):
  - methods: `is_dashed`, `dash_kind`
- **class** `RoleStyle` — L80 — Come il chiamante vuole disegnato un ruolo in uscita (D37, D128). Il
- `role_style(role, role_styles: Optional[Mapping[str, RoleStyle]]=None) -> RoleStyle` — L117 — Come si disegna `role`: la palette di topo (o il grigio di un ruolo di

#### `topo/model/text.py` — 106 lines

_topo/model/text.py_

- **class** `RenderedText` — L35 — Una stringa dentro l'immagine appiattita di un testo (`Text.rendered`).
- **class** `RenderedGeometry` — L44 — L'immagine che la sorgente disegna attorno a una stringa (linee, frecce,
  - methods: `is_empty`
- **class** `Text` — L62 — Un testo della sorgente. ``position`` è il punto d'ancoraggio — dove un

### `topo/` (root)

#### `topo/primitives.py` — 23 lines

_topo/primitives.py_

No module-level function or class.

### `topo/rules/`

#### `topo/rules/metadata_schema.py` — 38 lines

_metadata_schema.py_

No module-level function or class.

#### `topo/rules/validator.py` — 167 lines

_rules/validator.py_

- `validate(doc: Document) -> Result` — L29 — Valida l'input prima di heal().
- `validate_result(result: Result) -> Result` — L128 — Valida i Cluster dentro un Result già popolato da heal().

### `topo/` (root)

#### `topo/steps.py` — 52 lines

_topo/steps.py_

No module-level function or class.

### `topo/tools/`

#### `topo/tools/__init__.py` — 18 lines

_topo/tools/_

No module-level function or class.

#### `topo/tools/anchor.py` — 188 lines

_topo/tools/anchor.py_

- `anchor_texts(result: Result, snap_distance: float=0.0, pointer_distance: float=POINTER_TARGET_DISTANCE) -> Result` — L30 — Assegna ``cluster_ref`` a ogni testo di ``result.texts``.
- `pointer_target(result: Result, text: Text, distance: float=POINTER_TARGET_DISTANCE) -> Optional[str]` — L69 — L'elemento indicato dalla punta (``pointer[0]``) di ``text``, come
- `measured_references(result: Result, text: Text, distance: float=POINTER_TARGET_DISTANCE) -> list` — L97 — Gli elementi su cui cadono i ``measured_points`` di ``text``, come
- `_on_boundary(elements, point, distance: float) -> Optional[str]` — L115 — L'elemento col bordo più vicino a ``point``, se entro ``distance``.
- `resolve_target(result: Result, target: Optional[str]) -> Any` — L122 — L'oggetto (contorno o feature) a cui punta un ``target``, o ``None``.
- `_elements(result: Result) -> Iterator[Tuple[str, Any, bool]]` — L143 — (percorso, geometria shapely, è chiuso) per contorni e feature di ogni cluster.
- `_item_geometry(item)` — L158
- `_size(geom, closed: bool) -> float` — L166 — A parità di distanza vince l'elemento più piccolo: un foro sul bordo del pezzo.
- `_assign(position, refs, snap_distance: float) -> Optional[int]` — L171
- `_nearest_within(probe: Point, refs, snap_distance: float) -> Optional[int]` — L180 — L'indice della parte più vicina a ``probe``, se entro ``snap_distance`` (> 0).

#### `topo/tools/inject.py` — 97 lines

_inject.py_

- `inject(result, data_injector: Optional[Callable]=None, snap_distance: float=0.0)` — L39 — Arricchisce i Cluster con i dati estratti da un `data_injector` esterno.
- `_texts_by_part(result, snap_distance: float) -> Dict[int, List[str]]` — L74 — Testi di `result.texts` per indice di parte. Un testo coperto da più

#### `topo/tools/non_contour.py` — 51 lines

_topo/tools/non_contour.py_

- `non_contour_candidates(doc: Document, tolerance: Optional[float]=None) -> List[Edge]` — L41 — Edge di `doc.edges` che il criterio topologico di `heal()` escluderebbe dal

#### `topo/tools/promote.py` — 41 lines

_topo/tools/promote.py_

- `promote(result: Result, curve: OpenCurve \| ClosedCurve, cluster: Cluster, name: str, item: Optional[Any]=None) -> None` — L20 — Toglie `curve` da `result.loose` e mette `item` (la curva stessa se

#### `topo/tools/rotate.py` — 268 lines

_topo/tools/rotate.py_

- `structural_segments(result: Result, include_inners: bool=False) -> list` — L73 — Segmenti nativi dei contorni strutturali di ogni cluster: sempre
- `longest_structural_segment(result: Result, include_inners: bool=False) -> Tuple[Optional[object], float, Optional[float]]` — L89 — `(segment, length, angle_deg)` del segmento più lungo fra
- `_rotate_contour(contour: ClosedCurve, angle_rad: float, origin: Point) -> ClosedCurve` — L108
- `rotate_cluster(cluster: Cluster, angle_rad: float, origin: Point=(0.0, 0.0)) -> Cluster` — L117 — Nuovo `Cluster` con `outer`/`inners` ruotati di `angle_rad` (radianti,
- `rotate_result(result: Result, angle_rad: float, origin: Point=(0.0, 0.0)) -> Result` — L147 — Nuovo `Result` con ogni cluster (`rotate_cluster`), `loose`
- `rotate_document(doc: Document, angle_rad: float, origin: Point=(0.0, 0.0)) -> Document` — L187 — Nuovo `Document` con ogni `edge.segment` ruotato di `angle_rad`
- `_result_bbox_center(result: Result) -> Point` — L224 — Centro del bbox unito degli outer di tutti i cluster — vedi `rotate_to_longest`.
- `rotate_to_longest(result: Result, include_inners: bool=False, target_angle_deg: float=0.0, origin: Optional[Point]=None) -> Tuple[Result, float]` — L240 — Ruota `result` (già sano, da un `heal()` già fatto dal chiamante) in modo

#### `topo/tools/split.py` — 157 lines

_topo/tools/split.py_

- `split(result: Result, namer: Optional[Callable[[int, Cluster], str]]=None, min_area: float=DEFAULT_MIN_CLUSTER_AREA) -> List[Result]` — L26 — Un `Result` per parte, nell'ordine delle parti tenute.
- `cluster_passes_min_area(cluster: Cluster, min_area: float) -> bool` — L83 — True se la parte supera la soglia di area minima (min_area <= 0 = nessun filtro).
- `_assign(items, outers, probe_of, covering: bool) -> dict[int, list]` — L88 — id(cluster) → gli elementi che gli appartengono. Con `covering` vince la
- `_assign_loose(result: Result, outers) -> dict[int, list]` — L111 — id(cluster) → le curve sciolte che gli vanno, nell'ordine di
- `_local(items: list, i: int) -> list` — L127 — Copie di `items` con `cluster_ref` riferito al Result di una parte sola.
- `_probe_point(curve) -> Optional[tuple]` — L137 — Punto rappresentativo di una curva, per darla alla parte più vicina.
- `_outer_polygons(clusters) -> list` — L151 — (cluster, poligono dell'outer) per ogni cluster che ne ha uno.

#### `topo/tools/tabs.py` — 442 lines

_topo/tools/tabs.py_

- `_sub(a: Point, b: Point) -> Point` — L54
- `_add(a: Point, b: Point) -> Point` — L58
- `_scale(v: Point, s: float) -> Point` — L62
- `_dot(a: Point, b: Point) -> float` — L66
- `_unit_vector(v: Point) -> Point` — L70
- `_perp(v: Point) -> Point` — L77 — Ruota `v` di 90° (verso arbitrario, coerente fra le due chiamate).
- **class** `BridgeTab` — L87 — Risultato di un singolo ponte. `*_cut_{a,b}` sono `(punto, indice_lato)`
- `bridge_tabs(parent_points: List[Point], child_points: List[Point], anchor_parent: Point, anchor_child: Point, tab_width: float) -> BridgeTab` — L101 — Costruisce UNA linguetta fra `child_points` (contorno chiuso, il figlio
- `_cumulative_lengths_closed(points: List[Point]) -> List[float]` — L161 — `cum[i]` = distanza cumulata da `points[0]` a `points[i]` (lato i-1->i).
- `_split_closed_polyline_at_cuts(points: List[Point], cuts: List[Tuple[int, Point, int]]) -> List[List[Point]]` — L169 — Spezza il contorno chiuso `points` sui tagli in `cuts` — ognuno
- **class** `NestedBridgeResult` — L218 — Risultato per UNA coppia isola/genitore-diretto trovata nella gerarchia.
- `_discretize_closed(contour, tolerance: float) -> List[Point]` — L227 — Punti grezzi chiusi di un `Contour` (senza il punto di chiusura duplicato).
- `_ray_exit_point(points: List[Point], center: Point, direction: Point) -> Point` — L235 — Punto in cui il raggio da `center` verso `direction` esce dal contorno chiuso `points`.
- `is_tab_island(contour) -> bool` — L246 — `contour` è un'isola da collegare al genitore diretto: profondità pari
- `_outward_normal(points: List[Point], at: Point) -> Point` — L255 — Normale unitaria uscente dal contorno chiuso `points` nel suo punto
- `_split_pair(contour, parent, child_points: List[Point], parent_points: List[Point], bridges: List[BridgeTab]) -> NestedBridgeResult` — L282 — Spezza isola e genitore sui tagli di tutte le `bridges` della coppia, insieme.
- `_bridge_at(child_points: List[Point], parent_points: List[Point], anchor: Point, tab_width: float) -> BridgeTab` — L303 — Una linguetta nel punto `anchor`, scelto dal chiamante. Si proietta sul
- **class** `TabbedIsland` — L331 — Un'isola collegata da `bridge_parent_tabs`: i suoi tratti fra una linguetta e l'altra.
- **class** `ParentBridgeResult` — L338 — Risultato di `bridge_parent_tabs` per UN genitore e le sue isole. Se
- `bridge_parent_tabs(parent, island_anchors: Sequence[Tuple['Contour', Sequence[Point]]], tab_width: float, discretize_tolerance: float=0.05) -> ParentBridgeResult` — L351 — Collega le isole di UN genitore (`island_anchors`: coppie isola, punti)
- `bridge_nested_tabs(cluster, tab_width: float, tab_count: int=4, discretize_tolerance: float=0.05) -> List[NestedBridgeResult]` — L408 — Cammina `cluster.inners` (che porta `depth`/`parent` per ogni contorno,

### `topo_dxf/` (root)

#### `topo_dxf/__init__.py` — 62 lines

_topo_dxf/__init__.py_

No module-level function or class.

#### `topo_dxf/adapter.py` — 313 lines

_topo_dxf/adapter.py_

- `_raw_linetype_pattern(lt_entry) -> Optional[Tuple[float, ...]]` — L39 — Pattern grezzo (lunghezza totale + tratti con segno, `+` = tratto,
- `_color_rgb(aci: int, true_color: Optional[int]) -> Optional[Tuple[int, int, int]]` — L62 — Il colore effettivo in RGB: il true color se c'è, altrimenti l'indice
- `_entity_style(entity) -> EdgeStyle` — L73 — Cattura l'aspetto EFFETTIVO (linetype/colore) di un'entità DXF in un
- `_segment_key(segment) -> tuple` — L168 — Chiave univoca per deduplicazione.
- **class** `DxfAdapter` — L222 — Adapter DXF che traduce entità DXF in Edge del dominio Topo.
  - methods: `__init__`, `to_edges`

#### `topo_dxf/exporter.py` — 386 lines

_topo_dxf/exporter.py_

- `ensure_linetype(doc, name: str, pattern: Optional[Tuple[float, ...]]=None, description: str='') -> Optional[str]` — L23 — Garantisce che il linetype `name` esista in `doc` e ne ritorna il nome;
- `dxf_pattern(dash: Optional[Tuple[float, ...]]) -> Optional[Tuple[float, ...]]` — L49 — Il tratto di topo (segni con segno) nel pattern della tabella DXF, che
- `_style_attribs(doc, layer: str, style: Optional[EdgeStyle]=None) -> dict` — L57 — dxfattribs per una entità in output: layer + linetype della sorgente, se
- `arc_seg_to_bulge(arc: ArcSeg) -> float` — L85
- `_seg_end_point(seg) -> Optional[tuple]` — L101
- `segments_to_pts_with_bulge(segments: list) -> list` — L109
- `_add_spline(spline: BSplineSeg, msp, layer: str, style: Optional[EdgeStyle]=None) -> object` — L124 — Materializza una BSplineSeg come SPLINE nativa, ricostruita dalla primitiva
- `_add_ellipse(ellipse: EllipseSeg, msp, layer: str, style: Optional[EdgeStyle]=None) -> object` — L152 — Materializza una EllipseSeg come ELLIPSE nativa — mai una spline: topo
- `write_segments(segments: List, msp, layer: str, styles: Optional[List]=None) -> Optional[object]` — L179 — Materializza una lista di segmenti puri su msp.
- `write_native_segments(segments: List, msp, layer: str, styles: Optional[List]=None) -> List[object]` — L258 — Materializza segmenti aperti come geometria NATIVA, una entità DXF per
- `write_open_segments(segments: List, msp, layer: str, styles: Optional[List]=None) -> List[object]` — L316 — Materializza una lista di segmenti puri come geometria APERTA su msp.

#### `topo_dxf/inspect.py` — 141 lines

_topo_dxf/inspect.py_

- `_header(title: str) -> None` — L28
- `_point(x, nd: int=2) -> str` — L32 — Formatta un punto (x, y) con nd decimali.
- `inspect_dxf(path: str, entities: bool=True, limit: Optional[int]=40) -> None` — L37 — Apre un DXF/DWG con ezdxf e stampa cosa contiene, senza toccare topo.
- `_describe_dxf_entity(e) -> str` — L77
- `inspect_file(path: str, tolerance: float=DEFAULT_NODE_TOLERANCE, role_rules: Sequence[RoleRule]=(), run_heal: bool=True, entities: bool=True, coords: bool=False) -> None` — L114 — Apre un file e stampa i tre livelli in fila:

#### `topo_dxf/layers.py` — 95 lines

_topo_dxf/layers.py_

- `role_to_dxf_layer(role, element: object=None, layers: Optional[LayerMap]=None) -> str` — L57 — Nome del layer DXF per `role`. La scelta del chiamante (`layers`, chiavi
- `color_for_role(role) -> Optional[int]` — L79 — Il colore della palette di topo per `role` (D128) come indice ACI:
- `_slug(role) -> str` — L85

#### `topo_dxf/loader.py` — 389 lines

_topo_dxf/loader.py_

- `_text_signature(text) -> tuple` — L63
- `_merge_texts(base: list, extra: list) -> None` — L68 — Aggiunge a `base` i testi di `extra` non già presenti (per firma).
- `_warn_non_roundtrip_types(msp, sink: list, verbose: bool=False) -> None` — L86 — Avvisa sui tipi di entità che to_dxf() non riscrive (HATCH, IMAGE, …).
- `_emit(sink: list, msg: str, verbose: bool=False) -> None` — L99 — Aggiunge `msg` al canale warnings; lo stampa solo se verbose.
- `_configure_odafc(sink: list=None, verbose: bool=False) -> None` — L107 — Punta l'addon `odafc` all'eseguibile ODA File Converter.
- `_read_dwg(path: str, sink: list=None, verbose: bool=False)` — L148 — Legge un file DWG usando ezdxf.addons.odafc (wrapper di ODA File Converter).
- `_upgrade_to_r2010(doc, sink: list=None, verbose: bool=False) -> object` — L180 — Converte un documento DXF legacy in R2010.
- `load_dxf(path: str, upgrade: bool=False, explode_inserts: bool=True, flatten_z_flag: bool=True, verbose: bool=False, tolerance: float=DEFAULT_NODE_TOLERANCE, role_rules: Sequence[RoleRule]=(), ignore_layers=None, skip_layers: Sequence[str]=SKIP_LAYERS) -> Document` — L219 — Apre un documento DXF o DWG e lo traduce in un Document.
- `document_from_msp(msp, tolerance: float=DEFAULT_NODE_TOLERANCE, role_rules: Sequence[RoleRule]=(), ignore_layers=None, source_path: str='', skip_layers: Sequence[str]=SKIP_LAYERS) -> Document` — L349 — Costruisce un Document da un modelspace ezdxf già aperto.

#### `topo_dxf/mtext.py` — 45 lines

_topo_dxf/mtext.py_

- `clean_mtext(txt) -> str` — L18 — Testo semplice da una stringa MTEXT grezza: rimuove i codici di
- `mleader_text(entity) -> Optional[str]` — L37 — Testo grezzo di un MULTILEADER (prima della pulizia), None se assente.

#### `topo_dxf/parser.py` — 167 lines

_topo_dxf/parser.py_

- **class** `DxfEntityDispatcher` — L20 — Centralizza il routing per tipo di entità DXF.
  - methods: `__init__`, `parse`
- `_parse_line(entity, rev) -> tuple` — L47
- `_parse_arc(entity, rev) -> ArcSeg` — L57
- `_parse_spline(entity, rev) -> BSplineSeg` — L72 — Solo la geometria (MAP.md D135): grado, punti di controllo, nodi, pesi
- `_parse_circle(entity) -> CircleSeg` — L101
- `_parse_ellipse(entity, rev) -> EllipseSeg` — L108 — Un'ELLIPSE DXF è sempre percorsa CCW da `start_param` a `end_param`
- `_parse_polyline(entity, rev) -> list` — L126

#### `topo_dxf/recipes.py` — 58 lines

_topo_dxf/recipes.py_

- `split_to_files(doc: Document, output_folder, label='', source_file='', tolerance=None, namer=None, include_texts=True, min_area=DEFAULT_MIN_CLUSTER_AREA, exclude_types=None, text_layer=LAYER_ANNOTATION, is_structural=None, role_styles=None, layers=None) -> Result` — L25 — Pipeline multi-pezzo + salvataggio su disco: heal → `topo.split` →

#### `topo_dxf/sanitize.py` — 252 lines

_topo_dxf/sanitize.py_

- `normalize_ocs(msp, verbose: bool=False) -> None` — L19 — Normalizza il vettore di estrusione di tutte le entità OCS nel modelspace.
- `flatten_z(msp, verbose: bool=False) -> int` — L29 — Porta a 0 tutte le coordinate Z != 0 per LINE, ARC, CIRCLE,
- `sanitize(msp, flatten_z_flag: bool=True, verbose: bool=False) -> int` — L88 — Esegue tutti i sanitizer in sequenza sul modelspace ricevuto.
- `_explode_inserts(msp, sink: list=None) -> int` — L106 — Esplode tutti gli INSERT (blocchi) nel modelspace in entità primitive.
- `_key_for(entity) -> Optional[Hashable]` — L154 — Restituisce una chiave hashable che identifica univocamente
- `extract_keyed_entities(msp) -> List[Tuple[Hashable, Any]]` — L201 — Produce la lista (key, entity) per tutte le entità del msp.
- `delete_entities(refs: List[Any], msp) -> None` — L210 — Elimina le entità dal msp in-place.
- `_find_duplicates(keyed_entities: Iterable[Tuple[Hashable, Any]]) -> List[Any]` — L216 — Restituisce i ref delle entità duplicate (seconda occorrenza in poi).
- `deduplicate(msp) -> int` — L243 — Shortcut: estrae chiavi, trova duplicati, li elimina.

#### `topo_dxf/text_extractor.py` — 574 lines

_topo_dxf/text_extractor.py_

- **class** `DxfTextExtractor` — L43 — Traduce le entità di testo di un msp in list[Text].
  - methods: `__init__`, `extract`
- `_to_text(entity, role_rules: Sequence[RoleRule]=()) -> Optional[Text]` — L61
- `text_anchor(entity) -> Optional[Tuple[float, float]]` — L98 — Punto d'ancoraggio XY di un'entità di testo.
- `_mleader_anchor(entity) -> Optional[Tuple[float, float]]` — L117 — Primo vertice della direttrice di un MULTILEADER.
- `_dimension_anchor(entity) -> Optional[Tuple[float, float]]` — L129 — Def-point di una DIMENSION.
- `_fallback_anchor(entity) -> Optional[Tuple[float, float]]` — L137 — Cerca un qualsiasi attributo-punto usabile.
- `_extract_content(entity) -> str` — L153 — Testo pulito dell'entità, stringa vuota se non ne ha.
- `_width_factor(entity) -> float` — L163 — Stretch orizzontale effettivo del testo (1.0 = nessuno).
- `_dimension_text_of(entity, pos, role: str) -> Optional[Text]` — L193
- `_shown_text(override: Optional[str], rendered: RenderedGeometry, measured: Optional[float]) -> str` — L236 — La stringa che la quota mostra: l'override con ``<>`` sostituito dalla
- `_shown_value(rendered: RenderedGeometry, measured: Optional[float]) -> str` — L249 — La misura come la mostra il disegno (precisione, virgola), o calcolata.
- `_dimension_semantics(entity) -> Tuple[str, Optional[float]]` — L259 — (dim_type, valore misurato) di una DIMENSION.
- `_dimension_override(entity) -> Optional[str]` — L277 — Override esplicito del testo quota, o None se la quota mostra la misura.
- `_measured_points(entity, dim_type: str) -> List[Tuple[float, float]]` — L302 — I punti sulla geometria fra cui la quota misura, dai def-point:
- `_synthesize_dimension(entity)` — L320 — Ricostruisce l'immagine di una DIMENSION lineare dai def-point, quando il
- `_leader_text(entity, pos, role: str, source_kind) -> Optional[Text]` — L378
- `_leader_vertices(entity) -> List[Tuple[float, float]]` — L415
- `_render_block(entity) -> RenderedGeometry` — L432 — Espande l'immagine dell'entità in strokes/fills/texts puri.
- `_flatten_virtual(entity)` — L471 — Espande `virtual_entities()` ricorsivamente sugli INSERT (frecce a blocco).
- `_text_item(v) -> Optional[RenderedText]` — L480
- `_bbox_center(polylines) -> Optional[Tuple[float, float]]` — L497
- `_xy(p) -> Tuple[float, float]` — L505
- `_flattened_points(entity) -> List[Tuple[float, float]]` — L509 — Punti di un ARC o CIRCLE appiattito alla sagitta `_ARC_SAGITTA`.
- `_polyline_points(pl) -> Tuple[List[Tuple[float, float]], bool]` — L517
- `_solid_points(solid) -> List[Tuple[float, float]]` — L529 — SOLID/TRACE: 4 vertici in ordine 'a farfalla' → poligono convesso.
- `_dimension_text(entity) -> str` — L541 — Testo visualizzato della quota, quando l'immagine non è espandibile.
- `_dimension_measurement(entity) -> str` — L560
- `_f(value) -> Optional[float]` — L570

#### `topo_dxf/writer.py` — 380 lines

_topo_dxf/writer.py_

- `to_dxf(result: Result, source_doc: Optional[Document]=None, filter_cluster: Optional[Callable[[Cluster], bool]]=None, include_texts: bool=True, include_loose: bool=True, text_layer: str=LAYER_ANNOTATION, role_styles: Optional[Mapping[str, RoleStyle]]=None, layers: Optional[LayerMap]=None, allow_invalid: bool=True, exclude_types: Optional[Set[str]]=None) -> 'ezdxf.document.Drawing'` — L35 — Crea un documento DXF nuovo (R2010) e vi materializza il Result.
- `_write_texts(msp, texts: List[Text], book: '_Layers', text_layer: str) -> None` — L147 — Riscrive i testi della sorgente nel documento di output, tutti: quale
- `_emit_text(msp, text: Text, layer: str) -> None` — L168 — Con un'immagine (`rendered`: quote e richiami della sorgente) si
- `_emit_string(msp, note: Text, attribs: dict) -> None` — L179
- `_emit_rendered(msp, ann, attribs: dict) -> None` — L205 — Ri-materializza l'immagine appiattita (DIMENSION / LEADER di un DXF). I testi in
- `_write_loose(msp, result: Result, book: '_Layers') -> None` — L234 — Materializza `result.loose`, tutte: in un file per parte le ha
- `_write_attached_features(msp, cluster: Cluster, book: '_Layers') -> None` — L257 — Ogni collezione di `cluster.detected` (D70, D90): topo non sa cosa siano.
- `_remove_excluded_entities(msp, excluded_upper: Set[str]) -> None` — L289
- `_contour_role(contour, default: ContourRole)` — L295 — Il ruolo di contorno nel grafo: outer/inner se lo porta, `default` se
- **class** `_Layers` — L302 — I layer di un documento in scrittura (D128): il nome viene dalla scelta
  - methods: `__init__`, `setup`, `_setup_role`, `for_role`, `ensure`
- `_apply_role_style(doc, layer, role, style: RoleStyle) -> None` — L358 — Un `RoleStyle` (D37, D128) sul layer: colore in true color (l'ACI non ha

#### `topo_dxf/xdata.py` — 82 lines

_topo_dxf/xdata.py_

- `_outer_entity(doc)` — L17 — L'entità su layer OuterContour che porta gli XDATA: prima una polilinea,
- `write_metadata_to_dxf(doc, cluster: Cluster, extra: Optional[dict]=None)` — L28 — Scrive i metadati come XDATA sull'entità OuterContour.
- `read_metadata_from_dxf(doc) -> dict` — L57 — Legge i metadati TOPO XDATA dall'entità OuterContour.

### `topo_pdf/` (root)

#### `topo_pdf/__init__.py` — 13 lines

_topo_pdf/__init__.py_

No module-level function or class.

#### `topo_pdf/extractor_adapter.py` — 86 lines

_topo_pdf/extractor_adapter.py_

- `extract_drawings_from_page(page: Any) -> List[Dict[str, Any]]` — L23 — Estrae i disegni vettoriali dalla pagina PDF e normalizza l'output.

#### `topo_pdf/geometry_adapter.py` — 63 lines

_topo_pdf/geometry_adapter.py_

- `transform_point(x: float, y: float, page_height: float) -> tuple[float, float]` — L27 — Converte un punto da punti PDF (pt) a millimetri (mm)
- `sample_bezier_cubic(p1: tuple, p2: tuple, p3: tuple, p4: tuple, num_segments: int=16) -> list[tuple[float, float]]` — L37 — Campiona una curva di Bezier cubica in un set di punti lineari (poligonale).

#### `topo_pdf/graph_adapter.py` — 31 lines

_topo_pdf/graph_adapter.py_

- `map_sanitized_item_to_edge(item: tuple, page_idx: int) -> Edge \| list[Edge] \| None` — L12

#### `topo_pdf/loader.py` — 85 lines

_topo_pdf/loader.py_

- `load_pdf(path: str, snap_tolerance: float=0.15) -> list` — L22 — Apre un documento PDF, estrae le geometrie vettoriali da tutte le pagine,

#### `topo_pdf/sanitize.py` — 102 lines

_topo_pdf/sanitize.py_

- `sanitize_pdf_geometries(raw_items: list, page_height: float, snap_tolerance: float=0.15) -> list` — L12 — Prende gli item geometrici grezzi estratti dall'extractor, applica la conversione

## Internal dependencies

Which `topo, topo_dxf, topo_pdf` modules each module imports — "what works with what". Modules with no internal import are omitted.

| module | imports |
|---|---|
| `topo/__init__.py` | `topo` · `topo.core` · `topo.core.geometry_input` · `topo.core.heal` · `topo.core.island` · `topo.core.primitives.fitting` · `topo.inspect` · `topo.io.exporter` · `topo.io.svg` · `topo.io.text` · `topo.io.view_model` · `topo.model` · `topo.model.role` · `topo.model.role_rule` · `topo.model.style` · `topo.rules.validator` · `topo.tools.anchor` · `topo.tools.inject` · `topo.tools.non_contour` · `topo.tools.promote` · `topo.tools.rotate` · `topo.tools.split` |
| `topo/core/geometry/__init__.py` | `topo.core.geometry.axis` · `topo.core.geometry.build` · `topo.core.geometry.intersections` · `topo.core.geometry.lines` · `topo.core.geometry.measure` · `topo.core.geometry.regions` · `topo.core.geometry.shape` |
| `topo/core/geometry/axis.py` | `topo.core.primitives.segments` |
| `topo/core/geometry/build.py` | `topo.core.primitives.segments` |
| `topo/core/geometry/intersections.py` | `topo.core.primitives.segments` |
| `topo/core/geometry/measure.py` | `topo.core.geometry.regions` · `topo.core.primitives.segments` |
| `topo/core/geometry/points.py` | `topo.core.primitives.segments` |
| `topo/core/geometry/regions.py` | `topo.core.geometry.intersections` · `topo.core.primitives.polygon_builder` · `topo.core.primitives.segments` · `topo.core.primitives.trim` |
| `topo/core/geometry/shape.py` | `topo.core.geometry.measure` · `topo.core.primitives.segments` |
| `topo/core/geometry_input.py` | `topo.core.geometry.build` · `topo.core.primitives.segments` · `topo.core.topology.edge` · `topo.model.document` · `topo.model.role` |
| `topo/core/heal.py` | `topo.core.healing.hierarchy` · `topo.core.healing.normalizer` · `topo.core.healing.steps` · `topo.core.primitives.segments` · `topo.core.topology.loop_finder` · `topo.core.topology.noding` · `topo.model.document` · `topo.model.result` · `topo.model.role` · `topo.rules.validator` |
| `topo/core/healing/gap_solver.py` | `topo.core.geometry.intersections` · `topo.core.geometry.measure` · `topo.core.primitives.segments` · `topo.core.topology.edge` · `topo.model.role` |
| `topo/core/healing/hierarchy.py` | `topo.core.geometry.measure` · `topo.core.geometry.regions` · `topo.core.topology.loop_finder` · `topo.model.cluster` · `topo.model.contour` · `topo.model.curve` · `topo.model.role` |
| `topo/core/healing/islands.py` | `topo.core.topology.edge` · `topo.core.topology.noding` |
| `topo/core/healing/normalizer.py` | `topo.core.primitives.fitting` · `topo.core.primitives.segments` · `topo.core.topology.edge` · `topo.core.topology.graph` · `topo.model.role` |
| `topo/core/healing/outer_scan.py` | `topo.core.primitives.segments` · `topo.core.topology.edge` |
| `topo/core/healing/steps.py` | `topo.core.geometry.measure` · `topo.core.healing.gap_solver` · `topo.core.healing.hierarchy` · `topo.core.primitives` · `topo.core.primitives.polygon_builder` · `topo.core.primitives.segments` · `topo.core.topology.edge` · `topo.core.topology.graph` · `topo.core.topology.loop_finder` · `topo.core.topology.non_contour_edges` · `topo.model.cluster` · `topo.model.curve` · `topo.model.role` |
| `topo/core/island.py` | `topo.core.geometry.shape` · `topo.core.healing.gap_solver` · `topo.core.healing.hierarchy` · `topo.core.healing.islands` · `topo.core.healing.normalizer` · `topo.core.primitives.segments` · `topo.core.primitives.trim` · `topo.core.topology.edge` · `topo.core.topology.graph` · `topo.core.topology.loop_finder` · `topo.core.topology.noding` · `topo.core.topology.non_contour_edges` · `topo.core.topology.outer_face` · `topo.core.topology.rim` · `topo.model.cluster` · `topo.model.contour` · `topo.model.curve` · `topo.model.document` · `topo.model.result` · `topo.model.role` |
| `topo/core/primitives/__init__.py` | `topo.core.primitives.polygon_builder` · `topo.core.primitives.segments` |
| `topo/core/primitives/fitting.py` | `topo.core.geometry.points` · `topo.core.primitives.segments` |
| `topo/core/primitives/polygon_builder.py` | `topo.core.primitives` |
| `topo/core/primitives/trim.py` | `topo.core.primitives.segments` |
| `topo/core/topology/edge.py` | `topo.core.geometry.measure` · `topo.core.primitives.segments` · `topo.model.style` |
| `topo/core/topology/graph.py` | `topo.core.geometry.measure` · `topo.core.primitives.segments` · `topo.core.topology.edge` |
| `topo/core/topology/loop_finder.py` | `topo.core.geometry.measure` · `topo.core.primitives.polygon_builder` · `topo.core.primitives.segments` · `topo.core.topology.edge` · `topo.core.topology.graph` · `topo.model.curve` |
| `topo/core/topology/noding.py` | `topo.core.geometry.intersections` · `topo.core.geometry.measure` · `topo.core.primitives.segments` · `topo.core.topology.edge` |
| `topo/core/topology/non_contour_edges.py` | `topo.core.topology.edge` · `topo.core.topology.graph` · `topo.core.topology.noding` · `topo.core.topology.outer_face` |
| `topo/core/topology/outer_face.py` | `topo.core.primitives.segments` · `topo.core.topology.edge` · `topo.core.topology.graph` · `topo.core.topology.loop_finder` · `topo.core.topology.noding` · `topo.core.topology.rim` |
| `topo/core/topology/rim.py` | `topo.core.primitives.segments` · `topo.core.primitives.trim` · `topo.core.topology.edge` · `topo.core.topology.noding` |
| `topo/inspect.py` | `topo.core.geometry.measure` · `topo.core.primitives.segments` · `topo.core.topology.graph` |
| `topo/io/exporter.py` | `topo.model` · `topo.rules.metadata_schema` |
| `topo/io/svg.py` | `topo.io.view_model` · `topo.model` |
| `topo/io/text.py` | `topo.core.geometry.shape` · `topo.core.primitives.segments` · `topo.model` |
| `topo/io/view_model.py` | `topo.core.geometry.measure` · `topo.model` · `topo.model.role` |
| `topo/model/__init__.py` | `topo.core.topology.edge` · `topo.model.cluster` · `topo.model.contour` · `topo.model.curve` · `topo.model.detected` · `topo.model.document` · `topo.model.result` · `topo.model.role` · `topo.model.role_rule` · `topo.model.style` · `topo.model.text` |
| `topo/model/cluster.py` | `topo.model.contour` |
| `topo/model/contour.py` | `topo.core.primitives.polygon_builder` · `topo.core.primitives.segments` · `topo.model.curve` |
| `topo/model/curve.py` | `topo.core.primitives.segments` · `topo.model.style` |
| `topo/model/document.py` | `topo.core.topology.edge` · `topo.model.text` |
| `topo/model/result.py` | `topo.model.cluster` · `topo.model.curve` · `topo.model.text` |
| `topo/model/role_rule.py` | `topo.model.role` · `topo.model.style` |
| `topo/model/style.py` | `topo.model.role` |
| `topo/model/text.py` | `topo.model.role` |
| `topo/primitives.py` | `topo.core.primitives.segments` · `topo.core.primitives.trim` |
| `topo/rules/validator.py` | `topo.core.primitives.segments` · `topo.core.topology.graph` · `topo.model` · `topo.model.document` |
| `topo/steps.py` | `topo.core.healing.islands` · `topo.core.healing.normalizer` · `topo.core.healing.steps` · `topo.core.topology.loop_finder` · `topo.core.topology.noding` · `topo.core.topology.outer_face` |
| `topo/tools/__init__.py` | `topo.tools.anchor` · `topo.tools.inject` |
| `topo/tools/anchor.py` | `topo.model.result` · `topo.model.text` |
| `topo/tools/inject.py` | `topo.tools.anchor` |
| `topo/tools/non_contour.py` | `topo.core.healing.steps` · `topo.core.topology.edge` · `topo.model.document` |
| `topo/tools/promote.py` | `topo.model.cluster` · `topo.model.curve` · `topo.model.detected` · `topo.model.result` |
| `topo/tools/rotate.py` | `topo.core.geometry.measure` · `topo.core.primitives.segments` · `topo.model.cluster` · `topo.model.contour` · `topo.model.curve` · `topo.model.document` · `topo.model.result` |
| `topo/tools/split.py` | `topo.core.geometry.measure` · `topo.model` |
| `topo/tools/tabs.py` | `topo.core.geometry.intersections` · `topo.core.geometry.measure` · `topo.core.primitives.segments` |
| `topo_dxf/__init__.py` | `topo_dxf.inspect` · `topo_dxf.layers` · `topo_dxf.loader` · `topo_dxf.recipes` · `topo_dxf.writer` · `topo_dxf.xdata` |
| `topo_dxf/adapter.py` | `topo_dxf.parser` |
| `topo_dxf/inspect.py` | `topo_dxf.loader` |
| `topo_dxf/loader.py` | `topo_dxf.adapter` · `topo_dxf.layers` · `topo_dxf.sanitize` · `topo_dxf.text_extractor` |
| `topo_dxf/recipes.py` | `topo_dxf.layers` · `topo_dxf.writer` |
| `topo_dxf/text_extractor.py` | `topo_dxf.mtext` |
| `topo_dxf/writer.py` | `topo_dxf.exporter` · `topo_dxf.layers` |
| `topo_dxf/xdata.py` | `topo_dxf.layers` |
| `topo_pdf/__init__.py` | `topo_pdf.loader` |
| `topo_pdf/loader.py` | `topo_pdf.extractor_adapter` · `topo_pdf.graph_adapter` · `topo_pdf.sanitize` |
| `topo_pdf/sanitize.py` | `topo_pdf.geometry_adapter` |

