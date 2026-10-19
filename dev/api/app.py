"""API de paiement fictive (pôle Dev).

Traite des transactions fictives, les persiste en base, et expose des
métriques Prometheus (lues par le détecteur IA).

Contient volontairement une faille de démonstration (voir /pay/callback) :
elle met le service hors d'usage. C'est ce que l'attaque exploite ; seul un
redémarrage du conteneur (déclenché par le moteur de remédiation) le rétablit.
Aucune donnée réelle : tout est fictif.
"""
import os
import time
import uuid
from contextlib import asynccontextmanager

import jwt
import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel
from starlette.responses import Response

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
DB_DSN = os.getenv("DB_DSN", "postgresql://app:app@db:5432/payments")

# Métriques exposées sur /metrics. Les noms correspondent à ce que lit le
# détecteur IA (ai/detector/features.py) : ne pas les renommer sans prévenir.
REQUESTS = Counter("http_requests_total", "Requêtes HTTP traitées", ["method", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Durée des requêtes", ["handler"])

# État en mémoire : remis à zéro à chaque redémarrage du conteneur.
state = {"broken": False}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="API de paiement", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
bearer = HTTPBearer()


@app.middleware("http")
async def record_metrics(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    REQUESTS.labels(request.method, str(response.status_code)).inc()
    LATENCY.labels(request.url.path).observe(time.perf_counter() - start)
    return response


def connect() -> psycopg.Connection:
    return psycopg.connect(DB_DSN, autocommit=True)


def init_db():
    """Crée la table au démarrage, en réessayant tant que la base n'est pas prête."""
    for _ in range(15):
        try:
            with connect() as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS transactions ("
                    "id TEXT PRIMARY KEY, amount NUMERIC, currency TEXT, "
                    "status TEXT, created_at TIMESTAMPTZ DEFAULT now())"
                )
            return
        except psycopg.OperationalError:
            time.sleep(2)


def require_token(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "jeton invalide")


class TransactionIn(BaseModel):
    amount: float
    currency: str = "EUR"


@app.get("/healthz")
def healthz():
    if state["broken"]:
        raise HTTPException(503, "service dégradé")
    return {"status": "ok"}


@app.post("/transactions")
def create_transaction(tx: TransactionIn, _=Depends(require_token)):
    if state["broken"]:
        raise HTTPException(500, "erreur interne du service de paiement")
    row = {"id": str(uuid.uuid4()), "amount": tx.amount, "currency": tx.currency, "status": "accepted"}
    with connect() as conn:
        conn.execute(
            "INSERT INTO transactions (id, amount, currency, status) "
            "VALUES (%(id)s, %(amount)s, %(currency)s, %(status)s)",
            row,
        )
    return row


@app.get("/transactions")
def list_transactions():
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, amount, currency, status, created_at "
            "FROM transactions ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    return [
        {"id": r[0], "amount": float(r[1]), "currency": r[2], "status": r[3], "created_at": r[4].isoformat()}
        for r in rows
    ]


@app.post("/pay/callback")
def payment_callback(payload: dict):
    """FAILLE DE DÉMONSTRATION (laboratoire uniquement).

    Callback de paiement non authentifié : un payload malformé met le service
    hors d'usage (toutes les transactions suivantes échouent). Représente
    l'exploitation d'une vulnérabilité applicative. Le WAF ne bloque pas ce
    chemin : c'est à la détection ML + remédiation de rattraper l'incident.
    """
    if payload.get("status") == "__CRASH__":
        state["broken"] = True
    return {"received": True}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
