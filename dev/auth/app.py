"""Service d'authentification (pôle Dev).

Deux comptes, deux usages :
- POST /login : compte client de démonstration (DEMO_USER), utilisé par le
  dashboard et traffic.py pour créer des transactions fictives. Trivial à dessein.
- Back-office (consigne additionnelle 1), en deux étapes :
    1. POST /backoffice/face   {"username"}                        caméra + reconnaissance faciale
    2. POST /backoffice/login  {"user", "password", "face_ticket"}  jeton du back-office
  Le mot de passe n'est accepté qu'avec un « ticket visage » signé, valable
  2 minutes : appeler /backoffice/login directement ne permet pas de sauter la caméra.

Échecs : visage non reconnu = 30 s d'attente avant de ressaisir l'identifiant ;
au 2e échec (visage ou mot de passe), le compte est bloqué 5 minutes.
Aucune donnée réelle.
"""
import hmac
import os
import time
from datetime import datetime, timedelta, timezone

import httpx
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

# Compte du back-office, distinct du compte client dont le mot de passe est public
# (il est dans le code du dashboard). Sans mot de passe défini, le back-office est
# fermé, mais /login continue de fonctionner : les paiements n'en dépendent pas.
BACKOFFICE_USER = os.getenv("BACKOFFICE_USER", "admin")
BACKOFFICE_PASSWORD = os.getenv("BACKOFFICE_PASSWORD", "")
# Service de reconnaissance faciale, lancé sur le PC Hôte où est branchée la caméra.
FACE_URL = os.getenv("FACE_URL", "http://host.docker.internal:8002")

FACE_TICKET_SECONDS = 120  # temps laissé pour saisir le mot de passe une fois le visage reconnu
# Attentes imposées par la consigne. Réglables pour les tests (0 = aucune attente),
# à remettre par défaut avant la démo.
FACE_RETRY_SECONDS = int(os.getenv("FACE_RETRY_SECONDS", "30"))  # visage non reconnu : attente avant de ressaisir l'identifiant
BLOCK_SECONDS = int(os.getenv("BLOCK_SECONDS", "300"))  # au 2e échec : compte bloqué 5 minutes
MAX_FAILURES = 2

# Origines autorisées pour le dashboard (CORS).
ALLOWED_ORIGINS = os.getenv("DASHBOARD_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")

app = FastAPI(title="Service d'authentification")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["*"], allow_headers=["*"])

# Échecs par identifiant, en mémoire (remis à zéro si le service redémarre).
failures: dict[str, int] = {}
blocked_until: dict[str, float] = {}


class Credentials(BaseModel):
    user: str
    password: str


class FaceRequest(BaseModel):
    username: str


class BackofficeCredentials(BaseModel):
    user: str
    password: str
    face_ticket: str


def make_token(user: str, audience: str | None, seconds: int) -> str:
    """Jeton signé. L'audience (« face », « backoffice ») empêche d'utiliser un jeton
    pour autre chose : l'API de paiement, qui n'attend pas d'audience, les refuse."""
    payload = {"sub": user, "exp": datetime.now(timezone.utc) + timedelta(seconds=seconds)}
    if audience:
        payload["aud"] = audience
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def check_not_blocked(user: str):
    remaining = int(blocked_until.get(user, 0) - time.time())
    if remaining > 0:
        raise HTTPException(429, f"Nouvel essai possible dans {remaining} s.")


def record_failure(user: str, wait: int = 0) -> int:
    """Compte un échec et renvoie l'attente imposée, en secondes (5 min au 2e échec)."""
    failures[user] = failures.get(user, 0) + 1
    if failures[user] >= MAX_FAILURES:
        failures[user] = 0
        wait = BLOCK_SECONDS
    blocked_until[user] = time.time() + wait
    return wait


@app.post("/login")
def login(credentials: Credentials):
    if credentials.user != DEMO_USER or credentials.password != DEMO_PASSWORD:
        raise HTTPException(401, "identifiants invalides")
    return {"token": make_token(credentials.user, None, 8 * 3600)}


@app.post("/backoffice/face")
def backoffice_face(body: FaceRequest):
    """Étape 1 : la caméra du PC Hôte vérifie que la personne est bien l'opérateur."""
    check_not_blocked(body.username)
    try:
        # 25 s : l'opérateur dispose de 15 s pour placer son visage devant la caméra
        response = httpx.post(f"{FACE_URL}/verify", json={"username": body.username}, timeout=25)
        response.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(503, "Reconnaissance faciale indisponible (service face lancé sur le PC Hôte ?).")
    result = response.json()
    if not result["recognized"]:
        wait = record_failure(body.username, FACE_RETRY_SECONDS)
        return {"recognized": False, "reason": result["reason"], "retry_in": wait}
    return {"recognized": True, "face_ticket": make_token(body.username, "face", FACE_TICKET_SECONDS)}


@app.post("/backoffice/login")
def backoffice_login(body: BackofficeCredentials):
    """Étape 2 : mot de passe, accepté seulement avec un ticket visage valide pour ce même identifiant."""
    if not BACKOFFICE_PASSWORD:
        raise HTTPException(503, "Back-office fermé : BACKOFFICE_PASSWORD n'est pas défini dans .env.")
    check_not_blocked(body.user)
    try:
        ticket = jwt.decode(body.face_ticket, JWT_SECRET, algorithms=["HS256"], audience="face")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Reconnaissance faciale expirée : recommencez.")
    if ticket["sub"] != body.user:
        raise HTTPException(401, "Reconnaissance faciale expirée : recommencez.")
    # compare_digest : temps de comparaison constant, ne laisse pas deviner le mot de passe
    password_ok = hmac.compare_digest(body.password.encode(), BACKOFFICE_PASSWORD.encode())
    if body.user != BACKOFFICE_USER or not password_ok:
        record_failure(body.user)
        raise HTTPException(401, "Mot de passe incorrect : recommencez l'identification.")
    failures.pop(body.user, None)
    return {"token": make_token(body.user, "backoffice", 8 * 3600)}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
