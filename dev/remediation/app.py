"""Moteur de remédiation (pôle Dev).

Reçoit les alertes du détecteur IA (webhook) et rétablit le service
automatiquement, sans intervention humaine. C'est le SEUL composant autorisé
à agir sur les conteneurs : il a donc un accès au socket Docker, isolé ici et
protégé par un jeton. Il ne décide rien d'autre que l'action de reprise.
"""
import os
from datetime import datetime, timezone

import docker
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

TOKEN = os.getenv("REMEDIATION_TOKEN", "")
TARGET_CONTAINER = os.getenv("TARGET_CONTAINER", "api")

app = FastAPI(title="Moteur de remédiation")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

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
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "non autorisé")
    if incident.event == "anomaly":
        # Action de reprise : redémarrer le service de paiement pour effacer
        # l'état dégradé. Le choix de l'action vit ici, pas dans le détecteur.
        docker.from_env().containers.get(TARGET_CONTAINER).restart()
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
