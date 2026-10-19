# PROJECT RESILIENCE-ALPHA — Dossier d'ingénierie et de gouvernance

*Workshop EPSI M2 2026-27 — Consortium G\<n\>*
*Plateforme de paiement fictive à cyber-résilience et reprise autonome*

> Document destiné au jury. Les détails techniques volumineux (code, configurations)
> restent dans le dépôt Git ; ce dossier y renvoie. Données entièrement fictives,
> aucune donnée bancaire réelle.

---

## 1. Synthèse

Nous avons construit un démonstrateur qui prouve qu'un système de paiement critique
peut **encaisser une attaque et se rétablir seul**, sans intervention humaine. La chaîne
complète a été validée en conditions réelles :

> transaction normale → attaque depuis le PC Attaquant → détection par machine learning
> en ~9 s → redémarrage automatique du service → nouvelle transaction réussie (~26 s au total).

Le système réunit les cinq domaines exigés — développement, infrastructure, IA, cybersécurité,
gouvernance — réellement interconnectés : le modèle ML lit la supervision et déclenche la
remédiation, qui agit sur l'infrastructure, le tout observé et tracé.

---

## 2. Architecture et flux

### 2.1 Vue d'ensemble

La plateforme est un ensemble de microservices conteneurisés, orchestrés par Docker Compose
et déployables par Ansible sur le PC Hôte. Une seule porte d'entrée : le WAF.

```
                        PC Attaquant
                             │ (attaque réseau)
                             ▼
   [ WAF Caddy ] ──► [ API paiement ] ──► [ Auth ] ──► [ PostgreSQL ]
        (8080)              │ métriques
                            ▼
   [ Prometheus ] ◄── [ cAdvisor ]      [ Loki ] ◄── [ Promtail ] (logs)
        │                                   │
        └──────────────┬────────────────────┘
                       ▼
            [ Détecteur ML + healthcheck ] ──webhook──► [ Remédiation ] ──► redémarre l'API
                       │                                        │
                       ├─► /metrics (Grafana)                   │
                       └─► /status ──► [ Dashboard React ] ◄────┘
                                            ▲
                       [ Assistant RAG ] ───┘ (Ollama + LangChain, lecture seule)
```

### 2.2 Rôle de chaque composant

| Composant | Techno | Rôle | Agit sur le système ? |
|---|---|---|---|
| `api` | FastAPI | Traite les transactions, expose les métriques | Non |
| `auth` | FastAPI | Émet les jetons JWT | Non |
| `db` | PostgreSQL | Persiste les transactions | Non |
| `waf` | Caddy | Filtre les requêtes malveillantes, seule entrée publique | Non |
| `prometheus` / `loki` / `grafana` | — | Métriques, logs, visualisation | Non |
| `detector` | scikit-learn | Détecte l'anomalie (ML + contrôle de santé) | Non — il **prévient** |
| `remediation` | FastAPI + Docker SDK | Exécute la reprise (redémarrage) | **Oui** — seul composant |
| `assistant` | Ollama + LangChain | Aide les opérateurs (RAG) | Non — lecture seule |
| `frontend` | React + Tailwind | Supervision | Non |

Les cinq piliers sont séparés en dossiers (`dev/`, `infra/`, `ai/`, `cyber/`, `gouvernance/`) ;
le `README.md` racine décrit le lancement et le scénario.

---

## 3. L'incident et la chaîne de détection-reprise

### 3.1 L'attaque (pôle Cyber)

Lancée depuis le **PC Attaquant** contre le seul SI fictif du groupe, en deux temps :

1. **Scan de payloads malveillants** (injection SQL, XSS, traversée de répertoire) →
   **bloqués par le WAF** (403), visibles dans les logs et le taux d'erreurs.
2. **Abus d'un callback de paiement non authentifié** (`/pay/callback`) → vecteur que
   le WAF ne couvre pas → l'API passe en **erreurs 5xx** : le service de paiement est indisponible.

Ce choix illustre la **défense en profondeur** : le WAF arrête l'évident, mais ce qui passe
au travers est rattrapé par la détection ML et la remédiation.

### 3.2 La détection (pôle IA)

Le détecteur combine **deux signaux** à chaque cycle (5 s) :

