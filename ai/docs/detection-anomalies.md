# Procédure — Alerte du détecteur d'anomalies (AIOps)

## À quoi sert le détecteur

Le détecteur observe toutes les 5 secondes des indicateurs de la plateforme de paiement
(trafic, erreurs, latence, CPU de l'API, blocages du WAF). Il a appris à quoi ressemble le
fonctionnement normal. Quand l'activité ne ressemble plus à la normale pendant 3 mesures
d'affilée (environ 15 secondes), il déclare une anomalie et prévient automatiquement le
moteur de remédiation.

Le détecteur n'agit jamais lui-même sur le système. C'est le moteur de remédiation qui
décide et exécute l'action corrective.

## Les états possibles

| État | Signification | Que faire |
|---|---|---|
| normal | L'activité ressemble au trafic habituel. | Rien. |
| anomaly | Une anomalie est en cours, la remédiation a été prévenue. | Ne pas intervenir manuellement : laisser la reprise automatique se dérouler et suivre le dashboard. |
| unknown | Prometheus ou Loki ne répondent pas : le détecteur n'a pas de données. | Vérifier que les conteneurs prometheus et loki tournent. Aucune décision n'est prise sans données. |
| no_model | Aucun modèle entraîné, ou les features ont changé depuis l'entraînement. | Relancer la collecte puis l'entraînement (voir README de la partie IA). |

## Lire les « features en cause »

Chaque alerte indique les indicateurs les plus éloignés de la normale, avec un z-score :
le nombre d'écarts-types au-dessus (positif) ou en dessous (négatif) du trafic normal.
Un z-score de 8 signifie « très loin de l'habituel » ; un z-score de 1 est ordinaire.

| Feature en cause | Ce que cela suggère |
|---|---|
| req_rate très haut | Afflux de requêtes : possible déni de service. |
| req_rate proche de 0 | Plus aucune requête n'aboutit : service tombé ou injoignable. |
| err_4xx_rate haut | Beaucoup de requêtes refusées : brute force sur l'authentification, scan, ou injection bloquée. |
| err_5xx_rate haut | L'API plante : service dégradé ou base de données indisponible. |
| api_cpu haut | Le conteneur de l'API est saturé. |

## Vérifier que le service est vraiment rétabli

Le passage du détecteur à l'état normal (événement « recovered ») ne suffit pas à prouver
la reprise. Il faut aussi :

1. vérifier sur le dashboard que tous les services sont au vert ;
2. effectuer une nouvelle transaction fictive et vérifier qu'elle réussit ;
3. vérifier que les données sont cohérentes (pas de transaction en double ou perdue).

## Limites connues

- Le modèle ne connaît que le trafic normal enregistré pendant la collecte. Si l'usage
  change (nouveau parcours, charge plus forte), il faut collecter à nouveau et réentraîner.
- Une attaque lente et discrète, qui ressemble au trafic normal, peut ne pas être détectée.
- Une anomalie de disponibilité et une fuite de données ne demandent pas la même réponse :
  la reprise du service ne corrige pas une compromission.
