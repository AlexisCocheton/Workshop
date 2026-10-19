# Pôle Infrastructure

Déploiement reproductible et observabilité.

| Service | Port | Rôle |
|---|---|---|
| `prometheus` | 9090 | Collecte les métriques (API, détecteur, cAdvisor) |
| `cadvisor` | 8080 | Métriques CPU/mémoire des conteneurs |
| `loki` | 3100 | Centralise les logs (base du SIEM) |
| `promtail` | — | Envoie les logs des conteneurs à Loki |
| `grafana` | 3001 | Visualisation ; dashboard « RESILIENCE-ALPHA » préchargé |

## Chaîne d'observabilité

```
conteneurs ──logs──> promtail ──> loki ──┐
api, détecteur ──métriques──> prometheus ─┼─> grafana (dashboard + alertes)
cadvisor ──CPU/mémoire──> prometheus ─────┘        │
                                                   └─> détecteur IA (lit prometheus + loki)
```

Cette chaîne n'est pas décorative : le détecteur d'anomalies lit réellement
Prometheus et Loki pour décider. Si un service cesse d'exposer ses métriques,
le détecteur le voit (`/status` passe à `unknown`).

## Déploiement

- `compose.yml` (racine) définit et orchestre tous les conteneurs.
- `ansible/` automatise le lancement sur le PC Hôte (voir `ansible/README.md`).

Grafana : http://localhost:3001 (admin / mot de passe défini dans `.env`).
Le dashboard montre le score d'anomalie, le trafic par statut, la latence p95
et les logs du WAF — soit l'état du service avant, pendant et après l'incident.
