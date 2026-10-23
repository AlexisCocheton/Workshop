#!/usr/bin/env bash
# Clip Chrono - PC Attaquant -> SI fictif du groupe UNIQUEMENT (labo, sujet §3.4 et §9).
# Recon, attaque, puis on confirme l'impact et on regarde la cible se relever seule.
#   cd cyber/attack && bash clip.sh            (ou : bash clip.sh http://<ip>:<port>)
HOST="${1:-http://192.168.137.1:18080}"

token()  { curl -s -X POST "$HOST/auth/login" -H 'Content-Type: application/json' -d '{"user":"app","password":"app"}' | grep -o '"token":"[^"]*"' | cut -d'"' -f4; }
probe()  { curl -s -o /dev/null -w '%{http_code}' -X POST "$HOST/transactions" -H "Authorization: Bearer $(token)" -H 'Content-Type: application/json' -d '{"amount":20}'; }
health() { curl -s -o /dev/null -w '%{http_code}' "$HOST/healthz"; }

# Recon : la cible traite bien les paiements.
echo "[*] transaction cible -> $(probe)"

# Attaque (scan WAF -> tentatives d'exfiltration -> abus du callback).
python attack.py --target "$HOST"

# Impact : la cible ne répond plus.
while [ "$(health)" = "200" ]; do sleep 0.3; done
echo "[+] cible hors service"

# Elle se rétablit seule (remédiation automatique du défenseur).
while [ "$(health)" != "200" ]; do sleep 0.5; done
echo "[-] cible de nouveau en ligne"

# Le service encaisse de nouveau une transaction.
echo "[*] transaction cible -> $(probe)"
