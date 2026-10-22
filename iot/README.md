# Témoin LED du back-office (ESP8266)

Consigne additionnelle 1 : un NodeMCU ESP8266 équipé d'une LED bicolore rouge/vert, connecté
en WiFi au point d'accès du groupe, affiche l'état de la connexion au back-office.

| Situation | LED |
|---|---|
| Au repos | éteinte |
| Visage reconnu, mot de passe pas encore saisi | vert clignotant |
| Mot de passe validé | vert fixe 30 s, puis éteinte |
| Mot de passe faux | rouge, 10 clignotements, puis éteinte (on recommence l'identification) |
| Visage non reconnu | rouge fixe 30 s, puis éteinte |

## Fonctionnement

```
ESP8266 ──WiFi du PA, toutes les 300 ms──> WAF :8080  GET /auth/led ──> auth
                                                        réponse « green_blink 7 »
```

`auth` connaît chaque étape de la connexion : il garde le dernier événement (visage reconnu,
mot de passe faux…) et en déduit le mode de la LED pendant la durée voulue. L'ESP ne décide rien,
il affiche. Le numéro d'événement lui permet de rejouer les 10 clignotements à chaque nouvel échec.

Pourquoi l'ESP interroge le serveur, et pas l'inverse :
- l'ESP n'a pas besoin d'une adresse IP fixe ni d'un port ouvert ;
- s'il redémarre, il retrouve l'état au bout de 0,3 s ;
- la connexion au back-office ne dépend pas de l'ESP : débranché, elle fonctionne quand même.

`/auth/led` se lit sans authentification : elle donne la même information que la LED, visible de
toute la salle, et ne permet aucune action.

### Deux modes possibles

| Mode | Comment | Quand l'utiliser |
|---|---|---|
| **Interrogation** (défaut) | L'ESP fait `GET /auth/led` toutes les 300 ms. `auth` n'a rien à configurer. | L'ESP n'expose aucun port ; simple et robuste. |
| **Poussée** (optionnel) | `auth` envoie un `POST` à l'ESP à chaque étape, si `ESP_LED_URL` est défini (ex : `http://192.168.137.50/api/event`). Corps : `{event, mode, id}`, en-tête `Bearer ESP_LED_TOKEN` si l'ESP l'exige. | Si l'ESP tourne un firmware qui **reçoit** des événements (serveur HTTP sur l'ESP) plutôt que d'interroger. |

Les deux modes coexistent : activer la poussée n'empêche pas l'interrogation. La poussée est
**non bloquante** (thread séparé) : un ESP injoignable ne ralentit jamais l'authentification.

## Câblage

```
NodeMCU                      LED bicolore (3 pattes : la plus longue, au milieu, est la commune)
D1 ──── résistance ──────── patte rouge
D2 ──── résistance ──────── patte verte
G  ──────────────────────── patte commune
```

Une résistance par couleur, pour limiter le courant dans la LED et dans la broche.
Au démarrage, l'ESP fait un **autotest** : rouge 0,4 s, puis vert 0,4 s.
- Rien ne s'allume : la LED est à anode commune. Mettre la patte commune sur `3V` et
  `COMMON_ANODE = true` dans `src/main.cpp`.
- Couleurs inversées : échanger les fils de D1 et D2.

## Installation (une fois)

1. **CLion** (IDE imposé), avec le plugin **PlatformIO for CLion** : *Settings → Plugins →
   Marketplace*. Le plugin utilise PlatformIO Core, installé dans `%USERPROFILE%\.platformio\penv`.
2. Dans CLion : *File → Open* sur le dossier `iot/`.
3. Copier `include/secrets.example.h` en `include/secrets.h` (non versionné) et le remplir :
   nom et mot de passe du point d'accès, et `LED_URL`. Le port est celui du WAF sur le PC Hôte :
   8080, ou 18080 sur un poste qui utilise `compose.override.yml`.
4. Brancher la carte en USB. Si aucun port COM n'apparaît, installer le pilote CH340
   (la puce USB de la carte).
5. Dans CLion : *PlatformIO → Upload*, puis *Monitor*. Le journal doit afficher
   `WiFi connecte, IP 192.168.137.x`.

En ligne de commande, depuis `iot/` : `pio run -t upload`, puis `pio device monitor`.

## Tester sans la carte

```powershell
curl.exe http://127.0.0.1:8080/auth/led    # « off 0 » au repos ; change après un essai de connexion
```

## Dépannage

- **L'ESP ne se connecte pas au WiFi** : l'ESP8266 ne gère que le 2,4 GHz. Dans Windows,
  *Paramètres → Réseau → Point d'accès mobile → Bande réseau : 2,4 GHz*.
- **`erreur -1` dans le moniteur série** : l'ESP n'atteint pas le PC Hôte. Autoriser le port du
  WAF dans le pare-feu Windows (PowerShell administrateur) :
  `New-NetFirewallRule -DisplayName "RESILIENCE WAF" -Direction Inbound -Protocol TCP -LocalPort 8080 -RemoteAddress 192.168.137.0/24 -Action Allow`

## Choix et limites

- Interrogation toutes les 300 ms : la LED réagit en moins d'une demi-seconde. Cela fait environ
  3 requêtes/s sur le WAF, sans effet sur le détecteur d'anomalies : ses métriques viennent de
  l'API de paiement, pas d'`auth`.
- HTTP n'est pas chiffré sur le point d'accès ; le WiFi (WPA2) protège la liaison radio.
- Une seule LED pour le back-office : elle montre le dernier essai de connexion.
- Le back-office s'ouvre dès que le mot de passe est validé, pendant les 30 s de vert fixe :
  nous avons lu la consigne ainsi, plutôt que de faire attendre 30 s l'opérateur.
