FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

# Tourne en root volontairement : accès au socket Docker pour la reprise.
# C'est le seul service dans ce cas, et son endpoint est protégé par jeton.
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8200"]