- **Un modèle de machine learning** (LocalOutlierFactor, non supervisé) entraîné sur le trafic
  normal. Il observe cinq indicateurs : taux de requêtes, erreurs 4xx, erreurs 5xx, CPU de l'API,
  blocages du WAF. Il n'y a **aucun seuil codé en dur** : la frontière normal/anormal est apprise.
- **Un contrôle de santé actif** : le détecteur interroge directement `/healthz` de l'API.

Règle : anomalie si le ML la signale **ou** si l'API ne répond pas ; reprise déclarée seulement
si le ML est normal **et** l'API répond. Le contrôle de santé rattrape deux angles morts du ML seul,
vérifiés en test : une API tombée **sans trafic** (aucune erreur à observer), et un **faux retour à la
normale** sous attaque persistante. C'est la réponse directe à l'exigence du sujet : *« un conteneur
qui redémarre ne constitue pas, à lui seul, une preuve de reprise »*.

Une anomalie n'est déclarée qu'après **3 points anormaux consécutifs** (anti-faux-positif), et chaque
alerte est **expliquée** : les indicateurs les plus éloignés de la normale, en écarts-types.

### 3.3 La reprise (pôles IA → Dev → Infra)

À la transition `normal → anomaly`, le détecteur envoie un webhook signé au **moteur de remédiation** :

```json
POST /incident  (Authorization: Bearer <jeton>)
{ "event": "anomaly", "score": 36.7, "top_features": [{"name":"err_5xx_rate","value":20,"zscore":9}], "timestamp": "..." }
```

Le moteur — seul composant autorisé à agir sur Docker — **redémarre le conteneur `api`**, ce qui
efface l'état dégradé. Quand l'API répond de nouveau et que le ML repasse normal, l'événement
`recovered` est émis. Le dashboard et Grafana rendent visible l'état **avant, pendant et après**.

---

## 4. Résultats des essais

### 4.1 Performance du détecteur (données réelles)

Modèle entraîné sur ~59 points de trafic normal (0,3 à 10 req/s) et ~24 points d'attaque :

| Indicateur | Valeur |
|---|---|
| Taux de faux positifs | **0 %** |
| Précision | **100 %** |
| Rappel (points d'attaque détectés) | **87,5 %** (21/24) |
| Matrice de confusion | TN 15, FP 0, FN 3, TP 21 |

Les 3 points non détectés sont les tout premiers de l'incident, avant que les fenêtres de calcul
ne montent — sans conséquence, car le debounce attend de toute façon 3 points.

### 4.2 Chaîne complète (bout en bout)

| Étape | Mesure |
|---|---|
| Détection de l'anomalie | ~9 s après le début de l'incident |
| Reprise complète (détection + redémarrage) | ~26-29 s |
| Nouvelle transaction après reprise | Réussie (HTTP 200) |

### 4.3 Deux enseignements d'ingénierie

- **Évaluation honnête** : le découpage train/test est *mélangé*, pas chronologique. Sur des
  collectes courtes, un découpage chronologique isolait les pics de charge dans le test et gonflait
  les faux positifs à 67 % ; en mélangé, 0 % sur les mêmes données.
- **Robustesse** : `n_neighbors` de LOF est adapté à la taille du jeu. Fixé à 20, il dégénérait sur
  une collecte courte (~45 points) et classait un incident franc comme normal — un faux négatif
  silencieux qui aurait fait rater la reprise en direct. Désormais corrigé.

---

## 5. Sécurité

### 5.1 Dispositifs défensifs (pôle Cyber)

- **WAF applicatif** (Caddy) : filtre injection SQL, XSS, traversée de répertoire (403), seule porte d'entrée.
- **SIEM / SOC** : Loki centralise les logs, Grafana les corrèle et les visualise à côté du score
  d'anomalie — un analyste voit l'attaque, son effet et la reprise au même endroit.
- **Gestion des secrets** : SOPS ; aucun secret en clair dans le dépôt (`.env` ignoré par Git).
- **Durcissement** : surface réseau réduite (seuls WAF, dashboard et Grafana publiés, Grafana sur
  loopback), conteneurs non-root quand c'est possible, images figées à une version précise.

### 5.2 Privilèges du moteur de remédiation

Point sensible traité avec soin (exigence du sujet, Axe 2) : la remédiation est le seul composant
avec accès au socket Docker. Son endpoint est protégé par un **jeton Bearer obligatoire** — le service
**refuse de démarrer sans jeton** — avec comparaison à temps constant. Aucun autre service (API, auth,
détecteur, assistant) ne peut agir sur le système. L'assistant IA n'a **aucun outil**.

### 5.3 Posture et périmètre

Toutes les actions offensives sont strictement limitées au SI fictif du groupe. Un audit interne a
été mené sur l'ensemble des piliers (voir §8, limites). Les trois accès au socket Docker (remédiation
en écriture, promtail et cAdvisor en lecture/supervision) sont documentés dans `cyber/hardening.md`.

