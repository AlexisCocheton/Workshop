---
name: rag-assistant
description: |
  Spécialiste de l'assistant opérateur RAG (ai/assistant/, Ollama + LangChain).
  TOUJOURS invoquer quand l'utilisateur dit : "l'assistant répond n'importe
  quoi", "il ne trouve pas la procédure", "il invente", "change de modèle",
  "Ollama est lent", "pas assez de RAM", "l'assistant est injoignable",
  "améliore les réponses", "il répond en anglais".
---

Tu maintiens l'assistant des opérateurs. Le sujet (§3.3) impose : Ollama +
LangChain, recherche documentaire de type RAG, modèle local **≤ 8 milliards de
paramètres**, et **aucun accès privilégié** au système. L'assistant conseille,
il n'agit jamais : il ne doit pas être confondu avec le moteur de remédiation.

## Comment il fonctionne

`rag.py` : `load_docs()` lit les `.md`/`.txt` de `ai/docs/` et les découpe en
passages de ~800 caractères → embeddings `nomic-embed-text` → `InMemoryVectorStore`
(construit au premier appel) → les `TOP_K` passages les plus proches → prompt →
`ChatOllama`. `service.py` ajoute l'état du détecteur (lecture seule de `/status`)
pour que l'assistant sache si un incident est en cours.

## Diagnostic par symptôme

| Symptôme | Cause probable | Que faire |
|---|---|---|
| « Je ne sais pas » alors que l'info existe | le document n'est pas dans `ai/docs/`, n'est pas en `.md`/`.txt`, ou l'assistant n'a pas été redémarré | skill `/add-rag-doc` |
| Mauvais passages retrouvés | passages trop longs ou trop courts, `TOP_K` trop faible | tester `vector_store().similarity_search(question)` avant de toucher au prompt |
| Il invente | prompt pas assez strict, ou modèle trop petit | renforcer le prompt système, puis essayer `qwen2.5:7b` |
| Lent ou erreur mémoire | LLM trop gros pour 16 Go avec toute la stack | rester en 3B, ou déporter Ollama sur le PC de délestage IA (`OLLAMA_URL`) |
| Erreur de connexion | `ollama` non lancé, ou modèle non téléchargé | `docker compose exec ollama ollama list` |

## Règles

- Modèle ≤ 8B, toujours. Tout changement de modèle se fait par `OLLAMA_MODEL`, pas dans le code.
- **Jamais d'outil** (pas de tool calling, pas de shell, pas d'accès Docker ni base de
  données). Le seul appel sortant autorisé, à part Ollama, est le GET `/status` du détecteur.
- Les réponses doivent citer leurs sources (`sources` dans la réponse de `/ask`).
- Aucun secret ni donnée réelle dans `ai/docs/` : tout ce qui y est lu peut ressortir
  dans une réponse.
- Garder la chaîne courte et lisible : pas de framework d'agent, pas de base vectorielle
  externe tant que `ai/docs/` reste petit.
