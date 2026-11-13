# topo/core/topology/matching.py

"""
matching.py
-----------
Accoppiamento perfetto di peso minimo e T-join di peso minimo su un grafo
qualsiasi, coi pesi interi: nessuna geometria.

Tipi pubblici:
    max_weight_matching          — accoppiamento di peso massimo (Edmonds, blossom)
    min_weight_perfect_matching  — accoppiamento perfetto di peso minimo
    min_t_join                   — l'insieme di lati più leggero che rende
                                   dispari esattamente i nodi di T

I pesi sono interi: il confronto è esatto e il risultato non dipende dagli
arrotondamenti. Chi ha lunghezze in mm le converte prima in multipli di
FLOAT_NOISE. Scritto in Python puro su liste di interi, per un porting.
"""

from __future__ import annotations

import heapq
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from .graph import connected_groups

WeightedEdge = Tuple[int, int, int]


def max_weight_matching(n: int, edges: Sequence[WeightedEdge],
                        max_cardinality: bool = False) -> List[int]:
    """
    L'accoppiamento di peso massimo dei nodi 0..n-1 sui lati (i, j, peso),
    pesi interi; con `max_cardinality` il più pesante fra quelli col maggior
    numero di coppie. Restituisce `mate`: mate[v] è il compagno di v, -1 se
    v è solo.

    Metodo primale-duale di Edmonds coi blossom, O(n^3) (Galil 1986). Coi
    pesi interi i duali restano interi: tutti i conti sono esatti.
    """
    return _matching(n, edges, max_cardinality)[0]


