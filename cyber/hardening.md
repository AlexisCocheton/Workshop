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

Le WAF bloque les motifs d'injection SQL, XSS et traversée de répertoire (403).
Il ne prétend pas tout couvrir : le callback de paiement vulnérable passe à
travers, et c'est précisément ce que rattrapent la détection ML et la
remédiation. Défense en profondeur : plusieurs couches, aucune infaillible.

## SIEM / SOC

La fonction SIEM est assurée par Loki (centralisation des logs) + Grafana
(corrélation et visualisation). Le dashboard montre les blocages du WAF à côté
du score d'anomalie et du trafic : un analyste voit l'attaque, son effet et la
reprise au même endroit.
