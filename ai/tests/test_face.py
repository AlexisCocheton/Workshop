"""Tests de la reconnaissance faciale, sans caméra (image et visages simulés).

À lancer avec le venv du service, le seul qui a dlib :
    face\\.venv\\Scripts\\python -m pytest tests/test_face.py
Avec le venv principal, ces tests sont ignorés (skipped).
"""
import numpy as np
import pytest

pytest.importorskip("face_recognition")
from face import service  # noqa: E402  (après le importorskip)
from face.camera import placement_hint  # noqa: E402

KNOWN = np.zeros(128)  # visage enregistré de l'opérateur « admin »
CENTERED = (120, 420, 360, 220)  # haut, droite, bas, gauche : 200 px de large, au centre d'une image 640x480


@pytest.fixture
def camera(monkeypatch, tmp_path):
    """Remplace la caméra. Modifier `seen` change ce que la caméra « voit »."""
    monkeypatch.setattr(service, "FACE_ENCODINGS_DIR", tmp_path)
    np.save(tmp_path / "admin.npy", KNOWN)
    seen = {"encoding": KNOWN, "problem": None}

    def fake_capture(timeout):
        if seen["problem"]:
            return None, None, seen["problem"]
        return np.zeros((480, 640, 3), dtype=np.uint8), CENTERED, None

    monkeypatch.setattr(service, "capture_face", fake_capture)
    monkeypatch.setattr(service.face_recognition, "face_encodings", lambda image, faces: [seen["encoding"]])
    return seen


def verify(username):
    return service.verify(service.UsernameBody(username=username))["recognized"]


def test_same_face_is_recognized(camera):
    assert verify("admin") is True


def test_other_face_is_rejected(camera):
    camera["encoding"] = KNOWN + 0.1  # distance 0,1 x racine(128) = 1,13, au-delà du seuil 0,5
    assert verify("admin") is False


def test_badly_placed_face_is_rejected(camera):
    camera["problem"] = "Rapprochez-vous"  # temps écoulé sans visage bien placé
    assert verify("admin") is False


def test_unknown_or_malicious_username_is_rejected(camera):
    assert verify("inconnu") is False
    assert verify("../admin") is False
    assert service.encoding_path("../admin") is None


def test_placement_hint():
    assert placement_hint([CENTERED], 640, 480) is None
    assert placement_hint([], 640, 480) == "Placez votre visage dans l'ovale"
    assert placement_hint([CENTERED, CENTERED], 640, 480) == "Un seul visage SVP"  # intrus + opérateur
    assert placement_hint([(190, 370, 290, 270)], 640, 480) == "Rapprochez-vous"  # 100 px = 16 % de la largeur
    assert placement_hint([(40, 520, 440, 120)], 640, 480) == "Reculez un peu"  # 400 px = 62 %
    assert placement_hint([(120, 570, 360, 370)], 640, 480) == "Centrez votre visage dans l'ovale"  # 150 px à droite
