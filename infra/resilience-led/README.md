# Module IoT RESILIENCE — ESP8266 + LED bicolore

Firmware NodeMCU v2 (ESP8266) qui pilote la LED rouge/vert selon les événements envoyés par le back-office.

## 1. Câblage

| NodeMCU | Composant |
|---|---|
| **D1** (GPIO5) | résistance → patte **rouge** |
| **D2** (GPIO4) | résistance → patte **verte** |
| **G** | patte **commune** (la plus longue, au milieu) |

- Résistances fournies : bandes rouge-rouge-noir-noir-marron = **220 Ω** (vérifier au multimètre). Entre 150 et 470 Ω tout va bien.
- LED à **anode commune** (rare) : patte commune sur **3V** au lieu de G, et `LED_COMMON_ANODE 1` dans `config.h`.
- Pour savoir quelle patte est rouge/verte : faire le test série (§3) et inverser D1/D2 si les couleurs sont permutées.
- Éviter D3, D4, D8 : ce sont des broches de boot, la LED pourrait empêcher le démarrage.

## 2. Configuration et flash (CLion + PlatformIO)

1. `cp include/config.example.h include/config.h` puis remplir SSID/mot de passe du PA `RESILIENCE-G<n>` et un `API_TOKEN` aléatoire.
2. **Le point d'accès Windows doit être en 2,4 GHz** (Paramètres > Point d'accès mobile > Bande réseau) : l'ESP8266 ne voit pas le 5 GHz.
3. Ouvrir le dossier dans CLion → configuration `PlatformIO Upload` → puis `PlatformIO Monitor` (115200 bauds).
4. Au démarrage le moniteur affiche `[WiFi] connecte, IP=192.168.137.50`.

## 3. Tester sans le back-office

Dans le moniteur série, taper : `1` reconnu · `2` mot de passe OK · `3` mot de passe KO · `4` non reconnu · `0` éteindre.

## 4. Contrat d'API pour le back-office

Base : `http://192.168.137.50` — header obligatoire `Authorization: Bearer <API_TOKEN>`.

| Moment dans le login | Appel | Effet LED (géré par l'ESP) |
|---|---|---|
| Visage reconnu | `POST /api/event {"event":"recognized"}` | vert clignotant jusqu'au prochain événement (coupe après 2 min max) |
| Mot de passe validé | `{"event":"password_ok"}` | vert fixe 30 s puis éteinte |
| Mot de passe faux | `{"event":"password_ko"}` | rouge clignotant 10 fois puis éteinte |
| Visage non reconnu | `{"event":"not_recognized"}` | rouge fixe 30 s puis éteinte |
| Abandon / blocage | `{"event":"reset"}` | éteinte |

- `GET /api/status` (auth) : état courant, RSSI, uptime.
- `GET /health` (sans auth) : pour la supervision Prometheus/Grafana (blackbox exporter).
- Le back-office gère les règles (1 retry puis blocage 5 min, réaffichage de la page...) ; l'ESP ne gère que l'affichage.
- Exemple d'intégration Python : `tools/led_client.py` (`send_event()` ne lève jamais d'exception : si l'ESP est hors ligne, le login doit continuer de fonctionner).

```bash
curl -X POST http://192.168.137.50/api/event \
  -H "Authorization: Bearer $LED_TOKEN" -H "Content-Type: application/json" \
  -d '{"event":"recognized"}'
```

## 5. Sécurité (à mentionner à l'oral)

- Jeton Bearer comparé en temps constant ; à stocker dans le **Vault** côté back-office, jamais en dur dans le code du back.
- `config.h` exclu de git.
- Limite connue : HTTP en clair sur le PA du groupe (l'ESP8266 gère mal TLS serveur). Le PC attaquant étant sur le même PA, il peut sniffer le jeton → piste d'amélioration : signature HMAC + horodatage de chaque requête pour bloquer le rejeu.
