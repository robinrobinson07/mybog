import json
import time
import requests

FIREBASE_URL = "https://vo-robin-default-rtdb.asia-southeast1.firebasedatabase.app"
JSON_FILE = "pokemon_data.json"

TIMEOUT = 120
SLEEP = 0.5 

def sanitize_key(key: str) -> str:
    """
    Firebase không cho phép các ký tự: . $ # [ ] / hoặc ký tự điều khiển ASCII 0-31 or 127.
    Trong Pokemon data, phổ biến nhất là dấu chấm (.) trong 'Mr. Mime', 'Mime Jr.'
    """
    # Thay thế dấu chấm bằng chuỗi rỗng (Mr. Mime -> Mr Mime) hoặc ký tự khác
    return key.replace(".", "").replace("#", "").replace("$", "").replace("[", "").replace("]", "").replace("/", "")

def upload(path: str, data):
    url = f"{FIREBASE_URL}/{path}.json"
    try:
        r = requests.put(url, json=data, timeout=TIMEOUT)
        r.raise_for_status()
        print(f"[OK] Uploaded success: {path}")
        return True
    except requests.RequestException as e:
        print(f"[ERR] Failed to upload {path}: {e}")
        return False

def main():
    print(f"Reading {JSON_FILE}...")
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            raw_file_content = json.load(f)
    except FileNotFoundError:
        print("Lỗi: Không tìm thấy file JSON.")
        return

    if "pokemon" not in raw_file_content:
        print("Lỗi cấu trúc: File JSON thiếu key gốc 'pokemon'.")
        return

    data = raw_file_content["pokemon"]
    print(f"Found {len(data)} formats. Starting upload...")

    for fmt, ratings in data.items():
        for rating, pokemons_dict in ratings.items():
            path = f"pokemondata/{fmt}/{rating}"
            
            # --- BƯỚC QUAN TRỌNG: LÀM SẠCH KEY TRƯỚC KHI UPLOAD ---
            clean_dict = {}
            for poke_name, poke_data in pokemons_dict.items():
                safe_name = sanitize_key(poke_name)
                
                # Cập nhật lại field "name" bên trong data luôn cho đồng bộ (nếu cần)
                if isinstance(poke_data, dict):
                    poke_data["name"] = safe_name 
                    
                clean_dict[safe_name] = poke_data
            # -------------------------------------------------------

            count = len(clean_dict)
            print(f" -> Uploading {fmt}/{rating} ({count} pokemons)...")
            
            # Thử upload cả cục (Batch)
            success = upload(path, clean_dict)
            
            # Nếu upload cả cục vẫn lỗi (ví dụ file quá nặng), chuyển sang upload từng con
            if not success:
                print(f"   ⚠️ Batch upload failed. Switching to item-by-item upload for {fmt}/{rating}...")
                for p_name, p_data in clean_dict.items():
                    sub_path = f"{path}/{p_name}"
                    upload(sub_path, p_data)
                    time.sleep(0.1) # Nghỉ cực ngắn để không spam

            time.sleep(SLEEP)

    print("\nDONE: All data processed.")

if __name__ == "__main__":
    main()