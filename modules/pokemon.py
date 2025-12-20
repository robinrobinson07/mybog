import json
import re
import disnake
from disnake.ext import commands
from typing import Any, Dict, List, Tuple
from .pokemon_embed.smogon_fetch import fetch_and_build
from .pokemon_embed import PokemonMovesetView, build_embed_stat, pick_pokemon

fetch_and_build()
DATA_PATH = "pokemon_data.json"
MAX_CHOICES = 25
GEN_RE = re.compile(r"^(gen[1-9])(.+)$", re.I)


def load_data(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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
        more = [
            x for x in options
            if nq and nq in _norm(x) and x not in out
        ]
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
        self.raw: Dict[str, Any] = load_data(DATA_PATH)

        # Build 3-level index: gen -> format -> rating -> pokelist
        self.index: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for fmt_key, bucket in self.raw.items():
            gen, fmt = split_gen_and_format(fmt_key)
            self.index.setdefault(gen, {})[fmt] = bucket

        # cache gens
        self.gens: List[str] = sorted(
            [g for g in self.index.keys() if g != "unknown"]
        )
        if "unknown" in self.index:
            self.gens.append("unknown")

        # cache formats per gen
        self.formats_by_gen: Dict[str, List[str]] = {
            g: sorted(list(self.index[g].keys()))
            for g in self.index.keys()
        }

        # cache ratings per (gen, fmt)
        self.ratings_by_gf: Dict[Tuple[str, str], List[str]] = {}
        for g, fmts in self.index.items():
            for fmt, bucket in fmts.items():
                ratings = list((bucket or {}).keys())
                ratings_sorted = sorted(
                    ratings,
                    key=lambda x: int(x) if x.isdigit() else 10**18
                )
                self.ratings_by_gf[(g, fmt)] = ["all"] + ratings_sorted

        # cache pokemon per (gen, fmt, rating)
        self.pokemon_by_gfr: Dict[Tuple[str, str, str], List[str]] = {}
        for g, fmts in self.index.items():
            for fmt, bucket in fmts.items():
                # per rating
                for r, pokes in (bucket or {}).items():
                    names = [
                        p.get("name", "")
                        for p in (pokes or [])
                        if p.get("name")
                    ]
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
                        nm = p.get("name")
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
        gen: str = commands.Param(
            name="gen",
            description="gen1..gen9"
        ),
        format: str = commands.Param(
            name="format",
            description="ou/ubers/..."
        ),
        rating: str = commands.Param(
            name="rating",
            description="0/1500/1630/1760 hoặc all"
        ),
        pokemon: str = commands.Param(
            name="pokemon",
            description="Tên Pokémon"
        ),
    ):
        await inter.response.defer()

        g = (gen or "").strip().lower()
        fmt = (format or "").strip().lower()
        rat = (rating or "").strip().lower()
        poke = (pokemon or "").strip()

        if g not in self.index:
            await inter.edit_original_message(
                embed=disnake.Embed(
                    description="Gen không hợp lệ.",
                    color=disnake.Color.red()
                )
            )
            return

        if fmt not in self.index[g]:
            await inter.edit_original_message(
                embed=disnake.Embed(
                    description="Format không hợp lệ cho gen này.",
                    color=disnake.Color.red()
                )
            )
            return

        if rat != "all" and not rat.isdigit():
            await inter.edit_original_message(
                embed=disnake.Embed(
                    description="Rating phải là số hoặc all.",
                    color=disnake.Color.red()
                )
            )
            return

        # convert back to raw fmt key used by embed/query logic:
        # "gen9" + "ou" -> "gen9ou"
        raw_fmt_key = f"{g}{fmt}"

        # pick from raw JSON structure (format->rating->pokelist) vẫn y nguyên
        p, err = pick_pokemon(self.raw, raw_fmt_key, rat, poke)
        if err:
            await inter.edit_original_message(
                embed=disnake.Embed(
                    description=err,
                    color=disnake.Color.red()
                )
            )
            return

        view = PokemonMovesetView(
            fmt=raw_fmt_key,
            rating=rat,
            pokemon=poke,
            data=self.raw
        )

        await inter.edit_original_message(
            embed=build_embed_stat(raw_fmt_key, rat, p),
            view=view
        )

    # ---------- AUTOCOMPLETE ----------

    @moveset.autocomplete("gen")
    async def ac_gen(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user_input: str
    ):
        return _filter_choices(self.gens, user_input)

    @moveset.autocomplete("format")
    async def ac_format(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user_input: str
    ):
        g = (inter.filled_options.get("gen") or "").strip().lower()
        fmts = self.formats_by_gen.get(g, [])
        return _filter_choices(fmts, user_input)

    @moveset.autocomplete("rating")
    async def ac_rating(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user_input: str
    ):
        g = (inter.filled_options.get("gen") or "").strip().lower()
        fmt = (inter.filled_options.get("format") or "").strip().lower()
        ratings = self.ratings_by_gf.get((g, fmt), ["all"])
        return _filter_choices(ratings, user_input)

    @moveset.autocomplete("pokemon")
    async def ac_pokemon(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user_input: str
    ):
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
