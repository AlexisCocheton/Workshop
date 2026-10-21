"""Caméra avec guide de placement, commune à l'enregistrement (enroll.py) et à la vérification (service.py).

Une fenêtre s'ouvre sur l'écran du PC Hôte avec un ovale au centre. Tant que le
visage est mal placé, l'ovale est orange avec une consigne (« Rapprochez-vous »…) ;
quand il est bien placé, l'ovale passe au vert et l'image est prise. Cadrer le
visage de la même façon à l'enregistrement et à la vérification rend la
reconnaissance plus fiable.

L'aperçu n'est affiché que sur le PC Hôte : l'image de la caméra ne sort jamais de la machine.
"""
import threading
import time

import cv2
import face_recognition

from config import CAMERA_INDEX

WINDOW = "Camera : placez votre visage dans l'ovale (Q = annuler)"
STEADY_FRAMES = 3  # images bien placées d'affilée avant la capture : pas de photo prise en plein mouvement
camera_lock = threading.Lock()  # la caméra ne peut pas être ouverte deux fois en même temps


def placement_hint(faces: list, width: int, height: int) -> str | None:
    """Consigne à afficher, ou None si un seul visage est centré et à bonne distance.

    Bien placé : le visage occupe 20 à 60 % de la largeur de l'image, et son centre
    est à moins de 12 % (horizontalement) et 15 % (verticalement) du centre de l'image.
    Les consignes sont sans accents : la police d'OpenCV ne les affiche pas.
    """
    if len(faces) != 1:
        return "Un seul visage SVP" if faces else "Placez votre visage dans l'ovale"
    top, right, bottom, left = faces[0]
    size = (right - left) / width
    # Seuil bas (12 %) : accepte un visage à distance normale d'un portable. En
    # dessous, le visage est trop petit pour un encodage fiable.
    if size < 0.12:
        return "Rapprochez-vous"
    if size > 0.70:
        return "Reculez un peu"
    if abs((left + right) / 2 - width / 2) > 0.12 * width or abs((top + bottom) / 2 - height / 2) > 0.15 * height:
        return "Centrez votre visage dans l'ovale"
    return None


def show(frame, hint: str | None):
    """Aperçu en miroir (plus naturel pour se placer), avec l'ovale-guide et la consigne."""
    view = cv2.flip(frame, 1)
    height, width = view.shape[:2]
    color = (0, 200, 0) if hint is None else (0, 165, 255)  # BGR : vert = bien placé, orange = à corriger
    cv2.ellipse(view, (width // 2, height // 2), (int(width * 0.21), int(height * 0.38)), 0, 0, 360, color, 3)
    cv2.rectangle(view, (0, height - 50), (width, height), (0, 0, 0), -1)  # bandeau noir : consigne lisible à contre-jour
    cv2.putText(view, hint or "Parfait, ne bougez plus", (15, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    cv2.imshow(WINDOW, view)


def guide(camera, timeout: float | None):
    """Boucle d'aperçu : renvoie (image, visage, None) dès que le visage est bien placé,
    ou (None, None, dernière consigne) si le temps est écoulé ou si Q est pressé."""
    deadline = time.time() + timeout if timeout else float("inf")
    cv2.namedWindow(WINDOW)
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_TOPMOST, 1)  # au premier plan, devant le navigateur
    hint, steady = "Placez votre visage dans l'ovale", 0
    while time.time() < deadline:
        ok, frame = camera.read()
        if not ok:
            raise RuntimeError("caméra USB indisponible")
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # OpenCV donne du BGR, face_recognition attend du RVB
        faces = face_recognition.face_locations(image)  # ~140 ms : aperçu à ~7 images/s
        hint = placement_hint(faces, image.shape[1], image.shape[0])
        steady = steady + 1 if hint is None else 0
        show(frame, hint)
        if steady >= STEADY_FRAMES:
            return image, faces[0], None
        if cv2.waitKey(1) & 0xFF == ord("q"):
            return None, None, "annule"
    return None, None, hint


def capture_face(timeout: float | None = None):
    """Allume la caméra et guide la personne jusqu'à un visage bien placé (voir guide()).

    timeout : secondes laissées pour se placer (None = illimité). La caméra s'éteint
    et la fenêtre se ferme dans tous les cas.
    """
    with camera_lock:
        camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)  # DirectShow : pilote caméra Windows
        try:
            return guide(camera, timeout)
        finally:
            camera.release()
            cv2.destroyAllWindows()
            cv2.waitKey(1)  # sous Windows, la fermeture de la fenêtre n'est traitée qu'à cet appel
