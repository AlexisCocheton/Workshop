// =============================================================================
//  Workshop 2026-27 / M2 - Module IoT RESILIENCE
//  ESP8266 (NodeMCU v2) + LED bicolore rouge/vert
//
//  Le back-office choisit directement l'etat de la LED :
//    green_fixed  -> vert fixe
//    green_blink  -> vert clignotant
//    red_fixed    -> rouge fixe
//    red_blink    -> rouge clignotant
//    off          -> eteinte
//  L'etat est conserve jusqu'a l'evenement suivant.
//  Option "duration" (secondes) : la LED s'eteint seule apres ce delai.
//    ex. {"event":"green_fixed","duration":30}  -> vert fixe 30 s puis eteinte
//
//  API HTTP (header obligatoire : Authorization: Bearer <API_TOKEN>) :
//    POST /api/event   body JSON {"event":"green_blink"} ou {"event":"green_fixed","duration":30}
//    GET  /api/status  -> etat courant
//    GET  /health      -> sans auth, pour la supervision (Prometheus/Grafana)
// =============================================================================
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266mDNS.h>
#include <ArduinoJson.h>

#if __has_include("config.h")
#include "config.h"
#else
#warning "include/config.h absent : utilisation de config.example.h (copiez-le et adaptez-le)"
#include "config.example.h"
#endif

// ----------------------------------------------------------------------------
//  Machine a etats de la LED
// ----------------------------------------------------------------------------
enum class LedState : uint8_t { OFF, GREEN_BLINK, GREEN_FIXED, RED_BLINK, RED_FIXED };

static const char *stateName(LedState s) {
    switch (s) {
        case LedState::OFF:         return "off";
        case LedState::GREEN_BLINK: return "green_blink";
        case LedState::GREEN_FIXED: return "green_fixed";
        case LedState::RED_BLINK:   return "red_blink";
        case LedState::RED_FIXED:   return "red_fixed";
    }
    return "unknown";
}

static constexpr uint32_t BLINK_HALF_MS   = 250UL;     // 2 Hz
static constexpr uint32_t MAX_DURATION_S  = 3600UL;    // borne de securite sur "duration"

static LedState  g_state      = LedState::OFF;
static uint32_t  g_stateSince = 0;
static uint32_t  g_lastToggle = 0;
static uint32_t  g_durationMs = 0;   // 0 = jusqu'a l'evenement suivant
static bool      g_blinkOn    = false;
static String    g_lastEvent  = "boot";

static void writeLed(bool red, bool green) {
#if LED_COMMON_ANODE
    digitalWrite(PIN_RED,   red   ? LOW : HIGH);
    digitalWrite(PIN_GREEN, green ? LOW : HIGH);
#else
    digitalWrite(PIN_RED,   red   ? HIGH : LOW);
    digitalWrite(PIN_GREEN, green ? HIGH : LOW);
#endif
}

static void setState(LedState s, uint32_t durationMs = 0) {
    g_state      = s;
    g_stateSince = millis();
    g_lastToggle = g_stateSince;
    g_durationMs = (s == LedState::OFF) ? 0 : durationMs;
    g_blinkOn    = true;  // les clignotements commencent allumes

    switch (s) {
        case LedState::OFF:         writeLed(false, false); break;
        case LedState::GREEN_BLINK:
        case LedState::GREEN_FIXED: writeLed(false, true);  break;
        case LedState::RED_BLINK:
        case LedState::RED_FIXED:   writeLed(true,  false); break;
    }
    if (g_durationMs) Serial.printf("[LED] -> %s (%lu s)\n", stateName(s), (unsigned long)(g_durationMs / 1000));
    else              Serial.printf("[LED] -> %s\n", stateName(s));
}

static void updateLed() {
    const uint32_t now = millis();

    // Extinction automatique si une duree a ete demandee (robuste au debordement de millis())
    if (g_durationMs && now - g_stateSince >= g_durationMs) { setState(LedState::OFF); return; }

    const bool red   = (g_state == LedState::RED_BLINK);
    const bool green = (g_state == LedState::GREEN_BLINK);
    if ((red || green) && now - g_lastToggle >= BLINK_HALF_MS) {
        g_lastToggle = now;
        g_blinkOn = !g_blinkOn;
        writeLed(red && g_blinkOn, green && g_blinkOn);
    }
}

