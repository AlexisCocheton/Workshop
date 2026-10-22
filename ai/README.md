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
| `waf_blocks` | Loki, logs du WAF | `count_over_time({container="waf"} \|= "WAF_BLOCK" [30s])` |

> `waf_blocks` compte le marqueur `WAF_BLOCK` que le WAF ajoute à chaque blocage (pas le simple
> texte « 403 », qui apparaissait aussi dans des 403 applicatifs et faussait le modèle). Ce marqueur
> est absent du trafic normal : la feature vaut 0 au repos et monte sur une attaque applicative.

**Ce que l'IA envoie** au moteur de remédiation, à chaque changement d'état :

```http
POST $REMEDIATION_URL
Authorization: Bearer $REMEDIATION_TOKEN

{
  "event": "anomaly",            // ou "recovered"
  "score": 12.4,                 // > 0 = anormal
  "top_features": [{"name": "err_5xx_rate", "value": 8.0, "zscore": 9.1}, ...],
  "incident": {"category": "service_error", "reason": "...", "suspect_feature": "err_5xx_rate"},
  "timestamp": "2026-10-21T14:03:12+00:00"
}
```

**Ce que l'IA expose** sur le réseau interne :

| URL | Pour qui |
|---|---|
| `detector:8000/metrics` | Prometheus : `aiops_anomaly_score`, `aiops_anomaly` (0/1), pour Grafana |
| `detector:8000/status` | Dashboard : état (`normal`, `anomaly`, `unknown`, `no_model`), score, features en cause |
| `assistant:8001/ask` | Dashboard : `POST {"question": "..."}` → `{"answer", "sources"}` |
| `127.0.0.1:8002/verify` (PC Hôte, hors Docker) | `auth` via `host.docker.internal` : `POST {"username": "..."}` → `{"recognized", "reason"}` |

## Qualification de l'incident (détecteur spécialisé défense)

Quand le détecteur passe en anomalie, il ne dit plus seulement « anomalie » : il **qualifie
l'incident** par une catégorie, à partir de la feature la plus anormale (le z-score que le
modèle calcule déjà). Cela permet à la remédiation de choisir la bonne réponse et à
l'opérateur de comprendre tout de suite à quoi il a affaire.

| Catégorie | Déclenchée par | Sens |
|---|---|---|
| `api_down` | l'API ne répond plus (contrôle de santé) | panne de disponibilité, avec ou sans trafic |
| `app_attack` | pic d'erreurs 4xx ou de blocages WAF | scan, injection, brute force |
| `dos` | afflux de requêtes (`req_rate`) | déni de service |
| `service_error` | pic d'erreurs 5xx | panne interne ou vulnérabilité exploitée (ex : callback) |
| `unknown` | anormal sans feature dominante | à investiguer avant d'agir |

La catégorie est choisie selon la feature **la plus** anormale (pas un ordre fixe) : pendant
l'exploit du callback, le trafic monte avec les 5xx, mais les 5xx dominent, donc c'est bien
`service_error` et non `dos`. Le détecteur **ne décide ni n'agit** : il qualifie. La catégorie
est ajoutée au webhook, au `/status` (champ `incident`) et à l'alerte Telegram.

Côté réponse : l'assistant RAG dispose d'une procédure par catégorie (`docs/reponse-incident.md`),
pour guider l'opérateur. La riposte active (bloquer la source d'une attaque) est une action **au
WAF**, décidée par l'humain ou ajoutée au moteur de remédiation (pôle Dev) — jamais par le
détecteur ni l'assistant.

Qualification testée sans réseau : `tests/test_classify.py`.

## Alerte Telegram (notification humaine)

En plus de la remédiation automatique, le détecteur envoie un message Telegram au
**changement d'état** (passage en anomalie, puis retour à la normale) — jamais à chaque
point : même logique que le webhook, après le debounce de 3 points. L'alerte porte le score
et les features en cause, pour que l'opérateur sache *quoi* regarder.

Le détecteur **n'agit pas** pour autant : il notifie, la remédiation corrige. C'est une
alerte de supervision, pas un canal de commande.

Configuration (dans `.env`, jamais dans le code) :

