"""Assistant des opérateurs : cherche les passages utiles dans ai/docs/ et répond avec un LLM local.

Chaîne RAG : documents -> découpage en passages -> embeddings (Ollama)
-> recherche des passages proches de la question -> prompt -> LLM (Ollama).

L'assistant ne fait que LIRE : aucun outil, aucune action possible sur le système.
"""
from functools import cache
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import DOCS_DIR, EMBED_MODEL, OLLAMA_MODEL, OLLAMA_URL, TOP_K

PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Tu es l'assistant des opérateurs de la plateforme de paiement RESILIENCE-ALPHA. "
     "Réponds en français, de façon courte et concrète, UNIQUEMENT à partir des documents ci-dessous. "
     "Cite le nom du document utilisé. Si la réponse n'y est pas, dis que tu ne sais pas. "
     "Tu ne peux exécuter aucune action : tu conseilles, l'opérateur décide.\n\n"
     "État actuel du détecteur d'anomalies : {incident}\n\n"
     "Documents :\n{context}"),
    ("human", "{question}"),
])


def load_docs(folder: Path = DOCS_DIR) -> list[Document]:
    """Lit les .md et .txt du dossier et les découpe en passages d'environ 800 caractères."""
    docs = [
        Document(page_content=path.read_text(encoding="utf-8"), metadata={"source": path.name})
        for path in sorted(folder.rglob("*"))
        if path.suffix in {".md", ".txt"}
    ]
    # Passages assez grands pour qu'un tableau Markdown (en-tête + lignes) ne
    # soit pas coupé en deux : sinon une ligne « err_5xx_rate → l'API plante »
    # serait séparée de l'en-tête du tableau et deviendrait introuvable.
    splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=150)
    return splitter.split_documents(docs)


@cache
def vector_store() -> InMemoryVectorStore:
    """Index construit une seule fois, au premier appel (redémarrer le service après ajout d'un doc)."""
    embeddings = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_URL)
    return InMemoryVectorStore.from_documents(load_docs(), embeddings)


def answer(question: str, incident: str = "inconnu") -> dict:
    passages = vector_store().similarity_search(question, k=TOP_K)
    context = "\n\n".join(f"[{doc.metadata['source']}]\n{doc.page_content}" for doc in passages)
    llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_URL, temperature=0)
    reply = (PROMPT | llm).invoke({"question": question, "context": context, "incident": incident})
    return {"answer": reply.content, "sources": sorted({doc.metadata["source"] for doc in passages})}
