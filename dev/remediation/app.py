"""Moteur de remédiation (pôle Dev).

Reçoit les alertes du détecteur IA (webhook) et rétablit le service
automatiquement, sans intervention humaine. C'est le SEUL composant autorisé
à agir sur les conteneurs : il a donc un accès au socket Docker, isolé ici et
protégé par un jeton. Il ne décide rien d'autre que l'action de reprise.
"""
import os
import secrets
from datetime import datetime, timezone

import docker
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ce service peut agir sur Docker : le jeton est OBLIGATOIRE. On refuse de
# démarrer avec un jeton vide plutôt que d'exposer l'action sans protection.
TOKEN = os.getenv("REMEDIATION_TOKEN", "")
if not TOKEN:
    raise RuntimeError("REMEDIATION_TOKEN est obligatoire (le moteur agit sur Docker).")
TARGET_CONTAINER = os.getenv("TARGET_CONTAINER", "api")

# Origines autorisées pour le dashboard (CORS), au lieu de tout ouvrir.
ALLOWED_ORIGINS = os.getenv("DASHBOARD_ORIGINS", "http://localhost:3000").split(",")

app = FastAPI(title="Moteur de remédiation")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["*"], allow_headers=["*"])

events: list[dict] = []  # historique récent, affiché par le dashboard


class Incident(BaseModel):
    event: str  # "anomaly" ou "recovered"
    score: float | None = None
    top_features: list = []
    timestamp: str | None = None


def record(action: str, incident: Incident):
    events.insert(0, {
        "action": action,
        "event": incident.event,
        "top_features": incident.top_features,
        "at": datetime.now(timezone.utc).isoformat(),
    })
    del events[50:]
    print(f"[remediation] {action}", flush=True)


@app.post("/incident")
def handle_incident(incident: Incident, authorization: str = Header("")):
    # Comparaison à temps constant : ne fuite pas la longueur ni le contenu du jeton.
    if not secrets.compare_digest(authorization, f"Bearer {TOKEN}"):
        raise HTTPException(401, "non autorisé")
    if incident.event == "anomaly":
        # Action de reprise : redémarrer le service de paiement pour effacer
        # l'état dégradé. Le choix de l'action vit ici, pas dans le détecteur.
        try:
            docker.from_env().containers.get(TARGET_CONTAINER).restart()
        except docker.errors.DockerException as exc:
            record(f"ÉCHEC du redémarrage de '{TARGET_CONTAINER}' : {exc}", incident)
            raise HTTPException(500, "la remédiation a échoué")
        record(f"redémarrage du conteneur '{TARGET_CONTAINER}'", incident)
    else:
        record("retour à la normale constaté", incident)
    return {"ok": True}


@app.get("/events")
def get_events():
    return events


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
