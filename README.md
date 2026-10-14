# Radar de l'actu

Les mots qui font les titres de 20 médias français, sous forme de **réseau interactif**
(quels mots apparaissent ensemble) et de **tendances** (quels mots montent ou disparaissent).
Le site est statique et se met à jour seul toutes les deux heures grâce à GitHub Actions.

```
GitHub Actions (toutes les 2 h)
  └─ python -m pipeline.run
       fetch   flux RSS (pipeline/sources.yaml) → titres récents (< 48 h)
       nlp     spaCy fr_core_news_sm : noms, adjectifs, entités ; fusion des variantes
       store   data/articles/AAAA-MM-JJ.jsonl (90 jours) + data/counts/AAAA-MM-JJ.json (illimité)
       export  site/data/{graph-24h,graph-7d,trends,meta}.json
  └─ commit des données + déploiement de site/ sur GitHub Pages
```

## Structure

| Dossier | Contenu |
|---|---|
| `pipeline/` | Collecte, NLP, réseau de co-occurrences, tendances, export |
| `site/` | Page web (HTML + D3) qui lit `site/data/*.json` |
| `data/` | Historique versionné (un fichier par jour : seul celui du jour change à chaque run) |
| `tests/` | Tests `pytest` |
| `notebooks/` | Les notebooks d'exploration d'origine (nuages de mots, PDF, maquette D3) |

## En local

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                 # tests
.venv/bin/python -m pipeline.run              # collecte + export
.venv/bin/python -m pipeline.run --no-fetch   # ré-export sans lire les flux
.venv/bin/python -m pipeline.run --no-fetch --reprocess 7   # après une modif des règles NLP
python3 -m http.server 8765 -d site           # puis http://localhost:8765
```

## Mise en ligne

1. Créer un dépôt GitHub et y pousser ce dossier (branche `main`).
2. *Settings → Pages → Source : GitHub Actions*.
3. *Actions → Mise à jour du radar → Run workflow* pour un premier passage ; ensuite le cron
   prend le relais toutes les 2 h.

Les tendances deviennent pertinentes après environ une semaine de collecte (la référence est
la moyenne des 7 jours précédents).

## Réglages utiles

- **Médias suivis** : `pipeline/sources.yaml`.
- **Mots écartés** (« direct », « vidéo », mois…) : `MEDIA_NOISE` dans `pipeline/nlp.py`.
- **Thèmes** : listes de mots-clés dans `pipeline/categories.py`.
- **Seuils des tendances** : constantes en tête de `pipeline/trends.py`.

Seuls les titres et les liens sont conservés, jamais le contenu des articles.
