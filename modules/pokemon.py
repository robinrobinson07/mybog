# pokemon_moveset_lazy.py
import json
import re
import requests
import disnake
from disnake.ext import commands
from typing import Any, Dict, List, Tuple, Optional

from .pokemon_embed import PokemonMovesetView, build_embed_stat, pick_pokemon

# ======= CONFIG: Firebase REST =======
FIREBASE_URL = "https://vo-robin-default-rtdb.asia-southeast1.firebasedatabase.app"
TIMEOUT = 10  # seconds cho mỗi request
LOCAL_DATA_FALLBACK = "pokemon_data.json"  # nếu muốn fallback về file

MAX_CHOICES = 25
GEN_RE = re.compile(r"^(gen[1-9])(.+)$", re.I)


def _url(path: str) -> str:
    return f"{FIREBASE_URL.rstrip('/')}/{path.lstrip('/')}.json"


def _convert_rating_bucket(bucket: Any) -> List[Dict[str, Any]]:
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


def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower().strip() if ch.isalnum())


def _filter_choices(options: List[str], user_input: str) -> List[str]:
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
    m = GEN_RE.match(fmt_key)
    if not m:
        return "unknown", fmt_key
    return m.group(1).lower(), m.group(2).lower()


def load_minimal_index_from_firebase() -> Dict[str, Any]:
    """
    TẢI NHẸ (chỉ tên):
    - GET /pokemondata?shallow=true  -> list fmt_key
    - với mỗi fmt_key: GET /pokemondata/{fmt_key}?shallow=true -> list rating keys
    - với mỗi rating: GET /pokemondata/{fmt_key}/{rating}?shallow=true -> list item_keys
    - với mỗi item_key: GET /pokemondata/{fmt_key}/{rating}/{item_key}/name -> chỉ lấy name
    Trả về dict giống cấu trúc gốc nhưng mỗi item chỉ chứa {"name": "..."}.
    Nếu lỗi -> fallback đọc LOCAL_DATA_FALLBACK và tạo minimal index từ đó.
    """
    try:
        # lấy list fmt_key
        r = requests.get(_url("pokemondata"), params={"shallow": "true"}, timeout=TIMEOUT)
        r.raise_for_status()
        fmt_keys_obj = r.json() or {}
        fmt_keys = list(fmt_keys_obj.keys())

        minimal: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        # map (fmt_key, rating, name_lower) -> item_key (index) để dễ fetch sau
        key_by_entry: Dict[Tuple[str, str, str], str] = {}

        for fmt_key in fmt_keys:
            # lấy rating keys cho fmt_key
            rr = requests.get(_url(f"pokemondata/{fmt_key}"), params={"shallow": "true"}, timeout=TIMEOUT)
            rr.raise_for_status()
            ratings_obj = rr.json() or {}
            rating_keys = list(ratings_obj.keys())

            minimal_bucket: Dict[str, List[Dict[str, Any]]] = {}
            for rating in rating_keys:
                # lấy item keys dưới rating
                rrr = requests.get(_url(f"pokemondata/{fmt_key}/{rating}"), params={"shallow": "true"}, timeout=TIMEOUT)
                rrr.raise_for_status()
                items_obj = rrr.json() or {}
                item_keys = list(items_obj.keys())

                lst: List[Dict[str, Any]] = []
                for item_key in item_keys:
                    # lấy chỉ "name"
                    name_resp = requests.get(_url(f"pokemondata/{fmt_key}/{rating}/{item_key}/name"), timeout=TIMEOUT)
                    # name_resp có thể trả về null nếu không tồn tại
                    try:
                        name_val = name_resp.json()
                    except Exception:
                        name_val = None
                    if not name_val:
                        # phòng trường hợp name nằm trong object, fallback: lấy toàn object tên (nhỏ) — nhưng cố gắng skip
                        # để an toàn, thử lấy toàn object và đọc 'name'
                        full_try = requests.get(_url(f"pokemondata/{fmt_key}/{rating}/{item_key}"), timeout=TIMEOUT)
                        try:
                            full_json = full_try.json() or {}
                            name_val = full_json.get("name")
                        except Exception:
                            name_val = None

                    if name_val:
                        entry = {"name": name_val}
                        lst.append(entry)
                        key_by_entry[(fmt_key, rating, str(name_val).strip().lower())] = item_key
                minimal_bucket[str(rating)] = lst

            # tạo "all" union
            all_names = []
            seen = set()
            for rkey, items in minimal_bucket.items():
                for it in items:
                    nm = it.get("name")
                    if nm and nm not in seen:
                        seen.add(nm)
                        all_names.append({"name": nm})
                        # note: key_by_entry đã được map ở trên cho từng rating
            minimal_bucket["all"] = all_names
            minimal[fmt_key] = minimal_bucket

        # trả về minimal + key map (gọi hàm ngoài sẽ lưu map vào self)
        return {"_minimal": minimal, "_keys": key_by_entry}
    except requests.RequestException:
        # fallback local file: đọc local và tạo minimal structure
        try:
            with open(LOCAL_DATA_FALLBACK, "r", encoding="utf-8") as f:
                data = json.load(f)
                result_minimal: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
                key_by_entry: Dict[Tuple[str, str, str], str] = {}
                for fmt_key, ratings in (data or {}).items():
                    bucket_min = {}
                    for rating_key, rating_bucket in (ratings or {}).items():
                        lst = _convert_rating_bucket(rating_bucket)
                        small = []
                        idx = 0
                        for entry in lst:
                            if not isinstance(entry, dict):
                                idx += 1
                                continue
                            name = entry.get("name")
                            if name:
                                small.append({"name": name})
                                key_by_entry[(fmt_key, str(rating_key), str(name).strip().lower())] = str(idx)
                            idx += 1
                        bucket_min[str(rating_key)] = small
                    # all union
                    all_names = []
                    seen = set()
                    for ritems in bucket_min.values():
                        for it in ritems:
                            nm = it.get("name")
                            if nm and nm not in seen:
                                seen.add(nm)
                                all_names.append({"name": nm})
                    bucket_min["all"] = all_names
                    result_minimal[fmt_key] = bucket_min
                return {"_minimal": result_minimal, "_keys": key_by_entry}
        except Exception:
            return {"_minimal": {}, "_keys": {}}


