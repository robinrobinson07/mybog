import json
import time
import requests

FIREBASE_URL = "https://vo-robin-default-rtdb.asia-southeast1.firebasedatabase.app"
JSON_FILE = "pokemon_data.json"

TIMEOUT = 120     # tăng timeout
SLEEP = 0.5       # nghỉ giữa các request (tránh bị throttle)

def upload(path: str, data):
    url = f"{FIREBASE_URL}/{path}.json"
    r = requests.put(url, json=data, timeout=TIMEOUT)
    r.raise_for_status()
    print(f"[OK] uploaded {path}")

def main():
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # data = { format: { rating: [...] } }
    for fmt, ratings in data.items():
        for rating, pokemons in ratings.items():
            path = f"pokemondata/{fmt}/{rating}"
            upload(path, pokemons)
            time.sleep(SLEEP)

    print("\nDONE: all chunks uploaded successfully")

if __name__ == "__main__":
    main()
