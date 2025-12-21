import aiohttp
import asyncio
import json
import os

POKEAPI_URL = "https://pokeapi.co/api/v2"
REFERENCE_FILE = "modules/pokemon_modules/pokemon_name.json" 

class PokeApiService:
    def __init__(self):
        self.session = None
        self.pokemon_map = {} 
        self.load_reference()

    def load_reference(self):
        if os.path.exists(REFERENCE_FILE):
            try:
                with open(REFERENCE_FILE, "r", encoding="utf-8") as f:
                    self.pokemon_map = json.load(f)
                print(f"[PokeAPI] Loaded {len(self.pokemon_map)} pokemon from reference.")
            except Exception as e:
                print(f"[PokeAPI] Error loading reference file: {e}")
        else:
            print("[PokeAPI] Reference file not found.")

    async def get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    def slugify(self, name: str) -> str:
        original = name
        name = name.lower().strip()
        name = name.replace(" ", "-").replace(".", "").replace(":", "").replace("'", "")
        
        if "megazard" in name: return "charizard" 
        if "basculin-blue-striped" in name: return "basculin-blue-striped"
        
        if "ogerpon" in name and "mask" not in name:
            if name not in self.pokemon_map:
                name += "-mask"
        
        # [LOG] In ra sự thay đổi tên
        if original != name:
            print(f"[DEBUG-API] Slugify: '{original}' -> '{name}'")
        return name

    def get_api_url(self, slug_name: str) -> str:
        if slug_name in self.pokemon_map:
            p_id = self.pokemon_map[slug_name]
            return f"{POKEAPI_URL}/pokemon/{p_id}"
        
        for name, p_id in self.pokemon_map.items():
            if name.startswith(slug_name):
                print(f"[DEBUG-API] Fuzzy Match: '{slug_name}' matches '{name}' -> ID: {p_id}")
                return f"{POKEAPI_URL}/pokemon/{p_id}"

        return f"{POKEAPI_URL}/pokemon/{slug_name}"

    async def get_sprite(self, pokemon_name: str) -> str:
        slug = self.slugify(pokemon_name)
        url = self.get_api_url(slug) 
        session = await self.get_session()
        try:
            async with session.get(url) as resp:
                if resp.status != 200: return None
                data = await resp.json()
                sprites = data.get("sprites", {})
                return (sprites.get("other", {}).get("official-artwork", {}).get("front_default") or 
                        sprites.get("other", {}).get("home", {}).get("front_default") or
                        sprites.get("front_default"))
        except:
            return None

    async def get_sprites_batch(self, names: list):
        tasks = [self.get_sprite(name) for name in names]
        return await asyncio.gather(*tasks)

    async def get_pokemon_static_data(self, name: str):
        # [LOG]
        print(f"[DEBUG-API] get_pokemon_static_data CALLED for: '{name}'")
        slug = self.slugify(name)
        url = self.get_api_url(slug) 
        
        print(f"[DEBUG-API] Fetching URL: {url}")
        session = await self.get_session()
        
        try:
            async with session.get(url) as resp:
                print(f"[DEBUG-API] Response Code: {resp.status}")
                if resp.status != 200: 
                    print(f"[DEBUG-API] FAILED to get data for {slug}")
                    return None
                p_data = await resp.json()

            # Lấy thông tin Species (Mô tả, Loại)
            s_data = {}
            if p_data.get("species", {}).get("url"):
                async with session.get(p_data["species"]["url"]) as resp:
                    if resp.status == 200:
                        s_data = await resp.json()

            sprites = p_data.get("sprites", {})
            image_url = (sprites.get("other", {}).get("official-artwork", {}).get("front_default") or 
                         sprites.get("other", {}).get("home", {}).get("front_default") or
                         sprites.get("front_default"))

            # --- [FIX QUAN TRỌNG] Lấy Description an toàn ---
            desc = "No description."
            for entry in s_data.get("flavor_text_entries", []):
                if entry.get("language", {}).get("name") == "en":
                    desc = entry.get("flavor_text", "").replace("\n", " ").replace("\f", " ")
                    break
            
            # --- [FIX QUAN TRỌNG] Lấy Genus (Loài) an toàn ---
            # Thay vì gọi [7], ta lặp qua để tìm tiếng Anh
            species_text = "Pokémon"
            for genus_entry in s_data.get("genera", []):
                if genus_entry.get("language", {}).get("name") == "en":
                    species_text = genus_entry.get("genus", "Pokémon")
                    break

            print(f"[DEBUG-API] SUCCESS parsing data for {slug}")
            
            return {
                "id": p_data["id"],
                "name": p_data["name"],
                "types": [t["type"]["name"] for t in p_data["types"]],
                "height": p_data["height"] / 10,
                "weight": p_data["weight"] / 10,
                "stats": {s["stat"]["name"]: s["base_stat"] for s in p_data["stats"]},
                "species": species_text, # Đã sửa biến này
                "description": desc,
                "image_url": image_url
            }
        except Exception as e:
            print(f"[DEBUG-API-ERROR] {e}")
            import traceback
            traceback.print_exc()
            return None
        
    async def get_move_details(self, move_name: str):
        slug = self.slugify(move_name)
        session = await self.get_session()
        async with session.get(f"{POKEAPI_URL}/move/{slug}") as resp:
            if resp.status != 200: return None
            data = await resp.json()
        return {"type": data["type"]["name"], "category": data["damage_class"]["name"]}