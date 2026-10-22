# Architecture de la plateforme RESILIENCE-ALPHA

Vue d'ensemble des composants, pour qu'un opérateur sache qui fait quoi et où
regarder pendant un incident.

## Le chemin d'une requête

Tout passe par le WAF, seule porte d'entrée. Aucun service n'est accessible
directement de l'extérieur.

```
Client / Attaquant ──> WAF (Caddy) ──> API de paiement ──> Base PostgreSQL
                         │              Authentification
                         └── bloque les requêtes malveillantes (403)
```

## Les composants et leur rôle

| Composant | Rôle | Agit sur le système ? |
|---|---|---|
| WAF (Caddy) | Seule entrée. Filtre les attaques, journalise les blocages. | Non |
| API de paiement | Traite les transactions, expose les métriques. | Non |
| Authentification | Délivre les jetons (clients et back-office). | Non |
| Base PostgreSQL | Stocke les transactions, commandes, clients. | Non |
| Boutique | Site client (achats de confiseries) ; passe par le WAF comme un vrai client. | Non |
| Détecteur ML | Repère une anomalie et qualifie l'incident ; prévient la remédiation. | Non — il prévient |
| Remédiation | Redémarre l'API pour rétablir le service. Seul composant à agir. | Oui |
| Assistant (cet outil) | Répond aux questions des opérateurs. | Non — lecture seule |
| Dashboard | Supervision : état, score, transactions, journal. | Non |
| Prometheus / Loki / Grafana | Métriques, logs, visualisation (le SIEM). | Non |

## Où regarder pendant un incident

| Pour voir… | Aller sur… |
|---|---|
| L'état du service, le score d'anomalie, les transactions | le dashboard |
| Les métriques dans le temps (trafic, erreurs, CPU) | Grafana |
| Les blocages du WAF et les logs détaillés | Grafana (données de Loki) |
| Le journal des actions de remédiation | le dashboard (bloc remédiation) |

## Principe de séparation des rôles

Le détecteur **détecte**, la remédiation **agit**, l'assistant **conseille**.
Un seul composant (la remédiation) peut toucher au système, et son accès est
protégé par un jeton. Cette séparation évite qu'un composant compromis puisse
agir sur l'infrastructure.

## Le scénario de résilience démontré

1. Une transaction normale passe (client → WAF → API → base).
2. Une attaque depuis le PC Attaquant : scan bloqué par le WAF, puis abus du
   callback de paiement qui met l'API hors service (erreurs 5xx).
3. Le détecteur repère l'anomalie et prévient la remédiation.
4. La remédiation redémarre l'API, automatiquement.
5. Une nouvelle transaction réussit. Zéro intervention humaine.
