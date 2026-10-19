# Analyse de risques EBIOS Risk Manager — PROJECT RESILIENCE-ALPHA

> Méthode : **EBIOS Risk Manager** (ANSSI), 5 ateliers.
> Objet : la plateforme de paiement **fictive** conteneurisée du démonstrateur (données 100 % fictives).
> Objectif spécifique du projet : la plateforme doit **détecter une attaque et se rétablir sans intervention humaine**, puis le prouver par une nouvelle transaction réussie.

L'analyse colle à l'architecture réelle livrée et se termine par les **risques résiduels après reprise automatique**, point central du projet.

---

## Atelier 1 — Cadrage et socle de sécurité

### Périmètre

Démonstrateur mono-hôte orchestré par Docker Compose. Mission métier simulée : **encaisser une transaction de paiement et confirmer sa bonne exécution**. Le cycle de vie démontré va de l'attaque à la preuve de reprise (transaction fictive réussie après remédiation).

### Valeurs métier

| # | Valeur métier | Description | Besoin de sécurité dominant |
|---|---|---|---|
| VM1 | Service de paiement | Capacité de l'API FastAPI `api` à accepter et traiter une transaction. | **Disponibilité** |
| VM2 | Intégrité des transactions | Une transaction enregistrée en base `db` est exacte, complète, non rejouée. | **Intégrité** |
| VM3 | Confidentialité des données de transaction | Les transactions fictives et secrets ne fuient pas. | **Confidentialité** |
| VM4 | Preuve de reprise autonome | Capacité à démontrer la reprise sans humain (valeur de démonstration du workshop). | **Disponibilité + traçabilité** |

### Biens supports