def fetch_full_rating(fmt_key: str, rating: str) -> List[Dict[str, Any]]:
    """
    Tải toàn bộ rating bucket (dùng khi user yêu cầu chi tiết).
    Trả về list các object (convert từ dict->list nếu cần).
    """
    try:
        r = requests.get(_url(f"pokemondata/{fmt_key}/{rating}"), timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return _convert_rating_bucket(data)
    except requests.RequestException:
        return []


def fetch_full_entry_by_index(fmt_key: str, rating: str, index_key: str) -> Optional[Dict[str, Any]]:
    try:
        r = requests.get(_url(f"pokemondata/{fmt_key}/{rating}/{index_key}"), timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


class PokemonMoveset(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # --- THAY: chỉ tải index NHẸ (chỉ name + map key) ---
        loaded = load_minimal_index_from_firebase()
        self.raw_minimal: Dict[str, Dict[str, List[Dict[str, Any]]]] = loaded.get("_minimal", {})
        self.key_by_entry: Dict[Tuple[str, str, str], str] = loaded.get("_keys", {})

        # Build 3-level index: gen -> format -> rating -> pokelist (names only)
        self.index: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for fmt_key, bucket in self.raw_minimal.items():
            gen, fmt = split_gen_and_format(fmt_key)
            self.index.setdefault(gen, {})[fmt] = bucket

        # cache gens
        self.gens: List[str] = sorted([g for g in self.index.keys() if g != "unknown"])
        if "unknown" in self.index:
            self.gens.append("unknown")

        # cache formats per gen
        self.formats_by_gen: Dict[str, List[str]] = {
            g: sorted(list(self.index[g].keys())) for g in self.index.keys()
        }

        # cache ratings per (gen, fmt)
        self.ratings_by_gf: Dict[Tuple[str, str], List[str]] = {}
        for g, fmts in self.index.items():
            for fmt, bucket in fmts.items():
                ratings = list((bucket or {}).keys())
                ratings_sorted = sorted(ratings, key=lambda x: int(x) if x.isdigit() else 10**18)
                self.ratings_by_gf[(g, fmt)] = ["all"] + ratings_sorted

        # cache pokemon per (gen, fmt, rating) - names only
        self.pokemon_by_gfr: Dict[Tuple[str, str, str], List[str]] = {}
        for g, fmts in self.index.items():
            for fmt, bucket in fmts.items():
                for r, pokes in (bucket or {}).items():
                    names = [p.get("name", "") for p in (pokes or []) if isinstance(p, dict) and p.get("name")]
                    seen = set()
                    uniq = []
                    for nm in names:
                        if nm not in seen:
                            seen.add(nm)
                            uniq.append(nm)
                    self.pokemon_by_gfr[(g, fmt, r)] = uniq

                # all = union
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
        description="Smogon moveset lookup (gen + format + rating + pokemon)",
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

        if g not in self.index:
            await inter.edit_original_message(
                embed=disnake.Embed(description="Gen không hợp lệ.", color=disnake.Color.red())
            )
            return

        if fmt not in self.index[g]:
            await inter.edit_original_message(
                embed=disnake.Embed(description="Format không hợp lệ cho gen này.", color=disnake.Color.red())
            )
            return

        if rat != "all" and not rat.isdigit():
            await inter.edit_original_message(
                embed=disnake.Embed(description="Rating phải là số hoặc `all`.", color=disnake.Color.red())
            )
            return

        raw_fmt_key = f"{g}{fmt}"

        # TÌM item_key từ map nhẹ đã lưu
        item_key = self.key_by_entry.get((raw_fmt_key, rat, poke.lower()))
        # Nếu chưa thấy, cố gắng fetch full rating và tìm name (trong trường hợp index thiếu)
        full_rating_list = []
        if item_key is None:
            full_rating_list = fetch_full_rating(raw_fmt_key, rat)
            for idx, entry in enumerate(full_rating_list):
                if not isinstance(entry, dict):
                    continue
                nm = entry.get("name", "")
                if nm and nm.strip().lower() == poke.lower():
                    # chúng ta không biết index_key gốc (nó có thể là số hoặc id). 
                    # Nhưng vì chúng ta đã có entry object, dùng nó luôn.
                    p = entry
                    view_data = {raw_fmt_key: {rat: full_rating_list}}
                    view = PokemonMovesetView(fmt=raw_fmt_key, rating=rat, pokemon=poke, data=view_data)
                    await inter.edit_original_message(embed=build_embed_stat(raw_fmt_key, rat, p), view=view)
                    return
            # nếu vẫn không tìm -> lỗi
            await inter.edit_original_message(embed=disnake.Embed(description="Không tìm thấy Pokémon này trong rating.", color=disnake.Color.red()))
            return

        # nếu có item_key: fetch đầy đủ object tại path đó
        full_entry = fetch_full_entry_by_index(raw_fmt_key, rat, item_key)
        if not full_entry:
            # fallback: tải toàn bộ rating bucket và tìm object theo name
            full_rating_list = fetch_full_rating(raw_fmt_key, rat)
            p = None
            for entry in full_rating_list:
                if isinstance(entry, dict) and entry.get("name", "").strip().lower() == poke.lower():
                    p = entry
                    break
            if not p:
                await inter.edit_original_message(embed=disnake.Embed(description="Không tải được dữ liệu chi tiết cho Pokémon này.", color=disnake.Color.red()))
                return
            view_data = {raw_fmt_key: {rat: full_rating_list}}
            view = PokemonMovesetView(fmt=raw_fmt_key, rating=rat, pokemon=poke, data=view_data)
            await inter.edit_original_message(embed=build_embed_stat(raw_fmt_key, rat, p), view=view)
            return

        # nếu fetch entry thành công
        p = full_entry
        # để view/embed hoạt động giống trước: tải toàn bộ rating bucket (chỉ khi cần)
        if not full_rating_list:
            full_rating_list = fetch_full_rating(raw_fmt_key, rat)
        view_data = {raw_fmt_key: {rat: full_rating_list}}
        view = PokemonMovesetView(fmt=raw_fmt_key, rating=rat, pokemon=poke, data=view_data)
        await inter.edit_original_message(embed=build_embed_stat(raw_fmt_key, rat, p), view=view)

    # ---------- AUTOCOMPLETE ----------
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
