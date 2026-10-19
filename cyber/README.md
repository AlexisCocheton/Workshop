# Pôle Cybersécurité

Éprouver la plateforme (Red Team) et la défendre (Blue Team), sans sortir du laboratoire.

## Attaque (`attack/`)

Exécutée depuis le **PC Attaquant**, contre le SI fictif du groupe uniquement.
Scan de payloads (bloqués par le WAF) + abus du callback (panne de l'API) +
déni de service contrôlé. Voir `attack/README.md`.

## Défense

| Dispositif | Où | Rôle |
|---|---|---|
| WAF | `waf/Caddyfile` (service `waf`) | Filtre les requêtes malveillantes (403), seule porte d'entrée |
| SIEM / SOC | Loki + Grafana (pôle Infra) | Centralise et corrèle les logs, visualise l'incident |
| Durcissement | `hardening.md` | Surface réduite, non-root, privilèges maîtrisés |
| Secrets | `secrets/` (SOPS) | Aucun secret en clair dans le dépôt |

## Le point clé pour le jury

Le WAF ne bloque pas tout — le callback vulnérable passe. C'est **voulu** : il
montre la défense en profondeur. Ce que le WAF laisse passer, la détection ML et
la remédiation automatique le rattrapent. Attention à ne pas confondre
restauration de la disponibilité (ce que fait le redémarrage) et correction de la
vulnérabilité (qui, elle, resterait à corriger) — voir le pôle Gouvernance.