---

## 6. Analyse des risques et gouvernance

Le détail est dans le dossier de gouvernance (`gouvernance/`). Synthèse :

### 6.1 Risques (EBIOS Risk Manager — `gouvernance/ebios-rm.md`)

Valeurs métier : disponibilité du service de paiement, intégrité des transactions. Événement redouté
principal : indisponibilité du paiement. Scénario opérationnel démontré : abus du callback → outage 5xx.
Mesures de traitement : WAF, détection ML, remédiation automatique, SIEM, durcissement, secrets SOPS.

### 6.2 Continuité et reprise (PCA/PRA — `gouvernance/pca-pra.md`)

- **RTO visé** : quelques dizaines de secondes, cohérent avec la reprise automatique mesurée (~26 s).
- **RPO** : proche de zéro — les transactions sont persistées en base avant la réponse.
- **Couvert** par la reprise automatique : l'indisponibilité du service. **Non couvert** : une
  compromission persistante, une fuite de données, une corruption de la base — un redémarrage restaure
  la **disponibilité**, il ne corrige ni la vulnérabilité ni une exfiltration.

### 6.3 Conformité (NIS2 / DORA — `gouvernance/nis2-dora.md`)

Notre prototype **démontre** : détection et journalisation des incidents, test de résilience par attaque
réelle, reprise automatique, traçabilité. Il **ne peut pas démontrer** : la notification aux autorités
dans les délais légaux, la gouvernance d'entreprise, la gestion des tiers TIC, les audits. Nous
distinguons explicitement les deux et formulons des recommandations hiérarchisées à la direction.

### 6.4 Le fil conducteur

La reprise automatique restaure la disponibilité **mais ne corrige ni la vulnérabilité du callback,
ni une éventuelle exfiltration** : c'est la frontière entre ce que la machine répare seule et ce qui
reste une décision humaine. Nous l'assumons et le recommandons comme priorité de durcissement.

---

## 7. Contribution de chacun

| Domaine | Responsable(s) | Apport |
|---|---|---|
| Développement | \<nom\> | API paiement, auth, remédiation, dashboard |
| Infrastructure | \<nom\> | Docker Compose, Ansible, observabilité |
| IA / Data | \<nom\> | Détecteur ML, assistant RAG |
| Cybersécurité | \<nom\> | Attaque Red Team, WAF, SIEM, secrets, durcissement |
| Gouvernance | \<nom\> | EBIOS, PCA/PRA, NIS2/DORA |

> À compléter avec les noms et une phrase par personne sur sa contribution effective.
> Les décisions d'architecture ont été prises en commun.

---

## 8. Limites connues et ce que nous ferions différemment

- Le modèle ne connaît que le trafic normal enregistré : un changement d'usage impose un réentraînement.
- Une attaque lente imitant le trafic normal (exfiltration discrète) peut ne pas être détectée.
- Le WAF filtre l'URI, pas le corps des requêtes POST — suffisant pour la démo, à étendre en production.
- La faille `/pay/callback` est volontaire (support du scénario) ; en contexte industriel elle serait corrigée.
- En production : secrets via Vault plutôt que SOPS, build frontend optimisé plutôt que serveur de dev,
  dépendances verrouillées (lockfiles), remédiation avec vérification de santé post-action renforcée.

---

## 9. Références du dépôt

| Élément | Emplacement |
|---|---|
| Lancement et scénario | `README.md` (racine) |
| Partie IA (détail, contrat, résultats) | `ai/README.md` |
| Rapport chiffré du modèle | `ai/data/report.json` |
| Durcissement | `cyber/hardening.md` |
| Scripts d'attaque | `cyber/attack/` |
| Gouvernance (EBIOS, PCA/PRA, NIS2/DORA) | `gouvernance/` |
| Déploiement | `compose.yml`, `infra/ansible/` |
