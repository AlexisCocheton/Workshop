# Pôle Développement

Les microservices métier et le moteur de reprise.

| Service | Port interne | Rôle |
|---|---|---|
| `db` | 5432 | PostgreSQL : table `transactions` |
| `auth` | 8100 | Émet un jeton JWT (`POST /login`) |
| `api` | 8000 | API de paiement : `POST /transactions` (jeton requis), `GET /transactions`, `/metrics`, `/healthz` |
| `remediation` | 8200 | Reçoit l'alerte du détecteur (`POST /incident`) et redémarre `api` ; `GET /events` |
| `frontend` | 3000 | Dashboard React + Tailwind : état du détecteur, transaction de test, historique de remédiation |

## La faille de démonstration

`POST /pay/callback` avec `{"status": "__CRASH__"}` met l'API hors service
(toutes les transactions suivantes renvoient 500) jusqu'au redémarrage du
conteneur. Elle simule l'exploitation d'une vulnérabilité applicative : c'est
le point de départ du scénario d'incident. Voir le pôle Cyber pour l'attaque
et le pôle IA pour la détection.

## Le moteur de remédiation

C'est le seul composant avec un accès au socket Docker. Son endpoint `/incident`
est protégé par un jeton Bearer (`REMEDIATION_TOKEN`). Il ne fait qu'une chose :
redémarrer le conteneur cible (`TARGET_CONTAINER`, par défaut `api`) quand le
détecteur signale une anomalie. Le choix de l'action vit ici ; la détection, chez l'IA.

## Démarrage

Tout se lance depuis la racine du dépôt avec `docker compose up`. Voir le
`README.md` racine. En local, chaque service se lance avec
`uvicorn app:app --port <port>` après `pip install -r requirements.txt`.
