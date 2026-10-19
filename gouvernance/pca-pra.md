# Plan de Continuité et de Reprise d'Activité (PCA/PRA) — PROJECT RESILIENCE-ALPHA

> Périmètre : la plateforme de paiement **fictive** conteneurisée du démonstrateur.
> Particularité : la **reprise est automatique** (détection ML → moteur de remédiation → redémarrage du conteneur `api`), sans intervention humaine, puis prouvée par une nouvelle transaction fictive réussie.
> Ce PCA/PRA est dimensionné pour un **démonstrateur de 4 jours**, pas pour une production réelle — les objectifs et limites sont choisis en conséquence et justifiés.

---

## 1. Services critiques et priorités

Priorité : P1 (vital, reprise automatique visée) → P3 (support).

| Priorité | Service / composant | Rôle | Conséquence d'une perte |
|---|---|---|---|
| **P1** | `api` (FastAPI) | Traite les transactions de paiement, expose `/metrics` | **Arrêt de la mission** : plus aucun paiement → c'est l'incident que la reprise cible |
| **P1** | `db` (PostgreSQL) | Persiste les transactions | Perte d'intégrité/données : **non réparable par un simple redémarrage** |
| **P2** | `auth` (JWT) | Authentifie les appels sensibles | Transactions légitimes refusées, mais pas de perte de données |
| **P2** | `remediation` | Déclenche la reprise (socket Docker, Bearer) | **Plus de reprise automatique** → bascule en repli manuel |
| **P2** | Détecteur ML + Prometheus/Loki | Détecte l'anomalie et alerte | **Plus de déclenchement** → l'incident n'est plus vu automatiquement |
| **P3** | WAF Caddy | Filtre en frontal (403) | Surface d'attaque élargie, mais service encore debout |
| **P3** | `frontend` + Grafana + assistant RAG | Supervision humaine, aide opérateur | Perte de visibilité, pas de perte de service |

La chaîne critique de la reprise est : **`db` ← `api` ← remédiation ← détecteur ML ← observabilité**. Si un maillon P2 de cette chaîne tombe, on passe au repli manuel (§5).

---

## 2. Objectifs : RTO et RPO

### Définitions

- **RTO** (Recovery Time Objective) : durée maximale d'indisponibilité acceptée avant retour au service.
- **RPO** (Recovery Point Objective) : quantité maximale de données que l'on accepte de perdre (fenêtre entre la dernière sauvegarde utile et l'incident).

### Valeurs proposées

| Service | RTO cible | RPO cible |
|---|---|---|
| `api` (service de paiement, P1) | **≈ 30 à 60 secondes** | **≈ 0** (voir justification) |
| `db` (P1) | Pas de reprise auto — hors périmètre de la remédiation | **0 pour les transactions confirmées** |
| Chaîne de détection/remédiation (P2) | Repli manuel en **quelques minutes** | sans objet |

### Justification du RTO ≈ 30–60 s

Ce RTO n'est pas arbitraire : il correspond à la somme des étapes réellement mesurables du scénario SO-1 (cf. `ebios-rm.md`).

1. Le détecteur ML lit Prometheus/Loki par cycles courts → latence de détection de l'ordre de quelques secondes à quelques cycles.
2. Le webhook vers `remediation` est quasi immédiat.
3. `docker restart api` + redémarrage de FastAPI + healthcheck → quelques dizaines de secondes.

C'est volontairement **court et réaliste pour un démonstrateur** : on ne promet pas un RTO sub-seconde (irréaliste avec un redémarrage de conteneur), ni plusieurs minutes (ce serait l'échec de la démonstration d'autonomie). La borne haute (60 s) absorbe le temps de healthcheck et la latence de détection.

### Justification du RPO ≈ 0

Une transaction n'est **confirmée au client qu'après persistance en base `db`** (écriture avant réponse). Au moment de l'incident (pics de 5xx), les requêtes en cours échouent *avant* confirmation : elles ne sont donc pas « perdues » au sens RPO — elles n'ont jamais été acquittées. Les transactions déjà confirmées sont en base et le redémarrage de `api` ne touche pas `db`. Le RPO est donc **nul ou quasi nul pour les transactions confirmées**.

**Limite honnête :** ce RPO ≈ 0 ne vaut que si l'incident épargne `db`. Une corruption ou une perte de la base n'est **pas** couverte par la remédiation (§4) ; elle exigerait une sauvegarde/restauration, hors périmètre du prototype.

---

## 3. Scénarios couverts par la reprise automatique

| Scénario | Couvert ? | Mécanisme |
|---|---|---|
| **Abus de `/pay/callback` → API en 5xx** (SO-1) | ✅ **Oui, démontré** | Détection ML du taux de 5xx → webhook → redémarrage `api` → transaction de preuve |
| **Crash / blocage transitoire de `api`** | ✅ Oui | Même chaîne : anomalie détectée → redémarrage |
| **DoS volumétrique court** (SO-2) | ⚠️ Partiellement | Redémarrage efficace si l'attaque cesse ; **inefficace si le flood persiste** (le service retombe) |

---

## 4. Scénarios NON couverts par la reprise automatique

À exposer clairement : un redémarrage de conteneur ne répare qu'une **indisponibilité**, pas une atteinte à l'intégrité ou à la confidentialité.

