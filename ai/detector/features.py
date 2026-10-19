"""Ce que le modèle observe.

Chaque feature est une requête PromQL (Prometheus) ou LogQL (Loki) qui
renvoie UN nombre. C'est le seul fichier à adapter quand les pôles Dev et
Infra fixent les noms réels des métriques et des labels.
"""
import math

import httpx

from config import LOKI_URL, PROMETHEUS_URL

# nom de la feature -> (source, requête)
FEATURES = {
    "req_rate": ("prometheus", 'sum(rate(http_requests_total[30s]))'),
    "err_4xx_rate": ("prometheus", 'sum(rate(http_requests_total{status=~"4.."}[30s]))'),
    "err_5xx_rate": ("prometheus", 'sum(rate(http_requests_total{status=~"5.."}[30s]))'),
    "latency_p95": ("prometheus", 'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[30s])))'),
    # CPU de l'API : on lit process_cpu_seconds_total{job="api"}, exposé par
    # l'API elle-même (prometheus_client), plutôt que cAdvisor dont le label
    # `name` est absent sur Docker Desktop/WSL2.
    "api_cpu": ("prometheus", 'sum(rate(process_cpu_seconds_total{job="api"}[30s]))'),
    "waf_blocks": ("loki", 'sum(count_over_time({container="waf"} |= "403" [30s]))'),
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
