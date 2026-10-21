"""Évalue la recherche du RAG sur un jeu de questions (assistant.eval_questions).

Pour chaque question, on vérifie si la recherche ramène dans ses top-k :
  - le bon document (recall@k)
  - un passage contenant le terme exact attendu (ex : err_5xx_rate)

On compare trois méthodes pour prouver l'apport de l'hybride :
  hybride (BM25 + vectoriel)  vs  vectoriel seul  vs  BM25 seul.

Usage, dans le réseau Docker (accès à Ollama) :
    docker compose run --rm assistant python -m assistant.evaluate
Écrit aussi data/rag_eval.json (résultats, pour le dossier).
"""
import json

from config import DATA_DIR, TOP_K
from assistant.eval_questions import QUESTIONS
from assistant.rag import fuse, store


def _passages(ranking, passages, k):
    return [passages[i] for i in ranking[:k]]


def evaluate_method(st, method: str, k: int) -> dict:
    """Taux de bon document retrouvé et de terme exact trouvé, pour une méthode."""
    bon_doc = 0
    bon_terme = 0
    for q in QUESTIONS:
        vect = st._vector_ranking(q["question"])
        bm25 = st._bm25_ranking(q["question"])
        if method == "hybride":
            ranking = fuse([vect, bm25], k)
        elif method == "vectoriel":
            ranking = vect[:k]
        else:  # bm25
            ranking = bm25[:k]
        trouves = _passages(ranking, st.passages, k)
        sources = {p.metadata["source"] for p in trouves}
        texte = " ".join(p.page_content for p in trouves)
        if q["source"] in sources:
            bon_doc += 1
        if q["must_contain"].lower() in texte.lower():
            bon_terme += 1
    n = len(QUESTIONS)
    return {
        "bon_document": round(bon_doc / n, 2),   # recall@k du document
        "terme_exact": round(bon_terme / n, 2),  # le terme attendu est dans un passage retrouvé
    }


def main():
    st = store()
    # On évalue à plusieurs k : avec un petit corpus, un grand k ramène presque
    # tout et les méthodes se valent. Les petits k (1, 2, 3) montrent laquelle
    # CLASSE le mieux — c'est là que l'hybride se distingue.
    rapport = {
        "n_questions": len(QUESTIONS),
        "n_passages": len(st.passages),
        "par_k": {
            str(k): {m: evaluate_method(st, m, k) for m in ("hybride", "vectoriel", "bm25")}
            for k in (1, 2, 3, TOP_K)
        },
    }
    (DATA_DIR / "rag_eval.json").write_text(json.dumps(rapport, indent=2, ensure_ascii=False))
    print(json.dumps(rapport, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
