# Scripts d'attaque (PC Attaquant)

**Périmètre strict (sujet §3.4 et §9) :** ces scripts ne visent QUE le SI fictif
de votre propre groupe, sur le point d'accès du consortium. Jamais le réseau du
campus, un autre groupe ou un service accessible sur Internet. Aucune donnée
réelle.

## Installation (sur le PC Attaquant)

```powershell
pip install -r requirements.txt
```

## Attaque principale — panne applicative

```powershell
python attack.py --target http://192.168.137.1:8080
```

1. Scan de payloads malveillants → bloqués par le WAF (403) → visibles dans les
   logs (feature `waf_blocks`) et le taux d'erreurs 4xx.
2. Tentatives de récupération de données (injections d'extraction, endpoints
   sensibles comme `/.env` ou `/backup.sql`, énumération IDOR sur
   `/transactions/{id}`) → bloquées par le WAF (403) et erreurs 4xx. Aucune
   donnée réelle derrière ces routes : le but est de produire du trafic
   malveillant reconnaissable qui alimente `waf_blocks` et le taux d'erreurs.
3. Abus du callback `/pay/callback` → l'API passe en erreur 5xx (service de
   paiement indisponible).

C'est l'incident que le détecteur ML repère et que la remédiation corrige
automatiquement en redémarrant l'API.

## Attaque secondaire — déni de service contrôlé

```powershell
python dos.py --target http://192.168.137.1:8080 --seconds 20
```

Fait monter le trafic, la latence et le CPU. Montre que la détection ne repose
pas sur un seul indicateur.
