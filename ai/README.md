# Partie IA — RESILIENCE-ALPHA

La partie IA comporte deux composants aux rôles bien séparés (sujet §3.3) :

| Composant | Rôle | Agit sur le système ? |
|---|---|---|
| `detector` | Détecte une anomalie par machine learning à partir de Prometheus et Loki, puis prévient la remédiation | **Non** : il prévient, le moteur de remédiation (pôle Dev) décide et agit |
| `assistant` | Répond aux questions des opérateurs à partir de la documentation de l'équipe (RAG, Ollama + LangChain) | **Non** : lecture seule, aucun outil |

## Le flux

```
API paiement, WAF ──> Prometheus + Loki ──> detector (modèle LOF) ──webhook──> moteur de remédiation (Dev)
                                                 │
                                                 ├── /metrics ──> Prometheus ──> Grafana
                                                 └── /status  ──> dashboard React, assistant

Opérateur ──> dashboard ──> assistant /ask ──> passages de docs/ + LLM local (Ollama)
```

## Lancer

**En local (développement, tests)** depuis `ai/` :

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest
```

**Avec Docker**, depuis la racine du dépôt (le compose principal inclut `ai/compose.yml` ;
sans compose principal, ajouter `-f ai/compose.yml` à chaque commande) :

```powershell
docker compose up -d --build detector assistant ollama
docker compose exec ollama ollama pull qwen2.5:3b         # LLM, 3 milliards de paramètres
docker compose exec ollama ollama pull nomic-embed-text   # modèle d'embeddings du RAG
```

Si le LLM tourne sur le PC de délestage IA : ne pas lancer `ollama`, et définir
`OLLAMA_URL=http://<ip-du-pc-ia>:11434` dans le `.env`. C'est l'option **recommandée**
si le PC Hôte manque d'espace disque : l'image Ollama + les modèles pèsent ~5–6 Go.
Prévoir 10 Go libres sur le PC Hôte avant de lancer `ollama` localement.

## Entraîner le détecteur

Le modèle apprend le trafic **normal** de *notre* plateforme : il faut donc la faire tourner
avec du trafic de transactions fictives avant d'entraîner.

```powershell
docker compose run --rm detector python -m detector.collect --label normal --minutes 20
docker compose run --rm detector python -m detector.collect --label attack --minutes 5   # pendant l'attaque
docker compose run --rm detector python -m detector.train    # écrit data/model.joblib et data/report.json
docker compose restart detector
```

## Contrat d'interface avec les autres pôles

À valider avec Dev et Infra. Si un nom change, seul `detector/features.py` est à modifier (puis réentraîner).

**Ce que l'IA lit** (à fournir par Dev / Infra) :

| Feature | Source | Requête |
|---|---|---|
| `req_rate` | Prometheus, API métier | `http_requests_total` |
| `err_4xx_rate`, `err_5xx_rate` | Prometheus, API métier | `http_requests_total{status=~"4.."}`, `{status=~"5.."}` |
| `latency_p95` | Prometheus, API métier | `http_request_duration_seconds_bucket` |
| `api_cpu` | Prometheus, cAdvisor | `container_cpu_usage_seconds_total{name=~".*api.*"}` |
| `waf_blocks` | Loki, logs du WAF | `{container="waf"} \|= "403"` |

**Ce que l'IA envoie** au moteur de remédiation, à chaque changement d'état :

```http
POST $REMEDIATION_URL
Authorization: Bearer $REMEDIATION_TOKEN

{
  "event": "anomaly",            // ou "recovered"
  "score": 12.4,                 // > 0 = anormal
  "top_features": [{"name": "err_5xx_rate", "value": 8.0, "zscore": 9.1}, ...],
  "timestamp": "2026-10-21T14:03:12+00:00"
}
```

**Ce que l'IA expose** sur le réseau interne :

| URL | Pour qui |
|---|---|
| `detector:8000/metrics` | Prometheus : `aiops_anomaly_score`, `aiops_anomaly` (0/1), pour Grafana |
| `detector:8000/status` | Dashboard : état (`normal`, `anomaly`, `unknown`, `no_model`), score, features en cause |
| `assistant:8001/ask` | Dashboard : `POST {"question": "..."}` → `{"answer", "sources"}` |

## Sécurité

- Aucun service IA n'a accès au socket Docker ni à une action sur le système.
- L'assistant n'a aucun outil : il lit `docs/` (monté en lecture seule) et `/status`, rien d'autre.
- Le token du webhook vient de l'environnement (Vault/SOPS), jamais du code.
- Les conteneurs tournent sans être root ; les ports ne sont publiés que sur `127.0.0.1`.
- Aucune donnée réelle : uniquement les métriques de la plateforme fictive.

## Pour le dossier technique (§3.3)

**Données.** Six features mesurées toutes les 5 s (tableau ci-dessus). La collecte utilise
la même fonction que le service en production (`fetch_now`) : le modèle est entraîné exactement
sur ce qu'il voit en direct.

**Préparation.** Une valeur absente (aucune erreur 5xx) ou NaN (latence sans trafic) devient 0.
Les features sont centrées-réduites (`StandardScaler`) pour être comparables. Le trafic normal
est découpé dans le temps : les 75 % les plus anciens pour l'entraînement, les 25 % les plus
récents pour le test.

