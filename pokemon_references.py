import requests
import json
import os

# Cấu hình đường dẫn
OUTPUT_DIR = "pokemon_modules"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "pokemon_name.json")

# URL lấy toàn bộ danh sách (limit cao để lấy 1 lần cho nhanh)
POKEAPI_LIST_URL = "https://pokeapi.co/api/v2/pokemon?limit=100000&offset=0"

def create_reference_file():
    # 1. Tạo thư mục nếu chưa có
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"📁 Đã tạo thư mục {OUTPUT_DIR}")

    print("🔄 Đang tải danh sách toàn bộ Pokemon từ PokéAPI...")
    
    try:
        # 2. Gọi API
        response = requests.get(POKEAPI_LIST_URL, timeout=30)
        if response.status_code != 200:
            print(f"❌ Lỗi API: {response.status_code}")
            return

        data = response.json()
        results = data.get("results", [])
        
        # 3. Xử lý dữ liệu: Name -> ID
        pokemon_map = {}
        
        print(f"📥 Đã nhận {len(results)} pokemon. Đang xử lý...")

        for item in results:
            name = item['name']
            url = item['url']
            
            # URL có dạng: https://pokeapi.co/api/v2/pokemon/132/
            # Cắt chuỗi để lấy ID ở cuối
            try:
                # split('/') -> ['', 'api', 'v2', 'pokemon', '132', '']
                # Lấy phần tử kế cuối
                p_id = int(url.split('/')[-2])
                pokemon_map[name] = p_id
            except:
                continue

        # 4. Ghi ra file JSON
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(pokemon_map, f, indent=4)
            
        print(f"✅ THÀNH CÔNG! Đã lưu {len(pokemon_map)} pokemon vào '{OUTPUT_FILE}'")
        print("💡 Bây giờ bạn có thể dùng file này để lookup ID.")

    except Exception as e:
        print(f"❌ Có lỗi xảy ra: {e}")

if __name__ == "__main__":
    create_reference_file()