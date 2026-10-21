"""Test de la logique d'évaluation du RAG, sans Ollama (rankings et passages simulés)."""
from types import SimpleNamespace

from langchain_core.documents import Document

from assistant import evaluate


def _fake_store(monkeypatch):
    """Store factice : 3 passages, rankings fixes, sans embeddings ni réseau."""
    passages = [
        Document(page_content="err_5xx_rate haut : l'API plante.", metadata={"source": "detection-anomalies.md"}),
        Document(page_content="Catégorie app_attack : scan ou injection.", metadata={"source": "reponse-incident.md"}),
        Document(page_content="Le WAF bloque les injections.", metadata={"source": "reponse-incident.md"}),
    ]
    # vectoriel classe mal (passage 2 d'abord), BM25 trouve le bon en tête.
    st = SimpleNamespace(
        passages=passages,
        _vector_ranking=lambda q: [2, 0, 1],
        _bm25_ranking=lambda q: [1, 0, 2] if "app_attack" in q else [0, 2, 1],
    )
    return st


def test_evaluate_method_mesure_doc_et_terme(monkeypatch):
    st = _fake_store(monkeypatch)
    # Une seule question, dont la réponse est dans reponse-incident.md avec le terme app_attack.
    monkeypatch.setattr(evaluate, "QUESTIONS", [
        {"question": "que faire si app_attack ?", "source": "reponse-incident.md", "must_contain": "app_attack"},
    ])
    res = evaluate.evaluate_method(st, "hybride", k=2)
    assert res["bon_document"] == 1.0  # reponse-incident.md est retrouvé
    assert res["terme_exact"] == 1.0   # "app_attack" est dans un passage retrouvé


def test_bm25_retrouve_terme_que_vectoriel_rate(monkeypatch):
    # vectoriel classe le passage 0 (err_5xx_rate) en DERNIER ; BM25 en premier.
    passages = [
        Document(page_content="err_5xx_rate haut : l'API plante.", metadata={"source": "detection-anomalies.md"}),
        Document(page_content="Catégorie app_attack : scan.", metadata={"source": "reponse-incident.md"}),
        Document(page_content="Le WAF bloque les injections.", metadata={"source": "reponse-incident.md"}),
    ]
    st = SimpleNamespace(
        passages=passages,
        _vector_ranking=lambda q: [1, 2, 0],  # le bon passage (0) est dernier
        _bm25_ranking=lambda q: [0, 1, 2],     # BM25 le met premier
    )
    monkeypatch.setattr(evaluate, "QUESTIONS", [
        {"question": "que veut dire err_5xx_rate ?", "source": "detection-anomalies.md", "must_contain": "err_5xx_rate"},
    ])
    # Vectoriel seul avec k=1 ramène le passage 1 (rate le terme) ; l'hybride, grâce
    # à BM25 qui met le bon passage en tête, le retrouve.
    assert evaluate.evaluate_method(st, "vectoriel", k=1)["terme_exact"] == 0.0
    assert evaluate.evaluate_method(st, "hybride", k=2)["terme_exact"] == 1.0
