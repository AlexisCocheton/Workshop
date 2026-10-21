"""Assistant des opérateurs : cherche les passages utiles dans ai/docs/ et répond avec un LLM local.

Chaîne RAG, recherche HYBRIDE :
  documents -> découpage en passages
            -> deux recherches en parallèle :
               • vectorielle (embeddings Ollama) : trouve les passages au sens proche
               • BM25 (mots-clés) : trouve les termes EXACTS (err_5xx_rate, app_attack…)
            -> fusion des deux classements (Reciprocal Rank Fusion)
            -> passages retenus -> prompt -> LLM (Ollama)

Pourquoi hybride : la recherche vectorielle seule rate souvent un identifiant exact
(un nom de feature, une catégorie d'incident), que BM25 retrouve par le mot-clé.
Chacune compense l'angle mort de l'autre.

L'assistant ne fait que LIRE : aucun outil, aucune action possible sur le système.
"""
from functools import cache
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rank_bm25 import BM25Okapi

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

# Nombre de passages récupérés par CHAQUE méthode avant fusion. Un peu plus large
# que TOP_K : la fusion reclasse, puis on ne garde que les TOP_K meilleurs.
FETCH_K = max(TOP_K * 2, 10)
RRF_K = 60  # constante de lissage du Reciprocal Rank Fusion (valeur usuelle)


def load_docs(folder: Path = DOCS_DIR) -> list[Document]:
    """Lit les .md et .txt du dossier et les découpe en passages d'environ 1500 caractères."""
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


def _tokenize(text: str) -> list[str]:
    """Découpe en mots minuscules pour BM25. Les « _ » sont gardés (err_5xx_rate reste entier)."""
    return [mot for mot in "".join(c.lower() if c.isalnum() or c == "_" else " " for c in text).split() if mot]


class HybridStore:
    """Deux index sur les mêmes passages : vectoriel (sens) et BM25 (mots-clés)."""

    def __init__(self, passages: list[Document]):
        self.passages = passages
        embeddings = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_URL)
        self.vectors = InMemoryVectorStore.from_documents(passages, embeddings)
        self.bm25 = BM25Okapi([_tokenize(p.page_content) for p in passages])

    def _bm25_ranking(self, question: str) -> list[int]:
        """Indices des passages triés par score de mot-clé BM25 décroissant."""
        scores = self.bm25.get_scores(_tokenize(question))
        return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:FETCH_K]

    def _vector_ranking(self, question: str) -> list[int]:
        """Indices des passages triés par proximité sémantique (appelle Ollama)."""
        contenu_vers_indice = {p.page_content: i for i, p in enumerate(self.passages)}
        return [contenu_vers_indice[d.page_content] for d in self.vectors.similarity_search(question, k=FETCH_K)]

    def search(self, question: str, k: int = TOP_K) -> list[Document]:
        """Classements vectoriel et BM25 fusionnés par Reciprocal Rank Fusion, k meilleurs."""
        indices = fuse([self._vector_ranking(question), self._bm25_ranking(question)], k)
        return [self.passages[i] for i in indices]


def fuse(classements: list[list[int]], k: int) -> list[int]:
    """Reciprocal Rank Fusion : chaque élément gagne 1/(RRF_K + rang) dans chaque
    liste où il apparaît. Un passage bien classé par les DEUX méthodes ressort en tête.
    Renvoie les k meilleurs indices."""
    fusion: dict[int, float] = {}
    for classement in classements:
        for rang, indice in enumerate(classement):
            fusion[indice] = fusion.get(indice, 0.0) + 1.0 / (RRF_K + rang)
    return sorted(fusion, key=fusion.get, reverse=True)[:k]


@cache
def store() -> HybridStore:
    """Index construit une seule fois, au premier appel (redémarrer le service après ajout d'un doc)."""
    return HybridStore(load_docs())


def answer(question: str, incident: str = "inconnu") -> dict:
    passages = store().search(question, k=TOP_K)
    context = "\n\n".join(f"[{doc.metadata['source']}]\n{doc.page_content}" for doc in passages)
    llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_URL, temperature=0)
    reply = (PROMPT | llm).invoke({"question": question, "context": context, "incident": incident})
    return {"answer": reply.content, "sources": sorted({doc.metadata["source"] for doc in passages})}
