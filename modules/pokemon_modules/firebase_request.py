import requests
import asyncio
import concurrent.futures
from functools import partial
import re

FIREBASE_URL = "https://vo-robin-default-rtdb.asia-southeast1.firebasedatabase.app/pokemondata"

class PokemonService:
    def __init__(self):
        self.cache = {}
        self.is_ready = False
        self.session = requests.Session()
        # Executor chính cho các tác vụ nền
        self.main_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

    def _fetch_sync(self, url):
        """Hàm fetch cơ bản"""
        try:
            r = self.session.get(url, timeout=5)
            if r.status_code == 200:
                return r.json()
            return None
        except Exception:
            return None

    # --- PHẦN XỬ LÝ CACHE (Giữ nguyên logic song song tối ưu ở bước trước) ---
    def _build_cache_sync(self):
        print("[CACHE] Bắt đầu tải dữ liệu (Parallel Requests)...")
        all_formats = self._fetch_sync(f"{FIREBASE_URL}.json?shallow=true")
        if not all_formats: return

        temp_cache = {}
        # Dùng executor riêng để bắn request cache dồn dập
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as http_executor:
            future_to_fmt = {}
            for fmt_full in all_formats.keys():
                match = re.match(r"(gen[1-9])(.+)", fmt_full)
                if not match: continue
                gen_key, fmt_key = match.group(1), match.group(2)
                if fmt_key.startswith("-"): fmt_key = fmt_key[1:]

                if gen_key not in temp_cache: temp_cache[gen_key] = {}
                if fmt_key not in temp_cache[gen_key]: temp_cache[gen_key][fmt_key] = {}

                future = http_executor.submit(self._fetch_sync, f"{FIREBASE_URL}/{fmt_full}.json?shallow=true")
                future_to_fmt[future] = (gen_key, fmt_key, fmt_full)

            pokemon_tasks = {}
            for future in concurrent.futures.as_completed(future_to_fmt):
                gen, fmt, fmt_full = future_to_fmt[future]
                ratings = future.result()
                if ratings:
                    for rating in ratings:
                        p_future = http_executor.submit(self._fetch_sync, f"{FIREBASE_URL}/{fmt_full}/{rating}.json?shallow=true")
                        pokemon_tasks[p_future] = (gen, fmt, rating)

            for future in concurrent.futures.as_completed(pokemon_tasks):
                gen, fmt, rating = pokemon_tasks[future]
                p_data = future.result()
                if p_data:
                    temp_cache[gen][fmt][rating] = list(p_data.keys())

        self.cache = temp_cache
        self.is_ready = True
        print(f"[CACHE] Hoàn tất! Đã tải xong.")

    async def build_cache(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self.main_executor, self._build_cache_sync)

    # --- GETTERS ---
    def get_gens_cached(self) -> list[str]:
        return list(self.cache.keys())
    def get_formats_cached(self, gen: str) -> list[str]:
        if gen in self.cache: return list(self.cache[gen].keys())
        return []
    def get_ratings_cached(self, gen: str, fmt: str) -> list[str]:
        if gen in self.cache and fmt in self.cache[gen]:
            ratings = list(self.cache[gen][fmt].keys())
            try: ratings.sort(key=int)
            except: pass
            return ratings
        return []
    def get_pokemons_cached(self, gen: str, fmt: str, rating: str) -> list[str]:
        if gen in self.cache and fmt in self.cache[gen]:
            if rating == "all":
                # Lấy từ rating cao nhất làm danh sách gợi ý
                ratings = self.get_ratings_cached(gen, fmt)
                if ratings: return self.cache[gen][fmt].get(ratings[-1], [])
            else:
                return self.cache[gen][fmt].get(rating, [])
        return []

    # --- LOGIC MỚI: TÍNH TRUNG BÌNH KHI RATING="ALL" ---
    
    def _fetch_average_data_sync(self, gen, fmt, pokemon):
        """
        Hàm đồng bộ: Tải tất cả rating và tính trung bình.
        """
        ratings = self.get_ratings_cached(gen, fmt)
        if not ratings: return None

        full_fmt = f"{gen}{fmt}"
        
        # 1. Tải dữ liệu song song từ TẤT CẢ các rating
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for rating in ratings:
                url = f"{FIREBASE_URL}/{full_fmt}/{rating}/{pokemon}.json"
                futures.append(executor.submit(self._fetch_sync, url))
            
            for future in concurrent.futures.as_completed(futures):
                data = future.result()
                if data: results.append(data)

        if not results: return None

        # 2. Chuẩn bị biến chứa tổng
        # Cấu trúc: { "Moves": { "Earthquake": 180.5, ... } }
        agg_sections = {
            "Moves": {}, "Abilities": {}, "Items": {}, 
            "Spreads": {}, "Tera Types": {}, "Teammates": {}
        }
        total_raw_count = 0
        valid_count = len(results)
        
        # Dữ liệu của rating cao nhất (để dùng cho Checks & Counters hoặc fallback)
        highest_rating_data = results[-1] if results else None

        # 3. Cộng dồn dữ liệu
        for data in results:
            total_raw_count += data.get("raw_count", 0)
            sections = data.get("sections", {})
            
            for sec_name in agg_sections.keys():
                items = sections.get(sec_name, [])
                for item in items:
                    name = item.get("name")
                    pct = item.get("pct", 0)
                    if name:
                        if name not in agg_sections[sec_name]:
                            agg_sections[sec_name][name] = 0.0
                        agg_sections[sec_name][name] += pct

        # 4. Tính trung bình (Chia cho số lượng rating tham gia)
        final_sections = {}
        
        for sec_name, name_map in agg_sections.items():
            final_list = []
            for name, total_pct in name_map.items():
                avg_pct = total_pct / valid_count # Trung bình cộng
                final_list.append({"name": name, "pct": avg_pct})
            
            # Sắp xếp giảm dần theo %
            final_list.sort(key=lambda x: x["pct"], reverse=True)
            final_sections[sec_name] = final_list

        # 5. Xử lý riêng Checks & Counters
        # (Không thể tính trung bình text, nên lấy của rating cao nhất làm chuẩn)
        if highest_rating_data:
            final_sections["Checks and Counters"] = highest_rating_data.get("sections", {}).get("Checks and Counters", [])

        # 6. Trả về cấu trúc chuẩn như 1 pokemon thường
        return {
            "name": pokemon,
            "raw_count": total_raw_count, # Tổng số mẫu
            "info": f"Average stats from {valid_count} ratings ({', '.join(ratings)})",
            "sections": final_sections
        }

    async def get_pokemon_data_async(self, gen: str, fmt: str, rating: str, pokemon: str):
        full_fmt = f"{gen}{fmt}"
        
        # Nếu rating là "all", chạy logic tính trung bình
        if rating == "all":
            loop = asyncio.get_running_loop()
            # Gọi hàm _fetch_average_data_sync trong thread pool
            return await loop.run_in_executor(
                self.main_executor, 
                partial(self._fetch_average_data_sync, gen, fmt, pokemon)
            )

        # Nếu chọn rating cụ thể, chạy logic thường
        url = f"{FIREBASE_URL}/{full_fmt}/{rating}/{pokemon}.json"
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.main_executor, partial(self._fetch_sync, url))