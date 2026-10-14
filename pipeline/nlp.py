"""Extraction des termes d'un titre : noms, adjectifs et entités nommées (spaCy)."""

import re
import unicodedata
from collections import Counter
from functools import lru_cache

import spacy
from spacy.lang.fr.stop_words import STOP_WORDS

KEPT_POS = {"NOUN", "PROPN", "ADJ"}
ENTITY_LABELS = {"PER", "LOC", "ORG"}  # MISC est trop bruité sur des titres

# Rubriques et tics de titraille des médias, sans valeur informative.
MEDIA_NOISE = {
    "direct", "vidéo", "video", "photo", "info", "information", "franceinfo", "témoignage",
    "récit", "enquête", "entretien", "interview", "analyse", "chronique", "édito", "éditorial",
    "tribune", "podcast", "replay", "reportage", "carte", "infographie", "quiz", "exclusif",
    "question", "réponse", "point", "suivre", "live", "résumé", "image", "article",
    "an", "jour", "fois", "heure", "semaine", "mois", "année", "minute", "lundi", "mardi",
    "mercredi", "jeudi", "vendredi", "samedi", "dimanche", "hier", "aujourd'hui", "soir",
    "matin", "nouveau", "grand", "petit", "premier", "dernier", "seul", "autre", "même",
    "bon", "mauvais", "gros", "vrai", "possible", "nombreux", "prochain", "cas", "chose",
    "façon", "manière", "moment", "fin", "début", "part", "personne", "gens", "monde",
    "homme", "femme", "suite", "coup", "tour", "face", "lieu", "raison", "ans", "second", "quoi",
    "vue", "ancien", "pourcent", "million", "milliard", "janvier", "février", "mars", "avril",
    "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre",
}
STOP = {w.lower() for w in STOP_WORDS} | MEDIA_NOISE

# Préfixes de rubrique en début de titre (« EN DIRECT - », « VIDÉO. »…).
PREFIX_RE = re.compile(
    r"^\s*(?:(?:EN\s+)?DIRECT|VID[EÉ]OS?|PHOTOS?|INFO\s+[A-Z]+|INFOGRAPHIES?|REPORTAGE|"
    r"T[EÉ]MOIGNAGES?|R[EÉ]CIT|ENQU[EÊ]TE|ENTRETIEN|INTERVIEW|TRIBUNE|CARTE|EXCLUSIF|"
    r"QUIZ|ANALYSE|DOCUMENT|PODCAST|LIVE)\s*[-–—.:,|]\s*",
    re.IGNORECASE,
)
# Élisions minuscules seulement : « Le Pen », « La Rochelle » doivent rester intacts.
LEADING_DET_RE = re.compile(r"^(?:l'|d'|de |du |des )")


@lru_cache(maxsize=1)
def get_nlp():
    return spacy.load("fr_core_news_sm", disable=["parser"])


def preprocess(title: str) -> str:
    previous = None
    while previous != title:  # « EN DIRECT - VIDÉO. … »
        previous, title = title, PREFIX_RE.sub("", title)
    return title.replace("’", "'").strip()


# Prénoms composés à ne pas couper (« Jean-Luc Mélenchon »).
COMPOUND_FIRST = {"jean", "marie", "anne", "pierre", "paul", "louis", "jacques", "charles",
                  "françois", "saint", "sainte", "jean-pierre", "jean-marie"}
ACRONYM_RE = re.compile(r"^[A-ZÀ-Ý]{2,5}$")


def _normalize_entity(text: str) -> str:
    text = LEADING_DET_RE.sub("", text.strip(" '\"«»-–:,."))
    return re.sub(r"\s+", " ", text)


def split_matchup(name: str) -> list[str]:
    """Coupe les duels « Mélenchon-Le Pen », « Manchester City-PSG » en deux entités,
    sans toucher à « Jean-Luc Mélenchon » ni « Seine-Saint-Denis »."""
    for i, c in enumerate(name):
        if c != "-" or i == 0 or i == len(name) - 1:
            continue
        left, right = name[:i].strip(), name[i + 1:].strip()
        if not right[:1].isupper():
            continue
        if (" " in left or ACRONYM_RE.match(right) or ACRONYM_RE.match(left)
                or (" " in right and left.lower() not in COMPOUND_FIRST)):
            return split_matchup(left) + split_matchup(right)
    return [name]


