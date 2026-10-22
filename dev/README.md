# Pôle Développement

Les microservices métier et le moteur de reprise.

| Service | Port interne | Rôle |
|---|---|---|
| `db` | 5432 | PostgreSQL : `transactions`, `products`, `customers`, `wallet_movements`, `orders`, `order_items` |
| `auth` | 8100 | Jetons JWT : compte de démonstration (`POST /login`) et connexion du back-office (`/backoffice/*`) ; état de la LED (`GET /led`) |
| `api` | 8000 | API de paiement : `POST /transactions` (jeton requis), `GET /transactions`, `/metrics`, `/healthz` ; boutique : `/shop/*` |

## Comptes et connexion

| Compte | Où | Identifiants | Jeton obtenu |
|---|---|---|---|
| Démonstration | `auth` `POST /login` | `DEMO_USER` / `DEMO_PASSWORD` (`app` / `app`, volontairement publics) | Crée des transactions fictives ; utilisé par le dashboard et `ai/traffic.py` |
| Back-office | `auth` `POST /backoffice/face` puis `POST /backoffice/login` | `BACKOFFICE_USER` (`admin` par défaut) + visage + `BACKOFFICE_PASSWORD` | Accès au dashboard (audience `backoffice`) |
| Client boutique | `api` `POST /shop/register`, `POST /shop/login` | E-mail + mot de passe choisis à l'inscription | Audience `customer` : boutique seulement |
| Marchand | `api` `POST /shop/login` | `SHOP_MERCHANT_EMAIL` / `SHOP_MERCHANT_PASSWORD` | Jeton client + rôle marchand relu en base |

Connexion au back-office : l'identifiant déclenche la caméra du PC Hôte (service `face`) ; un
visage reconnu donne un « ticket visage » valable 2 minutes, sans lequel le mot de passe est
refusé. Visage non reconnu : 30 s d'attente (`FACE_RETRY_SECONDS`) ; au 2e échec, compte bloqué
5 minutes (`BLOCK_SECONDS`). Sans `BACKOFFICE_PASSWORD` dans `.env`, le back-office reste fermé
(503). `BACKOFFICE_TEST_USER` crée un compte qui saute la caméra, à ne jamais activer en démo.
Détails : [`ai/README.md`](../ai/README.md), section « Reconnaissance faciale du back-office ».

## Les transactions

Une ligne de `transactions` : `id` (UUID), `amount`, `currency` (`EUR`), `status` (`accepted`),
`created_at`. Elle naît de trois façons :

| Origine | Route | Remarque |
|---|---|---|
| Transaction fictive | `POST /transactions` (jeton de démonstration) | Bouton du dashboard, simulateur de trafic |
| Recharge de cagnotte | `POST /shop/wallet/topup` | Montant de 1 à 500 € ; la carte n'est pas transmise |
| Commande boutique | `POST /shop/orders` | Liée à la commande par `orders.transaction_id` |

