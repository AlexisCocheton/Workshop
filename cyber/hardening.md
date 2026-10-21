# Durcissement

Mesures défensives appliquées à la plateforme, et pourquoi.

## Surface réseau

- Seuls le WAF (`8080`), le dashboard (`3000`) et Grafana (`3001`) sont publiés.
  La base, l'authentification, l'API, la remédiation, Prometheus et Loki ne sont
  joignables que sur le réseau interne Docker.
- Toute entrée applicative passe par le WAF : aucun accès direct à l'API.
- Les interfaces de supervision destinées au dashboard (détecteur, remédiation)
  sont publiées sur `127.0.0.1` uniquement.

## Conteneurs

- Images figées à une version précise (pas de `latest`) pour la reproductibilité.
- `api` et `auth` tournent avec un utilisateur non-root.
- La documentation du RAG et le `Caddyfile` sont montés en lecture seule (`:ro`).
- **`no-new-privileges`** sur `api`, `auth` et le WAF : un process ne peut pas
  élever ses privilèges (même via un binaire setuid).
- **`cap_drop: ALL`** sur ces mêmes conteneurs : aucune capability Linux accordée
  (ni réseau brut, ni montage, ni changement d'identité…). Ils n'en ont besoin d'aucune.
- **Système de fichiers en lecture seule** (`read_only`) sur le WAF : un exploit ne
  peut rien écrire sur le disque du conteneur (seuls `/tmp`, `/config`, `/data` sont
  des volumes éphémères en RAM, où Caddy écrit son autosave).

## Privilèges et secrets

- Trois composants touchent au socket Docker, avec des rôles distincts :
  - **remédiation** : accès en lecture/écriture pour redémarrer un conteneur.
    C'est le seul à **agir** sur le système. Son endpoint est protégé par un
    jeton Bearer **obligatoire** (le service refuse de démarrer sans jeton) et
    la comparaison du jeton est à temps constant.
  - **promtail** : accès en lecture seule, pour découvrir les conteneurs et
    collecter leurs logs (observabilité). Il n'exécute aucune action.
  - **cadvisor** : conteneur privilégié avec montage de l'hôte en lecture seule,
    pour les métriques système. Nécessaire à l'observabilité ; à remplacer par
    des montages ciblés hors contexte démo.
  Aucun autre service (API, auth, détecteur, assistant IA) ne peut agir sur le système.
- Les secrets (mots de passe, jeton de remédiation, clé JWT) viennent de `.env`
  (jamais versionné en clair), chiffrable avec SOPS (voir `secrets/`). Aucune
  valeur faible par défaut : les services refusent de démarrer si un secret
  critique manque.

## WAF

Le WAF (Caddy) est la seule porte d'entrée. Ce qu'il fait :

- **Filtrage applicatif (403)** : motifs d'injection SQL, XSS, traversée de
  répertoire et injection de commandes, dans l'URI **et** dans le corps des POST
  (un payload peut être dans le body, pas seulement dans l'adresse).
- **Blocage des scanners** : requêtes d'outils d'attaque connus repérés à leur
  User-Agent (sqlmap, nikto, nmap, masscan) → 403.
- **En-têtes de sécurité** sur chaque réponse : `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Content-Security-Policy`
  (sources de contenu restreintes, anti-XSS), `Permissions-Policy` (caméra, micro,
  géoloc coupés), et suppression de la bannière `Server`.
- **Limite de taille du corps** (64 Ko) : un payload géant ne peut pas saturer l'API.
- **Limite de débit sur l'authentification** (10 tentatives / 10 s par IP sur `/auth`
  et `/shop/login`, via le module `caddy-ratelimit`) : freine le brute force de mots
  de passe (429). Le reste du trafic (paiements, navigation, callback) n'est pas limité,
  pour ne pas gêner la démo ni l'attaque.
- **Détection SSRF** : les URL vers des cibles internes (127.x, localhost, et l'adresse
  de métadonnées cloud `169.254.169.254`) sont bloquées (OWASP API7:2023).
- **Journalisation exploitable** : l'access log est activé au niveau du site (il
  ne l'était pas avant, ce qui rendait les blocages invisibles). Chaque blocage
  porte un marqueur `waf_event: "WAF_BLOCK …"`, distinct des 403 applicatifs, que
  le SIEM (Loki/Grafana) et le détecteur ML peuvent compter sans ambiguïté.

Il ne prétend pas tout couvrir : le callback de paiement vulnérable passe à
travers (faille de démonstration volontaire), et c'est précisément ce que
rattrapent la détection ML et la remédiation. Défense en profondeur : plusieurs
couches, aucune infaillible.

**À ajouter (image Caddy custom via xcaddy)** : une limite de débit par IP
(module tiers `caddy-ratelimit`, absent de l'image standard) pour freiner les
rafales. En attendant, un afflux de requêtes est détecté par le ML (catégorie
`dos`) et traité par la remédiation.

## SIEM / SOC

La fonction SIEM est assurée par Loki (centralisation des logs) + Grafana
(corrélation et visualisation). Le dashboard montre les blocages du WAF à côté
du score d'anomalie et du trafic : un analyste voit l'attaque, son effet et la
reprise au même endroit.