// Applique un evenement. Retourne false si evenement inconnu.
static bool handleEvent(const String &ev, uint32_t durationS = 0) {
    LedState target;
    if      (ev == "green_fixed") target = LedState::GREEN_FIXED;
    else if (ev == "green_blink") target = LedState::GREEN_BLINK;
    else if (ev == "red_fixed")   target = LedState::RED_FIXED;
    else if (ev == "red_blink")   target = LedState::RED_BLINK;
    else if (ev == "off")         target = LedState::OFF;
    else return false;

    if (durationS > MAX_DURATION_S) durationS = MAX_DURATION_S;
    g_lastEvent = ev;
    setState(target, durationS * 1000UL);
    return true;
}

// ----------------------------------------------------------------------------
//  Serveur HTTP
// ----------------------------------------------------------------------------
static ESP8266WebServer server(HTTP_PORT);

// Comparaison en temps constant (evite les attaques temporelles sur le jeton)
static bool constantTimeEquals(const String &a, const char *b) {
    const size_t lb = strlen(b);
    uint8_t diff = (a.length() != lb);
    for (size_t i = 0; i < a.length() && i < lb; ++i) diff |= (uint8_t)a[i] ^ (uint8_t)b[i];
    return diff == 0;
}

static void sendJson(int code, JsonDocument &doc) {
    String out;
    serializeJson(doc, out);
    server.send(code, "application/json", out);
}

static void sendError(int code, const char *msg) {
    JsonDocument doc;
    doc["error"] = msg;
    sendJson(code, doc);
}

static bool checkAuth() {
    const String h = server.header("Authorization");
    if (h.startsWith("Bearer ") && constantTimeEquals(h.substring(7), API_TOKEN)) return true;
    Serial.printf("[HTTP] 401 depuis %s\n", server.client().remoteIP().toString().c_str());
    sendError(401, "unauthorized");
    return false;
}

static void fillStatus(JsonDocument &doc) {
    doc["state"]      = stateName(g_state);
    doc["last_event"] = g_lastEvent;
    doc["state_ms"]   = millis() - g_stateSince;
    doc["uptime_s"]   = millis() / 1000;
    doc["rssi"]       = WiFi.RSSI();
    doc["ip"]         = WiFi.localIP().toString();
}

static void handleEventRoute() {
    if (!checkAuth()) return;

    JsonDocument body;
    if (deserializeJson(body, server.arg("plain")) || !body["event"].is<const char *>()) {
        sendError(400, "body attendu : {\"event\":\"green_fixed|green_blink|red_fixed|red_blink|off\", \"duration\":<secondes, optionnel>}");
        return;
    }
    const String   ev        = body["event"].as<const char *>();
    const uint32_t durationS = body["duration"] | 0;
    if (!handleEvent(ev, durationS)) { sendError(400, "evenement inconnu"); return; }

    Serial.printf("[HTTP] event=%s duration=%lu depuis %s\n", ev.c_str(), (unsigned long)durationS,
                  server.client().remoteIP().toString().c_str());
    JsonDocument doc;
    doc["ok"] = true;
    fillStatus(doc);
    sendJson(200, doc);
}

static void handleStatusRoute() {
    if (!checkAuth()) return;
    JsonDocument doc;
    fillStatus(doc);
    sendJson(200, doc);
}

static void handleHealthRoute() {
    JsonDocument doc;
    doc["status"] = "up";
    doc["device"] = DEVICE_HOSTNAME;
    sendJson(200, doc);
}

static void setupServer() {
    // Le header "Authorization" est collecte automatiquement par ESP8266WebServer (core >= 3.x).
    server.on("/api/event",  HTTP_POST, handleEventRoute);
    server.on("/api/status", HTTP_GET,  handleStatusRoute);
    server.on("/health",     HTTP_GET,  handleHealthRoute);
    server.onNotFound([] { sendError(404, "not found"); });
    server.begin();
}

