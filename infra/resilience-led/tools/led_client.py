"""Client de test / module a reutiliser cote back-office.

Usage (depuis le PC Hote connecte au PA RESILIENCE-G<n>) :
    python led_client.py recognized
    python led_client.py status

Variables d'environnement :
    LED_URL    (defaut http://192.168.137.50)
    LED_TOKEN  (meme valeur que API_TOKEN dans config.h)

Depuis un conteneur Docker Desktop (WSL2), l'ESP est joignable directement par son IP
192.168.137.x (le trafic sort par l'hote). Le back-office ne doit JAMAIS bloquer
l'authentification si l'ESP est hors ligne : timeout court + erreur journalisee.
"""
import json
import os
import sys
import urllib.request

LED_URL = os.environ.get("LED_URL", "http://192.168.137.50")
LED_TOKEN = os.environ.get("LED_TOKEN", "CHANGE-ME-jeton-long-et-aleatoire")
EVENTS = {"recognized", "password_ok", "password_ko", "not_recognized", "reset"}


def _call(method, path, body=None, timeout=2.0):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(LED_URL + path, data=data, method=method)
    req.add_header("Authorization", f"Bearer {LED_TOKEN}")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def send_event(event: str) -> bool:
    """A appeler depuis le back-office. Retourne False sans lever d'exception si l'ESP ne repond pas."""
    if event not in EVENTS:
        raise ValueError(f"evenement inconnu : {event}")
    try:
        _call("POST", "/api/event", {"event": event})
        return True
    except Exception as e:  # noqa: BLE001 - la LED ne doit jamais casser le login
        print(f"[led] echec envoi {event}: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"usage : {sys.argv[0]} <{'|'.join(sorted(EVENTS))}|status>")
    arg = sys.argv[1]
    print(json.dumps(_call("GET", "/api/status") if arg == "status" else _call("POST", "/api/event", {"event": arg}), indent=2))
