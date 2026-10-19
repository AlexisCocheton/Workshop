# RESILIENCE-ALPHA — partie IA

## Le projet

Workshop EPSI M2, octobre 2026, 4 jours (sujet : `Workshop 2026-27 M2 - Sujet PROJECT RESILIENCE-ALPHA.pdf`).
Une plateforme de paiement fictive conteneurisée subit une attaque lancée depuis le PC Attaquant ;
elle doit la détecter et se rétablir **sans intervention humaine**, puis une nouvelle transaction doit réussir.
Cinq pôles : Dev, Infra, IA/Data, Cyber, Gouvernance.

## Dépôt : les 5 piliers

Le dépôt contient les 5 piliers, orchestrés par `compose.yml` à la racine
(`docker compose up -d --build`). Voir `README.md` racine pour le scénario de démo.

| Pilier | Dossier | Résumé |
|---|---|---|
| Dev | `dev/` | `api` (paiement + /metrics + faille de démo `/pay/callback`), `auth`, `db`, `remediation` (redémarre `api`, seul avec accès Docker), `frontend` React/Tailwind |
| Infra | `infra/` | Prometheus, cAdvisor, Loki, Promtail, Grafana, Ansible |
| IA | `ai/` | détecteur ML + assistant RAG |
| Cyber | `cyber/` | `attack/` (Red Team), `waf/` (Caddy), `secrets/` (SOPS), `hardening.md` |
| Gouvernance | `gouvernance/` | EBIOS RM, PCA/PRA, NIS2/DORA |

**Mon périmètre : le pôle IA (sujet §3.3), dossier `ai/`.**

1. **Détecteur ML** (`ai/detector/`) : pas de seuils codés en dur ; lit Prometheus et Loki ; prévient le
   moteur de remédiation par webhook.
2. **Assistant RAG** (`ai/assistant/`) : Ollama + LangChain, modèle ≤ 8 milliards de paramètres, répond à
   partir de `ai/docs/`. Il ne doit pas être confondu avec la remédiation ni avoir d'accès privilégié.

Les autres pôles sont une base de départ cohérente, mais appartiennent à l'équipe : ne pas les modifier
sans le signaler. L'interface entre pôles (métriques lues, format du webhook, routes) est décrite dans la
section « Contrat d'interface » de `ai/README.md`.

## Contrat qui relie l'IA aux autres pôles

- L'`api` expose `http_requests_total{status}`, `http_request_duration_seconds_bucket` et
  `process_cpu_seconds_total{job="api"}` (CPU, source de `api_cpu` ; cAdvisor n'a pas le label `name`
  sur Docker Desktop) ; les logs du `waf` arrivent dans Loki sous `container="waf"`.
  Ces noms sont dans `ai/detector/features.py`.
- Le détecteur POST sur `http://remediation:8200/incident` (Bearer `REMEDIATION_TOKEN`) un corps
  `{event, score, top_features, timestamp}`.
- Le scénario d'incident : attaque sur `/pay/callback` → 5xx → détection → redémarrage de `api` → reprise.

## Ce que le jury note et qui me concerne

- **Axe 1 (5 pts)** : attaque → détection → reprise sans intervention. Si un humain doit corriger en live : 0/5.
  La détection doit donc être fiable en démo (ni raté, ni fausse alerte).
- **Axe 2 (4 pts)** : ML réellement branché sur la remédiation ; privilèges maîtrisés.
- **Axe 5 (3 pts)** : maîtrise du code présenté, y compris celui généré par IA. Je dois pouvoir expliquer chaque ligne.
- **Dossier** : données, préparation, modèle, résultats, limites (section « Pour le dossier » de `ai/README.md`).

## Règles de code

- **Le plus simple possible** : fonctions courtes, pas de classe ni d'abstraction sans besoin réel,
  commentaires en français qui expliquent le *pourquoi*. Un humain doit comprendre un fichier en une lecture.
- Réglages uniquement dans `ai/config.py` (variables d'environnement). Requêtes de métriques uniquement
  dans `ai/detector/features.py`.
- Le détecteur et l'assistant n'agissent jamais sur le système : pas de socket Docker, pas d'outil LLM.
- Tests sans réseau (données synthétiques, `monkeypatch`).
- Aucun secret dans le code, les logs ou les prompts envoyés à une IA (sujet §5). Aucune donnée bancaire réelle.
- Après un changement de comportement, mettre à jour `ai/README.md` (contrat, résultats, limites).

## Commandes (depuis `ai/`)

```powershell
.venv\Scripts\python -m pytest                                        # tests
.venv\Scripts\python -m detector.train                                # entraînement local
.venv\Scripts\python -m uvicorn detector.service:app --port 8000      # détecteur local
```

Avec Docker (racine du dépôt) : voir `ai/README.md`, sections « Lancer » et « Entraîner le détecteur ».

## Décisions déjà prises (ne pas revenir dessus sans raison)

- **LocalOutlierFactor plutôt qu'IsolationForest** : IsolationForest ignore une feature constante en temps
  normal (0 erreur 5xx, 0 blocage WAF), justement celle qui bouge pendant un incident. Comparatif chiffré dans le README.
- Collecte en direct avec la même fonction que le service (`fetch_now`) : pas d'écart entre entraînement et production.
- Webhook uniquement sur changement d'état, après 3 points anormaux d'affilée (debounce).
- RAG sans base vectorielle externe : `InMemoryVectorStore`, réindexé au démarrage. LLM par défaut `qwen2.5:3b`.

## Outils Claude du projet

- Agents : `ml-detector` (détection), `rag-assistant` (assistant), `jury-prep` (préparation de la soutenance).
- Skills : `/ai-check` (avant commit), `/retrain-model` (collecte et entraînement), `/add-rag-doc` (ajouter un document à l'assistant).
