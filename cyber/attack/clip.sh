#!/usr/bin/env bash
# Clip Chrono - PC Attaquant. A lancer DEPUIS le dossier cyber/attack :
#   cd cyber/attack
#   bash clip.sh              (ou colle les lignes ci-dessous en etant dans ce dossier)
HOST=http://192.168.137.1:18080

token() { curl -s -X POST $HOST/auth/login -H 'Content-Type: application/json' -d '{"user":"app","password":"app"}' | grep -o '"token":"[^"]*"' | cut -d'"' -f4; }
pay()   { curl -s -o /dev/null -w "%{http_code}" -X POST $HOST/transactions -H "Authorization: Bearer $(token)" -H 'Content-Type: application/json' -d '{"amount":20}'; }

echo "1) Paiement AVANT  -> $(pay)"
echo "2) ATTAQUE :"
python attack.py --target $HOST
echo "3) Reprise automatique :"
until [ "$(curl -s -o /dev/null -w '%{http_code}' $HOST/healthz)" = "200" ]; do echo "   ...API KO (503), remediation en cours"; sleep 1; done
echo "   -> API RETABLIE"
echo "4) Paiement APRES  -> $(pay)"
