"""Tests de la qualification des incidents (calcul pur, sans réseau)."""
from detector.classify import classify


def feats(**zscores):
    """Fabrique une liste top_features triée par |zscore|, comme service.explain."""
    items = [{"name": name, "value": 0.0, "zscore": z} for name, z in zscores.items()]
    return sorted(items, key=lambda f: abs(f["zscore"]), reverse=True)


def test_api_down_prioritaire_meme_sans_feature():
    # API injoignable : classé api_down quel que soit le trafic (ex : panne sans requête).
    assert classify(feats(err_5xx_rate=0.1), api_healthy=False)["category"] == "api_down"


def test_scan_ou_injection_est_app_attack():
    # Beaucoup de 4xx (requêtes refusées) -> attaque applicative (scan, brute force).
    assert classify(feats(err_4xx_rate=8.0), api_healthy=True)["category"] == "app_attack"


def test_afflux_de_requetes_est_dos():
    assert classify(feats(req_rate=9.0), api_healthy=True)["category"] == "dos"


def test_erreurs_5xx_sans_attaque_est_service_error():
    # L'exploit du callback : l'API renvoie des 5xx sans attaque réseau visible.
    result = classify(feats(err_5xx_rate=9.0), api_healthy=True)
    assert result["category"] == "service_error"
    assert result["suspect_feature"] == "err_5xx_rate"


def test_5xx_dominant_malgre_trafic_reste_service_error():
    # Pendant l'exploit du callback, le trafic monte avec les 5xx. Les 5xx dominent
    # (z plus fort) : on doit retenir la panne, pas prendre ça pour un déni de service.
    assert classify(feats(err_5xx_rate=9.0, req_rate=4.0), api_healthy=True)["category"] == "service_error"


def test_attaque_prioritaire_sur_erreur_serveur():
    # Scan (4xx) ET 5xx en même temps : on retient l'attaque, plus actionnable.
    assert classify(feats(err_4xx_rate=7.0, err_5xx_rate=5.0), api_healthy=True)["category"] == "app_attack"


def test_anomalie_sans_feature_dominante_est_unknown():
    # Tout est à peine au-dessus de la normale : aucune cause ne ressort.
    assert classify(feats(req_rate=1.2, err_4xx_rate=0.8), api_healthy=True)["category"] == "unknown"


def test_blocages_waf_est_app_attack():
    # Pic de blocages WAF (scan/injection) -> attaque applicative.
    result = classify(feats(waf_blocks=8.0), api_healthy=True)
    assert result["category"] == "app_attack"
    assert result["suspect_feature"] == "waf_blocks"


def test_suspect_feature_coherente_avec_categorie():
    # Une feature anormalement BASSE (z très négatif) est top-1 par valeur absolue,
    # mais la catégorie vient d'une feature HAUTE : suspect_feature doit être la feature
    # haute (cohérente avec la catégorie), pas la basse sans rapport.
    result = classify(feats(req_rate=-6.0, err_5xx_rate=4.0), api_healthy=True)
    assert result["category"] == "service_error"
    assert result["suspect_feature"] == "err_5xx_rate"  # pas req_rate (bas)
