# Pôle Développement

Les microservices métier et le moteur de reprise.

| Service | Port interne | Rôle |
|---|---|---|
| `db` | 5432 | PostgreSQL : table `transactions` |
| `auth` | 8100 | Émet un jeton JWT (`POST /login`) |
| `api` | 8000 | API de paiement : `POST /transactions` (jeton requis), `GET /transactions`, `/metrics`, `/healthz` |
| `remediation` | 8200 | Reçoit l'alerte du détecteur (`POST /incident`) et redémarre `api` ; `GET /events` |
| `frontend` | 3000 | Dashboard React + Tailwind (voir ci-dessous) |

## Le dashboard (`frontend/`)

Conçu pour rendre l'incident lisible **avant, pendant et après**, y compris à distance
(démo, Clip Chrono), aux couleurs de la charte EPSI. Un composant par bloc dans `src/components/` :

| Bloc | Rôle |
|---|---|
| `StatusBanner` | Phase en grand : opérationnel → dégradation → incident → reprise → rétabli (avec durée) |
| `ServiceCards` | État de l'API, du détecteur IA, de la remédiation et du WAF |
| `Timeline` | Score sur 5 min, seuil, bandes d'incident, repères de remédiation, frise de disponibilité, réticule et vue tableau |
| `Features` | Pourquoi l'alerte : indicateurs les plus inhabituels (z-score) |
| `RemediationLog` | Journal des actions du moteur de remédiation |
| `PaymentPanel` | Transaction de test et dernières transactions (preuve de reprise) |
| `Assistant` | Questions à l'assistant RAG (lecture seule) |
| `Friends` | Mode licorne 🦄 : chaton mascotte, décor flottant, licorne qui traverse l'écran à la reprise |

Le **mode licorne** est activé par défaut et se coupe d'un clic (bouton en haut à droite),
par exemple pour une présentation sérieuse. Le choix est mémorisé dans le navigateur, et les
animations s'arrêtent si le système demande de réduire les mouvements.

Les adresses des services se règlent par variables `VITE_*` (fichier `frontend/.env`, non versionné) ;
les valeurs par défaut correspondent aux ports du `compose.yml`.

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
