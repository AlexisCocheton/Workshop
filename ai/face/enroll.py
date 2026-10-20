"""Enregistre le visage d'un opérateur du back-office.

Usage, sur le PC Hôte, depuis ai/ :
    face\\.venv\\Scripts\\python -m face.enroll --user admin

Une fenêtre caméra s'ouvre avec un ovale-guide : la photo est prise dès que le
visage est bien placé (ovale vert). Q annule. Même guide qu'à la connexion, pour
que le visage soit cadré pareil aux deux moments. Seul le vecteur de 128 nombres
qui décrit le visage est gardé (data/face_encodings/<user>.npy), jamais la photo.
"""
import argparse

import face_recognition
import numpy as np

from face.camera import capture_face
from face.service import encoding_path


def enroll(username: str):
    path = encoding_path(username)
    if path is None:
        raise SystemExit("Identifiant invalide : lettres, chiffres, - et _ uniquement.")
    print(f"Placez le visage de « {username} » dans l'ovale de la fenêtre caméra (Q = annuler).")
    image, face, problem = capture_face()
    if problem:
        raise SystemExit(f"Visage non enregistré ({problem}).")
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, face_recognition.face_encodings(image, [face])[0])
    print(f"Visage enregistré : {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enregistre le visage d'un opérateur du back-office.")
    parser.add_argument("--user", required=True, help="identifiant de l'opérateur (ex : admin)")
    enroll(parser.parse_args().user)
