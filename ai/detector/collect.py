"""Enregistre les features en direct dans data/<label>.csv.

Usage :
    python -m detector.collect --label normal --minutes 20   # trafic habituel
    python -m detector.collect --label attack --minutes 5    # pendant l'attaque lancée du PC Attaquant

On collecte avec la même fonction que le service en production (fetch_now),
donc le modèle est entraîné exactement sur ce qu'il verra en direct.
Les lignes s'ajoutent au fichier existant : on peut collecter en plusieurs fois.
"""
import argparse
import csv
import time
from datetime import datetime, timezone

from config import DATA_DIR, POLL_SECONDS
from detector.features import FEATURE_NAMES, fetch_now


def main():
    parser = argparse.ArgumentParser(description="Collecte des features pour l'entraînement")
    parser.add_argument("--label", choices=["normal", "attack"], required=True)
    parser.add_argument("--minutes", type=float, required=True)
    args = parser.parse_args()

    path = DATA_DIR / f"{args.label}.csv"
    is_new_file = not path.exists()
    end = time.time() + args.minutes * 60

    with path.open("a", newline="") as file:
        writer = csv.writer(file)
        if is_new_file:
            writer.writerow(["timestamp", *FEATURE_NAMES, "label"])
        while time.time() < end:
            values = fetch_now()
            timestamp = datetime.now(timezone.utc).isoformat()
            writer.writerow([timestamp, *(values[name] for name in FEATURE_NAMES), args.label])
            file.flush()
            print(timestamp, values)
            time.sleep(POLL_SECONDS)

    print(f"Terminé : {path}")


if __name__ == "__main__":
    main()
