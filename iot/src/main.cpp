// Témoin LED du back-office (consigne additionnelle 1).
//
// L'ESP8266 se connecte au point d'accès du groupe et demande toutes les 300 ms
// l'état de sa LED au service auth (GET /auth/led, à travers le WAF). Il ne décide
// rien, il affiche. Réponse : « <mode> <numéro d'événement> », avec pour modes :
//   off          éteinte (par défaut)
//   green_blink  visage reconnu, en attente du mot de passe
//   green        mot de passe validé (30 s)
//   red_blink    mot de passe faux : exactement 10 clignotements
//   red          visage non reconnu (30 s)
#include <Arduino.h>
#include <ESP8266HTTPClient.h>
#include <ESP8266WiFi.h>

#include "secrets.h"  // WIFI_SSID, WIFI_PASSWORD, LED_URL : copier secrets.example.h

const int RED_PIN = D1;    // GPIO5
const int GREEN_PIN = D2;  // GPIO4
// Cathode commune (patte commune sur G) : false. Anode commune (patte commune sur 3V) : true,
// une couleur s'allume alors quand sa broche est à 0 V.
const bool COMMON_ANODE = false;
const unsigned long POLL_MS = 300;

String mode = "off";
long eventId = -1;
unsigned long redBlinkStart = 0;
unsigned long lastPoll = 0;
bool announced = false;

void setLed(bool red, bool green) {
  digitalWrite(RED_PIN, COMMON_ANODE ? !red : red);
  digitalWrite(GREEN_PIN, COMMON_ANODE ? !green : green);
}

// Demande l'état de la LED au serveur et met à jour `mode`.
void poll() {
  if (WiFi.status() != WL_CONNECTED) {
    mode = "off";
    return;
  }
  if (!announced) {
    Serial.printf("WiFi connecte, IP %s\n", WiFi.localIP().toString().c_str());
    announced = true;
  }
  WiFiClient client;
  HTTPClient http;
  http.setTimeout(1000);
  http.begin(client, LED_URL);
  int code = http.GET();
  if (code == 200) {
    String body = http.getString();  // ex. "red_blink 12"
    int space = body.indexOf(' ');
    String newMode = body.substring(0, space);
    long newId = body.substring(space + 1).toInt();
    if (newMode == "red_blink" && newId != eventId) {
      redBlinkStart = millis();  // nouvel échec : les 10 clignotements repartent de zéro
    }
    mode = newMode;
    eventId = newId;
  } else {
    Serial.printf("GET %s : erreur %d\n", LED_URL, code);
    mode = "off";  // serveur injoignable : LED éteinte plutôt qu'un état périmé
  }
  http.end();
}

// Allume la LED selon `mode`. Les clignotements suivent l'horloge, sans bloquer la boucle.
void render() {
  unsigned long now = millis();
  if (mode == "green") {
    setLed(false, true);
  } else if (mode == "red") {
    setLed(true, false);
  } else if (mode == "green_blink") {
    setLed(false, now % 1000 < 500);  // 0,5 s allumée, 0,5 s éteinte
  } else if (mode == "red_blink") {
    unsigned long t = now - redBlinkStart;
    setLed(t < 5000 && t % 500 < 250, false);  // 10 x (0,25 s allumée + 0,25 s éteinte), puis éteinte
  } else {
    setLed(false, false);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(RED_PIN, OUTPUT);
  pinMode(GREEN_PIN, OUTPUT);
  // Autotest au démarrage : rouge puis vert, pour vérifier le câblage d'un coup d'œil.
  setLed(true, false);
  delay(400);
  setLed(false, true);
  delay(400);
  setLed(false, false);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);  // le SDK se reconnecte seul si le WiFi tombe
  Serial.printf("\nConnexion au WiFi %s...\n", WIFI_SSID);
}

void loop() {
  if (millis() - lastPoll >= POLL_MS) {
    lastPoll = millis();
    poll();
  }
  render();
  delay(10);
}
