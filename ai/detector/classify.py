"""Qualifie une anomalie détectée : de quel genre d'incident s'agit-il ?

Le modèle dit *qu'il y a* une anomalie et *quelles features* sont les plus
éloignées de la normale (z-scores). Cette qualification traduit ces features en
une catégorie lisible, pour que la remédiation choisisse la bonne réponse et que
l'opérateur comprenne vite ce qui se passe.

Ce module ne fait que CLASSER (calcul pur, aucune action, aucun réseau) :
décider et agir restent du ressort de la remédiation (pôle Dev).

Les catégories, du signal le plus caractéristique au moins spécifique :
- api_down      : l'API ne répond plus (contrôle de santé), avec ou sans trafic
- app_attack    : beaucoup de requêtes refusées / bloquées (scan, injection, brute force)
- dos           : afflux massif de requêtes (déni de service)
- service_error : l'API renvoie des erreurs 5xx sans signe d'attaque réseau (panne interne)
- unknown       : anormal, mais aucune feature ne domine nettement
"""

# Au-delà de ce z-score, une feature est considérée « nettement anormale ».
# Cohérent avec l'échelle du modèle (StandardScaler) : ~3 écarts-types.
STRONG = 3.0


def classify(top_features: list[dict], api_healthy: bool) -> dict:
    """Catégorise l'incident à partir des features en cause et de la santé de l'API.

    top_features : liste {name, value, zscore}, triée par |zscore| (voir service.explain).
    Renvoie {category, reason, suspect_feature} : suspect_feature est la feature
    la plus anormale, celle que la remédiation ou l'opérateur regardera en premier.
    """
    # Les features anormalement HAUTES (z positif fort) : c'est la hausse qui trahit l'incident,
    # pas une valeur basse. On indexe par nom pour un accès simple.
    high = {f["name"]: f["zscore"] for f in top_features if f["zscore"] >= STRONG}
    worst = top_features[0]["name"] if top_features else None

    # 1. API injoignable : le signal le plus sûr, indépendant du trafic.
    if not api_healthy:
        return _result("api_down", "L'API ne répond plus au contrôle de santé.", worst)

    if not high:
        return _result("unknown", "Comportement anormal sans cause dominante identifiée.", worst)

    # On catégorise selon la feature la PLUS anormale, pas selon un ordre fixe :
    # pendant l'exploit du callback, le trafic monte en même temps que les 5xx ;
    # c'est le signal le plus fort qui dit s'il s'agit d'une panne ou d'un afflux.
    dominante = max(high, key=high.get)
    categories = {
        "err_4xx_rate": ("app_attack", "Beaucoup de requêtes refusées : scan, injection ou brute force probable."),
        "waf_blocks": ("app_attack", "Beaucoup de requêtes bloquées par le WAF : scan ou injection probable."),
        "req_rate": ("dos", "Afflux massif de requêtes : déni de service probable."),
        "err_5xx_rate": ("service_error", "L'API renvoie des erreurs internes (5xx) : panne ou vulnérabilité exploitée."),
    }
    category, reason = categories.get(dominante, ("unknown", "Comportement anormal sans cause dominante identifiée."))
    return _result(category, reason, worst)


def _result(category: str, reason: str, suspect_feature: str | None) -> dict:
    return {"category": category, "reason": reason, "suspect_feature": suspect_feature}
