import aiohttp
import asyncio
import json
import os

POKEAPI_URL = "https://pokeapi.co/api/v2"
# Lưu ý: Đảm bảo đường dẫn này đúng với cấu trúc thư mục của bạn
REFERENCE_FILE = "modules/pokemon_modules/pokemon_name.json" 

class PokeApiService:
    def __init__(self):
        self.session = None
        self.pokemon_map = {} 
        self.load_reference()

    def load_reference(self):
        """Load danh sách tên -> ID từ file json"""
        if os.path.exists(REFERENCE_FILE):
            try:
                with open(REFERENCE_FILE, "r", encoding="utf-8") as f:
                    self.pokemon_map = json.load(f)
                print(f"[PokeAPI] Loaded {len(self.pokemon_map)} pokemon from reference.")
            except Exception as e:
                print(f"[PokeAPI] Error loading reference file: {e}")
        else:
            print("[PokeAPI] Reference file not found. Please run 'reference.py'.")

    async def get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    def slugify(self, name: str) -> str:
        """Chuẩn hóa tên Pokemon để tra cứu"""
        name = name.lower().strip()
        # Thay khoảng trắng bằng gạch ngang, bỏ ký tự đặc biệt
        name = name.replace(" ", "-").replace(".", "").replace(":", "").replace("'", "")
        
        # Fix cứng một số trường hợp đặc biệt của Smogon
        if "megazard" in name: return "charizard" 
        if "basculin-blue-striped" in name: return "basculin-blue-striped"
        
        # Ogerpon: Nếu thiếu mask thì tự động thêm (trừ khi tên đó đã có trong map)
        if "ogerpon" in name and "mask" not in name:
            if name not in self.pokemon_map:
                name += "-mask"
                
        return name

    def get_api_url(self, slug_name: str) -> str:
        """
        Lấy URL API thông minh:
        1. Tìm chính xác (Exact match).
        2. Nếu không thấy, tìm key bắt đầu bằng tên này (StartsWith).
        3. Fallback gọi bằng tên gốc.
        """
        # 1. Ưu tiên tìm chính xác
        if slug_name in self.pokemon_map:
            p_id = self.pokemon_map[slug_name]
            return f"{POKEAPI_URL}/pokemon/{p_id}"
        
        # 2. Cơ chế chống Ditto (StartsWith)
        # Ví dụ: Tìm "enamorus" không thấy -> Tìm thấy "enamorus-therian" -> Lấy ID 10249
        for name, p_id in self.pokemon_map.items():
            # Kiểm tra nếu key trong json bắt đầu bằng slug_name (kèm dấu gạch ngang để tránh nhầm)
            # vd: "urshifu-rapid..." startswith "urshifu" -> OK
            if name.startswith(slug_name):
                return f"{POKEAPI_URL}/pokemon/{p_id}"

        # 3. Fallback: Gọi bằng tên (Hy vọng API tự redirect hoặc user nhập đúng ID)
        return f"{POKEAPI_URL}/pokemon/{slug_name}"

    async def get_sprite(self, pokemon_name: str) -> str:
        slug = self.slugify(pokemon_name)
        url = self.get_api_url(slug) # Sử dụng hàm get URL thông minh mới
        
        session = await self.get_session()
        try:
            async with session.get(url) as resp:
                if resp.status != 200: return None
                data = await resp.json()
                sprites = data.get("sprites", {})
                # Ưu tiên: Official Art -> Home -> Default
                return (sprites.get("other", {}).get("official-artwork", {}).get("front_default") or 
                        sprites.get("other", {}).get("home", {}).get("front_default") or
                        sprites.get("front_default"))
        except:
            return None

    async def get_sprites_batch(self, names: list):
        tasks = [self.get_sprite(name) for name in names]
        return await asyncio.gather(*tasks)

    async def get_pokemon_static_data(self, name: str):
        slug = self.slugify(name)
        url = self.get_api_url(slug) 
        
        session = await self.get_session()
        
        async with session.get(url) as resp:
            if resp.status != 200: return None
            p_data = await resp.json()

        # Lấy thông tin loài để lấy mô tả
        async with session.get(p_data["species"]["url"]) as resp:
            s_data = await resp.json() if resp.status == 200 else {}

        sprites = p_data.get("sprites", {})
        image_url = (sprites.get("other", {}).get("official-artwork", {}).get("front_default") or 
                     sprites.get("other", {}).get("home", {}).get("front_default") or
                     sprites.get("front_default"))

        desc = "No description."
        for entry in s_data.get("flavor_text_entries", []):
            if entry["language"]["name"] == "en":
                desc = entry["flavor_text"].replace("\n", " ").replace("\f", " ")
                break

        return {
            "id": p_data["id"],
            "name": p_data["name"],
            "types": [t["type"]["name"] for t in p_data["types"]],
            "height": p_data["height"] / 10,
            "weight": p_data["weight"] / 10,
            "stats": {s["stat"]["name"]: s["base_stat"] for s in p_data["stats"]},
            "species": s_data.get("genera", [{}])[7].get("genus", "Pokémon") if s_data.get("genera") else "Pokémon",
            "description": desc,
            "image_url": image_url
        }

    async def get_move_details(self, move_name: str):
        slug = self.slugify(move_name)
        session = await self.get_session()
        async with session.get(f"{POKEAPI_URL}/move/{slug}") as resp:
            if resp.status != 200: return None
            data = await resp.json()
        return {"type": data["type"]["name"], "category": data["damage_class"]["name"]}