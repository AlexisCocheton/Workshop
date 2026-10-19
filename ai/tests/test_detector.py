"""Tests du détecteur sur des données synthétiques (aucun appel réseau)."""
import numpy as np
import pandas as pd

from detector import features
from detector.features import FEATURE_NAMES
from detector.service import Debouncer, explain, score
from detector.train import evaluate, train

NORMAL_POINT = {name: 10.0 for name in FEATURE_NAMES}


def normal_traffic(n=500, seed=0):
    rng = np.random.default_rng(seed)
    data = pd.DataFrame({name: rng.normal(10, 1, n) for name in FEATURE_NAMES})
    data["label"] = "normal"
    return data


def test_normal_point_is_not_anomalous():
    model = train(normal_traffic())
    assert score(model, NORMAL_POINT) < 0


def test_spike_is_anomalous_and_explained():
    model = train(normal_traffic())
    spike = NORMAL_POINT | {FEATURE_NAMES[0]: 50.0}
    assert score(model, spike) > 0
    assert explain(model, spike)[0]["name"] == FEATURE_NAMES[0]


def test_feature_constant_in_normal_traffic_is_still_watched():
    # Ex : jamais d'erreur 5xx en temps normal. C'est le cas qu'IsolationForest ratait.
    normal = normal_traffic()
    normal[FEATURE_NAMES[1]] = 0.0
    model = train(normal)
    assert score(model, NORMAL_POINT | {FEATURE_NAMES[1]: 5.0}) > 0


def test_evaluate_on_synthetic_attack():
    normal = normal_traffic()
    attack = normal_traffic(50, seed=1)
    attack[FEATURE_NAMES[0]] *= 10
    attack["label"] = "attack"

    report = evaluate(train(normal[:400]), normal[400:], attack)

    assert report["recall"] > 0.9
    assert report["false_positive_rate"] < 0.1


def test_debouncer_needs_n_consecutive_points():
    debouncer = Debouncer(3)
    assert [debouncer.update(True) for _ in range(3)] == [None, None, "anomaly"]
    assert debouncer.update(False) is None  # un seul point normal ne suffit pas
    assert debouncer.update(True) is None  # remet le compteur à zéro
    assert [debouncer.update(False) for _ in range(3)] == [None, None, "recovered"]


def test_fetch_now_turns_empty_and_nan_into_zero(monkeypatch):
    answers = iter([[], [{"value": [0, "NaN"]}]] + [[{"value": [0, "2.5"]}]] * len(FEATURE_NAMES))
    monkeypatch.setattr(features, "_query", lambda source, query: next(answers))

    values = features.fetch_now()

    assert values[FEATURE_NAMES[0]] == 0.0
    assert values[FEATURE_NAMES[1]] == 0.0
    assert values[FEATURE_NAMES[2]] == 2.5
