# Gestion des secrets (SOPS)

Les secrets (mots de passe de base, jeton de remédiation, clé JWT) vivent dans
le fichier `.env` à la racine. Ce fichier **n'est jamais versionné en clair**
(il est dans `.gitignore`). Pour le partager dans le dépôt de façon sûre, on le
chiffre avec [SOPS](https://github.com/getsops/sops) + [age](https://github.com/FiloSottile/age).

On a choisi SOPS plutôt que HashiCorp Vault : pas de serveur à faire tourner, ce
qui suffit à un démonstrateur de quatre jours. Vault serait le choix d'une mise
en production (secrets dynamiques, révocation, baux).

## Mise en place (une fois)

```powershell
# Générer une paire de clés ; garder la clé privée HORS du dépôt
age-keygen -o key.txt
# Copier la clé publique (age1...) dans .sops.yaml
```

## Chiffrer / déchiffrer le .env

```powershell
sops -e .env > .env.enc      # chiffré, versionnable
sops -d .env.enc > .env      # déchiffré en local avant de lancer la stack
```

Seul `.env.enc` est committé. Le `.env` en clair reste local.

## Règle

Aucun secret en clair dans le dépôt, les logs, les images Docker ou les prompts
envoyés à une IA (sujet §5). Le `.env.example` ne contient que des valeurs
d'exemple à remplacer.
