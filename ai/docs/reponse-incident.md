# Procédure — Répondre à une attaque ou une panne

Quand le détecteur passe en anomalie, il qualifie l'incident par une **catégorie**
(visible sur le dashboard et dans l'alerte Telegram). Cette procédure dit quoi faire
pour chaque catégorie. La remédiation automatique agit déjà ; ces étapes servent à
vérifier et, si besoin, à décider d'une action humaine complémentaire.

## Rappel : ce que fait le système tout seul

| Étape | Automatique ? |
|---|---|
| Détecter l'anomalie (ML + contrôle de santé) | Oui |
| Qualifier l'incident (catégorie) | Oui |
| Redémarrer l'API pour restaurer le service | Oui (moteur de remédiation) |
| Prévenir l'opérateur (dashboard, Telegram) | Oui |
| Bloquer la source de l'attaque | Non : décision humaine (voir ci-dessous) |
| Corriger la vulnérabilité exploitée | Non : décision humaine |

## Que faire selon la catégorie d'incident

| Catégorie | Ce qui se passe | Vérifier | Action humaine éventuelle |
|---|---|---|---|
| api_down | L'API ne répond plus au contrôle de santé. | Que le redémarrage automatique a eu lieu, et que `/healthz` répond de nouveau 200. | Si l'API retombe aussitôt, l'attaque est persistante : couper la source au WAF. |
| app_attack | Beaucoup de requêtes refusées ou bloquées (scan, injection, brute force). | L'IP source dans les logs du WAF ; si le WAF bloque bien (403). | Bloquer l'IP source au WAF ; vérifier qu'aucune requête malveillante n'est passée. |
| dos | Afflux massif de requêtes (déni de service). | Le débit de requêtes, le CPU de l'API. | Limiter le débit au WAF ; bloquer la source si l'afflux persiste. |
| service_error | L'API renvoie des erreurs 5xx sans attaque réseau visible. | Que le redémarrage a effacé l'erreur ; les logs de l'API pour la cause. | Si l'erreur revient, la cause est interne (ex : callback exploité) : corriger le code. |
| unknown | Anormal, mais aucune cause ne ressort. | Les features en cause (z-scores) sur le dashboard ; corréler avec Grafana. | Investiguer avant d'agir : ne pas bloquer au hasard. |

## Vérifier que le service est vraiment rétabli

Le passage à l'état normal (« recovered ») ne suffit pas à prouver la reprise.
Il faut aussi :

1. vérifier sur le dashboard que tous les services sont au vert ;
2. effectuer une nouvelle transaction fictive et vérifier qu'elle réussit ;
3. vérifier que les données sont cohérentes (pas de transaction en double ou perdue).

## Disponibilité restaurée n'est pas compromission corrigée

Un redémarrage restaure la **disponibilité**. Il ne corrige **ni** la vulnérabilité
exploitée, **ni** une éventuelle exfiltration de données. Après un `app_attack` ou un
`api_down` répété :

- si l'attaque visait seulement à rendre le service indisponible, la reprise suffit ;
- si des données ont pu être lues ou modifiées, le redémarrage n'y change rien :
  il faut analyser les logs, estimer ce qui a pu fuiter, et corriger la faille.

## Bloquer une source d'attaque (si décidé)

Le blocage d'une IP est une action défensive **au WAF**, pas une action du détecteur
ni de l'assistant. Elle est réversible et doit viser uniquement la machine attaquante
du laboratoire. Consigner l'IP bloquée, l'heure et la raison, pour pouvoir débloquer
ensuite.

## Limites connues

- Une attaque lente et discrète, qui ressemble au trafic normal, peut ne pas être détectée.
- Le détecteur dit *qu'il y a* une anomalie et *de quel genre* ; le choix de l'action
  reste à la remédiation (automatique) et à l'opérateur (décisions humaines).
- Bloquer une source ne protège pas d'une attaque venue d'une autre machine.
