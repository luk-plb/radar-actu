"""Tendances : part des titres qui citent un terme sur les dernières 24 h, comparée à sa part
moyenne sur les 7 jours précédents."""

import math
from collections import Counter
from datetime import date, timedelta

from .categories import categorize

BASELINE_DAYS = 7
MIN_RECENT = 4       # citations minimum sur 24 h pour être « en hausse »
MIN_BASELINE = 3     # citations moyennes par jour minimum pour être « en baisse »
PRIOR = 2            # lissage : équivaut à 2 titres « neutres » ajoutés de chaque côté


def trend_scores(recent: Counter, recent_total: int, baseline: Counter, baseline_total: int,
                 baseline_days: int) -> dict[str, dict]:
    """Score = log2 du rapport des parts lissées. > 0 : le terme monte."""
    if recent_total == 0:
        return {}
    out = {}
    for term in set(recent) | set(baseline):
        r, b = recent.get(term, 0), baseline.get(term, 0)
        share_r = (r + PRIOR * 0.5) / (recent_total + PRIOR)
        share_b = (b + PRIOR * 0.5) / (baseline_total + PRIOR) if baseline_total else share_r
        out[term] = {
            "recent": r,
            "baseline_per_day": round(b / baseline_days, 2) if baseline_days else 0,
            "score": round(math.log2(share_r / share_b), 3),
        }
    return out


def rising_falling(scores: dict[str, dict], limit: int = 15) -> tuple[list, list]:
    rising = [dict(word=t, **s, new=s["baseline_per_day"] == 0) for t, s in scores.items()
              if s["recent"] >= MIN_RECENT and s["score"] > 0.5]
    falling = [dict(word=t, **s) for t, s in scores.items()
               if s["baseline_per_day"] >= MIN_BASELINE and s["score"] < -0.5]
    rising.sort(key=lambda x: (x["score"], x["recent"]), reverse=True)
    falling.sort(key=lambda x: x["score"])
    for item in rising + falling:
        item["category"] = categorize(item["word"])
    return rising[:limit], falling[:limit]


def build_trends(store, today: date, recent_counts: Counter, recent_total: int,
                 extra_terms: set[str], days: int = 30, top_terms: int = 120) -> dict:
    day_list = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    daily = {d: store.load_counts(d) for d in day_list}

    # Référence : les 7 jours complets avant hier (la fenêtre de 24 h chevauche hier et aujourd'hui).
    base_days = [today - timedelta(days=i) for i in range(2, 2 + BASELINE_DAYS)]
    baseline, baseline_total, n_base = Counter(), 0, 0
    for d in base_days:
        c = daily.get(d) or store.load_counts(d)
        if c and c["articles"]:
            baseline.update(c["terms"])
            baseline_total += c["articles"]
            n_base += 1

    scores = trend_scores(recent_counts, recent_total, baseline, baseline_total, n_base)
    rising, falling = rising_falling(scores) if n_base else ([], [])

    totals_30 = Counter()
    for c in daily.values():
        if c:
            totals_30.update(c["terms"])
    selected = ({t for t, _ in totals_30.most_common(top_terms)} | extra_terms
                | {x["word"] for x in rising + falling})
    series = {t: [(daily[d] or {"terms": {}})["terms"].get(t, 0) for d in day_list]
              for t in sorted(selected)}

    return {
        "days": [d.isoformat() for d in day_list],
        "totals": [(daily[d] or {"articles": 0})["articles"] for d in day_list],
        "history_days": n_base,
        "rising": rising,
        "falling": falling,
        "series": series,
        "categories": {t: categorize(t) for t in series},
        # Retiré avant l'export : sert à annoter les nœuds du graphe.
        "_scores": scores if n_base else {},
    }
