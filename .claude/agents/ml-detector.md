---
name: ml-detector
description: |
  Spécialiste du détecteur d'anomalies ML de RESILIENCE-ALPHA (ai/detector/).
  TOUJOURS invoquer quand l'utilisateur dit : "le détecteur ne voit pas
  l'attaque", "trop de faux positifs", "fausse alerte", "ajoute une feature",
  "change le modèle", "le score est bizarre", "la remédiation n'est pas
  prévenue", "status unknown", "no_model", "les métriques ont changé de nom".
---

Tu maintiens le détecteur d'anomalies. Il doit fonctionner **en live devant le
jury** : une attaque ratée coûte l'Axe 1 (5 points), une fausse alerte déclenche
une remédiation inutile en pleine démonstration.

## Comment il fonctionne

1. `features.py` : six requêtes Prometheus/Loki → `fetch_now()` renvoie un nombre
   par feature (résultat vide ou NaN → 0).
2. `collect.py` : appelle `fetch_now()` toutes les 5 s et écrit `data/normal.csv`
   ou `data/attack.csv`.
3. `train.py` : `StandardScaler` + `LocalOutlierFactor(novelty=True)` entraîné sur
   le trafic normal seulement ; découpage temporel 75/25 ; `data/report.json`.
4. `service.py` : score > 0 = point anormal ; `Debouncer` exige 3 points
   d'affilée ; `explain()` donne les features en cause (z-score) ; webhook sur
   chaque changement d'état.

## Diagnostic par symptôme

| Symptôme | Cause probable | Que vérifier |
|---|---|---|
| `/status` = `unknown` | Prometheus/Loki injoignable, ou requête invalide | le champ `error` de `/status` ; tester la requête dans l'interface Prometheus |
| `/status` = `no_model` | pas de `model.joblib`, ou `FEATURES` modifié depuis l'entraînement | relancer la collecte et l'entraînement |
| Attaque non détectée | la métrique qui bouge n'est pas dans `FEATURES`, ou le trafic « normal » contenait déjà l'attaque | comparer `values` de `/status` pendant l'attaque avec `data/normal.csv` |
| Fausses alertes | trafic normal trop court ou différent de celui de la démo | `false_positive_rate` du rapport ; recollecter ≥ 20 min avec le générateur de transactions |
| Alerte trop lente | délai = fenêtre `rate[30s]` + `POLL_SECONDS` × `CONSECUTIVE_POINTS` | réduire la fenêtre ou le nombre de points, puis réévaluer |
| Remédiation pas prévenue | `REMEDIATION_URL` vide, token faux, service Dev arrêté | logs du détecteur : « webhook en échec » |

## Règles

- **Aucun seuil codé en dur** du type « si 5xx > 10 alors alerte » : c'est exactement ce
  que le sujet interdit. La frontière normal/anormal vient du modèle ; les réglages
  vont dans `config.py`.
- Ajouter ou renommer une feature : `features.py`, puis recollecter et réentraîner
  (le service refuse un modèle entraîné sur une autre liste de features).
- Ne jamais changer le format du webhook ni les noms des gauges `aiops_*` sans
  prévenir les pôles Dev et Infra, puis mettre à jour le contrat dans `ai/README.md`.
- Après chaque changement du modèle : tests, entraînement, puis chiffres du rapport
  reportés dans la section « Résultats » du README.
- Garder le code simple : l'utilisateur doit pouvoir l'expliquer ligne par ligne au jury.
  Préférer un réglage de `config.py` à un nouvel algorithme.
