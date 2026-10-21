"""Alerte Telegram quand le détecteur passe en anomalie ou revient à la normale.

Notification pour un humain, EN PLUS de la remédiation automatique (qui, elle,
redémarre l'API). Le détecteur n'agit pas : il envoie juste un message.

Token et chat_id viennent du .env (jamais du code). S'ils sont absents, la
fonction ne fait rien : l'alerte est optionnelle, le reste du détecteur tourne
normalement.
"""
import httpx

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def _format(event: str, score: float | None, top_features: list[dict]) -> str:
    """Message lisible sur téléphone. HTML simple accepté par l'API Telegram."""
    if event == "anomaly":
        lignes = [
            "\U0001F6A8 <b>Anomalie détectée</b> — RESILIENCE-ALPHA",
            f"Score : <b>{score}</b> (seuil d'alerte : 0)",
        ]
        # Les features les plus éloignées de la normale : le « pourquoi » de l'alerte.
        for feature in top_features[:3]:
            lignes.append(f"• {feature['name']} = {feature['value']} (z={feature['zscore']})")
        lignes.append("La remédiation automatique a été déclenchée.")
        return "\n".join(lignes)
    return "✅ <b>Retour à la normale</b> — RESILIENCE-ALPHA\nLe service est rétabli."


def send_alert(event: str, score: float | None, top_features: list[dict]) -> None:
    """Envoie l'alerte. Silencieux si Telegram n'est pas configuré ou en cas d'erreur réseau."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": _format(event, score, top_features), "parse_mode": "HTML"}
    try:
        httpx.post(url, json=payload, timeout=5).raise_for_status()
    except httpx.HTTPError as exc:
        # Une alerte qui échoue ne doit pas interrompre la détection.
        print(f"[detector] alerte Telegram en échec : {exc}", flush=True)
