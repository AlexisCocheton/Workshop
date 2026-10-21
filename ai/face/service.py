"""Reconnaissance faciale pour la connexion au back-office (consigne additionnelle 1).

Lancement sur le PC Hôte, depuis ai/ (la caméra USB n'est pas accessible depuis Docker Desktop) :
    face\\.venv\\Scripts\\python -m uvicorn face.service:app --host 127.0.0.1 --port 8002

    POST /verify  {"username": "..."}  ->  {"recognized": bool, "reason": str | None}
    GET  /healthz

À chaque /verify, une fenêtre caméra s'ouvre sur l'écran du PC Hôte pour guider
l'opérateur (voir camera.py). Seul le service auth appelle ce service.
L'enregistrement d'un visage ne passe PAS par HTTP mais par face.enroll, sur le
PC Hôte : sinon un conteneur compromis (l'API après l'exploit du callback)
pourrait remplacer le visage de référence par le sien.
"""
import re

import face_recognition
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config import FACE_CAPTURE_SECONDS, FACE_ENCODINGS_DIR, FACE_TOLERANCE
from face.camera import capture_face

app = FastAPI(title="Reconnaissance faciale")
USERNAME = re.compile(r"[A-Za-z0-9_-]{1,32}")


class UsernameBody(BaseModel):
    username: str


def encoding_path(username: str):
    """Fichier du visage enregistré, ou None si l'identifiant contient d'autres caractères
    que lettres, chiffres, - et _ (empêche « ../ » de sortir du dossier)."""
    if not USERNAME.fullmatch(username):
        return None
    return FACE_ENCODINGS_DIR / f"{username}.npy"


@app.post("/verify")
def verify(body: UsernameBody):
    # La caméra s'allume toujours, même pour un identifiant inconnu : même comportement vu de l'extérieur.
    try:
        image, face, problem = capture_face(FACE_CAPTURE_SECONDS)
    except RuntimeError as error:
        raise HTTPException(503, str(error))
    if problem:
        return {"recognized": False, "reason": f"Visage pas bien placé à temps ({problem})"}

    path = encoding_path(body.username)
    if path is None or not path.exists():
        # Le détail ne va que dans le journal du PC Hôte : la réponse reste la même qu'un
        # visage inconnu, pour ne pas révéler quels comptes existent. !r : pas d'injection de lignes.
        print(f"[face] {body.username!r} : aucun visage enregistré pour cet identifiant", flush=True)
        return {"recognized": False, "reason": "Visage non reconnu"}
    known = np.load(path)
    distance = face_recognition.face_distance([known], face_recognition.face_encodings(image, [face])[0])[0]
    # La distance n'est que journalisée : la renvoyer aiderait un attaquant à s'approcher du seuil.
    print(f"[face] {body.username!r} : distance {distance:.2f} (seuil {FACE_TOLERANCE})", flush=True)
    if distance > FACE_TOLERANCE:
        return {"recognized": False, "reason": "Visage non reconnu"}
    return {"recognized": True, "reason": None}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
