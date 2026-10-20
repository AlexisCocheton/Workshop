"""Service d'authentification (pôle Dev).

Émet un jeton JWT signé que l'API de paiement vérifie. Trivial à dessein :
un seul utilisateur de démonstration, défini par variables d'environnement.
Aucune donnée réelle.
"""
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Secret JWT obligatoire (partagé avec l'API qui vérifie les jetons).
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET est obligatoire.")
DEMO_USER = os.getenv("DEMO_USER", "app")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "app")

# Origines autorisées pour le dashboard (CORS).
ALLOWED_ORIGINS = os.getenv("DASHBOARD_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")

app = FastAPI(title="Service d'authentification")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["*"], allow_headers=["*"])


class Credentials(BaseModel):
    user: str
    password: str


@app.post("/login")
def login(credentials: Credentials):
    if credentials.user != DEMO_USER or credentials.password != DEMO_PASSWORD:
        raise HTTPException(401, "identifiants invalides")
    payload = {"sub": credentials.user, "exp": datetime.now(timezone.utc) + timedelta(hours=8)}
    return {"token": jwt.encode(payload, JWT_SECRET, algorithm="HS256")}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
