import json
import re
import requests
import disnake
from disnake.ext import commands
from typing import Any, Dict, List, Tuple

from .pokemon_embed import PokemonMovesetView, build_embed_stat, pick_pokemon

# ======= CONFIG: Firebase REST =======
FIREBASE_URL = "https://vo-robin-default-rtdb.asia-southeast1.firebasedatabase.app"
TIMEOUT = 10 
LOCAL_DATA_FALLBACK = "pokemon_data.json" 

MAX_CHOICES = 25
GEN_RE = re.compile(r"^(gen[1-9])(.+)$", re.I)


def _url(path: str) -> str:
    return f"{FIREBASE_URL.rstrip('/')}/{path.lstrip('/')}.json"


def _convert_rating_bucket(bucket: Any) -> List[Dict[str, Any]]:
    # ... (Giữ nguyên hàm này từ code gốc) ...
    if bucket is None:
        return []
    if isinstance(bucket, list):
        return bucket
    if isinstance(bucket, dict):
        try:
            keys = sorted(bucket.keys(), key=lambda k: int(k))
        except Exception:
            keys = list(bucket.keys())
        out = []
        for k in keys:
            v = bucket.get(k)
            if isinstance(v, dict):
                out.append(v)
            else:
                out.append(v)
        return out
    return []


def load_data_from_firebase_optimized() -> Dict[str, Any]:
    """
    Load toàn bộ data NHƯNG xóa sạch nội dung chi tiết (sections, stats...),
    chỉ giữ lại 'name' để làm Autocomplete cho nhẹ RAM.
    """
    try:
        r = requests.get(_url("pokemondata"), timeout=TIMEOUT)
        r.raise_for_status()
        fb = r.json()
        if not isinstance(fb, dict):
            fb = {}

        # --- ĐOẠN XỬ LÝ MỚI: STRIP DATA ---
        # Duyệt qua từng gen, từng format, từng rating
        for fmt_key, ratings in fb.items():
            if not isinstance(ratings, dict): continue
            
            for rating_key, rating_content in ratings.items():
                # Chuẩn hóa bucket thành list
                items = _convert_rating_bucket(rating_content)
                clean_items = []
                
                for item in items:
                    if isinstance(item, dict) and "name" in item:
                        # CHỈ GIỮ LẠI NAME, xóa hết phần nặng
                        clean_items.append({"name": item["name"]})
                
                # Gán ngược lại vào dict (bây giờ nó rất nhẹ)
                ratings[rating_key] = clean_items
        
        return fb
        
    except requests.RequestException:
        # Fallback giữ nguyên logic cũ
        try:
            with open(LOCAL_DATA_FALLBACK, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}


def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower().strip() if ch.isalnum())


def _filter_choices(options: List[str], user_input: str) -> List[str]:
    # ... (Giữ nguyên hàm này từ code gốc) ...
    if not options:
        return []
    q = (user_input or "").strip().lower()
    if not q:
        return options[:MAX_CHOICES]

    pref = [x for x in options if x.lower().startswith(q)]
    if len(pref) >= MAX_CHOICES:
        return pref[:MAX_CHOICES]

    sub = [x for x in options if q in x.lower() and x not in pref]
    out = pref + sub

    if len(out) < MAX_CHOICES:
        nq = _norm(q)
        more = [x for x in options if nq and nq in _norm(x) and x not in out]
        out.extend(more)

    return out[:MAX_CHOICES]


def split_gen_and_format(fmt_key: str) -> Tuple[str, str]:
    # ... (Giữ nguyên hàm này từ code gốc) ...
    m = GEN_RE.match(fmt_key)
    if not m:
        return "unknown", fmt_key
    return m.group(1).lower(), m.group(2).lower()


