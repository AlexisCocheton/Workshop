"""API de l'assistant opérateur.

Lancement : uvicorn assistant.service:app --port 8001

    POST /ask  {"question": "..."}  ->  {"answer": "...", "sources": [...]}
"""
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from assistant.rag import answer
from config import DASHBOARD_ORIGINS, DETECTOR_URL

app = FastAPI(title="Assistant opérateur (RAG)")
app.add_middleware(CORSMiddleware, allow_origins=DASHBOARD_ORIGINS, allow_methods=["*"], allow_headers=["*"])


class Question(BaseModel):
    question: str


def detector_status() -> str:
    """Lit l'état du détecteur (lecture seule) pour que l'assistant sache si un incident est en cours."""
    try:
        status = httpx.get(f"{DETECTOR_URL}/status", timeout=2).json()
    except (httpx.HTTPError, ValueError):
        return "détecteur injoignable"
    return f"état = {status.get('state')}, features en cause = {status.get('top_features')}"


@app.post("/ask")
def ask(body: Question):
    return answer(body.question, incident=detector_status())
