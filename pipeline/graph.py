"""Réseau de co-occurrences : deux termes sont liés quand ils apparaissent dans le même titre.
Version pondérée de build_word_graph() (notebooks/wordCloud.ipynb, version « par titre »)."""

from collections import Counter
from itertools import combinations

from .categories import categorize


def build_graph(articles: list[dict], resolve, max_nodes: int = 60, max_links: int = 220,
                headlines_per_node: int = 6) -> dict:
    """articles : dicts avec "terms" ([[terme, type], …]), "title", "link", "source", "published"."""
    per_article = []
    freq = Counter()
    kinds: dict[str, Counter] = {}
    for a in articles:
        terms = {resolve(t): k for t, k in a["terms"]}
        per_article.append((a, terms))
        for t, k in terms.items():
            freq[t] += 1
            kinds.setdefault(t, Counter())[k] += 1

    top = [t for t, c in freq.most_common(max_nodes) if c >= 2]
    top_set = set(top)

    pair_weights = Counter()
    sources: dict[str, Counter] = {t: Counter() for t in top}
    headlines: dict[str, list[dict]] = {t: [] for t in top}
    for a, terms in sorted(per_article, key=lambda x: x[0]["published"], reverse=True):
        present = sorted(t for t in terms if t in top_set)
        for t in present:
            sources[t][a["source"]] += 1
            if len(headlines[t]) < headlines_per_node:
                headlines[t].append({k: a[k] for k in ("title", "link", "source", "published")})
        for pair in combinations(present, 2):
            pair_weights[pair] += 1

    # Poids ≥ 2 pour garder un graphe lisible, sauf si le corpus est trop petit.
    min_weight = 2 if sum(1 for w in pair_weights.values() if w >= 2) >= 20 else 1
    links = [{"source": s, "target": t, "weight": w}
             for (s, t), w in pair_weights.most_common(max_links) if w >= min_weight]

    nodes = []
    for t in top:
        kind = kinds[t].most_common(1)[0][0]
        nodes.append({
            "id": t,
            "count": freq[t],
            "kind": kind,
            "category": categorize(t),
            "sources": dict(sources[t].most_common()),
        })
    return {"articles": len(articles), "nodes": nodes, "links": links, "headlines": headlines}