class PokemonMoveset(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # --- THAY ĐỔI: Dùng hàm load optimized ---
        # self.raw bây giờ chỉ chứa khung xương và tên pokemon (RAM thấp)
        self.raw: Dict[str, Any] = load_data_from_firebase_optimized()

        # --- LOGIC DƯỚI ĐÂY GIỮ NGUYÊN 100% ---
        # Vì cấu trúc self.raw vẫn y hệt json gốc (chỉ thiếu ruột bên trong),
        # nên code build index bên dưới hoạt động bình thường cho Autocomplete.
        self.index: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for fmt_key, bucket in self.raw.items():
            gen, fmt = split_gen_and_format(fmt_key)
            self.index.setdefault(gen, {})[fmt] = bucket

        self.gens: List[str] = sorted([g for g in self.index.keys() if g != "unknown"])
        if "unknown" in self.index:
            self.gens.append("unknown")

        self.formats_by_gen: Dict[str, List[str]] = {
            g: sorted(list(self.index[g].keys())) for g in self.index.keys()
        }

        self.ratings_by_gf: Dict[Tuple[str, str], List[str]] = {}
        for g, fmts in self.index.items():
            for fmt, bucket in fmts.items():
                ratings = list((bucket or {}).keys())
                ratings_sorted = sorted(ratings, key=lambda x: int(x) if x.isdigit() else 10**18)
                self.ratings_by_gf[(g, fmt)] = ["all"] + ratings_sorted

        self.pokemon_by_gfr: Dict[Tuple[str, str, str], List[str]] = {}
        for g, fmts in self.index.items():
            for fmt, bucket in fmts.items():
                for r, pokes in (bucket or {}).items():
                    # pokes ở đây là list rút gọn (chỉ có name)
                    names = [p.get("name", "") for p in (pokes or []) if isinstance(p, dict) and p.get("name")]
                    seen = set()
                    uniq = []
                    for nm in names:
                        if nm not in seen:
                            seen.add(nm)
                            uniq.append(nm)
                    self.pokemon_by_gfr[(g, fmt, r)] = uniq

                all_names = []
                seen = set()
                for r, pokes in (bucket or {}).items():
                    for p in (pokes or []):
                        nm = p.get("name") if isinstance(p, dict) else None
                        if nm and nm not in seen:
                            seen.add(nm)
                            all_names.append(nm)
                self.pokemon_by_gfr[(g, fmt, "all")] = all_names

    @commands.slash_command(
        name="moveset",
        description="Smogon moveset lookup (Optimized RAM)",
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def moveset(
        self,
        inter: disnake.ApplicationCommandInteraction,
        gen: str = commands.Param(name="gen", description="gen1..gen9"),
        format: str = commands.Param(name="format", description="ou/ubers/..."),
        rating: str = commands.Param(name="rating", description="0/1500/1630/1760 hoặc all"),
        pokemon: str = commands.Param(name="pokemon", description="Tên Pokémon"),
    ):
        await inter.response.defer()

        g = (gen or "").strip().lower()
        fmt = (format or "").strip().lower()
        rat = (rating or "").strip().lower()
        poke = (pokemon or "").strip()

        # Validation (Giữ nguyên)
        if g not in self.index:
            await inter.edit_original_message(embed=disnake.Embed(description="Gen không hợp lệ.", color=disnake.Color.red()))
            return

        if fmt not in self.index[g]:
            await inter.edit_original_message(embed=disnake.Embed(description="Format không hợp lệ.", color=disnake.Color.red()))
            return

        if rat != "all" and not rat.isdigit():
            await inter.edit_original_message(embed=disnake.Embed(description="Rating không hợp lệ.", color=disnake.Color.red()))
            return

        raw_fmt_key = f"{g}{fmt}"

        # === PHẦN THAY ĐỔI: FETCH REAL DATA ===
        # Lúc này self.raw chỉ có tên, không có stats. Ta phải tải data thật.
        # URL mục tiêu: /pokemondata/gen9ou/1760.json (nhẹ, nhanh)
        
        try:
            # Nếu user chọn 'all', ta phải tải cả cục format (nặng hơn chút) hoặc xử lý riêng.
            # Để đơn giản và tối ưu, ở đây ta request đúng path.
            if rat == "all":
                target_path = f"pokemondata/{raw_fmt_key}"
            else:
                target_path = f"pokemondata/{raw_fmt_key}/{rat}"

            fetched_r = requests.get(_url(target_path), timeout=5)
            fetched_r.raise_for_status()
            fetched_data = fetched_r.json()
            
            # Chuẩn hóa data vừa tải về
            if rat == "all":
                # Nếu tải 'all', data trả về là dict { "0": [...], "1500": [...] }
                # Cần convert các bucket con
                for k, v in fetched_data.items():
                    fetched_data[k] = _convert_rating_bucket(v)
            else:
                # Nếu tải rating lẻ, data trả về là bucket (dict hoặc list)
                # Cần đưa nó về dạng bucket chuẩn
                fetched_data = _convert_rating_bucket(fetched_data)

        except Exception as e:
            await inter.edit_original_message(embed=disnake.Embed(description=f"Lỗi tải dữ liệu chi tiết: {e}", color=disnake.Color.red()))
            return

        # === TẠO RA 'TEMP RAW' ĐỂ TÁI SỬ DỤNG HÀM CŨ ===
        # Hàm pick_pokemon và PokemonMovesetView cần cấu trúc full như self.raw cũ.
        # Ta tạo một dict giả lập chỉ chứa đúng phần data vừa tải về.
        
        temp_raw = {}
        if rat == "all":
             temp_raw = { raw_fmt_key: fetched_data }
        else:
             temp_raw = { raw_fmt_key: { rat: fetched_data } }

        # Gọi hàm pick_pokemon với dữ liệu vừa fetch (thay vì self.raw trống rỗng)
        p, err = pick_pokemon(temp_raw, raw_fmt_key, rat, poke)
        
        if err:
            await inter.edit_original_message(embed=disnake.Embed(description=err, color=disnake.Color.red()))
            return

        # Truyền temp_raw vào View để các nút bấm hoạt động với dữ liệu này
        view = PokemonMovesetView(fmt=raw_fmt_key, rating=rat, pokemon=poke, data=temp_raw)
        await inter.edit_original_message(embed=build_embed_stat(raw_fmt_key, rat, p), view=view)

    # ---------- AUTOCOMPLETE (GIỮ NGUYÊN 100%) ----------
    # Vì self.raw đã được "load optimized" (chỉ giữ lại name),
    # nên các hàm này vẫn chạy đúng logic cũ mà không cần sửa dòng nào.
    
    @moveset.autocomplete("gen")
    async def ac_gen(self, inter: disnake.ApplicationCommandInteraction, user_input: str):
        return _filter_choices(self.gens, user_input)

    @moveset.autocomplete("format")
    async def ac_format(self, inter: disnake.ApplicationCommandInteraction, user_input: str):
        g = (inter.filled_options.get("gen") or "").strip().lower()
        fmts = self.formats_by_gen.get(g, [])
        return _filter_choices(fmts, user_input)

    @moveset.autocomplete("rating")
    async def ac_rating(self, inter: disnake.ApplicationCommandInteraction, user_input: str):
        g = (inter.filled_options.get("gen") or "").strip().lower()
        fmt = (inter.filled_options.get("format") or "").strip().lower()
        ratings = self.ratings_by_gf.get((g, fmt), ["all"])
        return _filter_choices(ratings, user_input)

    @moveset.autocomplete("pokemon")
    async def ac_pokemon(self, inter: disnake.ApplicationCommandInteraction, user_input: str):
        g = (inter.filled_options.get("gen") or "").strip().lower()
        fmt = (inter.filled_options.get("format") or "").strip().lower()
        rat = (inter.filled_options.get("rating") or "all").strip().lower()

        if not g or not fmt:
            return []

        names = self.pokemon_by_gfr.get((g, fmt, rat))
        if names is None:
            names = self.pokemon_by_gfr.get((g, fmt, "all"), [])

        return _filter_choices(names, user_input)


def setup(bot: commands.Bot):
    bot.add_cog(PokemonMoveset(bot))
