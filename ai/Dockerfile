# Une seule image pour les deux services IA : compose.yml choisit la commande.
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Durcissement : les services ne tournent pas en root.
RUN useradd --create-home app && mkdir -p data && chown -R app data
USER app
ENV PYTHONUNBUFFERED=1