| # | Bien support | Rattaché à | Pilier |
|---|---|---|---|
| BS1 | Conteneur `api` (FastAPI, endpoint paiement, `/pay/callback`, métriques Prometheus) | VM1, VM2 | DEV |
| BS2 | Conteneur `db` (PostgreSQL, persistance des transactions) | VM2, VM3 | DEV |
| BS3 | Conteneur `auth` (émission/validation JWT) | VM2, VM3 | DEV |
| BS4 | Conteneur `remediation` (socket Docker, jeton Bearer, redémarrage de `api`) | VM1, VM4 | DEV |
| BS5 | Détecteur ML (LocalOutlierFactor, lit Prometheus/Loki, webhook) | VM1, VM4 | IA |
| BS6 | Pile observabilité (Prometheus, Grafana, Loki/Promtail) | VM4 | INFRA |
| BS7 | WAF Caddy (reverse proxy, 403 sur payloads malveillants) | VM1, VM2 | CYBER |
| BS8 | Réseau Docker interne + hôte 192.168.137.1 (point d'accès RESILIENCE-G\<n\>) | toutes | INFRA |
| BS9 | Secrets (JWT, jeton Bearer remédiation) gérés par SOPS | VM3 | CYBER |
| BS10 | Dashboard `frontend` React/Tailwind + assistant RAG (Ollama, lecture seule) | VM4 | IA / DEV |

### Événements redoutés (ER)

| # | Événement redouté | Valeur métier | Impact | Gravité |
|---|---|---|---|---|
| ER1 | Indisponibilité du service de paiement (l'API ne répond plus / 5xx) | VM1 | Aucun paiement encaissé, mission interrompue | **G3 — Grave** |
| ER2 | Altération / rejeu d'une transaction | VM2 | Montants faux, double encaissement | **G4 — Critique** |
| ER3 | Fuite de transactions fictives ou de secrets | VM3 | Perte de confidentialité, exposition du jeton Bearer → prise de contrôle de la remédiation | **G4 — Critique** |
| ER4 | Reprise autonome qui échoue ou ne prouve rien | VM4 | Objectif du projet non atteint, perte de confiance | **G3 — Grave** |

Échelle de gravité : G1 mineure · G2 significative · G3 grave · G4 critique.

### Socle de sécurité existant (déjà en place dans le démonstrateur)

Conteneurs non-root, ports internes **non exposés** (seul le WAF Caddy est en frontal), images **figées** par digest, secrets hors du code via **SOPS**, journalisation centralisée Loki/Promtail, métriques Prometheus. Écart assumé pour un prototype : pas de gestion de correctifs ni d'audit tiers (voir atelier 5 et `nis2-dora.md`).

---

## Atelier 2 — Sources de risque / objectifs visés

Firme financière fictive → sources de risque adaptées.

| # | Source de risque (SR) | Objectif visé (OV) | Motivation | Pertinence pour le démonstrateur |
|---|---|---|---|---|
| SR1 | **Attaquant opportuniste** (scan automatisé, script-kiddie) | Trouver un endpoint faible et le marteler | Opportunité, nuisance | **Élevée** — c'est la source jouée par la Red Team : scan de payloads + abus de `/pay/callback`. |
| SR2 | **Concurrent / officine mandatée** | Rendre le service de paiement indisponible pour nuire à la réputation | Avantage commercial | Moyenne — même effet (DoS applicatif) mais ciblé. |
| SR3 | **Hacktiviste** | Défigurer, perturber, revendiquer une interruption de service financier | Idéologie, visibilité | Moyenne — vise VM1/VM4. |
| SR4 | **Initié / mauvaise manipulation** | Accès aux secrets ou au socket Docker | Appât du gain, erreur | Faible dans le périmètre (mono-hôte), mais ER3 l'illustre. |

La source **SR1** est celle réellement incarnée par le PC Attaquant distinct. Les autres servent à élargir l'analyse stratégique (atelier 3).

---

## Atelier 3 — Scénarios stratégiques

Chemins d'attaque de haut niveau, depuis une source de risque vers une valeur métier, via des parties prenantes / biens supports.

| # | Scénario stratégique | SR | Chemin | VM visée | ER |
|---|---|---|---|---|---|
| SS1 | **Saturation applicative par endpoint vulnérable** | SR1 | Internet → WAF Caddy → `api` (`/pay/callback` non authentifié) → épuisement/erreurs | VM1 | ER1 |
| SS2 | **Déni de service volumétrique** | SR2/SR3 | Internet → WAF → flood de requêtes → `api` saturée | VM1 | ER1 |
| SS3 | **Injection / exploitation applicative** | SR1 | Internet → WAF → tentative d'injection sur l'API | VM2 | ER2 |
| SS4 | **Vol de secret et détournement de la remédiation** | SR4/SR1 | Accès à un secret (jeton Bearer) → pilotage de `remediation` → actions Docker arbitraires | VM3/VM1 | ER3 |

SS1 est le scénario stratégique **démontré de bout en bout**. SS4 est le scénario le plus grave et sert à motiver le durcissement et SOPS.

---

## Atelier 4 — Scénarios opérationnels

Déclinaison technique pas-à-pas des scénarios stratégiques sur les biens supports réels.

### SO-1 (principal, réellement démontré) — Abus du callback → outage 5xx → reprise autonome

Décline **SS1**. C'est le scénario joué devant le jury.

| Étape | Acteur | Action technique | Bien support | Observable |
|---|---|---|---|---|
| 1 | PC Attaquant | Reconnaissance : scan de payloads malveillants vers le service | BS7 (WAF Caddy) | Logs Caddy → requêtes en **403** (bloquées) |
| 2 | PC Attaquant | Pivot : abus de l'endpoint **`/pay/callback` non authentifié** (requêtes répétées) | BS1 (`api`) | L'API bascule hors service → **pics d'erreurs 5xx** |
| 3 | Détecteur ML | Lit le taux de 5xx via Prometheus/Loki ; le `LocalOutlierFactor` classe le point comme **anomalie** (pas de seuil codé en dur) | BS5, BS6 | Score d'anomalie franchit la normalité apprise |
| 4 | Détecteur ML | Appelle le **webhook** du moteur de remédiation | BS5 → BS4 | Requête webhook authentifiée (Bearer) |
| 5 | `remediation` | Via le socket Docker, **redémarre le conteneur `api`** | BS4 → BS1 | `docker restart api` journalisé |
| 6 | `api` | Redémarre « propre », le service de paiement redevient disponible | BS1, BS2 | 5xx retombent, `/metrics` sains |
| 7 | Opérateur / test | **Nouvelle transaction fictive** → réussie, persistée en `db` | BS1, BS2 | Transaction OK = **preuve de reprise (ER4 évité)** |

**Résultat attendu : zéro intervention humaine entre l'étape 2 et l'étape 7.**

### SO-2 — Déni de service volumétrique (partiellement démontrable)

Décline **SS2**. Flood de requêtes légitimes-looking passant le WAF → charge sur `api` → latence et 5xx. Même chaîne de détection/remédiation que SO-1, mais un simple redémarrage **ne suffit pas** si le flood continue (voir risque résiduel RR2).

### SO-3 — Scan / injection bloqués par le WAF (démontré en défense)

Décline **SS3**. Les payloads malveillants (patterns d'injection, chemins sensibles) sont **arrêtés en 403 par Caddy** avant d'atteindre `api`. Visible dans les logs Loki/Grafana (corrélation SIEM/SOC). Démontre une mesure préventive, pas un incident réussi.

### SO-4 — Détournement de la remédiation (analysé, non joué)

Décline **SS4**. Si le jeton Bearer fuite, un attaquant pourrait piloter `remediation` (seul composant avec accès au socket Docker). Mesures : secret sous **SOPS**, conteneur non-root, surface d'appel minimale. Non démontré, mais dimensionne la criticité de BS9.

---

## Atelier 5 — Traitement du risque

### Mesures retenues (toutes présentes dans le démonstrateur)

| # | Mesure | Type | Traite | Pilier |
|---|---|---|---|---|
| M1 | WAF applicatif **Caddy** (403 sur payloads) | Prévention | SS3, partie SS1/SS2 | CYBER |
| M2 | **Détection ML** non supervisée (LOF, pas de seuil en dur) sur 5xx | Détection | SS1, SS2 | IA |
| M3 | **Remédiation automatique** (redémarrage `api`) | Réaction | ER1 (disponibilité) | DEV |
| M4 | **SIEM/SOC** Loki + Grafana (corrélation logs/alertes) | Détection + traçabilité | tous | CYBER/INFRA |
| M5 | **Durcissement** : non-root, ports internes non exposés, images figées | Prévention | SS4, surface d'attaque | CYBER/INFRA |
| M6 | **Secrets SOPS** (JWT, Bearer remédiation) | Prévention | ER3, SS4 | CYBER |
| M7 | **Observabilité** Prometheus/Grafana | Détection + preuve | ER4 | INFRA |
| M8 | **Auth JWT** sur les endpoints sensibles | Prévention | ER2, ER3 | DEV |

### Risques résiduels APRÈS reprise automatique

Point décisif du projet : la reprise **restaure la disponibilité, elle ne corrige pas la cause**.

| # | Risque résiduel | Pourquoi il subsiste | Traitement complémentaire (hors scope prototype) |
|---|---|---|---|
| RR1 | **Vulnérabilité `/pay/callback` toujours ouverte** | Le redémarrage remet `api` « propre » mais l'endpoint non authentifié reste exploitable → attaque rejouable en boucle | Authentifier/supprimer le callback, rate-limiting, patch applicatif |
| RR2 | **DoS persistant non résolu par un redémarrage** | Si l'attaque continue, `api` retombe aussitôt après chaque restart (boucle) | Blocage IP/WAF dynamique, circuit-breaker, limite de redémarrages |
| RR3 | **Exfiltration non réparée par un redémarrage** | Si des données/secrets ont fuité (ER3), redémarrer `api` n'annule rien | Rotation des secrets, investigation forensique, confinement |
| RR4 | **Faux négatif / faux positif du modèle ML** | Modèle non supervisé entraîné sur du trafic normal : une attaque « lente » peut passer, ou un pic légitime déclencher un redémarrage inutile | Réentraînement périodique, garde-fous, supervision humaine |
| RR5 | **Détournement de la remédiation** (SO-4) | Composant à fort privilège (socket Docker) ; si le Bearer fuite, surface critique | Rotation Bearer, allow-list d'actions, isolation renforcée |

### Matrice de risques

Gravité et vraisemblance : 1 (faible) à 4 (critique). Risque résiduel évalué **après application des mesures et de la reprise automatique**.

| Risque | Gravité | Vraisemblance (avant) | Mesure principale | Risque résiduel |
|---|---|---|---|---|
| ER1 via SO-1 (callback → 5xx) | 3 | 4 | M2 + M3 (détection ML + remédiation) | **Moyen** — dispo restaurée en secondes, mais RR1/RR2 (cause intacte) |
| ER1 via SO-2 (DoS volumétrique) | 3 | 3 | M1 + M3 | **Moyen-élevé** — RR2 (restart insuffisant si flood continu) |
| ER2 (altération/rejeu) via SO-3 | 4 | 2 | M1 + M8 (WAF + JWT) | **Faible** — payloads bloqués en 403, auth sur endpoints |
| ER3 (fuite données/secrets) | 4 | 2 | M5 + M6 (durcissement + SOPS) | **Faible-moyen** — RR3 (un redémarrage ne répare pas une fuite) |
| ER4 (reprise ne prouve rien) | 3 | 2 | M3 + M7 (remédiation + observabilité) | **Faible** — transaction post-reprise = preuve mesurable |
| Détournement remédiation (SO-4) | 4 | 1 | M5 + M6 | **Faible** — mais impact critique si réalisé (RR5) |

### Conclusion de l'analyse

Le démonstrateur traite efficacement l'**axe disponibilité** (ER1) par la chaîne détection ML → remédiation, et prévient l'**axe intégrité/confidentialité** (ER2/ER3) par WAF, JWT, durcissement et SOPS. Le message à porter au jury est la **frontière de la reprise autonome** : elle rend le service de nouveau utilisable, mais les risques résiduels RR1 à RR3 montrent qu'une résilience complète exige, au-delà de la machine, une correction de la cause et une décision humaine.
