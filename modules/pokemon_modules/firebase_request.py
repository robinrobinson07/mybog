import requests
import asyncio
import concurrent.futures
from functools import partial
import re
from urllib.parse import quote  # <--- THÊM DÒNG NÀY

FIREBASE_URL = "https://vo-robin-default-rtdb.asia-southeast1.firebasedatabase.app/pokemondata"

class PokemonService:
    def __init__(self):
        self.cache = {}
        self.is_ready = False
        self.session = requests.Session()
        self.main_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

    def _fetch_sync(self, url):
        try:
            # quote() giúp xử lý các ký tự đặc biệt trong URL
            r = self.session.get(url, timeout=5)
            if r.status_code == 200:
                return r.json()
            return None
        except Exception:
            return None

    def _build_cache_sync(self):
        print("[CACHE] Starting data fetch (Parallel Requests)...")
        all_formats = self._fetch_sync(f"{FIREBASE_URL}.json?shallow=true")
        if not all_formats: return

        temp_cache = {}
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
        print(f"[CACHE] Complete.")

    async def build_cache(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self.main_executor, self._build_cache_sync)

    def get_gens_cached(self) -> list[str]: return list(self.cache.keys())
    def get_formats_cached(self, gen: str) -> list[str]: return list(self.cache[gen].keys()) if gen in self.cache else []
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
                ratings = self.get_ratings_cached(gen, fmt)
                if ratings: return self.cache[gen][fmt].get(ratings[-1], [])
            else:
                return self.cache[gen][fmt].get(rating, [])
        return []

    # --- LOGIC TÍNH TRUNG BÌNH TOÀN BỘ (SỬA URL ENCODE) ---
    def _fetch_average_data_sync(self, gen, fmt, pokemon):
        ratings = self.get_ratings_cached(gen, fmt)
        if not ratings: return None
        full_fmt = f"{gen}{fmt}"
        
        safe_pokemon = quote(pokemon)

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self._fetch_sync, f"{FIREBASE_URL}/{full_fmt}/{r}/{safe_pokemon}.json") for r in ratings]
            for future in concurrent.futures.as_completed(futures):
                data = future.result()
                if data: results.append(data)

        if not results: return None

        total_raw_count = sum(d.get("raw_count", 0) for d in results)
        if total_raw_count == 0: total_raw_count = 1

        agg_sections = {
            "Moves": {}, "Abilities": {}, "Items": {}, 
            "Spreads": {}, "Tera Types": {}, "Teammates": {}
        }
        agg_counters = {} 

        for data in results:
            weight = data.get("raw_count", 0)
            sections = data.get("sections", {})
            
            for sec_name in agg_sections.keys():
                items = sections.get(sec_name, [])
                for item in items:
                    name = item.get("name")
                    pct = item.get("pct", 0)
                    if name:
                        if name not in agg_sections[sec_name]: agg_sections[sec_name][name] = 0.0
                        agg_sections[sec_name][name] += (pct * weight)

            counters = sections.get("Checks and Counters", [])
            for c in counters:
                opp = c.get("opponent") or c.get("name")
                if not opp: continue
                
                raw = c.get("raw", "")
                score = 0
                match = re.search(r"([\d\.]+)", raw) 
                if match: score = float(match.group(1))
                
                if opp not in agg_counters:
                    agg_counters[opp] = {"weighted_score": 0.0, "detail": c.get("detail", ""), "max_weight": 0}
                
                agg_counters[opp]["weighted_score"] += (score * weight)
                
                if weight > agg_counters[opp]["max_weight"]:
                    agg_counters[opp]["detail"] = c.get("detail", "")
                    agg_counters[opp]["max_weight"] = weight

        final_sections = {}
        for sec_name, name_map in agg_sections.items():
            final_list = [{"name": name, "pct": val / total_raw_count} for name, val in name_map.items()]
            final_list.sort(key=lambda x: x["pct"], reverse=True)
            final_sections[sec_name] = final_list

        final_counters = []
        for opp, val in agg_counters.items():
            avg_score = val["weighted_score"] / total_raw_count
            final_counters.append({
                "opponent": opp,
                "pct": avg_score,
                "detail": val["detail"]
            })
        
        final_counters.sort(key=lambda x: x["pct"], reverse=True)
        final_sections["Checks and Counters"] = final_counters

        return {
            "name": pokemon,
            "raw_count": total_raw_count,
            "info": f"Weighted average from {len(results)} ratings ({', '.join(ratings)})",
            "sections": final_sections
        }

    async def get_pokemon_data_async(self, gen: str, fmt: str, rating: str, pokemon: str):
        full_fmt = f"{gen}{fmt}"
        if rating == "all":
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self.main_executor, partial(self._fetch_average_data_sync, gen, fmt, pokemon))
        safe_pokemon = quote(pokemon)
        url = f"{FIREBASE_URL}/{full_fmt}/{rating}/{safe_pokemon}.json"
        
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.main_executor, partial(self._fetch_sync, url))
