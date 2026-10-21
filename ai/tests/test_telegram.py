"""Tests de l'alerte Telegram, sans réseau (httpx.post remplacé)."""
import pytest

from detector import telegram


def test_message_anomaly_contient_score_et_features():
    msg = telegram._format("anomaly", 36.7, [{"name": "err_5xx_rate", "value": 20.0, "zscore": 9.1}])
    assert "Anomalie détectée" in msg
    assert "36.7" in msg
    assert "err_5xx_rate" in msg


def test_message_recovered():
    assert "Retour à la normale" in telegram._format("recovered", None, [])


def test_send_alert_ne_fait_rien_sans_config(monkeypatch):
    # Sans token/chat_id, aucun appel réseau ne doit partir.
    appels = []
    monkeypatch.setattr(telegram, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(telegram, "TELEGRAM_CHAT_ID", "")
    monkeypatch.setattr(telegram.httpx, "post", lambda *a, **k: appels.append(1))
    telegram.send_alert("anomaly", 10.0, [])
    assert appels == []


def test_send_alert_poste_quand_configure(monkeypatch):
    envois = []

    class FakeResponse:
        def raise_for_status(self):
            pass

    def fake_post(url, json, timeout):
        envois.append((url, json))
        return FakeResponse()

    monkeypatch.setattr(telegram, "TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setattr(telegram, "TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(telegram.httpx, "post", fake_post)
    telegram.send_alert("anomaly", 10.0, [{"name": "req_rate", "value": 5.0, "zscore": 3.0}])

    assert len(envois) == 1
    url, body = envois[0]
    assert "123:ABC" in url  # le token est dans l'URL de l'API Telegram
    assert body["chat_id"] == "42"
    assert "req_rate" in body["text"]


def test_send_alert_silencieux_si_reseau_echoue(monkeypatch):
    def boom(url, json, timeout):
        raise telegram.httpx.ConnectError("injoignable")

    monkeypatch.setattr(telegram, "TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setattr(telegram, "TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(telegram.httpx, "post", boom)
    telegram.send_alert("anomaly", 10.0, [])  # ne doit pas lever d'exception
