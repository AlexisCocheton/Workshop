"""Tests de la préparation des documents du RAG (sans Ollama)."""
from assistant.rag import load_docs


def test_load_docs_splits_and_keeps_source(tmp_path):
    (tmp_path / "procedure.md").write_text("# Procédure\n" + "Vérifier l'API. " * 200, encoding="utf-8")
    (tmp_path / "schema.png").write_bytes(b"ignored")

    chunks = load_docs(tmp_path)

    assert len(chunks) > 1
    assert {chunk.metadata["source"] for chunk in chunks} == {"procedure.md"}


def test_project_docs_are_loaded():
    assert load_docs()
