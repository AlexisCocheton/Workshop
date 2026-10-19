"""Simulateur de clients légitimes : génère du trafic NORMAL et réaliste.

Sert à collecter le trafic normal avant l'entraînement du détecteur, et à
animer la plateforme pendant la démo. Le trafic enchaîne des cycles :
calme -> montée en charge -> palier -> descente. Le modèle doit avoir vu
tous ces régimes : entraîné seulement sur un trafic stable, il prenait une
simple montée en charge pour une attaque (constaté en test).

Usage (depuis ai/, contre le WAF du groupe) :
    python traffic.py --target http://127.0.0.1:8080 --minutes 20
"""
import argparse
import os
import random
import time

import httpx

DEMO_USER = os.getenv("DEMO_USER", "app")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "app")


def send_one(client: httpx.Client, target: str, token: str):
    """Une action d'utilisateur : surtout des paiements et des consultations."""
    draw = random.random()
    if draw < 0.03:
        # Erreur client ordinaire (jeton expiré) : un peu de 4xx fait partie du normal.
        client.post(f"{target}/transactions", json={"amount": 10}, headers={"Authorization": "Bearer expire"})
    elif draw < 0.55:
        amount = round(random.uniform(5, 500), 2)
        client.post(f"{target}/transactions", json={"amount": amount}, headers={"Authorization": f"Bearer {token}"})
    else:
        client.get(f"{target}/transactions")


def run_phase(client, target, token, seconds, start_rate, end_rate, deadline):
    """Envoie des requêtes pendant `seconds`, le débit passant de start_rate à end_rate (req/s)."""
    start = time.time()
    end = min(start + seconds, deadline)
    while time.time() < end:
        progress = (time.time() - start) / seconds
        rate = start_rate + (end_rate - start_rate) * progress
        if rate < 0.1:
            time.sleep(1)  # phase calme : aucun client
            continue
        try:
            send_one(client, target, token)
        except httpx.HTTPError:
            pass
        time.sleep(1 / rate)


def main():
    parser = argparse.ArgumentParser(description="Trafic normal de clients fictifs")
    parser.add_argument("--target", default="http://127.0.0.1:8080", help="URL du WAF du groupe")
    parser.add_argument("--minutes", type=float, default=20)
    parser.add_argument("--max-rate", type=float, default=6, help="débit maximal d'un palier (req/s)")
    args = parser.parse_args()

    deadline = time.time() + args.minutes * 60
    with httpx.Client(timeout=5) as client:
        login = {"user": DEMO_USER, "password": DEMO_PASSWORD}
        token = client.post(f"{args.target}/auth/login", json=login).json()["token"]
        while time.time() < deadline:
            peak = random.uniform(1, args.max_rate)
            print(f"cycle : palier à {peak:.1f} req/s", flush=True)
            run_phase(client, args.target, token, random.uniform(20, 40), 0, 0, deadline)  # calme
            run_phase(client, args.target, token, random.uniform(20, 40), 0, peak, deadline)  # montée
            run_phase(client, args.target, token, random.uniform(30, 60), peak, peak, deadline)  # palier
            run_phase(client, args.target, token, random.uniform(15, 30), peak, 0, deadline)  # descente
    print("Terminé.")


if __name__ == "__main__":
    main()
