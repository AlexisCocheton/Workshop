# PROJECT RESILIENCE-ALPHA

Plateforme de paiement **fictive** qui détecte une attaque et se rétablit
**sans intervention humaine**, puis le prouve par une nouvelle transaction.
Workshop EPSI M2 2026-27. Données entièrement fictives, aucune donnée réelle.

## Le projet en 5 piliers

| Pilier | Dossier | Contenu |
|---|---|---|
| **Développement** | [`dev/`](dev/) | API de paiement, authentification, base, moteur de remédiation, dashboard React/Tailwind |
| **Infrastructure** | [`infra/`](infra/) | Docker Compose, Ansible, Prometheus, Grafana, Loki |
| **IA / Data** | [`ai/`](ai/) | Détection d'anomalies par ML + assistant RAG local (Ollama/LangChain) |
| **Cybersécurité** | [`cyber/`](cyber/) | Attaque Red Team, WAF, SIEM, durcissement, secrets SOPS |
| **Gouvernance** | [`gouvernance/`](gouvernance/) | EBIOS RM, PCA/PRA, NIS2/DORA, recommandations |

## Le scénario démontré

```
1. NORMAL      Une transaction fictive passe (dashboard → WAF → API → base).
2. ATTAQUE     Depuis le PC Attaquant : scan bloqué par le WAF (403), puis abus
               du callback /pay/callback → l'API tombe en erreur 5xx.
3. DÉTECTION   Le détecteur ML lit Prometheus/Loki, repère l'anomalie (5xx), et
               prévient le moteur de remédiation par webhook.
4. REPRISE     La remédiation redémarre le conteneur api, automatiquement.
5. PREUVE      Une nouvelle transaction fictive réussit. Zéro intervention humaine.
```

Le tout est visible sur le dashboard (http://127.0.0.1:3000) et dans Grafana
(http://127.0.0.1:3001) : état du service avant, pendant et après l'incident.

> **Ouvrir via `127.0.0.1`, pas `localhost`.** Sous Windows + Docker Desktop, le navigateur
> peut résoudre `localhost` en IPv6 vers le relais WSL (`wslrelay`), qui accepte la connexion
> sans jamais répondre : la page charge à l'infini. Constaté sur notre poste.

## Démarrer la plateforme (PC Hôte)

Prérequis : Docker Desktop avec WSL2.

```powershell
copy .env.example .env        # puis remplacer les valeurs
docker compose up -d --build
```

Télécharger les modèles de l'assistant IA (une fois) :

```powershell
docker compose exec ollama ollama pull qwen2.5:3b
docker compose exec ollama ollama pull nomic-embed-text
```

Entraîner le détecteur sur le trafic normal : voir [`ai/README.md`](ai/README.md),
section « Entraîner le détecteur ».

Le dashboard (back-office) demande une connexion avec **reconnaissance faciale** : le service
`face` doit tourner sur le PC Hôte, où est branchée la caméra USB, et `BACKOFFICE_PASSWORD`
doit être défini dans `.env`. Voir [`ai/README.md`](ai/README.md), section « Reconnaissance
faciale du back-office ».

## Jouer la démonstration

```powershell
# Depuis le PC Attaquant, contre le SI fictif du groupe uniquement :
python cyber/attack/attack.py --target http://192.168.137.1:8080
```

Puis observer sur le dashboard : passage en `anomaly`, redémarrage automatique,
retour à `normal`, et une nouvelle transaction qui réussit.

## Services et ports

| Exposé sur l'hôte | Service | Interne seulement |
|---|---|---|
| 8080 (WAF, entrée publique) | api, auth | db, prometheus, loki, promtail, cadvisor, ollama |
| 3000 (dashboard) | frontend | |
| 3001 (Grafana) | grafana | |
| 127.0.0.1:8000 / 8001 / 8200 | détecteur / assistant / remédiation (pour le dashboard) | |

## Carte du dépôt

```
compose.yml          orchestration des 5 piliers
.env.example         secrets et réglages (copier en .env)
dev/                 microservices + remédiation + dashboard
infra/               observabilité + Ansible
ai/                  détecteur ML + assistant RAG  (tests : cd ai && pytest)
cyber/               attaque + WAF + secrets + durcissement
gouvernance/         EBIOS, PCA/PRA, NIS2/DORA
```
