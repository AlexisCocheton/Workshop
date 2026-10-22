#pragma once
// Copier ce fichier en config.h et adapter les valeurs.
// config.h est ignore par git (contient des secrets).

// ---- WiFi : point d'acces du groupe (hotspot Windows du PC Hote) ----
#define WIFI_SSID      "RESILIENCE-G1"       // remplacer 1 par le numero du groupe
#define WIFI_PASSWORD  "mot-de-passe-du-PA"

// ---- Adressage ----
// Le hotspot Windows distribue du 192.168.137.0/24, passerelle = PC Hote (192.168.137.1).
// IP fixe recommandee : le back-office (dans Docker) ne resout pas toujours les noms mDNS .local.
#define USE_STATIC_IP  1
#define STATIC_IP      192, 168, 137, 50
#define GATEWAY_IP     192, 168, 137, 1
#define SUBNET_MASK    255, 255, 255, 0

#define DEVICE_HOSTNAME "resilience-led"     // aussi annonce en mDNS : resilience-led.local
#define HTTP_PORT       80

// ---- Securite API ----
// Jeton partage avec le back-office (a stocker cote serveur dans le Vault).
// Generer par ex. : python -c "import secrets; print(secrets.token_urlsafe(32))"
#define API_TOKEN "CHANGE-ME-jeton-long-et-aleatoire"

// ---- Materiel ----
#define PIN_RED   D1   // GPIO5  (broches sures au boot, contrairement a D3/D4/D8)
#define PIN_GREEN D2   // GPIO4
// 0 = LED a cathode commune (patte commune -> G)
// 1 = LED a anode commune   (patte commune -> 3V)
#define LED_COMMON_ANODE 0

// Securite : si le mot de passe n'est jamais saisi, le vert clignotant s'arrete apres ce delai.
#define GREEN_BLINK_TIMEOUT_MS 120000UL
