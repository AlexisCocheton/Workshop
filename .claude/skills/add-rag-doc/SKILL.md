---
name: add-rag-doc
description: |
  Ajoute un document de l'équipe à la base de connaissance de l'assistant RAG
  et vérifie qu'il est bien retrouvé.
  TOUJOURS utiliser ce skill quand l'utilisateur dit : "ajoute ce doc à
  l'assistant", "l'assistant doit connaître le PCA", "ajoute la procédure",
  "mets l'architecture dans le RAG", "l'assistant ne connaît pas X".
---

# Ajouter un document à l'assistant

## 1. Préparer le document

- Format `.md` ou `.txt` uniquement. Un PDF ou un Word des autres pôles (EBIOS,
  PCA/PRA, architecture) doit être converti en Markdown : copier le texte, garder
  les titres, retirer les en-têtes et pieds de page répétés.
- Nom de fichier explicite, en minuscules : `pca-pra.md`, `architecture.md`,
  `procedure-redemarrage-api.md`. Ce nom apparaît dans les sources des réponses.
- Des titres clairs (`##`) et des paragraphes courts : le découpage en passages
  d'environ 800 caractères suit mieux un texte structuré.
- **Relire avant d'ajouter** : aucun secret, mot de passe, IP sensible ou donnée
  réelle. Tout ce qui est dans `ai/docs/` peut ressortir dans une réponse.

## 2. L'ajouter

Copier le fichier dans `ai/docs/`, puis vérifier qu'il est bien lu :

```powershell
cd ai
.venv\Scripts\python -m pytest tests/test_rag.py -q
```

## 3. Recharger l'assistant

L'index est construit au démarrage du service :

```powershell
docker compose restart assistant
```

## 4. Vérifier avec une vraie question

Poser une question dont la réponse n'existe que dans le nouveau document :

```powershell
curl -s -X POST http://127.0.0.1:8001/ask -H "Content-Type: application/json" -d "{\"question\": \"...\"}"
```

Le nom du fichier doit apparaître dans `sources`. Sinon : le passage n'est pas
retrouvé. Reformuler les titres du document avec les mots qu'un opérateur
emploierait, ou augmenter `TOP_K`.
