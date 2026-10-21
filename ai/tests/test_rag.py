"""Tests du RAG : préparation des docs, tokenisation, BM25 et fusion RRF (sans Ollama)."""
from rank_bm25 import BM25Okapi

from assistant.rag import _tokenize, fuse, load_docs


def test_load_docs_splits_and_keeps_source(tmp_path):
    (tmp_path / "procedure.md").write_text("# Procédure\n" + "Vérifier l'API. " * 200, encoding="utf-8")
    (tmp_path / "schema.png").write_bytes(b"ignored")

    chunks = load_docs(tmp_path)

    assert len(chunks) > 1
    assert {chunk.metadata["source"] for chunk in chunks} == {"procedure.md"}


def test_project_docs_are_loaded():
    assert load_docs()


def test_tokenize_garde_les_identifiants_entiers():
    # Un nom de feature avec underscore ne doit pas être coupé : BM25 doit pouvoir
    # le retrouver tel quel. La ponctuation sépare, les chiffres sont gardés.
    assert _tokenize("err_5xx_rate haut : l'API plante !") == ["err_5xx_rate", "haut", "l", "api", "plante"]


def test_bm25_retrouve_un_identifiant_exact():
    # L'angle mort du vectoriel : une recherche sur un terme technique exact.
    passages = [
        "La latence augmente quand le service est saturé.",
        "err_5xx_rate haut signifie que l'API plante.",
        "Le WAF bloque les injections SQL.",
    ]
    bm25 = BM25Okapi([_tokenize(p) for p in passages])
    scores = bm25.get_scores(_tokenize("que veut dire err_5xx_rate"))
    # Le passage qui contient err_5xx_rate doit avoir le meilleur score.
    assert scores.argmax() == 1


def test_fuse_favorise_un_passage_classe_par_les_deux():
    # Passage 2 : classé 1er par le vectoriel ET 1er par BM25 -> doit sortir en tête.
    # Passage 0 : 1er du vectoriel seulement. Passage 5 : 1er de BM25 seulement.
    vectoriel = [0, 2, 1]
    bm25 = [2, 5, 3]
    resultat = fuse([vectoriel, bm25], k=3)
    assert resultat[0] == 2  # présent en tête des deux listes
    assert set(resultat) == {2, 0, 5}  # puis les meilleurs de chaque liste


def test_fuse_respecte_k():
    assert len(fuse([[0, 1, 2, 3], [3, 2, 1, 0]], k=2)) == 2
