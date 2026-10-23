"""Entraîne le détecteur sur le trafic normal, puis l'évalue sur le trafic d'attaque.

Usage : python -m detector.train

Entrées : data/normal.csv (obligatoire), data/attack.csv (optionnel, sert à l'évaluation)
Sorties : data/model.joblib (modèle utilisé par le service), data/report.json (résultats)
"""
import json

import joblib
import pandas as pd
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from config import CONTAMINATION, DATA_DIR, MODEL_PATH
from detector.features import FEATURE_NAMES


def train(normal: pd.DataFrame):
    """Apprend à quoi ressemble le trafic normal.

    StandardScaler met toutes les features à la même échelle (sinon la latence
    en secondes pèserait moins que le nombre de requêtes). LocalOutlierFactor
    compare ensuite chaque nouveau point à ses plus proches voisins du trafic
    normal : plus il est loin d'eux, plus il est anormal.

    Pourquoi pas IsolationForest : il ignore une feature constante pendant
    l'apprentissage (ex : 0 erreur 5xx en temps normal) et ne voit donc pas
    une panne qui fait monter cette feature (voir README, « Choix du modèle »).
    """
    # n_neighbors doit rester bien inférieur au nombre de points, sinon LOF
    # dégénère (sur des collectes courtes de ~45 points, 20 voisins donnent des
    # scores aberrants). On vise un tiers du jeu, borné entre 5 et 40 : sur une
    # collecte longue (~170 points), trop peu de voisins rend la frontière de
    # densité sensible à un point normal isolé (faux positif) ; ~35-40 voisins la
    # lissent et éliminent ce faux positif sans manquer d'attaque (vérifié).
    n_neighbors = max(5, min(40, len(normal) // 3))
    model = make_pipeline(
        StandardScaler(),
        LocalOutlierFactor(n_neighbors=n_neighbors, novelty=True, contamination=CONTAMINATION),
    )
    model.fit(normal[FEATURE_NAMES])
    return model


def evaluate(model, normal_test: pd.DataFrame, attack: pd.DataFrame) -> dict:
    """Compare les prédictions aux étiquettes, point par point (sans le debounce du service)."""
    data = pd.concat([normal_test, attack])
    y_true = (data["label"] == "attack").astype(int)
    y_pred = (model.predict(data[FEATURE_NAMES]) == -1).astype(int)  # scikit-learn : -1 = anomalie
    tn, fp, fn, tp = (int(x) for x in confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel())
    return {
        "false_positive_rate": round(fp / max(tn + fp, 1), 3),  # trafic normal pris pour une attaque
        "recall": round(tp / max(tp + fn, 1), 3),  # points d'attaque détectés
        "precision": round(tp / max(tp + fp, 1), 3),  # alertes qui étaient de vraies attaques
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "n_normal_test": len(normal_test),
        "n_attack": len(attack),
    }


def main():
    normal = pd.read_csv(DATA_DIR / "normal.csv")
    attack_path = DATA_DIR / "attack.csv"
    attack = pd.read_csv(attack_path) if attack_path.exists() else normal.iloc[0:0]

    # 25 % du trafic normal sont gardés pour le test. On mélange (shuffle) car
    # les collectes sont courtes : sans mélange, tout un régime de débit (ex : les
    # pics de charge) se retrouverait uniquement dans le test, que le modèle
    # n'aurait jamais appris, gonflant artificiellement les faux positifs.
    normal_train, normal_test = train_test_split(normal, test_size=0.25, shuffle=True, random_state=42)

    model = train(normal_train)
    report = evaluate(model, normal_test, attack)

    joblib.dump({"model": model, "features": FEATURE_NAMES}, MODEL_PATH)
    (DATA_DIR / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