| Scénario non couvert | Pourquoi | Ce qu'il faudrait |
|---|---|---|
| **Compromission persistante** (porte dérobée, implant) | Le redémarrage recharge l'image mais ne chasse pas un attaquant toujours présent, et la vulnérabilité `/pay/callback` reste ouverte (RR1) | Correctif applicatif, confinement, reconstruction |
| **Fuite / exfiltration de données** (ER3, RR3) | Redémarrer `api` n'annule pas une donnée déjà sortie | Rotation des secrets, investigation, notification |
| **Corruption de la base `db`** | La remédiation ne touche jamais `db` ; aucun rollback automatique | Sauvegarde/restauration, contrôle d'intégrité |
| **DoS persistant** (RR2) | Boucle : chaque redémarrage est suivi d'une rechute | Blocage au WAF, rate-limiting, circuit-breaker |
| **Panne du moteur de remédiation ou du détecteur** | Si le maillon P2 tombe, plus de reprise auto | **Repli manuel** (§5) |

---

## 5. Rôles et responsabilités

Reprise majoritairement **machine-to-machine** ; l'humain supervise et reprend la main en repli.

| Acteur | Responsabilité | Phase |
|---|---|---|
| **Détecteur ML** (IA) | Observe Prometheus/Loki, qualifie l'anomalie (LOF), **alerte** par webhook | Détection |
| **Moteur `remediation`** (DEV) | Reçoit l'alerte (Bearer), **agit** : `docker restart api` via le socket Docker | Réaction |
| **`api` / `db`** (DEV) | Redémarrent proprement, confirment la disponibilité et la persistance | Reprise |
| **Opérateur humain** | **Supervise** via le dashboard `frontend` + Grafana ; interroge l'**assistant RAG** (lecture seule) pour contextualiser ; déclenche le **repli manuel** si besoin | Supervision / escalade |
| **Pilier CYBER (SOC)** | Corrèle les logs (Loki/Grafana), confirme l'origine, décide du traitement de la cause (RR1–RR3) | Analyse post-incident |

L'opérateur **n'intervient pas** dans la boucle nominale (c'est l'objet de la démonstration) ; il n'intervient que si la reprise automatique échoue ou si l'incident sort du périmètre couvert (§4).

---

## 6. Procédures

### 6.1 Procédure de reprise automatique (nominale)

1. **Détection** — le détecteur ML repère l'anomalie sur le taux de 5xx (seuil appris, non codé en dur).
2. **Alerte** — appel du webhook de `remediation` avec le jeton Bearer.
3. **Action** — `remediation` exécute `docker restart api` via le socket Docker.
4. **Vérification** — healthcheck de `api`, retour des métriques `/metrics` à la normale, chute des 5xx.
5. **Preuve** — une **nouvelle transaction fictive** est émise et réussit (persistée en `db`).
6. **Traçabilité** — l'ensemble (détection, alerte, redémarrage, transaction de preuve) est journalisé dans Loki et visible sur Grafana/`frontend`.

**Critère de succès :** service rétabli dans le RTO (≈ 30–60 s) **sans action humaine**, preuve mesurable.

### 6.2 Procédure de repli manuel (si la remédiation échoue)

Déclenchée si : pas de redémarrage après alerte, rechute immédiate (DoS persistant), ou panne du détecteur/remédiation.

1. **Constat** — l'opérateur voit sur Grafana/`frontend` que les 5xx persistent et qu'aucun redémarrage n'est journalisé.
2. **Contexte** — interrogation de l'assistant RAG (procédures, architecture) ; corrélation des logs par le SOC.
3. **Action manuelle** — redémarrage manuel du conteneur `api` (`docker compose restart api`), ou, si le callback est en cause, **coupure/filtrage de `/pay/callback`** au niveau du WAF Caddy (traitement de la cause RR1).
4. **Confinement si suspicion d'atteinte** — en cas de fuite ou compromission suspectée (§4) : isolation réseau, rotation du Bearer/JWT (SOPS), **pas de simple redémarrage**.
5. **Vérification** — transaction de test, retour des métriques à la normale.
6. **Post-mortem** — consignation de l'incident, décision sur la correction de la cause.

---

## 7. Risques subsistant après la reprise

Alignés sur les risques résiduels de `ebios-rm.md` :

- **RR1 — La cause reste ouverte.** Après redémarrage, `/pay/callback` est de nouveau exploitable : l'attaque est rejouable. La disponibilité est restaurée, pas la sécurité.
- **RR2 — Le DoS persistant bat la reprise.** Si l'attaque continue, on entre dans une boucle redémarrage/rechute ; il faut traiter la cause au WAF.
- **RR3 — Une fuite n'est pas réparée.** Un redémarrage n'efface pas une exfiltration ni une compromission latente.
- **RR4 — Qualité de la détection.** Un faux négatif retarde la reprise ; un faux positif provoque un redémarrage inutile.
- **Dépendance mono-hôte.** Tout tourne sur l'hôte 192.168.137.1 : sa panne n'est couverte par aucune redondance dans le prototype.

**Synthèse :** le PCA/PRA garantit une **reprise de disponibilité rapide et autonome** (RTO court, RPO ≈ 0 sur les transactions confirmées) pour l'incident démontré, tout en assumant que la **résilience complète** — correction de la cause, traitement d'une fuite, redondance — relève d'une organisation humaine et de mesures hors du périmètre d'un démonstrateur de 4 jours.
