"""Service de détection : note le trafic en continu et prévient la remédiation.

Lancement : uvicorn detector.service:app --port 8000

    GET /status   état courant (lu par le dashboard et par l'assistant)
    GET /metrics  gauges aiops_* scrapées par Prometheus, affichées dans Grafana

Le détecteur n'agit jamais sur le système : il prévient le moteur de
remédiation (pôle Dev) par webhook, qui décide et exécute l'action.
"""
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
import joblib
import pandas as pd
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest

from config import (
    CONSECUTIVE_POINTS,
    DASHBOARD_ORIGINS,
    MODEL_PATH,
    POLL_SECONDS,
    REMEDIATION_TOKEN,
    REMEDIATION_URL,
)
from detector.features import FEATURE_NAMES, api_healthy, fetch_now

ANOMALY_SCORE = Gauge("aiops_anomaly_score", "Score du modèle : > 0 = point anormal")
ANOMALY = Gauge("aiops_anomaly", "1 si une anomalie est déclarée (après debounce), sinon 0")

status = {"state": "starting", "score": None, "api_healthy": None, "values": {}, "top_features": [], "error": None}


class Debouncer:
    """Change d'état seulement après N points d'affilée qui contredisent l'état actuel.

    Évite qu'un pic isolé déclenche une remédiation, et qu'on annonce la reprise trop tôt.
    """

    def __init__(self, n: int):
        self.n = n
        self.in_anomaly = False
        self.streak = 0

    def update(self, is_anomalous: bool) -> str | None:
        """Renvoie "anomaly" ou "recovered" au moment du changement d'état, sinon None."""
        if is_anomalous == self.in_anomaly:
            self.streak = 0
            return None
        self.streak += 1
        if self.streak < self.n:
            return None
        self.in_anomaly = is_anomalous
        self.streak = 0
        return "anomaly" if is_anomalous else "recovered"


def score(model, values: dict) -> float:
    """Score d'anomalie : > 0 = anormal (opposé du decision_function de scikit-learn)."""
    return float(-model.decision_function(pd.DataFrame([values])[FEATURE_NAMES])[0])


def explain(model, values: dict, top: int = 3) -> list[dict]:
    """Les features les plus éloignées de la normale, en nombre d'écarts-types (z-score).

    Le StandardScaler du modèle connaît déjà la moyenne et l'écart-type du trafic normal.
    """
    zscores = model[0].transform(pd.DataFrame([values])[FEATURE_NAMES])[0]
    ranked = sorted(zip(FEATURE_NAMES, zscores), key=lambda pair: abs(pair[1]), reverse=True)
    return [{"name": name, "value": values[name], "zscore": round(float(z), 1)} for name, z in ranked[:top]]


def notify_remediation(event: str):
    """Envoie l'événement au moteur de remédiation (3 essais)."""
    print(f"[detector] {event} : {status['top_features']}", flush=True)
    if not REMEDIATION_URL:
        return
    payload = {
        "event": event,
        "score": status["score"],
        "top_features": status["top_features"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    headers = {"Authorization": f"Bearer {REMEDIATION_TOKEN}"}
    for _ in range(3):
        try:
            httpx.post(REMEDIATION_URL, json=payload, headers=headers, timeout=5).raise_for_status()
            return
        except httpx.HTTPError as exc:
            print(f"[detector] webhook en échec : {exc}", flush=True)
            time.sleep(1)


def run_forever():
    if not MODEL_PATH.exists():
        status["state"] = "no_model"  # lancer d'abord detector.collect puis detector.train
        return
    saved = joblib.load(MODEL_PATH)
    if saved["features"] != FEATURE_NAMES:
        status["state"] = "no_model"
        status["error"] = "features.py a changé depuis l'entraînement : relancer detector.train"
        return
    model = saved["model"]
    debouncer = Debouncer(CONSECUTIVE_POINTS)

    while True:
        try:
            values = fetch_now()
        except httpx.HTTPError as exc:
            # Supervision injoignable : on ne décide rien sans données.
            status.update(state="unknown", error=str(exc))
            time.sleep(POLL_SECONDS)
            continue

        point_score = score(model, values)
        healthy = api_healthy()
        # Un point est anormal si le ML l'estime anormal OU si l'API ne répond
        # pas. Le contrôle de santé rattrape deux angles morts : une API tombée
        # sans trafic (pas de 5xx à voir), et un « faux retour à la normale »
        # après un redémarrage raté (le ML ne verrait plus d'erreurs, mais
        # l'API resterait cassée). On ne déclare la reprise que si l'API répond.
        is_anomalous = point_score > 0 or not healthy
        event = debouncer.update(is_anomalous)
        status.update(
            state="anomaly" if debouncer.in_anomaly else "normal",
            score=round(point_score, 3),
            api_healthy=healthy,
            values=values,
            top_features=explain(model, values),
            error=None,
        )
        ANOMALY_SCORE.set(point_score)
        ANOMALY.set(int(debouncer.in_anomaly))
        if event:
            notify_remediation(event)
        time.sleep(POLL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=run_forever, daemon=True).start()
    yield


app = FastAPI(title="Détecteur d'anomalies AIOps", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=DASHBOARD_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.get("/status")
def get_status():
    return status


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