**Modèle.** `LocalOutlierFactor` (scikit-learn), non supervisé : il n'apprend que le trafic normal
et mesure à quel point un nouveau point est éloigné de ses 20 plus proches voisins.
Le seuil n'est pas codé en dur : il est déduit des données (1 % du trafic normal toléré comme atypique).
Le service ne déclare une anomalie qu'après 3 points anormaux d'affilée (~15 s), pour ne pas
déclencher une remédiation sur un pic isolé. Chaque alerte est expliquée par les features les
plus éloignées de la normale (z-score).

**Choix du modèle.** Trois modèles comparés sur des données simulées (part de points détectés) :

| Scénario simulé | IsolationForest | **LOF (retenu)** | EllipticEnvelope |
|---|---|---|---|
| Faux positifs sur trafic normal | 0,5 % | 0,5 % | 1 % |
| DoS : requêtes ×5, CPU ×3, latence ×4 | 100 % | 100 % | 100 % |
| Requêtes ×3 seules | 14 % | 100 % | 100 % |
| API tombée : 0 requête, 5 erreurs 5xx/s | 32 % | 100 % | 100 % |
| 2 erreurs 5xx/s (0 en temps normal) | 1 % | 100 % | 1 % |
| Brute force : 10 erreurs 4xx/s | 92 % | 100 % | 100 % |
| WAF : 20 blocages / 30 s (0 en temps normal) | 1 % | 100 % | 1 % |

IsolationForest ne coupe jamais sur une feature constante pendant l'apprentissage : il ne voit
donc pas une feature qui vaut toujours 0 en temps normal (erreurs 5xx, blocages WAF), alors que
c'est précisément ce qui bouge lors d'un incident.

**Résultats sur notre plateforme** (collecte réelle du 2026-10-19 : ~59 points de trafic normal
varié de 0,3 à 10 req/s, ~24 points d'attaque callback → 5xx) :

| Indicateur | Valeur |
|---|---|
| Faux positifs (trafic normal) | 0 % |
| Précision | 100 % |
| Rappel (points d'attaque détectés) | 87,5 % |
| Matrice de confusion | TN 15, FP 0, FN 3, TP 21 |
| Délai de détection observé (bout en bout) | ~13 s après le début de l'incident |
| Délai de reprise complète (détection + redémarrage) | ~26 s, nouvelle transaction réussie |

Les 3 points ratés (FN) sont les tout premiers de l'incident, avant que les fenêtres `rate[30s]`
ne montent : c'est attendu et sans conséquence (le debounce attend de toute façon 3 points).

**Note sur l'évaluation.** Le découpage train/test du trafic normal est *mélangé* (`shuffle=True`),
pas chronologique. Les collectes étant courtes, un découpage chronologique isolerait tout un régime
de débit (les pics de charge) dans le test, que le modèle n'aurait jamais appris, ce qui gonflerait
artificiellement les faux positifs (mesuré : 67 % en chronologique contre 0 % en mélangé, mêmes données).

## Assistant RAG — vérifié en réel

Testé le 2026-10-19 avec `qwen2.5:3b` + `nomic-embed-text` sur Ollama local : l'assistant
répond en français à partir de `docs/`, cite sa source, et dit « je ne sais pas » hors périmètre.
Les passages sont découpés en 1500 caractères (et non 800) pour qu'un **tableau Markdown** ne soit
pas coupé entre son en-tête et ses lignes — sinon une ligne comme « err_5xx_rate → l'API plante »
devient introuvable. Rédiger les docs de l'équipe avec des titres clairs et des tableaux courts.

## Limites du détecteur

- Le modèle ne connaît que le trafic normal enregistré : si l'usage change, il faut réentraîner.
- Une feature toujours nulle en temps normal n'a pas d'échelle apprise : une petite valeur
  (ex : 0,5 erreur 5xx/s) passe inaperçue, seule une hausse franche est détectée.
- Une attaque lente qui imite le trafic normal (exfiltration discrète) peut ne pas être vue.
- Le détecteur dit *qu'il y a* une anomalie et *sur quoi* ; le choix de l'action reste à la remédiation.
- Les noms de métriques sont des hypothèses tant que Dev et Infra ne les ont pas confirmés.

## Fichiers

| Fichier | Rôle |
|---|---|
| `config.py` | Tous les réglages (URLs, seuils, modèles), lus depuis l'environnement |
| `detector/features.py` | Les requêtes Prometheus/Loki que le modèle observe |
| `detector/collect.py` | Enregistre les features dans `data/normal.csv` ou `data/attack.csv` |
| `detector/train.py` | Entraîne et évalue le modèle |
| `detector/service.py` | Détection en continu, `/status`, `/metrics`, webhook |
| `assistant/rag.py` | Chaîne RAG : documents → passages → LLM |
| `assistant/service.py` | API `/ask` |
| `docs/` | Base de connaissance de l'assistant (procédures, architecture, PCA/PRA en `.md`) |
| `tests/` | Tests sans réseau : `python -m pytest` |
