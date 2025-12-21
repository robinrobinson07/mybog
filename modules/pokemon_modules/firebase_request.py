import requests
import statistics
from functools import lru_cache

FIREBASE_URL = "https://vo-robin-default-rtdb.asia-southeast1.firebasedatabase.app/pokemondata"

class PokemonService:
    def __init__(self):
        self.session = requests.Session()

    @lru_cache(maxsize=32)
    def get_formats(self, gen: str) -> list[str]:
        """Lấy danh sách format của một Gen (dùng shallow=true để chỉ lấy key)"""
        url = f"{FIREBASE_URL}/{gen}.json?shallow=true"
        try:
            r = self.session.get(url, timeout=5)
            if r.status_code == 200 and r.json():
                return list(r.json().keys())
            return []
        except Exception:
            return []

    @lru_cache(maxsize=64)
    def get_ratings(self, gen: str, fmt: str) -> list[str]:
        """Lấy danh sách rating của Format"""
        url = f"{FIREBASE_URL}/{gen}/{fmt}.json?shallow=true"
        try:
            r = self.session.get(url, timeout=5)
            if r.status_code == 200 and r.json():
                ratings = list(r.json().keys())
                # Sort số (0, 1500, 1695) cho đẹp
                try:
                    ratings.sort(key=int)
                except:
                    pass
                return ratings
            return []
        except Exception:
            return []

    @lru_cache(maxsize=128)
    def get_pokemons(self, gen: str, fmt: str, rating: str) -> list[str]:
        """Lấy danh sách Pokemon. Nếu rating='all', lấy list của rating đầu tiên tìm thấy"""
        target_rating = rating
        if rating == "all":
            # Nếu all, lấy rating thấp nhất (thường là '0' hoặc '1500') để có list pokemon đầy đủ nhất
            avail_ratings = self.get_ratings(gen, fmt)
            if avail_ratings:
                target_rating = avail_ratings[0]
            else:
                return []
        
        url = f"{FIREBASE_URL}/{gen}/{fmt}/{target_rating}.json?shallow=true"
        try:
            r = self.session.get(url, timeout=5)
            if r.status_code == 200 and r.json():
                return sorted(list(r.json().keys()))
            return []
        except Exception:
            return []

    def get_pokemon_data(self, gen: str, fmt: str, rating: str, pokemon: str):
        """Lấy dữ liệu chi tiết. Xử lý logic gộp nếu rating='all'"""
        if rating != "all":
            url = f"{FIREBASE_URL}/{gen}/{fmt}/{rating}/{pokemon}.json"
            r = self.session.get(url, timeout=10)
            if r.status_code == 200:
                return r.json()
            return None
        else:
            return self._get_avg_data(gen, fmt, pokemon)

    def _get_avg_data(self, gen: str, fmt: str, pokemon: str):
        """Logic tính trung bình cộng cho rating 'all'"""
        ratings = self.get_ratings(gen, fmt)
        if not ratings:
            return None

        # Container để cộng dồn dữ liệu
        # Cấu trúc: { 'sections': { 'Moves': {'Earthquake': [80.5, 90.0]} } }
        aggregated = {"sections": {}} 
        valid_count = 0

        for rt in ratings:
            url = f"{FIREBASE_URL}/{gen}/{fmt}/{rt}/{pokemon}.json"
            try:
                r = self.session.get(url, timeout=5)
                data = r.json()
                if not data or "sections" not in data:
                    continue
                
                valid_count += 1
                sections = data["sections"]
                
                for sec_name, items in sections.items():
                    if sec_name not in aggregated["sections"]:
                        aggregated["sections"][sec_name] = {}
                    
                    # Items là list các dict: [{"name": "A", "pct": 50}, ...]
                    for item in items:
                        # Checks and Counters cấu trúc khác, tạm thời bỏ qua hoặc lấy của rating cao nhất
                        # Ở đây xử lý các mục có 'pct' (Abilities, Moves, etc.)
                        if "pct" in item:
                            name = item.get("name")
                            pct = item.get("pct", 0)
                            if name not in aggregated["sections"][sec_name]:
                                aggregated["sections"][sec_name][name] = []
                            aggregated["sections"][sec_name][name].append(pct)
                        elif "opponent" in item: 
                            # Xử lý Checks and Counters: Chỉ gộp, không tính avg vì nó phức tạp
                            if sec_name not in aggregated["sections"]:
                                aggregated["sections"][sec_name] = []
                            # Logic checks counters cho 'all' rất phức tạp, 
                            # ở đây ta chỉ lấy list của rating cao nhất (thường là chuẩn nhất)
                            # Nên tạm thời bỏ qua loop này cho C&C
                            pass
            except:
                continue

        if valid_count == 0:
            return None

        # Tính trung bình và format lại về chuẩn cũ
        final_data = {"sections": {}, "name": pokemon, "info": "Average Stats (All Ratings)"}
        
        for sec_name, items_dict in aggregated["sections"].items():
            final_data["sections"][sec_name] = []
            if isinstance(items_dict, dict): # Xử lý Moves, Abilities...
                for name, pct_list in items_dict.items():
                    avg_pct = sum(pct_list) / len(ratings) # Chia cho tổng số rating tham gia
                    final_data["sections"][sec_name].append({
                        "name": name,
                        "pct": avg_pct
                    })
                # Sort lại theo phần trăm giảm dần
                final_data["sections"][sec_name].sort(key=lambda x: x["pct"], reverse=True)
            
        # Với Checks and Counters, lấy dữ liệu từ rating cao nhất (thường là chuẩn meta nhất)
        if ratings:
            best_rating = ratings[-1]
            url = f"{FIREBASE_URL}/{gen}/{fmt}/{best_rating}/{pokemon}/sections/Checks and Counters.json"
            try:
                r = self.session.get(url)
                if r.status_code == 200:
                    final_data["sections"]["Checks and Counters"] = r.json()
            except:
                pass

        return final_data