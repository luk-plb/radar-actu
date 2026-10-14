"""Lecture des flux RSS."""

import calendar
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import yaml

USER_AGENT = "Mozilla/5.0 (compatible; radar-actu/1.0; +https://github.com/)"

# Un article publié plus de 48 h avant sa collecte n'est pas de l'actualité « du moment »
# (certains flux, comme L'Obs, renvoient des centaines d'anciens articles).
MAX_AGE = timedelta(hours=48)


def load_sources(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["sources"]


def clean_title(title: str) -> str:
    title = title.replace("\xa0", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", title).strip()


def _entry_date(entry) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)


def parse_entries(source: str, entries, fetched_at: datetime) -> list[dict]:
    articles = []
    for entry in entries:
        title = clean_title(entry.get("title", ""))
        link = entry.get("link", "").strip()
        if not title or not link:
            continue
        published = _entry_date(entry) or fetched_at
        if published < fetched_at - MAX_AGE:
            continue
        published = min(published, fetched_at)  # dates dans le futur
        articles.append({
            "link": link,
            "source": source,
            "title": title,
            "published": published.isoformat(timespec="seconds"),
        })
    return articles


def fetch_source(source: dict, fetched_at: datetime) -> tuple[list[dict], dict]:
    """Renvoie (articles, statut). Ne lève jamais d'exception : un flux en panne ne
    doit pas faire échouer tout le run."""
    status = {"name": source["name"], "ok": False, "entries": 0, "error": None}
    try:
        feed = feedparser.parse(source["url"], agent=USER_AGENT)
    except Exception as e:  # réseau, timeout…
        status["error"] = str(e)[:200]
        return [], status
    if not feed.entries:
        status["error"] = repr(feed.get("bozo_exception", "flux vide"))[:200]
        return [], status
    articles = parse_entries(source["name"], feed.entries, fetched_at)
    status.update(ok=True, entries=len(articles))
    return articles, status


def fetch_all(sources: list[dict], fetched_at: datetime | None = None) -> tuple[list[dict], list[dict]]:
    fetched_at = fetched_at or datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda s: fetch_source(s, fetched_at), sources))
    articles, statuses = [], []
    seen = set()
    for source_articles, status in results:
        statuses.append(status)
        for a in source_articles:
            if a["link"] not in seen:
                seen.add(a["link"])
                articles.append(a)
    return articles, statuses