`GET /transactions` renvoie les 20 dernières, avec `source` (`boutique` si liée à une commande,
sinon `fictive`), `order_id` et `items` (nombre d'articles). Pendant l'incident, les trois routes
de création répondent 500 : aucune transaction n'est créée jusqu'au redémarrage de l'`api`.
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
| `GET /shop/wallet` | Cagnotte du compte connecté (épargne pour le marchand) : solde et 50 derniers mouvements |
| `POST /shop/wallet/topup` | Recharge de la cagnotte par carte (1 à 500 €) : une transaction créée ; 500 pendant l'incident |
| `POST /shop/orders` | Commande payée avec la cagnotte (jeton client) : prix lus en base, stock et solde vérifiés (402 si insuffisant), épargne du marchand créditée, une transaction créée, tout ou rien |
| `GET /shop/orders` | Historique du client connecté, et de lui seul |
| `GET /shop/profile` | Profil du client connecté : e-mail, prénom, téléphone, adresse (jamais le mot de passe) |
| `PUT /shop/profile` | Modification du profil (e-mail unique, code postal à 5 chiffres) |
| `PUT /shop/profile/password` | Changement de mot de passe : l'ancien est exigé, le jeton seul ne suffit pas |
| `POST /shop/merchant/products/{id}/restock` | Marchand : ajoute `quantity` (1 à 10 000) au stock d'une confiserie |
| `POST /shop/merchant/products` | Marchand : ajoute une confiserie (nom, description, prix, stock, emoji, photo JPEG facultative) |
| `DELETE /shop/merchant/products/{id}` | Marchand : retire une confiserie du catalogue (archivée : l'historique des commandes la garde) |
| `GET /shop/products/{id}/image` | Photo envoyée par le marchand (les produits de départ ont la leur dans `shop/public/products/`) |
| `POST /shop/merchant/payout` | Marchand : virement de son épargne vers un IBAN (clé modulo 97 vérifiée ; fictif, rien ne part) |

Le compte marchand est défini par `SHOP_MERCHANT_EMAIL` et `SHOP_MERCHANT_PASSWORD`
dans `.env` : l'`api` le crée (ou lui redonne son rôle) à chaque démarrage. On ne
peut pas devenir marchand en s'inscrivant. Il n'y a qu'un marchand : un compte créé avec une ancienne
valeur de `SHOP_MERCHANT_EMAIL` perd le rôle au démarrage suivant. Le marchand se connecte par le lien
« Connexion » de l'en-tête et obtient l'onglet « Espace marchand ». Le rôle
(`customers.is_merchant`) est relu en base à chaque appel `/shop/merchant/*` :
un client reçoit 403.

Le jeton client porte l'audience `customer` : il ne sert ni sur `/transactions`
ni au back-office. Le site ne recharge le catalogue qu'à l'ouverture et après une
commande (pas de rafraîchissement périodique), pour ne pas fausser le trafic
« normal » appris par le détecteur.

Les achats sont payés avec une cagnotte (`customers.balance`, jamais négative,
journal dans `wallet_movements`). Le client la recharge par carte sur la page
« Ma cagnotte » ; chaque commande la débite et crédite d'autant l'épargne du
compte marchand (celui de `SHOP_MERCHANT_EMAIL`), dans la même transaction SQL.
Le marchand vire son épargne vers son compte bancaire depuis la page « Épargne ».

À la recharge, le formulaire de carte (`shop/src/components/PaymentForm.jsx`)
demande l'e-mail du reçu, le titulaire, le numéro, la date d'expiration et le
code de sécurité (CVC). Il s'appuie sur deux bibliothèques libres :
`react-credit-cards-2` (aperçu visuel de la carte, marque détectée) et
`card-validator` de Braintree (numéro vérifié par Luhn, date non dépassée, CVC
de 3 ou 4 chiffres selon la marque). Les données de carte restent en mémoire le
temps du paiement : rien dans `localStorage`, et le CVC n'est jamais conservé
(interdit par PCI-DSS). Seul un résumé masqué (marque et 4 derniers chiffres)
s'affiche dans la confirmation ; l'API ne reçoit que le montant. Pour tester :
`4242 4242 4242 4242`, n'importe quelle date future, n'importe quel CVC. Un vrai
site passerait par un prestataire (Stripe Elements, par exemple) pour que la
carte ne transite jamais par nos serveurs.

Les photos des produits sont dans `shop/public/products/<id>.jpg` (sans photo,
le site affiche l'emoji du produit). Elles viennent de Wikimedia Commons sous
licence libre ; auteurs et licences sont dans `shop/src/credits.js` et affichés
en bas de la boutique, comme l'exigent les licences CC BY / CC BY-SA.

La page d'accueil présente la boutique physique (fictive) de Montpellier avec
une mini-carte : `react-leaflet` et les tuiles OpenStreetMap, gratuites et sans
clé d'API (le navigateur doit donc avoir accès à Internet pour afficher le fond
de carte). Adresse, position GPS et horaires se changent dans `shop/src/store.js`.

Pour ouvrir la boutique depuis un autre PC du réseau, ajouter son adresse
(`http://<IP du PC Hôte>:3002`) à `SHOP_ORIGINS` dans `.env` (CORS).

Composants de `shop/src/components/` :

| Composant | Rôle |
|---|---|
| `Header` | En-tête, nom de la boutique (`SHOP_NAME`), onglets, solde de la cagnotte, lien « Connexion » |
| `Home` | Page d'accueil : présentation de la boutique physique |
| `StoreInfo`, `StoreMap` | Coordonnées, horaires, itinéraire ; mini-carte OpenStreetMap (`react-leaflet`) |
| `ProductGrid` | Catalogue ; photo du produit, ou emoji à défaut |
| `Cart`, `QuantityInput` | Panier et saisie de quantité bornée au stock ; paiement avec la cagnotte |
| `AuthForm` | Connexion ou création de compte client |
| `Wallet`, `PaymentForm` | Page « Ma cagnotte » : solde, mouvements, recharge par carte |
| `PaymentPending` | Fenêtre modale pendant un paiement ou un virement (évite le double envoi) |
| `Orders` | Historique d'achat du client connecté |
| `Profile`, `ProfileForm`, `PasswordForm` | Page « Mon profil » : informations personnelles et mot de passe |
| `Merchant` | Espace marchand : stock, ajout et retrait de confiseries |
| `Savings` | Épargne du marchand et virement vers un IBAN |

## Le dashboard (`frontend/`)

Conçu pour rendre l'incident lisible **avant, pendant et après**, y compris à distance
(démo, Clip Chrono), aux couleurs de la charte EPSI. Un composant par bloc dans `src/components/` :

| Bloc | Rôle |
|---|---|
| `Login` | Connexion au back-office : identifiant → caméra → mot de passe (les règles sont appliquées par `auth`) |
| `StatusBanner` | Phase en grand : opérationnel → dégradation → incident → reprise → rétabli (avec durée) |
| `ServiceCards` | État de l'API, du détecteur IA, de la remédiation et du WAF |
| `Timeline` | Score sur 5 min, seuil, bandes d'incident, repères de remédiation, frise de disponibilité, réticule et vue tableau |
| `Features` | Pourquoi l'alerte : indicateurs les plus inhabituels (z-score) |
| `RemediationLog` | Journal des actions du moteur de remédiation |
| `WafBlocks` | Requêtes bloquées par le WAF (type, méthode et URL tentée, IP source), lues dans Loki via le détecteur |
| `PaymentPanel` | Transaction de test et dernières transactions (preuve de reprise) |
| `Assistant` | Questions à l'assistant RAG (lecture seule) |
| `Friends` | Mode licorne 🦄 : chaton mascotte, décor flottant, licorne qui traverse l'écran à la reprise |
| `Card` | Cadre commun à tous les blocs |

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
