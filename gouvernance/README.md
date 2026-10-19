# Pilier GOUVERNANCE & TRANSFORMATION — PROJECT RESILIENCE-ALPHA

> Workshop EPSI M2 — cyber-résilience et reprise autonome.
> Plateforme de paiement **fictive**, conteneurisée, qui doit détecter une attaque, se rétablir **sans intervention humaine**, puis prouver la reprise par une nouvelle transaction réussie.
> Données 100 % fictives, aucune donnée bancaire réelle. Activité financière fictive → enjeux **NIS2** et **DORA**.

## Objet du pilier

Le pilier Gouvernance ne produit pas de code. Il **cadre le risque, encadre la reprise et situe le démonstrateur dans ses obligations réglementaires**. Autrement dit, il répond à trois questions que posera le jury :

1. *De quoi se protège-t-on, et qu'est-ce qui reste exposé même après la reprise automatique ?* → EBIOS Risk Manager.
2. *Que garantit-on en continuité et en reprise, avec quels objectifs chiffrés et quelles limites ?* → PCA/PRA.
3. *Qu'est-ce que ce prototype prouve réellement au regard de NIS2 et DORA, et que ne peut-il pas prouver en 4 jours ?* → NIS2/DORA.

Le fil conducteur commun aux trois documents est le **scénario réellement démontré** : abus de l'endpoint de callback non authentifié `/pay/callback` → pics d'erreurs 5xx sur l'API de paiement → détection par le modèle ML → alerte au moteur de remédiation → redémarrage automatique du conteneur `api` → nouvelle transaction fictive réussie.

## Documents du pilier

| Fichier | Contenu | Question traitée |
|---|---|---|
| `README.md` | Ce document : intro, liste, liens inter-piliers. | Où est quoi ? |
| `ebios-rm.md` | Analyse de risques EBIOS RM en 5 ateliers, appliquée à notre architecture. Matrice de risques. | De quoi se protège-t-on ? |
| `pca-pra.md` | Plan de Continuité / Reprise d'Activité : services critiques, RTO/RPO justifiés, scénarios couverts vs non couverts, rôles, procédures. | Que garantit-on ? |
| `nis2-dora.md` | Enjeux NIS2 et DORA, tableau démontré vs non démontrable, recommandations à une direction. | Que prouve-t-on réglementairement ? |

## Rattachement à l'architecture du démonstrateur

Chaque document référence des composants réels, pas de la conformité générique :

- **Pilier DEV** — conteneurs `db` (PostgreSQL), `auth` (JWT), `api` (FastAPI, métriques Prometheus), `remediation` (seul composant avec accès au socket Docker, jeton Bearer), `frontend` (dashboard React/Tailwind).
- **Pilier INFRA** — Docker Compose, playbooks Ansible, observabilité Prometheus + Grafana + Loki/Promtail.
- **Pilier IA** — détecteur d'anomalies `LocalOutlierFactor` (non supervisé, pas de seuil codé en dur) qui lit Prometheus/Loki et prévient la remédiation par webhook ; assistant RAG local (Ollama + LangChain, ≤ 8B), en lecture seule.
- **Pilier CYBER** — attaque Red Team depuis un PC Attaquant distinct ; défense WAF Caddy (403), SIEM/SOC via Loki + Grafana, durcissement (non-root, ports internes non exposés, images figées), secrets SOPS.

## Comment les piliers se relient aux documents de gouvernance

| Pilier | Ce que le pilier fournit | Ce que la gouvernance en fait |
|---|---|---|
| DEV | Les biens supports (`api`, `db`, `auth`), la remédiation, la persistance des transactions. | Biens supports de l'atelier 1 EBIOS ; justifie le RPO ≈ 0 du PCA. |
| INFRA | L'observabilité (métriques + logs) et le déploiement reproductible. | Preuve de journalisation (DORA/NIS2) ; source de la détection ; base du RTO. |
| IA | La détection d'anomalie et le déclenchement de la reprise. | Cœur du scénario opérationnel EBIOS ; moteur du RTO automatique ; test de résilience. |
| CYBER | L'attaque jouée et les défenses (WAF, SIEM, durcissement, SOPS). | Sources de risque et scénarios opérationnels ; mesures de traitement de l'atelier 5. |

## Message clé porté par le pilier

La reprise automatique **restaure la disponibilité** mais ne corrige ni la vulnérabilité exploitée (`/pay/callback` non authentifié) ni une éventuelle exfiltration. Les trois documents insistent sur cette frontière : ce que la machine répare seule, et ce qui reste du ressort d'une gouvernance humaine.
