---
name: retrain-model
description: |
  Workflow complet pour (ré)entraîner le détecteur d'anomalies : collecte du
  trafic normal, collecte pendant l'attaque, entraînement, lecture du rapport,
  mise à jour du README.
  TOUJOURS utiliser ce skill quand l'utilisateur dit : "entraîne le modèle",
  "réentraîne", "collecte les données", "on a changé l'API", "nouvelle
  attaque", "les résultats du modèle", "remplis les résultats du dossier".
---

# (Ré)entraîner le détecteur

Les commandes se lancent depuis la racine du dépôt, stack complète démarrée
(API, Prometheus, Loki, WAF, générateur de transactions).

## 1. Vérifier que les features remontent

```powershell
docker compose run --rm detector python -c "from detector.features import fetch_now; print(fetch_now())"
```

Chaque feature doit avoir une valeur plausible. Une erreur HTTP ou une feature
toujours à 0 alors que du trafic passe : corriger `ai/detector/features.py` avec
les vrais noms de métriques et de labels avant d'aller plus loin.

## 2. Collecter le trafic normal (au moins 20 minutes)

Dans un premier terminal, lancer le simulateur de clients (depuis `ai/`) :

```powershell
.venv\Scripts\python traffic.py --target http://127.0.0.1:8080 --minutes 21
```

Dans un second terminal, collecter :

```powershell
docker compose run --rm detector python -m detector.collect --label normal --minutes 20
```

Le simulateur enchaîne phases calmes, montées en charge, paliers et descentes, avec
quelques erreurs 4xx ordinaires. Ne pas raccourcir la collecte : avec 5 minutes de
trafic stable, le modèle a pris une montée en charge pour une attaque (fausse alerte
et redémarrage inutile constatés en test). Aucune attaque pendant cette phase, sinon
le modèle apprendra l'attaque comme « normale ». Repartir d'un fichier vide si le
comportement de l'API a changé (supprimer `ai/data/normal.csv`).

## 3. Collecter pendant l'attaque

Lancer la collecte, puis l'attaque depuis le PC Attaquant (pôle Cyber) :

```powershell
docker compose run --rm detector python -m detector.collect --label attack --minutes 5
```

Ne garder que la période où l'attaque est active : supprimer à la main dans
`ai/data/attack.csv` les lignes d'avant le lancement et d'après l'arrêt.

## 4. Entraîner et lire le rapport

```powershell
docker compose run --rm detector python -m detector.train
docker compose restart detector
```

Lire `ai/data/report.json` :

| Indicateur | Cible | Si raté |
|---|---|---|
| `false_positive_rate` | < 2 % | collecter plus de trafic normal, plus varié |
| `recall` | > 80 % des points d'attaque | vérifier que la métrique qui bouge pendant l'attaque fait partie des features |

Le rappel est mesuré point par point : les premiers points d'une attaque, avant que
les fenêtres `rate[30s]` ne montent, sont souvent ratés. C'est attendu.

## 5. Vérifier en conditions réelles

Relancer l'attaque et suivre `curl -s http://127.0.0.1:8000/status` : passage en
`anomaly`, webhook reçu par la remédiation, puis retour à `normal`. Noter le délai
de détection observé.

## 6. Reporter les résultats

Mettre à jour `ai/README.md`, section « Résultats sur notre plateforme » : chiffres
du rapport, volume de données, délai de détection, type d'attaque testée. Ce sont
ces chiffres qui iront dans le dossier technique.