def _matching(n: int, edges: Sequence[WeightedEdge],
              max_cardinality: bool) -> Tuple[List[int], List[int], List[int]]:
    """(mate, duali, padre di ogni nodo e blossom): i duali dei nodi
    0..n-1 e dei blossom n..2n-1 rimasti alla fine, per `_slack`."""
    nedge = len(edges)
    if n == 0 or nedge == 0:
        return [-1] * n, [0] * (2 * n), [-1] * (2 * n)
    for i, j, w in edges:
        if i == j or not (0 <= i < n and 0 <= j < n):
            raise ValueError(f"lato non valido ({i}, {j})")
        if not isinstance(w, int):
            raise TypeError("i pesi devono essere interi")
    maxweight = max(0, max(w for _, _, w in edges))

    # l'estremo p (0..2*nedge-1) è il nodo edges[p // 2][p % 2]
    endpoint = [edges[p // 2][p % 2] for p in range(2 * nedge)]
    # per ogni nodo, gli estremi remoti dei suoi lati
    neighbend: List[List[int]] = [[] for _ in range(n)]
    for k, (i, j, _) in enumerate(edges):
        neighbend[i].append(2 * k + 1)
        neighbend[j].append(2 * k)

    mate = [-1] * n                       # estremo remoto del lato accoppiato
    label = [0] * (2 * n)                 # 0 libero, 1 S, 2 T (blossom esterni e nodi)
    labelend = [-1] * (2 * n)             # estremo da cui il blossom ha preso l'etichetta
    inblossom = list(range(n))            # blossom esterno di ogni nodo
    blossomparent = [-1] * (2 * n)
    blossomchilds: List = [None] * (2 * n)
    blossombase = list(range(n)) + [-1] * n
    blossomendps: List = [None] * (2 * n)
    bestedge = [-1] * (2 * n)             # lato di slack minimo verso un blossom S
    blossombestedges: List = [None] * (2 * n)
    unusedblossoms = list(range(n, 2 * n))
    dualvar = [maxweight] * n + [0] * n
    allowedge = [False] * nedge
    queue: List[int] = []

    def slack(k: int) -> int:
        i, j, w = edges[k]
        return dualvar[i] + dualvar[j] - 2 * w

    def leaves(b: int):
        if b < n:
            yield b
        else:
            for t in blossomchilds[b]:
                if t < n:
                    yield t
                else:
                    yield from leaves(t)

    def assign_label(w: int, t: int, p: int) -> None:
        b = inblossom[w]
        label[w] = label[b] = t
        labelend[w] = labelend[b] = p
        bestedge[w] = bestedge[b] = -1
        if t == 1:
            queue.extend(leaves(b))
        else:
            base = blossombase[b]
            assign_label(endpoint[mate[base]], 1, mate[base] ^ 1)

    def scan_blossom(v: int, w: int) -> int:
        """La base del nuovo blossom fra v e w, -1 se c'è un cammino aumentante."""
        path = []
        base = -1
        while v != -1 or w != -1:
            b = inblossom[v]
            if label[b] & 4:
                base = blossombase[b]
                break
            path.append(b)
            label[b] = 5
            if labelend[b] == -1:
                v = -1
            else:
                v = endpoint[labelend[b]]
                b = inblossom[v]
                v = endpoint[labelend[b]]
            if w != -1:
                v, w = w, v
        for b in path:
            label[b] = 1
        return base

    def add_blossom(base: int, k: int) -> None:
        v, w, _ = edges[k]
        bb = inblossom[base]
        bv = inblossom[v]
        bw = inblossom[w]
        b = unusedblossoms.pop()
        blossombase[b] = base
        blossomparent[b] = -1
        blossomparent[bb] = b
        blossomchilds[b] = path = []
        blossomendps[b] = endps = []
        while bv != bb:
            blossomparent[bv] = b
            path.append(bv)
            endps.append(labelend[bv])
            v = endpoint[labelend[bv]]
            bv = inblossom[v]
        path.append(bb)
        path.reverse()
        endps.reverse()
        endps.append(2 * k)
        while bw != bb:
            blossomparent[bw] = b
            path.append(bw)
            endps.append(labelend[bw] ^ 1)
            w = endpoint[labelend[bw]]
            bw = inblossom[w]
        label[b] = 1
        labelend[b] = labelend[bb]
        dualvar[b] = 0
        for v in leaves(b):
            if label[inblossom[v]] == 2:
                queue.append(v)
            inblossom[v] = b
        bestedgeto = [-1] * (2 * n)
        for bv in path:
            if blossombestedges[bv] is None:
                nblists = [[p // 2 for p in neighbend[v]] for v in leaves(bv)]
            else:
                nblists = [blossombestedges[bv]]
            for nblist in nblists:
                for k2 in nblist:
                    i, j, _ = edges[k2]
                    if inblossom[j] == b:
                        i, j = j, i
                    bj = inblossom[j]
                    if (bj != b and label[bj] == 1
                            and (bestedgeto[bj] == -1 or slack(k2) < slack(bestedgeto[bj]))):
                        bestedgeto[bj] = k2
            blossombestedges[bv] = None
            bestedge[bv] = -1
        blossombestedges[b] = [k2 for k2 in bestedgeto if k2 != -1]
        bestedge[b] = -1
        for k2 in blossombestedges[b]:
            if bestedge[b] == -1 or slack(k2) < slack(bestedge[b]):
                bestedge[b] = k2

    def expand_blossom(b: int, endstage: bool) -> None:
        for s in blossomchilds[b]:
            blossomparent[s] = -1
            if s < n:
                inblossom[s] = s
            elif endstage and dualvar[s] == 0:
                expand_blossom(s, endstage)
            else:
                for v in leaves(s):
                    inblossom[v] = s
        if not endstage and label[b] == 2:
            # il blossom T si apre: rietichetta i figli lungo il cammino pari
            entrychild = inblossom[endpoint[labelend[b] ^ 1]]
            childs = blossomchilds[b]
            j = childs.index(entrychild)
            if j & 1:
                j -= len(childs)
                jstep, endptrick = 1, 0
            else:
                jstep, endptrick = -1, 1
            p = labelend[b]
            while j != 0:
                label[endpoint[p ^ 1]] = 0
                label[endpoint[blossomendps[b][j - endptrick] ^ endptrick ^ 1]] = 0
                assign_label(endpoint[p ^ 1], 2, p)
                allowedge[blossomendps[b][j - endptrick] // 2] = True
                j += jstep
                p = blossomendps[b][j - endptrick] ^ endptrick
                allowedge[p // 2] = True
                j += jstep
            bv = childs[j]
            label[endpoint[p ^ 1]] = label[bv] = 2
            labelend[endpoint[p ^ 1]] = labelend[bv] = p
            bestedge[bv] = -1
            j += jstep
            while childs[j] != entrychild:
                bv = childs[j]
                if label[bv] == 1:
                    j += jstep
                    continue
                reached = -1
                for v in leaves(bv):
                    if label[v] != 0:
                        reached = v
                        break
                if reached != -1:
                    label[reached] = 0
                    label[endpoint[mate[blossombase[bv]]]] = 0
                    assign_label(reached, 2, labelend[reached])
                j += jstep
        label[b] = labelend[b] = -1
        blossomchilds[b] = blossomendps[b] = None
        blossombase[b] = -1
        blossombestedges[b] = None
        bestedge[b] = -1
        unusedblossoms.append(b)

    def augment_blossom(b: int, v: int) -> None:
        t = v
        while blossomparent[t] != b:
            t = blossomparent[t]
        if t >= n:
            augment_blossom(t, v)
        i = j = blossomchilds[b].index(t)
        if i & 1:
            j -= len(blossomchilds[b])
            jstep, endptrick = 1, 0
        else:
            jstep, endptrick = -1, 1
        while j != 0:
            j += jstep
            t = blossomchilds[b][j]
            p = blossomendps[b][j - endptrick] ^ endptrick
            if t >= n:
                augment_blossom(t, endpoint[p])
            j += jstep
            t = blossomchilds[b][j]
            if t >= n:
                augment_blossom(t, endpoint[p ^ 1])
            mate[endpoint[p]] = p ^ 1
            mate[endpoint[p ^ 1]] = p
        blossomchilds[b] = blossomchilds[b][i:] + blossomchilds[b][:i]
        blossomendps[b] = blossomendps[b][i:] + blossomendps[b][:i]
        blossombase[b] = blossombase[blossomchilds[b][0]]

    def augment_matching(k: int) -> None:
        v, w, _ = edges[k]
        for s, p in ((v, 2 * k + 1), (w, 2 * k)):
            while True:
                bs = inblossom[s]
                if bs >= n:
                    augment_blossom(bs, s)
                mate[s] = p
                if labelend[bs] == -1:
                    break
                t = endpoint[labelend[bs]]
                bt = inblossom[t]
                s = endpoint[labelend[bt]]
                j = endpoint[labelend[bt] ^ 1]
                if bt >= n:
                    augment_blossom(bt, j)
                mate[j] = labelend[bt]
                p = labelend[bt] ^ 1

    for _ in range(n):
        # uno stadio: cerca un cammino aumentante
        label[:] = [0] * (2 * n)
        bestedge[:] = [-1] * (2 * n)
        blossombestedges[n:] = [None] * n
        allowedge[:] = [False] * nedge
        queue[:] = []
        for v in range(n):
            if mate[v] == -1 and label[inblossom[v]] == 0:
                assign_label(v, 1, -1)
        augmented = False
        while True:
            while queue and not augmented:
                v = queue.pop()
                for p in neighbend[v]:
                    k = p // 2
                    w = endpoint[p]
                    if inblossom[v] == inblossom[w]:
                        continue
                    kslack = 0
                    if not allowedge[k]:
                        kslack = slack(k)
                        if kslack <= 0:
                            allowedge[k] = True
                    if allowedge[k]:
                        if label[inblossom[w]] == 0:
                            assign_label(w, 2, p ^ 1)
                        elif label[inblossom[w]] == 1:
                            base = scan_blossom(v, w)
                            if base >= 0:
                                add_blossom(base, k)
                            else:
                                augment_matching(k)
                                augmented = True
                                break
                        elif label[w] == 0:
                            label[w] = 2
                            labelend[w] = p ^ 1
                    elif label[inblossom[w]] == 1:
                        b = inblossom[v]
                        if bestedge[b] == -1 or kslack < slack(bestedge[b]):
                            bestedge[b] = k
                    elif label[w] == 0:
                        if bestedge[w] == -1 or kslack < slack(bestedge[w]):
                            bestedge[w] = k
            if augmented:
                break
            # nessun lato ammesso porta avanti: aggiorna i duali
            deltatype = -1
            delta = deltaedge = deltablossom = 0
            if not max_cardinality:
                deltatype = 1
                delta = min(dualvar[:n])
            for v in range(n):
                if label[inblossom[v]] == 0 and bestedge[v] != -1:
                    d = slack(bestedge[v])
                    if deltatype == -1 or d < delta:
                        delta, deltatype, deltaedge = d, 2, bestedge[v]
            for b in range(2 * n):
                if blossomparent[b] == -1 and label[b] == 1 and bestedge[b] != -1:
                    kslack = slack(bestedge[b])
                    if kslack % 2:
                        raise AssertionError("slack dispari fra due blossom S")
                    d = kslack // 2
                    if deltatype == -1 or d < delta:
                        delta, deltatype, deltaedge = d, 3, bestedge[b]
            for b in range(n, 2 * n):
                if (blossombase[b] >= 0 and blossomparent[b] == -1 and label[b] == 2
                        and (deltatype == -1 or dualvar[b] < delta)):
                    delta, deltatype, deltablossom = dualvar[b], 4, b
            if deltatype == -1:
                deltatype = 1
                delta = max(0, min(dualvar[:n]))
            for v in range(n):
                if label[inblossom[v]] == 1:
                    dualvar[v] -= delta
                elif label[inblossom[v]] == 2:
                    dualvar[v] += delta
            for b in range(n, 2 * n):
                if blossombase[b] >= 0 and blossomparent[b] == -1:
                    if label[b] == 1:
                        dualvar[b] += delta
                    elif label[b] == 2:
                        dualvar[b] -= delta
            if deltatype == 1:
                break
            if deltatype == 2:
                allowedge[deltaedge] = True
                i, j, _ = edges[deltaedge]
                if label[inblossom[i]] == 0:
                    i, j = j, i
                queue.append(i)
            elif deltatype == 3:
                allowedge[deltaedge] = True
                i, j, _ = edges[deltaedge]
                queue.append(i)
            else:
                expand_blossom(deltablossom, False)
        if not augmented:
            break
        for b in range(n, 2 * n):
            if (blossomparent[b] == -1 and blossombase[b] >= 0
                    and label[b] == 1 and dualvar[b] == 0):
                expand_blossom(b, True)

    return [endpoint[p] if p >= 0 else -1 for p in mate], dualvar, blossomparent


def _slack(i: int, j: int, w: int, dual: List[int], parent: List[int]) -> int:
    """Lo slack del lato (i, j, w) coi duali finali: negativo = il lato
    migliorerebbe l'accoppiamento (verifica di ottimalità di Edmonds)."""
    s = dual[i] + dual[j] - 2 * w
    up_i, up_j = [i], [j]
    while parent[up_i[-1]] != -1:
        up_i.append(parent[up_i[-1]])
    while parent[up_j[-1]] != -1:
        up_j.append(parent[up_j[-1]])
    for bi, bj in zip(reversed(up_i), reversed(up_j)):
        if bi != bj:
            break
        s += 2 * dual[bi]
    return s


def min_weight_perfect_matching(n: int, edges: Sequence[WeightedEdge]) -> List[int]:
    """
    L'accoppiamento perfetto di peso minimo dei nodi 0..n-1 sui lati
    (i, j, peso), pesi interi. Restituisce `mate` (mate[v] = compagno di v);
    `ValueError` se nessun accoppiamento copre tutti i nodi.

    Fra gli accoppiamenti col maggior numero di coppie, peso massimo di
    (C - peso) con C maggiore di ogni peso: se ce n'è uno perfetto, è quello
    di peso minimo.
    """
    if not edges:
        if n:
            raise ValueError("nessun accoppiamento perfetto")
        return []
    top = max(w for _, _, w in edges) + 1
    mate = max_weight_matching(n, [(i, j, top - w) for i, j, w in edges],
                               max_cardinality=True)
    if any(m == -1 for m in mate):
        raise ValueError("nessun accoppiamento perfetto")
    return mate


def _min_perfect_on_complete(dist: List[List[int]], start: int = 8) -> List[int]:
    """
    L'accoppiamento perfetto di peso minimo sul grafo completo dei nodi
    0..n-1 (n pari) coi pesi interi `dist[i][j]`. Si risolve sulle coppie
    più vicine (`start` per nodo), poi si aggiungono le coppie escluse che
    coi duali finali hanno slack negativo, finché non ce n'è nessuna: allora
    i duali sono ammissibili su tutto il grafo e l'accoppiamento è ottimo
    anche lì (dualità di Edmonds). Il risultato non dipende da `start`.
    """
    n = len(dist)
    if n == 0:
        return []
    top = max(max(row) for row in dist) + 1
    # ogni coppia in più vale più di qualunque differenza di peso: il più
    # pesante è perfetto, se il grafo ne ha uno
    big = n * top + 1
    weight = lambda i, j: big + top - dist[i][j]
    chosen = set()
    for i in range(n):
        near = sorted((dist[i][j], j) for j in range(n) if j != i)[:start]
        chosen.update((min(i, j), max(i, j)) for _, j in near)
    while True:
        pairs = sorted(chosen)
        mate, dual, parent = _matching(n, [(i, j, weight(i, j)) for i, j in pairs], False)
        if any(m == -1 for m in mate):
            # le coppie scelte non coprono tutti: a chi resta solo, tutte le sue
            chosen.update((min(i, j), max(i, j)) for i in range(n) if mate[i] == -1
                          for j in range(n) if j != i)
            continue
        outer = []
        for v in range(n):
            while parent[v] != -1:
                v = parent[v]
            outer.append(v)
        missing = []
        for i in range(n):
            row, di, oi = dist[i], dual[i], outer[i]
            for j in range(i + 1, n):
                # fra due blossom esterni diversi lo slack è quello dei due nodi
                s = di + dual[j] - 2 * (big + top - row[j])
                if s < 0 and oi == outer[j]:
                    s = _slack(i, j, big + top - row[j], dual, parent)
                if s < 0 and (i, j) not in chosen:
                    missing.append((i, j))
        if not missing:
            return mate
        chosen.update(missing)


def _shortest_paths(n: int, adj: List[List[Tuple[int, int, int]]],
                    source: int) -> Tuple[List[int], List[int]]:
    """(distanza, lato da cui si arriva) da `source` a ogni nodo; -1 se irraggiungibile."""
    dist = [-1] * n
    via = [-1] * n
    dist[source] = 0
    heap = [(0, source)]
    done = [False] * n
    while heap:
        d, u = heapq.heappop(heap)
        if done[u]:
            continue
        done[u] = True
        for v, w, k in adj[u]:
            nd = d + w
            if dist[v] == -1 or nd < dist[v]:
                dist[v] = nd
                via[v] = k
                heapq.heappush(heap, (nd, v))
    return dist, via


def min_t_join(n: int, edges: Sequence[WeightedEdge],
               terminals: Iterable[int]) -> Tuple[Set[int], Set[int]]:
    """
    Il T-join di peso minimo: gli indici dei lati di `edges` (i, j, peso),
    pesi interi >= 0, il cui insieme ha grado dispari esattamente nei nodi
    di `terminals`. Restituisce (lati, terminali scoperti): un terminale è
    scoperto quando la sua componente connessa ne ha un numero dispari, e
    allora nessun insieme di lati lo può rendere dispari.

    Cammini minimi fra i terminali di ogni componente, accoppiamento perfetto
    di peso minimo su quelle distanze, differenza simmetrica dei cammini
    (Edmonds-Johnson 1973). A pari peso decide l'ordine dei lati.
    """
    for _, _, w in edges:
        if w < 0:
            raise ValueError("pesi negativi")
    adj: List[List[Tuple[int, int, int]]] = [[] for _ in range(n)]
    for k, (i, j, w) in enumerate(edges):
        adj[i].append((j, w, k))
        adj[j].append((i, w, k))
    tset = sorted(set(terminals))
    paths: Dict[int, Tuple[List[int], List[int]]] = {t: _shortest_paths(n, adj, t) for t in tset}
    # i terminali per componente: chi si raggiunge sta nella stessa
    reached = [(a, b) for a in range(len(tset)) for b in range(len(tset))
               if a < b and paths[tset[a]][0][tset[b]] != -1]
    groups = [[tset[a] for a in group] for group in connected_groups(len(tset), reached)]

    chosen: Set[int] = set()
    uncovered: Set[int] = set()
    for group in groups:
        if len(group) % 2:
            uncovered.update(group)
            continue
        mate = _min_perfect_on_complete([[paths[s][0][t] for t in group] for s in group])
        for a, b in enumerate(mate):
            if a > b:
                continue
            source, target = group[a], group[b]
            via = paths[source][1]
            v = target
            while v != source:
                k = via[v]
                chosen ^= {k}
                i, j, _ = edges[k]
                v = i if j == v else j
    return chosen, uncovered
