# tests/engine/topology/test_matching.py

import random
import unittest

from topo.core.topology.matching import (
    _min_perfect_on_complete, max_weight_matching, min_t_join, min_weight_perfect_matching,
)


def _matchings(edges):
    """Ogni accoppiamento di `edges`, come lista di indici di lati."""
    out = []

    def rec(k, used, chosen):
        if k == len(edges):
            out.append(list(chosen))
            return
        rec(k + 1, used, chosen)
        i, j, _ = edges[k]
        if i not in used and j not in used:
            chosen.append(k)
            rec(k + 1, used | {i, j}, chosen)
            chosen.pop()

    rec(0, frozenset(), [])
    return out


def _random_graph(rnd, n_max=8, m_max=12):
    n = rnd.randint(2, n_max)
    edges = []
    for _ in range(rnd.randint(0, m_max)):
        i, j = rnd.sample(range(n), 2)
        # pesi piccoli (tanti pareggi) e grandi
        edges.append((i, j, rnd.choice([rnd.randint(0, 5), rnd.randint(0, 10 ** 9)])))
    return n, edges


def _mate_weight(edges, mate, pick):
    """Peso dell'accoppiamento `mate`; fra lati paralleli sceglie `pick` (max o min)."""
    total = 0
    for v, m in enumerate(mate):
        if m > v:
            total += pick(w for i, j, w in edges if {i, j} == {v, m})
    return total


class TestMaxWeightMatching(unittest.TestCase):

    def test_matches_brute_force_on_random_graphs(self):
        rnd = random.Random(1)
        for _ in range(400):
            n, edges = _random_graph(rnd)
            every = _matchings(edges)
            for max_cardinality in (False, True):
                mate = max_weight_matching(n, edges, max_cardinality)
                for v, m in enumerate(mate):
                    self.assertTrue(m == -1 or mate[m] == v)
                pool = every
                if max_cardinality:
                    size = max(len(x) for x in every)
                    pool = [x for x in every if len(x) == size]
                    self.assertEqual(sum(m != -1 for m in mate), 2 * size)
                best = max(sum(edges[k][2] for k in x) for x in pool)
                self.assertEqual(_mate_weight(edges, mate, max), best, (n, edges))

    def test_weights_must_be_integers(self):
        with self.assertRaises(TypeError):
            max_weight_matching(2, [(0, 1, 1.5)])


class TestMinWeightPerfectMatching(unittest.TestCase):

    def test_matches_brute_force_on_random_graphs(self):
        rnd = random.Random(2)
        for _ in range(400):
            n, edges = _random_graph(rnd)
            perfect = [x for x in _matchings(edges) if 2 * len(x) == n]
            if not perfect:
                with self.assertRaises(ValueError):
                    min_weight_perfect_matching(n, edges)
                continue
            mate = min_weight_perfect_matching(n, edges)
            best = min(sum(edges[k][2] for k in x) for x in perfect)
            self.assertEqual(_mate_weight(edges, mate, min), best, (n, edges))

    def test_blossom_needed(self):
        # il triangolo 0-1-2 con la coda 2-3: l'unico perfetto è {0-1, 2-3}
        edges = [(0, 1, 5), (1, 2, 1), (0, 2, 1), (2, 3, 9)]
        self.assertEqual(min_weight_perfect_matching(4, edges), [1, 0, 3, 2])


class TestMinPerfectOnComplete(unittest.TestCase):

    def test_few_pairs_per_node_still_exact(self):
        # una coppia per nodo all'inizio: le altre entrano solo coi duali
        rnd = random.Random(5)
        for _ in range(300):
            n = rnd.choice([2, 4, 6, 8, 10])
            dist = [[0] * n for _ in range(n)]
            for i in range(n):
                for j in range(i + 1, n):
                    dist[i][j] = dist[j][i] = rnd.choice([rnd.randint(1, 3), rnd.randint(0, 10 ** 9)])
            mate = _min_perfect_on_complete(dist, start=1)
            best = min(sum(dist[a][b] for a, b in pairing) for pairing in _pairings(list(range(n))))
            self.assertEqual(sum(dist[i][m] for i, m in enumerate(mate) if m > i), best)


def _pairings(nodes):
    """Ogni modo di accoppiare `nodes` (in numero pari)."""
    if not nodes:
        yield []
        return
    first = nodes[0]
    for k in range(1, len(nodes)):
        for rest in _pairings(nodes[1:k] + nodes[k + 1:]):
            yield [(first, nodes[k])] + rest


class TestMinTJoin(unittest.TestCase):

    def test_matches_brute_force_on_random_graphs(self):
        rnd = random.Random(3)
        for _ in range(300):
            n, edges = _random_graph(rnd, n_max=7, m_max=10)
            terminals = set(rnd.sample(range(n), rnd.randint(0, n)))
            chosen, uncovered = min_t_join(n, edges, terminals)
            best = None
            for mask in range(1 << len(edges)):
                odd, weight = set(), 0
                for k, (i, j, w) in enumerate(edges):
                    if mask >> k & 1:
                        odd ^= {i, j}
                        weight += w
                if odd == terminals and (best is None or weight < best):
                    best = weight
            if best is None:
                self.assertTrue(uncovered)
                continue
            self.assertFalse(uncovered)
            odd = set()
            for k in chosen:
                odd ^= {edges[k][0], edges[k][1]}
            self.assertEqual(odd, terminals)
            self.assertEqual(sum(edges[k][2] for k in chosen), best, (n, edges, terminals))

    def test_odd_component_is_uncovered(self):
        chosen, uncovered = min_t_join(4, [(0, 1, 1), (2, 3, 1)], {0, 1, 2})
        self.assertEqual(uncovered, {2})
        self.assertEqual(chosen, {0})

    def test_negative_weight_raises(self):
        with self.assertRaises(ValueError):
            min_t_join(2, [(0, 1, -1)], {0, 1})


if __name__ == "__main__":
    unittest.main()
