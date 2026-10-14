"""Classement thématique d'un terme (repris et étendu de categorizeWord() de la maquette)."""

CATEGORIES = {
    "politique": [
        "gouvernement", "président", "présidentiel", "ministre", "parti", "élection", "électoral",
        "député", "sénat", "sénateur", "assemblée", "législatif", "municipal", "vote", "scrutin",
        "candidat", "campagne", "macron", "le pen", "bardella", "mélenchon", "lfi",
        "rassemblement national", "renaissance", "républicain", "socialiste", "écologiste",
        "matignon", "élysée", "motion", "censure", "réforme", "maire", "politique", "gauche",
        "droite", "extrême", "insoumis", "attal", "retailleau", "philippe", "glucksmann", "rn", "ps", "lr",
        "zemmour", "hollande", "sarkozy", "lecornu", "bayrou", "ruffin", "tondelier",
    ],
    "international": [
        "ukraine", "russie", "russe", "poutine", "zelensky", "israël", "israélien", "gaza",
        "hamas", "palestinien", "liban", "iran", "syrie", "chine", "chinois", "états-unis",
        "américain", "trump", "washington", "otan", "onu", "guerre", "moyen-orient", "europe",
        "européen", "bruxelles", "allemagne", "royaume-uni", "inde", "afrique", "diplomat",
        "frappe", "cessez-le-feu", "houthiste", "kremlin", "pékin", "téhéran", "riyad",
        "kiev", "kyiv", "moscou", "netanyahou", "xi jinping", "pape", "vatican", "léon xiv",
        "venezuela", "soudan", "taïwan", "corée",
    ],
    "économie": [
        "économie", "économique", "inflation", "euro", "bourse", "entreprise", "emploi",
        "chômage", "croissance", "budget", "impôt", "fiscal", "dette", "prix", "salaire",
        "retraite", "banque", "marché", "industrie", "commerce", "taxe", "pib", "énergie",
        "carburant", "électricité", "smic", "pouvoir d'achat", "licenciement", "grève",
    ],
    "société": [
        "justice", "procès", "tribunal", "police", "gendarme", "enquête", "meurtre", "attaque",
        "attentat", "terroris", "violence", "école", "collège", "lycée", "lycéen", "élève",
        "université", "étudiant", "logement", "immigration", "migrant", "agriculteur",
        "accident", "incendie", "drame", "victime", "prison", "fusillade", "manifestation",
        "mobilisation", "jeune", "famille", "enfant",
    ],
    "sport": [
        "sport", "football", "foot", "rugby", "tennis", "match", "championnat", "coupe",
        "ligue", "psg", "om", "olympique", "jo", "tour de france", "mbappé", "bleus",
        "sélection", "entraîneur", "but", "victoire", "défaite", "finale", "stade", "joueur",
        "manchester", "real madrid", "barcelone", "ligue 1", "champions",
    ],
    "culture": [
        "culture", "cinéma", "film", "musique", "livre", "théâtre", "festival", "série",
        "artiste", "chanteur", "musée", "exposition", "concert", "roman", "prix goncourt",
        "acteur", "actrice", "album",
    ],
    "sciences": [
        "santé", "hôpital", "médecin", "vaccin", "covid", "maladie", "cancer", "traitement",
        "climat", "climatique", "environnement", "écologie", "carbone", "pollution",
        "biodiversité", "météo", "canicule", "inondation", "tempête", "sécheresse",
        "technologie", "numérique", "internet", "intelligence artificielle", "ia", "données",
        "espace", "science", "scientifique", "recherche", "nucléaire",
    ],
}
ORDER = list(CATEGORIES) + ["général"]


def categorize(term: str) -> str:
    t = term.lower().replace("etats-unis", "états-unis")
    words = set(t.replace("-", " ").split())
    for category, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw == t or kw in words or (" " in kw and kw in t) or (len(kw) >= 5 and t.startswith(kw)):
                return category
    return "général"
