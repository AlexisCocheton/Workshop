# Continuité et reprise (PCA/PRA) — l'essentiel pour l'opérateur

Résumé opérationnel. Le document complet est dans `gouvernance/pca-pra.md`.

## Services critiques

| Priorité | Service | Conséquence d'une perte |
|---|---|---|
| P1 | API de paiement | Plus aucun paiement : c'est l'incident que la reprise cible. |
| P1 | Base PostgreSQL | Perte de données : **non réparable par un redémarrage**. |
| P2 | Remédiation | Plus de reprise automatique : passer en repli manuel. |
| P2 | Détecteur ML + supervision | L'incident n'est plus vu automatiquement. |
| P3 | WAF, dashboard, assistant | Perte de filtrage ou de visibilité, pas de perte de service. |

## Objectifs de reprise

| Terme | Définition | Valeur visée |
|---|---|---|
| RTO | Temps max d'indisponibilité avant retour du service | ~30 à 60 secondes (reprise automatique) |
| RPO | Données max que l'on accepte de perdre | ~0 pour les transactions confirmées |

Le RPO est proche de zéro car **une transaction est écrite en base avant la
réponse au client** : un redémarrage de l'API ne perd aucune transaction déjà confirmée.

## Ce que la reprise automatique couvre, et ce qu'elle ne couvre pas

| Situation | Couvert par la reprise auto ? |
|---|---|
| API hors service (erreurs 5xx, callback exploité) | **Oui** : redémarrage de l'API. |
| Indisponibilité passagère du service de paiement | **Oui**. |
| Compromission persistante (vulnérabilité non corrigée) | **Non** : un redémarrage ne corrige pas la faille. |
| Fuite ou corruption de données | **Non** : à traiter manuellement (analyse, restauration). |

Un redémarrage restaure la **disponibilité**, pas la **sécurité**. Après un
incident répété ou une attaque, vérifier qu'aucune donnée n'a été lue ou modifiée.

## Repli manuel (si la reprise automatique ne fonctionne pas)

Si le détecteur ou la remédiation est hors service, l'incident n'est plus traité
automatiquement. L'opérateur doit alors :

1. constater l'état sur le dashboard et Grafana ;
2. redémarrer manuellement le service de paiement ;
3. vérifier la reprise par une nouvelle transaction (voir « Vérifier que le
   service est vraiment rétabli » dans la procédure de réponse à incident).

## Preuve de reprise

Le service n'est considéré rétabli que si une **nouvelle transaction réussit**.
Le simple passage du détecteur à l'état normal ne suffit pas.
