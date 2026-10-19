# Partie IA — RESILIENCE-ALPHA

La partie IA comporte deux composants aux rôles bien séparés (sujet §3.3) :

| Composant | Rôle | Agit sur le système ? |
|---|---|---|
| `detector` | Détecte une anomalie par machine learning (Prometheus/Loki) **et** par contrôle de santé actif de l'API, puis prévient la remédiation | **Non** : il prévient, le moteur de remédiation (pôle Dev) décide et agit |
| `assistant` | Répond aux questions des opérateurs à partir de la documentation de l'équipe (RAG, Ollama + LangChain) | **Non** : lecture seule, aucun outil |

## Le flux

```
API paiement, WAF ──> Prometheus + Loki ──> detector (modèle LOF) ──webhook──> moteur de remédiation (Dev)
                                                 │
                                                 ├── /metrics ──> Prometheus ──> Grafana
                                                 └── /status  ──> dashboard React, assistant

Opérateur ──> dashboard ──> assistant /ask ──> passages de docs/ + LLM local (Ollama)
```

## Détection : ML + contrôle de santé actif

Le détecteur combine deux signaux à chaque cycle :

1. **Le modèle ML** (LocalOutlierFactor) sur les métriques Prometheus/Loki : détecte
   les comportements anormaux (pics de 5xx, de trafic, de blocages WAF…).
2. **Un contrôle de santé actif** : il interroge directement `GET /healthz` de l'API.

Règle : **anomalie si le ML la signale OU si l'API ne répond pas** ; **retour à la
normale seulement si le ML est normal ET l'API répond 200**.

Le contrôle de santé rattrape deux angles morts du ML seul — vérifiés en test :
- une **API tombée sans trafic** (aucune erreur 5xx à observer) est quand même détectée ;
- après un redémarrage, on ne déclare « recovered » que si l'API répond vraiment, ce qui
  évite un **faux retour à la normale** sous attaque persistante. C'est la réponse directe
  au sujet : « un conteneur qui redémarre ne constitue pas, à lui seul, une preuve de reprise ».

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
avec du trafic de transactions fictives avant d'entraîner. `traffic.py` simule des clients
légitimes en cycles **calme → montée en charge → palier → descente**. Le modèle doit avoir vu
tous ces régimes : entraîné sur 5 min de trafic stable, il prenait une simple montée en charge
pour une attaque (fausse alerte constatée en test). D'où **au moins 15-20 min** de collecte.

```powershell
.venv\Scripts\python traffic.py --target http://127.0.0.1:8080 --minutes 21   # dans un autre terminal
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
| `api_cpu` | Prometheus, API elle-même | `process_cpu_seconds_total{job="api"}` (cAdvisor n'expose pas le label `name` sur Docker Desktop) |
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

**Résultats sur notre plateforme** (collecte réelle du 2026-10-19 : 178 points de trafic normal
en 15 min — cycles calme / montée / palier / descente, de 0,3 à 4,4 req/s, générés par
`traffic.py` — et 24 points d'attaque callback → 5xx) :

| Indicateur | Valeur |
|---|---|
| Faux positifs (45 points de trafic normal de test) | 0 % |
| Précision | 100 % |
| Rappel (points d'attaque détectés) | 87,5 % |
| Matrice de confusion | TN 45, FP 0, FN 3, TP 21 |
| Fausses alertes en direct (5 min de trafic variable, 3 cycles) | 0 (score max −0,46, seuil 0) |
| Délai de reprise complète (détection + redémarrage) | ~30 s, nouvelle transaction réussie |

Les 3 points ratés (FN) sont les tout premiers de l'incident, avant que les fenêtres `rate[30s]`
ne montent : c'est attendu et sans conséquence (le debounce attend de toute façon 3 points).

**Compromis de sensibilité.** Entraîné sur un trafic normal riche, le modèle tolère mieux les
variations de charge, mais réagit moins aux petits taux d'erreurs : ~5 erreurs 5xx/s sont
nécessaires pour qu'il bascule seul (2/s restent sous le seuil). Une API réellement tombée est
de toute façon couverte par le contrôle de santé actif, indépendant du trafic.

**Fausse alerte corrigée.** Une première version, entraînée sur 5 min de trafic stable (~45 points),
prenait la *montée en charge* au démarrage du trafic pour une anomalie (score positif à 1,5 req/s) :
elle a déclenché un redémarrage inutile de l'API pendant un test. Le modèle actuel, entraîné sur
15 min de cycles variés, ne produit aucun score positif sur la même montée.

**Note sur l'évaluation.** Le découpage train/test du trafic normal est *mélangé* (`shuffle=True`),
pas chronologique. Les collectes étant courtes, un découpage chronologique isolerait tout un régime
de débit (les pics de charge) dans le test, que le modèle n'aurait jamais appris, ce qui gonflerait
artificiellement les faux positifs (mesuré : 67 % en chronologique contre 0 % en mélangé, mêmes données).

**Deux réglages appris en conditions réelles (importants pour la fiabilité en démo) :**
- **`n_neighbors` adapté à la taille du jeu** (`max(5, min(20, n//3))`). Avec une collecte courte
  (~45 points d'entraînement), un `n_neighbors` fixé à 20 fait dégénérer LOF : un incident franc
  (5xx = 20/s) obtenait un score négatif (classé normal) au lieu de +37. C'était un faux négatif
  silencieux qui aurait fait rater la reprise en direct.
- **`latency_p95` retirée des features.** Sur un PC Hôte saturé (toute la stack + Ollama), la latence
  au repos (~0,2 s) dépasse celle de l'entraînement et déclenche des faux positifs. L'incident se
  détecte très bien sans elle (surtout via `err_5xx_rate`). Elle est commentée dans `features.py`,
  réactivable sur une machine moins chargée.

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
| `traffic.py` | Simulateur de clients légitimes (trafic normal pour la collecte et la démo) |
| `detector/features.py` | Les requêtes Prometheus/Loki que le modèle observe |
| `detector/collect.py` | Enregistre les features dans `data/normal.csv` ou `data/attack.csv` |
| `detector/train.py` | Entraîne et évalue le modèle |
| `detector/service.py` | Détection en continu, `/status`, `/metrics`, webhook |
| `assistant/rag.py` | Chaîne RAG : documents → passages → LLM |
| `assistant/service.py` | API `/ask` |
| `docs/` | Base de connaissance de l'assistant (procédures, architecture, PCA/PRA en `.md`) |
| `tests/` | Tests sans réseau : `python -m pytest` |
