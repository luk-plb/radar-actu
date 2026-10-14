from collections import Counter
from datetime import date, datetime, timedelta, timezone

import pytest

from pipeline.categories import categorize
from pipeline.fetch import parse_entries
from pipeline.graph import build_graph
from pipeline.nlp import (canonical_forms, extract_terms, make_resolver, person_aliases,
                          preprocess, split_matchup)
from pipeline.store import Store
from pipeline.trends import build_trends, rising_falling, trend_scores

identity = make_resolver({})


# --- nlp -------------------------------------------------------------------------------------
def test_preprocess_strips_rubric_prefixes():
    assert preprocess("EN DIRECT - VIDÉO. Les députés votent") == "Les députés votent"
    assert preprocess("PSG-OM : le Classique") == "PSG-OM : le Classique"


def test_extract_terms_lemmas_entities_and_stop_words():
    [terms] = extract_terms(["VIDÉO. Les députés votent la réforme des retraites à l'Assemblée nationale"])
    found = dict(terms)
    assert found["Assemblée nationale"] == "ORG"
    assert {"député", "réforme", "retraite"} <= set(found)
    assert "vidéo" not in found and "le" not in found


def test_title_initial_common_noun_is_not_a_proper_noun():
    [terms] = extract_terms(["Présidentielle 2027 : vers un duel au second tour"])
    assert ["présidentielle", "W"] in terms


@pytest.mark.parametrize("name, expected", [
    ("Mélenchon-Le Pen", ["Mélenchon", "Le Pen"]),
    ("Manchester City-PSG", ["Manchester City", "PSG"]),
    ("PSG-OM", ["PSG", "OM"]),
    ("Jean-Luc Mélenchon", ["Jean-Luc Mélenchon"]),
    ("Seine-Saint-Denis", ["Seine-Saint-Denis"]),
])
def test_split_matchup(name, expected):
    assert split_matchup(name) == expected


def test_aliases_chain_and_case():
    corpus = [[["Marine Le Pen", "PER"], ["Etats-Unis", "LOC"]], [["Le Pen", "PER"], ["États-Unis", "LOC"]],
              [["retraite", "W"], ["retraité", "W"]]]
    resolve = make_resolver({**canonical_forms(corpus), **person_aliases(corpus)})
    assert resolve("Le Pen") == "Marine Le Pen"
    assert resolve("Pen") == "Marine Le Pen"
    assert resolve("Etats-Unis") == "États-Unis"
    assert resolve("retraite") == "retraite"  # pas de fusion d'accents sur les noms communs


def test_person_alias_ambiguous_is_skipped():
    corpus = [[["Marine Le Pen", "PER"], ["Jean-Marie Le Pen", "PER"]]]
    assert "Le Pen" not in person_aliases(corpus)


# --- fetch -----------------------------------------------------------------------------------
def test_parse_entries_filters_old_and_clamps_future():
    now = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)
    entries = [
        {"title": "Récent\xa0 titre", "link": "a", "published_parsed": (now - timedelta(hours=1)).timetuple()},
        {"title": "Vieux", "link": "b", "published_parsed": (now - timedelta(days=5)).timetuple()},
        {"title": "Futur", "link": "c", "published_parsed": (now + timedelta(hours=3)).timetuple()},
        {"title": "", "link": "d"},
        {"title": "Sans date", "link": "e"},
    ]
    out = {a["link"]: a for a in parse_entries("X", entries, now)}
    assert set(out) == {"a", "c", "e"}
    assert out["a"]["title"] == "Récent titre"
    assert out["c"]["published"] == now.isoformat(timespec="seconds")


# --- graph -----------------------------------------------------------------------------------
def _article(terms, i=0, source="S"):
    return {"title": f"t{i}", "link": f"l{i}", "source": source, "published": f"2026-10-14T0{i % 10}:00:00+00:00",
            "terms": [[t, "W"] for t in terms]}


def test_graph_weights_and_no_self_loops():
    arts = [_article(["guerre", "Ukraine", "guerre"], i) for i in range(3)] + [_article(["budget", "vote"], 5)] * 2
    g = build_graph(arts, identity)
    ids = {n["id"]: n for n in g["nodes"]}
    assert ids["guerre"]["count"] == 3  # un terme compte une fois par titre
    weights = {(l["source"], l["target"]): l["weight"] for l in g["links"]}
    assert weights[("Ukraine", "guerre")] == 3
    assert all(l["source"] != l["target"] for l in g["links"])
    assert len(g["headlines"]["guerre"]) == 3


def test_graph_drops_singletons():
    g = build_graph([_article(["unique"], 1), _article(["double"], 2), _article(["double"], 3)], identity)
    assert [n["id"] for n in g["nodes"]] == ["double"]


# --- trends ----------------------------------------------------------------------------------
def test_trend_scores_direction():
    scores = trend_scores(Counter(nouveau=20, stable=10, ancien=1), 200,
                          Counter(stable=70, ancien=70), 1400, 7)
    assert scores["nouveau"]["score"] > 2
    assert abs(scores["stable"]["score"]) < 0.3
    assert scores["ancien"]["score"] < -1
    rising, falling = rising_falling(scores)
    assert rising[0]["word"] == "nouveau" and rising[0]["new"]
    assert falling[0]["word"] == "ancien"


def test_build_trends_series_from_counts(tmp_path):
    store = Store(tmp_path)
    today = date(2026, 10, 14)
    for i in range(2, 9):
        d = today - timedelta(days=i)
        store.write_counts(d, [_article(["budget", "vote"], j) for j in range(10)], identity)
    t = build_trends(store, today, Counter(guerre=12, budget=2), 100, set())
    assert t["history_days"] == 7
    assert len(t["days"]) == 30 and t["days"][-1] == "2026-10-14"
    assert t["series"]["budget"][-3] == 10
    assert t["rising"][0]["word"] == "guerre"
    assert categorize("Ukraine") == "international" and categorize("Etats-Unis") == "international"
