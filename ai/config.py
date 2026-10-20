"""Configuration de la partie IA.

Tout se règle par variables d'environnement ; les valeurs par défaut
correspondent aux noms de services du docker-compose.
"""
import os
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"

# --- Supervision (sources des données du détecteur) ---
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")

# Contrôle de santé actif : le détecteur sonde directement l'API métier.
# Permet de voir une API tombée même sans trafic, et de ne déclarer la reprise
# que si l'API répond vraiment (« un conteneur qui redémarre n'est pas une preuve »).
API_HEALTH_URL = os.getenv("API_HEALTH_URL", "http://api:8000/healthz")

# --- Détecteur d'anomalies ---
MODEL_PATH = DATA_DIR / "model.joblib"
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "5"))            # un point de mesure toutes les 5 s
CONSECUTIVE_POINTS = int(os.getenv("CONSECUTIVE_POINTS", "3"))  # points anormaux d'affilée avant d'alerter
CONTAMINATION = float(os.getenv("CONTAMINATION", "0.01"))       # part de points atypiques tolérée dans le trafic normal

# --- Moteur de remédiation (pôle Dev) : prévenu par webhook ---
REMEDIATION_URL = os.getenv("REMEDIATION_URL", "")  # vide = pas de webhook (le détecteur ne fait que journaliser)
REMEDIATION_TOKEN = os.getenv("REMEDIATION_TOKEN", "")

# --- Assistant RAG ---
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")  # 8B paramètres maximum (sujet §3.3)
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
DETECTOR_URL = os.getenv("DETECTOR_URL", "http://detector:8000")
TOP_K = int(os.getenv("TOP_K", "5"))  # nombre de passages de documentation envoyés au LLM

# --- Dashboard ---
# Origines autorisées pour les appels du dashboard (CORS), au lieu de tout ouvrir.
DASHBOARD_ORIGINS = os.getenv("DASHBOARD_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
