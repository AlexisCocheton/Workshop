---
name: ai-check
description: |
  Checklist qualité de la partie IA, à exécuter avant tout commit ou rendu.
  Vérifie dans l'ordre : tests, absence de seuils codés en dur, sécurité,
  contrat d'interface avec les autres pôles, documentation.
  TOUJOURS utiliser ce skill quand l'utilisateur dit : "valide avant commit",
  "check qualité", "c'est prêt ?", "tout est bon ?", "vérifie avant de
  pousser", "avant le gel du code", "on peut rendre ?".
---

# Vérification de la partie IA

Chaque phase doit être verte avant de passer à la suivante. Donner un verdict
par phase (OK / à corriger + fichier:ligne).

## Phase 1 — Tests

```powershell
cd ai
.venv\Scripts\python -m pytest -q
```

Aucun test ne doit toucher le réseau : s'il devient lent ou dépend de la
connexion, un appel réel à Prometheus, Loki ou Ollama s'est glissé dedans.

## Phase 2 — Pas de seuil codé en dur

Le sujet refuse une détection « réduite à quelques conditions codées en dur ».
Chercher dans `ai/detector/` toute comparaison d'une métrique à une valeur fixe
(`> 10`, `>= 0.5`…). Seule exception légitime : `score > 0`, la frontière apprise
par le modèle. Les réglages (`POLL_SECONDS`, `CONSECUTIVE_POINTS`, `CONTAMINATION`)
doivent venir de `ai/config.py`.

## Phase 3 — Sécurité

- Aucun secret en clair : rechercher `token`, `password`, `secret`, `key` dans `ai/` ;
  seules des lectures `os.getenv(...)` sont acceptables.
- L'assistant n'a aucun outil : pas de `bind_tools`, `subprocess`, `docker`, accès
  base de données dans `ai/assistant/`.
- `ai/compose.yml` : pas de montage de `/var/run/docker.sock`, ports publiés sur
  `127.0.0.1` seulement, `docs/` monté en lecture seule.
- `OLLAMA_MODEL` ≤ 8 milliards de paramètres.
- Aucune donnée réelle dans `ai/data/` ni `ai/docs/`.

## Phase 4 — Contrat avec les autres pôles

```powershell
git diff -- ai/detector/features.py ai/detector/service.py ai/assistant/service.py
```

Si les features, le format du webhook, les gauges `aiops_*` ou les routes HTTP
ont changé : la section « Contrat d'interface » de `ai/README.md` est-elle à jour ?
Rappeler à l'utilisateur de prévenir les pôles Dev / Infra concernés.

## Phase 5 — Documentation

- `ai/README.md`, section « Pour le dossier » : les résultats correspondent-ils au
  dernier `ai/data/report.json` ? Les limites sont-elles toujours vraies ?
- Le code ajouté est-il lisible sans explication orale ? Sinon, simplifier avant
  de commenter.

## Si une phase échoue

Corriger avant de continuer. Une phase 3 rouge est bloquante : la sécurité du
moteur et des accès fait partie de la note (Axe 2).