```
TELEGRAM_BOT_TOKEN=123456789:ABC...     # donné par @BotFather
TELEGRAM_CHAT_ID=...                     # id du destinataire (voir ci-dessous)
```

Récupérer le `chat_id` : écrire un message au bot, puis ouvrir
`https://api.telegram.org/bot<TOKEN>/getUpdates` → champ `chat.id`.

Si les deux variables sont vides, l'alerte est simplement désactivée : le détecteur fonctionne
à l'identique. Une alerte qui échoue (réseau coupé) n'interrompt jamais la détection.

## Sécurité

- Aucun service IA n'a accès au socket Docker ni à une action sur le système.
- L'assistant n'a aucun outil : il lit `docs/` (monté en lecture seule) et `/status`, rien d'autre.
- Le token du webhook vient de l'environnement (Vault/SOPS), jamais du code.
- Les conteneurs tournent sans être root ; les ports ne sont publiés que sur `127.0.0.1`.
- Aucune donnée réelle : uniquement les métriques de la plateforme fictive.

## Pour le dossier technique (§3.3)

**Données.** Cinq features mesurées toutes les 5 s (tableau ci-dessus). La collecte utilise
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

**Résultats sur notre plateforme** (collecte réelle du 2026-10-22 : 173 points de trafic normal
en 15 min — cycles calme / montée / palier / descente, de 0,4 à 4,6 req/s, générés par
`traffic.py`, incluant la navigation sur la boutique `/shop/*` et ~3 % d'erreurs 4xx légitimes
(jetons expirés) — et 36 points d'attaque scan + callback, avec blocages WAF) :

| Indicateur | Valeur |
|---|---|
| Faux positifs (44 points de trafic normal de test) | 0 % |
| Précision | 100 % |
| Rappel (points d'attaque détectés) | 91,7 % (33/36) |
| Matrice de confusion | TN 44, FP 0, FN 3, TP 33 |
| Délai de reprise complète (détection + redémarrage) | ~30 s, nouvelle transaction réussie |

Le modèle inclut le trafic de la boutique, la feature `waf_blocks` et, désormais, un faible taux
d'erreurs 4xx légitimes dans le trafic normal : il tolère ainsi qu'un opérateur ou un client
génère ponctuellement des 401/403 sans crier à l'attaque (voir « Dérive applicative » plus bas).
Les 3 points d'attaque ratés sont des points de bordure (début/fin d'attaque, sans 5xx ni blocage
WAF, quasi indiscernables du normal) — absorbés par le debounce 3-points.

**Compromis de sensibilité.** Entraîné sur un trafic normal riche, le modèle tolère mieux les
variations de charge, mais réagit moins aux petits taux d'erreurs : ~5 erreurs 5xx/s sont
nécessaires pour qu'il bascule seul (2/s restent sous le seuil). Une API réellement tombée est
de toute façon couverte par le contrôle de santé actif, indépendant du trafic.

**Fausse alerte corrigée.** Une première version, entraînée sur 5 min de trafic stable (~45 points),
prenait la *montée en charge* au démarrage du trafic pour une anomalie (score positif à 1,5 req/s) :
elle a déclenché un redémarrage inutile de l'API pendant un test. Le modèle actuel, entraîné sur
des cycles variés (boutique incluse), ne produit aucun score positif sur la même montée.

**Dérive applicative (data drift) — cas vécu, instructif.** En sécurisant `GET /orders` (jeton
obligatoire), le dashboard s'est mis à recevoir des 401 en boucle quand son jeton manquait ou avait
expiré. Ce flux de 4xx, *jamais vu à l'entraînement*, a fait basculer le détecteur en anomalie
permanente : un **faux positif**, non pas dû au modèle mais à un changement de l'application qui a
modifié la distribution du trafic. Double correction : (1) côté application, le dashboard cesse de
marteler l'API et repasse par la connexion sur un 401 ; (2) côté modèle, le trafic normal de
réentraînement inclut désormais un faible taux de 4xx légitimes, pour que le détecteur les tolère.
C'est le risque classique d'un détecteur figé face à une plateforme qui évolue : toute modification
notable de l'application doit s'accompagner d'une recollecte et d'un réentraînement.

**Note sur l'évaluation.** Le découpage train/test du trafic normal est *mélangé* (`shuffle=True`),
pas chronologique. Les collectes étant courtes, un découpage chronologique isolerait tout un régime
de débit (les pics de charge) dans le test, que le modèle n'aurait jamais appris, ce qui gonflerait
artificiellement les faux positifs (mesuré : 67 % en chronologique contre 0 % en mélangé, mêmes données).

**Deux réglages appris en conditions réelles (importants pour la fiabilité en démo) :**
- **`n_neighbors` adapté à la taille du jeu** (`max(5, min(40, n//3))`). Avec une collecte courte
  (~45 points d'entraînement), trop de voisins fait dégénérer LOF : un incident franc (5xx = 20/s)
  obtenait un score négatif (classé normal) au lieu de +37 — un faux négatif silencieux. À l'inverse,
  sur une collecte longue (~170 points), trop *peu* de voisins (plafond à 20) rend la frontière de
  densité sensible à un point normal isolé : ~35-40 voisins la lissent et éliminent ce faux positif
  sans manquer d'attaque (vérifié). D'où le plafond relevé à 40, qui s'adapte aux deux régimes.
- **`latency_p95` retirée des features.** Sur un PC Hôte saturé (toute la stack + Ollama), la latence
  au repos (~0,2 s) dépasse celle de l'entraînement et déclenche des faux positifs. L'incident se
  détecte très bien sans elle (surtout via `err_5xx_rate`). Elle est commentée dans `features.py`,
  réactivable sur une machine moins chargée.

## Assistant RAG — vérifié en réel

Testé avec `qwen2.5:3b` + `nomic-embed-text` sur Ollama local : l'assistant
répond en français à partir de `docs/`, cite sa source, et dit « je ne sais pas » hors périmètre.
Les passages sont découpés en 1500 caractères (et non 800) pour qu'un **tableau Markdown** ne soit
pas coupé entre son en-tête et ses lignes — sinon une ligne comme « err_5xx_rate → l'API plante »
devient introuvable. Rédiger les docs de l'équipe avec des titres clairs et des tableaux courts.

**Recherche hybride (BM25 + vectoriel).** Deux recherches tournent en parallèle sur les mêmes
passages, puis leurs classements sont fusionnés par *Reciprocal Rank Fusion* :

- **vectorielle** (embeddings) : trouve les passages au **sens** proche de la question ;
- **BM25** (mots-clés) : trouve les **termes exacts** — un nom de feature (`err_5xx_rate`), une
  catégorie d'incident (`app_attack`)… que la recherche vectorielle seule rate souvent.

Chacune compense l'angle mort de l'autre. Implémenté simplement (bibliothèque `rank-bm25` + fusion
maison, pas de grosse dépendance), testable sans Ollama (`tests/test_rag.py` : BM25 retrouve un
identifiant exact, la fusion favorise un passage bien classé par les deux méthodes).

> **Performance.** Les embeddings et la génération tournent sur Ollama **CPU**. Sur un PC Hôte
> saturé (peu de RAM libre), la première réponse peut être lente (construction de l'index +
> chargement du modèle). Pour la démo, précharger les modèles et, si besoin, déporter Ollama sur
> le PC de délestage IA (`OLLAMA_URL`) : c'est l'option recommandée quand la RAM manque.

**Évaluation de la recherche.** Un jeu de 17 questions d'opérateur (`assistant/eval_questions.py`),
couvrant les quatre documents de `docs/` (détection, réponse à incident, architecture, continuité/reprise),
chacune liée au document qui contient la réponse et à un terme exact attendu. Le script
`assistant/evaluate.py` mesure, pour chaque méthode, la part de bonnes réponses retrouvées dans
les *k* premiers passages (`data/rag_eval.json`) :

À **k=1** (le bon passage doit être en toute première position), l'hybride bat chaque méthode prise
seule : le vectoriel et BM25 ratent chacun des cas différents (identifiants exacts vs sens), la fusion
récupère le meilleur des deux. Les chiffres détaillés sont dans `data/rag_eval.json`, à régénérer
après chaque ajout de document :
`docker compose run --rm assistant python -m assistant.evaluate`.

## Limites du détecteur

- Le modèle ne connaît que le trafic normal enregistré : si l'usage change, il faut réentraîner.
- Une feature toujours nulle en temps normal n'a pas d'échelle apprise : une petite valeur
  (ex : 0,5 erreur 5xx/s) passe inaperçue, seule une hausse franche est détectée.
- Une attaque lente qui imite le trafic normal (exfiltration discrète) peut ne pas être vue.
- Le détecteur dit *qu'il y a* une anomalie et *sur quoi* ; le choix de l'action reste à la remédiation.
- Les noms de métriques sont des hypothèses tant que Dev et Infra ne les ont pas confirmés.

## Reconnaissance faciale du back-office (consigne additionnelle 1)

La connexion au back-office (le dashboard) se fait en deux étapes : identifiant, puis la
caméra USB du PC Hôte confirme le visage, puis mot de passe.

```
Dashboard ──> WAF ──> auth /backoffice/face ──> face /verify (PC Hôte : fenêtre caméra, 15 s max)
                         │ reconnu : « ticket visage » signé, valable 2 min
Dashboard ──> WAF ──> auth /backoffice/login (identifiant + mot de passe + ticket) ──> jeton back-office
```

| Cas | Ce qui se passe |
|---|---|
| Visage reconnu (un seul visage devant la caméra) | Le champ mot de passe s'affiche |
| Visage non reconnu, ou plusieurs visages | Identifiant vidé, 30 s d'attente avant un nouvel essai |
| Mot de passe faux | On recommence toute l'identification |
| 2e échec (visage ou mot de passe) | Compte bloqué 5 minutes |

Ces règles sont appliquées par `auth`, pas par la page : appeler l'API directement ne permet
pas de sauter la caméra (vérifié : mot de passe juste sans ticket visage = refus 401).

**Guide de placement** (`face/camera.py`). Une fenêtre caméra s'ouvre au premier plan sur l'écran
du PC Hôte, en miroir, avec un ovale au centre : orange avec une consigne (« Rapprochez-vous »,
« Reculez un peu », « Centrez votre visage », « Un seul visage SVP ») tant que le visage est mal
placé, vert quand il l'est ; la photo est prise après 3 images bien placées d'affilée. Bien placé =
le visage occupe 20 à 60 % de la largeur de l'image et son centre est proche du centre de l'image.
Le même guide sert à l'enregistrement : le visage est cadré pareil aux deux moments, ce qui réduit
la distance entre eux et donc les refus à tort (avant le guide, nous avions mesuré 0,45 pour un
seuil de 0,5). L'aperçu reste sur le PC Hôte : l'image ne circule jamais sur le réseau.

**Modèle.** `face_recognition` (bibliothèque dlib) : un réseau pré-entraîné transforme un visage
en un vecteur de 128 nombres. Deux visages sont la même personne si la distance entre leurs
vecteurs est ≤ 0,5 (`FACE_TOLERANCE`). Aucun entraînement de notre part : on enregistre un
vecteur par opérateur. IA légère : CPU seul, ~100 Mo de modèles. Mesuré sur notre caméra :
**même personne 0,19 avec le guide de placement** (0,33 à 0,45 sans), **autre personne 0,65**.

**Pourquoi hors Docker.** Docker Desktop (WSL2) n'a pas accès aux webcams USB. Le service tourne
donc sur le PC Hôte, n'écoute que sur `127.0.0.1` (injoignable depuis le réseau du groupe,
vérifié), et `auth` le joint par `host.docker.internal`.

### Installation (une fois, sur le PC Hôte)

Prérequis : Python 3.12, CMake et Visual Studio Build Tools (C++), car dlib se compile.

```powershell
# depuis ai/
py -3.12 -m venv face\.venv
$env:PATH = "C:\Program Files\CMake\bin;" + $env:PATH
face\.venv\Scripts\python -m pip install -r face\requirements.txt
face\.venv\Scripts\python -m face.enroll --user admin    # photo prise quand l'ovale est vert
```

Puis ajouter `BACKOFFICE_PASSWORD=<mot de passe fort>` dans `.env` et `docker compose up -d auth`.
Sans lui, le back-office reste fermé, mais les paiements fonctionnent quand même.

### Avant chaque démo

```powershell
face\.venv\Scripts\python -m uvicorn face.service:app --host 127.0.0.1 --port 8002
```

Sans ce service, personne ne peut ouvrir le dashboard (« reconnaissance faciale indisponible »).

Pour tester sans attendre entre deux essais, et avec un compte `test` qui saute la caméra
(le mot de passe du back-office reste demandé) :
`$env:FACE_RETRY_SECONDS=0; $env:BLOCK_SECONDS=0; $env:BACKOFFICE_TEST_USER="test"; docker compose up -d auth`.
Avant la démo, un simple `docker compose up -d auth` depuis un **nouveau** terminal remet
les attentes de la consigne (30 s, puis 5 min) et désactive le compte `test`.
Tests sans caméra : `face\.venv\Scripts\python -m pytest tests/test_face.py`.

### Sécurité et données

- Aucun enregistrement de visage par HTTP, seulement `face.enroll` sur le PC Hôte : sinon un
  conteneur compromis (l'API après l'exploit du callback) pourrait remplacer le visage de référence.
- Seul le vecteur est stocké, jamais la photo. `data/face_encodings/` est exclu de Git
  (donnée biométrique, RGPD art. 9).
- Les jetons « visage » et « back-office » portent une audience (`aud`). L'API de paiement
  s'en sert pour cloisonner : un jeton « visage » ou « client » (`customer`) est refusé partout
  côté paiement (vérifié) ; seul le jeton « back-office » (l'opérateur) et le compte de service
  du simulateur de trafic peuvent **lire** les paiements (`GET /orders`, `GET /transactions`).
  Ces deux routes de lecture ne sont donc plus publiques : auparavant ouvertes pour simplifier
  l'affichage du dashboard, elles exigent désormais un jeton (OWASP A01, « Broken Access Control »).
- Le compte back-office (`BACKOFFICE_USER`, `admin` par défaut) est distinct du compte client
  `app`, dont le mot de passe est public (il est dans le code du dashboard).

### Limites

- Pas de détection du vivant : une photo de l'opérateur montrée à la caméra peut passer.
  Parade possible : demander un clignement d'yeux ou un mouvement de tête.
- Les compteurs d'échecs sont en mémoire : ils repartent à zéro si `auth` redémarre.
- Le jeton back-office ouvre l'interface, mais les API de supervision (détecteur, remédiation)
  ne le vérifient pas : elles restent protégées par leur publication sur `127.0.0.1` seulement.
- Un seul compte opérateur. La gestion des habilitations dans le back-office (ajouter ou retirer
  un opérateur, des rôles) reste à faire.

## Fichiers

| Fichier | Rôle |
|---|---|
| `config.py` | Tous les réglages (URLs, seuils, modèles), lus depuis l'environnement |
| `traffic.py` | Simulateur de clients légitimes (trafic normal pour la collecte et la démo) |
| `detector/features.py` | Les requêtes Prometheus/Loki que le modèle observe |
| `detector/collect.py` | Enregistre les features dans `data/normal.csv` ou `data/attack.csv` |
| `detector/train.py` | Entraîne et évalue le modèle |
| `detector/service.py` | Détection en continu, `/status`, `/metrics`, webhook |
| `detector/classify.py` | Qualifie l'incident (attaque, panne…) à partir des features |
| `detector/telegram.py` | Alerte Telegram au changement d'état (optionnelle) |
| `assistant/rag.py` | Chaîne RAG : documents → recherche hybride (BM25 + vectoriel) → LLM |
| `assistant/service.py` | API `/ask` |
| `assistant/eval_questions.py` | Jeu de questions d'évaluation de la recherche |
| `assistant/evaluate.py` | Mesure la qualité de la recherche (hybride vs vectoriel vs BM25) |
| `face/service.py` | Reconnaissance faciale du back-office : `/verify` (sur le PC Hôte) |
| `face/camera.py` | Fenêtre caméra avec ovale-guide, commune à la vérification et à l'enregistrement |
| `face/enroll.py` | Enregistre le visage d'un opérateur |
| `face/requirements.txt` | Dépendances du venv séparé `face/.venv` (Python 3.12, dlib) |
| `docs/` | Base de connaissance de l'assistant (procédures, architecture, PCA/PRA en `.md`) |
| `tests/` | Tests sans réseau : `python -m pytest` |
