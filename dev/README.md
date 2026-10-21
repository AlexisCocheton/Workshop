# Pôle Développement

Les microservices métier et le moteur de reprise.

| Service | Port interne | Rôle |
|---|---|---|
| `db` | 5432 | PostgreSQL : `transactions`, `products`, `customers`, `orders`, `order_items` |
| `auth` | 8100 | Émet un jeton JWT (`POST /login`) ; connexion du back-office |
| `api` | 8000 | API de paiement : `POST /transactions` (jeton requis), `GET /transactions`, `/metrics`, `/healthz` ; boutique : `/shop/*` |
| `remediation` | 8200 | Reçoit l'alerte du détecteur (`POST /incident`) et redémarre `api` ; `GET /events` |
| `frontend` | 3000 | Dashboard / back-office React + Tailwind (voir ci-dessous) |
| `shop` | 3002 | Boutique de confiseries React + Tailwind, site public des clients (voir ci-dessous) |

## La boutique (`shop/`)

Le site client : catalogue de confiseries, panier, compte client, paiement et
historique d'achat. Il est **séparé du back-office** (autre port, autre code) :
la boutique peut être exposée au réseau, le back-office reste réservé à l'opérateur.

Elle n'appelle que le WAF (`:8080`), qui relaie `/shop/*` vers l'`api`. Le trafic
client suit donc le même chemin que l'attaque : filtré, journalisé dans Loki,
compté dans les métriques que lit le détecteur. Pendant l'incident, le paiement
échoue (500) ; après le redémarrage automatique, il repasse : c'est la preuve de reprise.

| Route (`api`) | Rôle |
|---|---|
| `GET /shop/products` | Catalogue (inséré au premier démarrage, liste `PRODUCTS`) |
| `POST /shop/register` | Création de compte : mot de passe haché (scrypt salé), jeton client |
| `POST /shop/login` | Connexion : même message d'erreur que l'e-mail existe ou non |
| `POST /shop/orders` | Commande payée (jeton client) : prix lus en base, stock vérifié, une transaction créée, tout ou rien |
| `GET /shop/orders` | Historique du client connecté, et de lui seul |

Le jeton client porte l'audience `customer` : il ne sert ni sur `/transactions`
ni au back-office. Le site ne recharge le catalogue qu'à l'ouverture et après une
commande (pas de rafraîchissement périodique), pour ne pas fausser le trafic
« normal » appris par le détecteur.

Au paiement, le formulaire de carte (`shop/src/components/PaymentForm.jsx`)
demande l'e-mail du reçu, l'adresse de livraison (rue, code postal, ville), le titulaire, le numéro, la date d'expiration et le
code de sécurité (CVC). Il s'appuie sur deux bibliothèques libres :
`react-credit-cards-2` (aperçu visuel de la carte, marque détectée) et
`card-validator` de Braintree (numéro vérifié par Luhn, date non dépassée, CVC
de 3 ou 4 chiffres selon la marque). Les données de carte restent en mémoire le
temps du paiement : rien dans `localStorage`, et le CVC n'est jamais conservé
(interdit par PCI-DSS). Seul un résumé masqué (marque et 4 derniers chiffres)
s'affiche dans la confirmation ; l'API ne reçoit que le panier. Pour tester :
`4242 4242 4242 4242`, n'importe quelle date future, n'importe quel CVC. Un vrai
site passerait par un prestataire (Stripe Elements, par exemple) pour que la
carte ne transite jamais par nos serveurs.

Les photos des produits sont dans `shop/public/products/<id>.jpg` (sans photo,
le site affiche l'emoji du produit). Elles viennent de Wikimedia Commons sous
licence libre ; auteurs et licences sont dans `shop/src/credits.js` et affichés
en bas de la boutique, comme l'exigent les licences CC BY / CC BY-SA.

Pour ouvrir la boutique depuis un autre PC du réseau, ajouter son adresse
(`http://<IP du PC Hôte>:3002`) à `SHOP_ORIGINS` dans `.env` (CORS).

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
