// Copier ce fichier en secrets.h (non versionné, comme le .env) et le remplir.
#pragma once

// Point d'accès du groupe, partagé par le PC Hôte
#define WIFI_SSID "RESILIENCE-G<n>"
#define WIFI_PASSWORD "mot-de-passe-du-point-d-acces"

// État de la LED, servi par auth à travers le WAF du PC Hôte.
// 192.168.137.1 = adresse du PC Hôte sur son point d'accès Windows.
#define LED_URL "http://192.168.137.1:8080/auth/led"
