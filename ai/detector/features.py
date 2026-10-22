"""Ce que le modèle observe.

Chaque feature est une requête PromQL (Prometheus) ou LogQL (Loki) qui
renvoie UN nombre. C'est le seul fichier à adapter quand les pôles Dev et
Infra fixent les noms réels des métriques et des labels.
"""
import json
import math
import time
from datetime import datetime, timezone
from urllib.parse import unquote

import httpx

from config import API_HEALTH_URL, LOKI_URL, PROMETHEUS_URL

# nom de la feature -> (source, requête)
FEATURES = {
    "req_rate": ("prometheus", 'sum(rate(http_requests_total[30s]))'),
    "err_4xx_rate": ("prometheus", 'sum(rate(http_requests_total{status=~"4.."}[30s]))'),
    "err_5xx_rate": ("prometheus", 'sum(rate(http_requests_total{status=~"5.."}[30s]))'),
    # latency_p95 retirée : sur un PC Hôte saturé (toute la stack + Ollama), la
    # latence au repos (~0,2 s) dépasse de loin celle de l'entraînement et
    # provoque des faux positifs. À réactiver sur une machine moins chargée :
    # "latency_p95": ("prometheus", 'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[30s])))'),
    # CPU de l'API : on lit process_cpu_seconds_total{job="api"}, exposé par
    # l'API elle-même (prometheus_client), plutôt que cAdvisor dont le label
    # `name` est absent sur Docker Desktop/WSL2.
    "api_cpu": ("prometheus", 'sum(rate(process_cpu_seconds_total{job="api"}[30s]))'),
    # waf_blocks RÉACTIVÉE. Elle avait été retirée car le filtre `|= "403"` attrapait
    # toute ligne contenant « 403 » (403 applicatifs d'auth inclus) : non nulle en temps
    # normal, elle cassait l'hypothèse « 0 en temps normal » du modèle. Le WAF émet
    # maintenant un marqueur de log DISTINCT à chaque blocage (`log_append waf_event
    # "WAF_BLOCK …"` dans cyber/waf/Caddyfile) : on compte ce marqueur, jamais présent
    # dans le trafic normal. La condition posée lors du retrait est donc remplie.
    "waf_blocks": ("loki", 'sum(count_over_time({container="waf"} |= "WAF_BLOCK" [30s]))'),
}
FEATURE_NAMES = list(FEATURES)

API_URL = {
    "prometheus": f"{PROMETHEUS_URL}/api/v1/query",
    "loki": f"{LOKI_URL}/loki/api/v1/query",
}


def _query(source: str, query: str) -> list:
    response = httpx.get(API_URL[source], params={"query": query}, timeout=5)
    response.raise_for_status()
    return response.json()["data"]["result"]


def fetch_now() -> dict[str, float]:
    """Valeur actuelle de chaque feature.

    Un résultat vide (ex : aucune erreur 5xx) ou NaN (ex : latence sans trafic) vaut 0.
    """
    values = {}
    for name, (source, query) in FEATURES.items():
        result = _query(source, query)
        value = float(result[0]["value"][1]) if result else 0.0
        values[name] = 0.0 if math.isnan(value) else value
    return values


def api_healthy() -> bool:
    """Contrôle de santé actif : l'API répond-elle 200 sur /healthz ?

    Indépendant du ML et du trafic : une API tombée est vue même si personne ne
    l'appelle. Injoignable ou code != 200 (ex : 503) -> non saine.
    """
    try:
        return httpx.get(API_HEALTH_URL, timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


def recent_waf_blocks(limit: int = 15, minutes: int = 10) -> list[dict]:
    """Dernières requêtes bloquées par le WAF, lues dans les logs (Loki).

    Lecture seule, pour affichage : on extrait de chaque blocage le type (injection,
    scanner…), l'URL tentée, l'IP source, l'heure. Renvoie [] si Loki ne répond pas
    ou si rien n'a été bloqué.
    """
    end = int(time.time() * 1e9)
    start = end - minutes * 60 * 10**9
    try:
        response = httpx.get(
            f"{LOKI_URL}/loki/api/v1/query_range",
            params={"query": '{container="waf"} |= "WAF_BLOCK"', "start": start,
                    "end": end, "limit": limit, "direction": "backward"},
            timeout=5,
        )
        response.raise_for_status()
        streams = response.json()["data"]["result"]
    except (httpx.HTTPError, KeyError):
        return []

    blocks = []
    for stream in streams:
        for timestamp, line in stream["values"]:
            try:
                log = json.loads(line)
            except json.JSONDecodeError:
                continue
            request = log.get("request", {})
            blocks.append({
                # waf_event = « WAF_BLOCK injection » : on garde le mot après WAF_BLOCK (le type).
                "type": log.get("waf_event", "WAF_BLOCK").replace("WAF_BLOCK", "").strip() or "bloqué",
                "uri": unquote(request.get("uri", "")),  # dé-encode %20, %3C… pour la lisibilité
                "client_ip": request.get("client_ip", request.get("remote_ip", "?")),
                "method": request.get("method", ""),
                "at": datetime.fromtimestamp(int(timestamp) / 1e9, tz=timezone.utc).isoformat(),
            })
    # Loki renvoie par stream : on retrie par heure décroissante et on limite.
    blocks.sort(key=lambda b: b["at"], reverse=True)
    return blocks[:limit]
