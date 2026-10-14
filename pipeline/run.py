"""Point d'entrée : python -m pipeline.run [--no-fetch]

1. lit les flux RSS et garde les articles inédits ;
2. extrait leurs termes (spaCy) et les ajoute à data/articles/ ;
3. recalcule les comptages des jours touchés (data/counts/) ;
4. exporte les JSON publics dans site/data/ (réseau 24 h et 7 j, tendances, statut des flux)."""

import argparse
import json
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .fetch import fetch_all, load_sources
from .graph import build_graph
from .nlp import canonical_forms, extract_terms, make_resolver, person_aliases
from .store import PARIS, Store
from .trends import build_trends

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("pipeline")


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))


def reprocess(store: Store, days: list) -> set:
    """Ré-extrait les termes des articles déjà stockés (après un changement des règles NLP)."""
    touched = set()
    for day in days:
        articles = store.load_articles(day)
        if articles:
            for article, terms in zip(articles, extract_terms([a["title"] for a in articles])):
                article["terms"] = terms
            store.rewrite_articles(day, articles)
            touched.add(day)
    return touched


def run(fetch: bool = True, data_dir: Path = ROOT / "data", site_dir: Path = ROOT / "site" / "data",
        now: datetime | None = None, reprocess_days: int = 0) -> dict:
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(PARIS).date()
    store = Store(data_dir)
    touched = set()
    statuses = None

    if reprocess_days:
        touched |= reprocess(store, [today - timedelta(days=i) for i in range(reprocess_days)])
        log.info("%d jours retraités", len(touched))

    if fetch:
        fetched, statuses = fetch_all(load_sources(ROOT / "pipeline" / "sources.yaml"), now)
        known = {a["link"] for a in store.load_range(today - timedelta(days=4), today + timedelta(days=1))}
        new = [a for a in fetched if a["link"] not in known]
        for article, terms in zip(new, extract_terms([a["title"] for a in new])):
            article["terms"] = terms
            article["fetched_at"] = now.isoformat(timespec="seconds")
        touched |= store.append_articles(new)
        failed = [s["name"] for s in statuses if not s["ok"]]
        log.info("%d articles lus, %d nouveaux. Flux en échec : %s",
                 len(fetched), len(new), ", ".join(failed) or "aucun")

    recent = store.load_range(today - timedelta(days=8), today)
    corpus = [a["terms"] for a in recent]
    resolve = make_resolver({**canonical_forms(corpus), **person_aliases(corpus)})
    for day in touched:
        store.write_counts(day, store.load_articles(day), resolve)

    def since(delta):
        limit = now - delta
        return [a for a in recent if datetime.fromisoformat(a["published"]) >= limit]

    window_24h, window_7d = since(timedelta(hours=24)), since(timedelta(days=7))
    graph_24h = build_graph(window_24h, resolve)
    graph_7d = build_graph(window_7d, resolve)

    recent_counts = Counter(t for a in window_24h for t in {resolve(term) for term, _ in a["terms"]})
    graph_terms = {n["id"] for n in graph_24h["nodes"] + graph_7d["nodes"]}
    trends = build_trends(store, today, recent_counts, len(window_24h), graph_terms)
    scores = trends.pop("_scores")
    for graph in (graph_24h, graph_7d):
        for node in graph["nodes"]:
            node["trend"] = scores.get(node["id"], {}).get("score")

    generated_at = now.isoformat(timespec="seconds")
    for name, graph, window in (("graph-24h", graph_24h, "24h"), ("graph-7d", graph_7d, "7j")):
        write_json(site_dir / f"{name}.json", {"generated_at": generated_at, "window": window, **graph})
    write_json(site_dir / "trends.json", {"generated_at": generated_at, **trends})

    meta_path = site_dir / "meta.json"
    if statuses is None and meta_path.exists():  # --no-fetch : on garde le dernier statut connu
        statuses = json.loads(meta_path.read_text(encoding="utf-8")).get("sources", [])
    meta = {
        "generated_at": generated_at,
        "articles_24h": len(window_24h),
        "articles_7d": len(window_7d),
        "sources": statuses or [],
    }
    write_json(meta_path, meta)
    store.purge(today)
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-fetch", action="store_true", help="reconstruit les JSON sans lire les flux")
    parser.add_argument("--reprocess", type=int, default=0, metavar="JOURS",
                        help="ré-extrait les termes des N derniers jours stockés")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    meta = run(fetch=not args.no_fetch, reprocess_days=args.reprocess)
    log.info("Export : %d articles sur 24 h, %d sur 7 j", meta["articles_24h"], meta["articles_7d"])


if __name__ == "__main__":
    main()
