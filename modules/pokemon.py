import json
import re
import requests
import disnake
from disnake.ext import commands
from typing import Any, Dict, List, Tuple

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
    """
    Firebase có thể lưu rating như:
      - list of objects (giống json gốc) -> giữ nguyên
      - dict: { "0": {...}, "1": {...}, ... } hoặc { "12345": {...}, ... } -> chuyển sang list
    Trả về list (có thể rỗng).
    """
    if bucket is None:
        return []
    if isinstance(bucket, list):
        return bucket
    if isinstance(bucket, dict):
        # sort keys numerically nếu có thể, nếu không giữ thứ tự key trên dict
        try:
            keys = sorted(bucket.keys(), key=lambda k: int(k))
        except Exception:
            keys = list(bucket.keys())
        out = []
        for k in keys:
            v = bucket.get(k)
            # nếu v là dict chứa con (ví dụ chứa "name", "sections"...), lấy v
            if isinstance(v, dict):
                out.append(v)
            else:
                # nếu v chưa phải dict (lỗi dữ liệu), skip hoặc lấy trực tiếp
                out.append(v)
        return out
    # khác -> trả về rỗng
    return []


def load_data_from_firebase() -> Dict[str, Any]:
    """
    GET toàn bộ /pokemondata từ Firebase và chuyển về dạng raw giống json gốc:
      raw = {
        "gen9ou": {
           "1760": [ {name:..., sections:...}, ... ],
           "1825": [ ... ],
           ...
        },
        "gen9uu": { ... }
      }
    Nếu request lỗi -> thử fallback đọc file LOCAL_DATA_FALLBACK
    """
    try:
        r = requests.get(_url("pokemondata"), timeout=TIMEOUT)
        r.raise_for_status()
        fb = r.json()
        if not isinstance(fb, dict):
            fb = {}

        raw: Dict[str, Any] = {}
        # fb: { fmt_key: { rating: { idx: obj, ... } or [ ... ] } }
        for fmt_key, ratings in fb.items():
            if not isinstance(ratings, dict):
                # nếu cấu trúc lạ, skip
                continue
            raw_bucket: Dict[str, Any] = {}
            for rating_key, rating_bucket in ratings.items():
                # rating_key có thể là "1760" hoặc "all" etc.
                # convert rating_bucket -> list
                lst = _convert_rating_bucket(rating_bucket)
                raw_bucket[str(rating_key)] = lst
            raw[fmt_key] = raw_bucket
        return raw
    except requests.RequestException:
        # fallback: local file (giúp dev test khi offline)
        try:
            with open(LOCAL_DATA_FALLBACK, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            # nếu vẫn lỗi -> trả về rỗng để bot không crash
            return {}


def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower().strip() if ch.isalnum())


def _filter_choices(options: List[str], user_input: str) -> List[str]:
    if not options:
        return []
    q = (user_input or "").strip().lower()
    if not q:
        return options[:MAX_CHOICES]

    # ưu tiên prefix match trước
    pref = [x for x in options if x.lower().startswith(q)]
    if len(pref) >= MAX_CHOICES:
        return pref[:MAX_CHOICES]

    # rồi substring match
    sub = [x for x in options if q in x.lower() and x not in pref]
    out = pref + sub

    if len(out) < MAX_CHOICES:
        nq = _norm(q)
        more = [x for x in options if nq and nq in _norm(x) and x not in out]
        out.extend(more)

    return out[:MAX_CHOICES]


def split_gen_and_format(fmt_key: str) -> Tuple[str, str]:
    """
    fmt_key: "gen9ou" -> ("gen9", "ou")
            "gen9legendszaou" -> ("gen9", "legendszaou")
    fallback: ("unknown", fmt_key)
    """
    m = GEN_RE.match(fmt_key)
    if not m:
        return "unknown", fmt_key
    return m.group(1).lower(), m.group(2).lower()


class PokemonMoveset(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # --- THAY: đọc từ firebase thay vì local json ---
        self.raw: Dict[str, Any] = load_data_from_firebase()

        # Build 3-level index: gen -> format -> rating -> pokelist
        self.index: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for fmt_key, bucket in self.raw.items():
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

        # cache pokemon per (gen, fmt, rating)
        self.pokemon_by_gfr: Dict[Tuple[str, str, str], List[str]] = {}
        for g, fmts in self.index.items():
            for fmt, bucket in fmts.items():
                # per rating
                for r, pokes in (bucket or {}).items():
                    # pokes is list of dicts (converted above)
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

        # convert back to raw fmt key used by embed/query logic: "gen9" + "ou" -> "gen9ou"
        raw_fmt_key = f"{g}{fmt}"

        # pick from raw JSON/Firebase-structure (format->rating->pokelist)
        p, err = pick_pokemon(self.raw, raw_fmt_key, rat, poke)
        if err:
            await inter.edit_original_message(embed=disnake.Embed(description=err, color=disnake.Color.red()))
            return

        view = PokemonMovesetView(fmt=raw_fmt_key, rating=rat, pokemon=poke, data=self.raw)
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
