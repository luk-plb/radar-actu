"""Stockage en fichiers texte versionnés dans git :
- data/articles/AAAA-MM-JJ.jsonl : un article par ligne (titre, lien, date, termes), gardé 90 jours ;
- data/counts/AAAA-MM-JJ.json    : fréquences journalières des termes, gardées sans limite.
Un fichier par jour : seul celui du jour change à chaque run, ce qui garde le dépôt léger."""

import json
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
RETENTION_DAYS = 90


def paris_day(iso: str) -> date:
    return datetime.fromisoformat(iso).astimezone(PARIS).date()


class Store:
    def __init__(self, root: Path):
        self.articles_dir = root / "articles"
        self.counts_dir = root / "counts"
        self.articles_dir.mkdir(parents=True, exist_ok=True)
        self.counts_dir.mkdir(parents=True, exist_ok=True)

    # --- articles -------------------------------------------------------------------------
    def _articles_path(self, day: date) -> Path:
        return self.articles_dir / f"{day.isoformat()}.jsonl"

    def load_articles(self, day: date) -> list[dict]:
        path = self._articles_path(day)
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def load_range(self, start: date, end: date) -> list[dict]:
        out = []
        day = start
        while day <= end:
            out.extend(self.load_articles(day))
            day += timedelta(days=1)
        return out

    def append_articles(self, articles: list[dict]) -> set[date]:
        """Ajoute les articles au fichier de leur jour de publication ; renvoie les jours touchés."""
        by_day: dict[date, list[dict]] = {}
        for a in articles:
            by_day.setdefault(paris_day(a["published"]), []).append(a)
        for day, items in by_day.items():
            with open(self._articles_path(day), "a", encoding="utf-8") as f:
                for a in items:
                    f.write(json.dumps(a, ensure_ascii=False) + "\n")
        return set(by_day)

    def rewrite_articles(self, day: date, articles: list[dict]) -> None:
        with open(self._articles_path(day), "w", encoding="utf-8") as f:
            for a in articles:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")

    def purge(self, today: date) -> int:
        limit = today - timedelta(days=RETENTION_DAYS)
        removed = 0
        for path in self.articles_dir.glob("*.jsonl"):
            if date.fromisoformat(path.stem) < limit:
                path.unlink()
                removed += 1
        return removed

    # --- comptages journaliers ---------------------------------------------------------------
    def write_counts(self, day: date, articles: list[dict], resolve) -> None:
        terms = Counter()
        kinds: dict[str, Counter] = {}
        for a in articles:
            for term, kind in {resolve(t): k for t, k in a["terms"]}.items():
                terms[term] += 1
                kinds.setdefault(term, Counter())[kind] += 1
        payload = {
            "day": day.isoformat(),
            "articles": len(articles),
            # On écarte les termes vus une seule fois : bruit, et fichiers plus légers.
            "terms": {t: c for t, c in terms.most_common() if c >= 2},
            "kinds": {t: k.most_common(1)[0][0] for t, k in kinds.items()
                      if terms[t] >= 2 and k.most_common(1)[0][0] != "W"},
        }
        with open(self.counts_dir / f"{day.isoformat()}.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    def load_counts(self, day: date) -> dict | None:
        path = self.counts_dir / f"{day.isoformat()}.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)