def _keep_word(word: str) -> bool:
    return len(word) >= 3 and word not in STOP and any(c.isalpha() for c in word) \
        and not any(c.isdigit() for c in word)


def terms_from_doc(doc) -> list[list[str]]:
    """Liste de [terme, type] sans doublon. type ∈ PER, LOC, ORG, NP (nom propre isolé), W (mot)."""
    terms: dict[str, str] = {}
    covered = set()
    for ent in doc.ents:
        if ent.label_ not in ENTITY_LABELS:
            continue
        for name in split_matchup(_normalize_entity(ent.text)):
            if len(name) >= 2 and name[0].isupper() and name.lower() not in STOP:
                terms.setdefault(name, ent.label_)
        covered.update(range(ent.start, ent.end))
    for tok in doc:
        if tok.i in covered or tok.pos_ not in KEPT_POS:
            continue
        # Un nom commun en tête de titre porte une majuscule et passe souvent pour un PROPN.
        if (tok.pos_ == "PROPN" and tok.i > 0 and tok.text[:1].isupper()
                and not tok.text.isupper()):
            term, kind = tok.text, "NP"
        else:
            term, kind = tok.lemma_.lower(), "W"
        if _keep_word(term.lower()):
            terms.setdefault(term, kind)
    return [[t, k] for t, k in terms.items()]


def extract_terms(titles: list[str]) -> list[list[list[str]]]:
    nlp = get_nlp()
    return [terms_from_doc(doc) for doc in nlp.pipe((preprocess(t) for t in titles), batch_size=128)]


def person_aliases(all_terms: list[list[list[str]]]) -> dict[str, str]:
    """« Macron » → « Emmanuel Macron », « Le Pen » → « Marine Le Pen », quand un seul nom
    complet correspond dans le corpus."""
    full_names: dict[str, set[str]] = {}
    for terms in all_terms:
        for term, kind in terms:
            parts = term.split()
            if kind == "PER" and len(parts) >= 2:
                full_names.setdefault(" ".join(parts[1:]), set()).add(term)
    return {last: next(iter(names)) for last, names in full_names.items() if len(names) == 1}


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def canonical_forms(all_terms: list[list[list[str]]]) -> dict[str, str]:
    """« Etats-Unis » → « États-Unis » (variantes d'accent, noms propres seulement :
    « retraite » et « retraité » sont deux mots) puis la casse : « ukraine » → « Ukraine »,
    mais « Présidentielle » → « présidentielle », selon la graphie la plus fréquente."""
    counts = Counter(term for terms in all_terms for term, _ in terms)
    proper = [t for t in counts if t[:1].isupper()]
    groups: dict[str, list[str]] = {}
    for term in proper:
        groups.setdefault(strip_accents(term).lower(), []).append(term)
    aliases = {}
    for variants in groups.values():
        best = max(variants, key=lambda t: (t != strip_accents(t), counts[t]))
        aliases.update({v: best for v in variants if v != best})
    lower_to_proper = {}
    for term in proper:
        target = aliases.get(term, term)
        if counts[target] >= lower_to_proper.get(term.lower(), ("", -1))[1]:
            lower_to_proper[term.lower()] = (target, counts[target])
    for term in counts:
        if term[:1].islower() and term in lower_to_proper:
            target, n = lower_to_proper[term]
            if n >= counts[term]:
                aliases[term] = target
            else:  # le nom commun domine : les variantes en majuscule le rejoignent
                for variant, best in list(aliases.items()) + [(target, target)]:
                    if best == target:
                        aliases[variant] = term
    return aliases


def make_resolver(aliases: dict[str, str]):
    """Suit les chaînes d'alias (« Pen » → « Le Pen » → « Marine Le Pen »)."""
    def resolve(term: str) -> str:
        for _ in range(4):
            if term not in aliases or aliases[term] == term:
                break
            term = aliases[term]
        return term
    return resolve