// ----------------------------------------------------------------------------
//  WiFi (reconnexion non bloquante)
// ----------------------------------------------------------------------------
static bool g_wasConnected = false;

static void setupWifi() {
    WiFi.mode(WIFI_STA);
    WiFi.persistent(false);
    WiFi.setAutoReconnect(true);
    WiFi.hostname(DEVICE_HOSTNAME);
#if USE_STATIC_IP
    WiFi.config(IPAddress(STATIC_IP), IPAddress(GATEWAY_IP), IPAddress(SUBNET_MASK), IPAddress(GATEWAY_IP));
#endif
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.printf("[WiFi] connexion a %s ...\n", WIFI_SSID);
}

// Diagnostic : liste les reseaux 2,4 GHz visibles par l'ESP (il ne voit jamais le 5 GHz)
static void scanNetworks() {
    Serial.println("[WiFi] scan des reseaux visibles...");
    const int n = WiFi.scanNetworks();
    for (int i = 0; i < n; ++i)
        Serial.printf("   %-32s canal %2d  %4d dBm%s\n", WiFi.SSID(i).c_str(), WiFi.channel(i), WiFi.RSSI(i),
                      WiFi.SSID(i) == WIFI_SSID ? "   <== PA cible" : "");
    if (n <= 0) Serial.println("   (aucun reseau)");
    WiFi.scanDelete();
}

static const char *wifiStatusName(wl_status_t s) {
    switch (s) {
        case WL_NO_SSID_AVAIL:  return "SSID introuvable (PA eteint, en 5 GHz, ou nom different)";
        case WL_WRONG_PASSWORD: return "mot de passe incorrect";
        case WL_CONNECT_FAILED: return "echec de connexion";
        case WL_DISCONNECTED:   return "deconnecte / en cours";
        case WL_IDLE_STATUS:    return "en attente";
        default:                return "autre";
    }
}

static void checkWifi() {
    static uint32_t lastLog = 0;
    if (WiFi.status() != WL_CONNECTED && millis() - lastLog >= 5000) {
        lastLog = millis();
        Serial.printf("[WiFi] statut : %s\n", wifiStatusName(WiFi.status()));
    }
    const bool connected = WiFi.status() == WL_CONNECTED;
    if (connected && !g_wasConnected) {
        Serial.printf("[WiFi] connecte, IP=%s RSSI=%d dBm\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
        if (MDNS.begin(DEVICE_HOSTNAME)) MDNS.addService("http", "tcp", HTTP_PORT);
    } else if (!connected && g_wasConnected) {
        Serial.println("[WiFi] connexion perdue, reconnexion automatique...");
    }
    g_wasConnected = connected;
}

// ----------------------------------------------------------------------------
//  Commandes serie (tests sans back-office, depuis le moniteur serie de CLion)
//    1=green_fixed 2=green_blink 3=red_fixed 4=red_blink 0=off
// ----------------------------------------------------------------------------
static void checkSerial() {
    if (!Serial.available()) return;
    switch (Serial.read()) {
        case '1': handleEvent("green_fixed"); break;
        case '2': handleEvent("green_blink"); break;
        case '3': handleEvent("red_fixed");   break;
        case '4': handleEvent("red_blink");   break;
        case '0': handleEvent("off");         break;
        default: break;
    }
}

// ----------------------------------------------------------------------------
void setup() {
    Serial.begin(115200);
    delay(100);
    Serial.println("\n=== RESILIENCE - module LED ESP8266 ===");

    pinMode(PIN_RED, OUTPUT);
    pinMode(PIN_GREEN, OUTPUT);
    setState(LedState::OFF);  // eteinte par defaut (consigne)

    WiFi.mode(WIFI_STA);
    scanNetworks();
    setupWifi();
    setupServer();
}

void loop() {
    checkWifi();
    server.handleClient();
    MDNS.update();
    updateLed();
    checkSerial();
}