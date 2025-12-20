import re
import disnake
from typing import Any, Dict, List, Optional, Tuple

STAT_SECTIONS = ["Moves", "Abilities", "Items", "Spreads", "Tera Types"]
TEAM_SECTION = "Teammates"
CHECK_SECTION = "Checks and Counters"


def _fmt_pct(x: float) -> str:
    return f"{x:.2f}%"


def _norm_name(s: str) -> str:
    return "".join(ch for ch in s.lower().strip() if ch.isalnum())


def _top_entries(entries: List[Dict[str, Any]], k: int) -> List[Tuple[str, float]]:
    pairs: List[Tuple[str, float]] = []
    for e in entries:
        if "name" in e and "pct" in e:
            pairs.append((str(e["name"]), float(e["pct"])))
    pairs.sort(key=lambda t: t[1], reverse=True)
    return pairs[:k]


def _merge_average_across_ratings(
    format_bucket: Dict[str, Any],
    pokemon_name: str,
) -> Optional[Dict[str, Any]]:
    ratings = list(format_bucket.keys())
    if not ratings:
        return None

    target = _norm_name(pokemon_name)
    per_rating: List[Optional[Dict[str, Any]]] = []

    for r in ratings:
        pokes = format_bucket.get(r, []) or []
        found = None

        for p in pokes:
            if _norm_name(p.get("name", "")) == target:
                found = p
                break

        if not found:
            for p in pokes:
                if _norm_name(p.get("name", "")).startswith(target):
                    found = p
                    break

        per_rating.append(found)

    if all(x is None for x in per_rating):
        return None

    base = next(x for x in per_rating if x is not None)
    out: Dict[str, Any] = {
        "name": base.get("name", pokemon_name),
        "raw_count": None,
        "avg_weight": None,
        "viability_ceiling": None,
        "sections": {},
    }

    all_sections = set()
    for p in per_rating:
        if p and isinstance(p.get("sections"), dict):
            all_sections.update(p["sections"].keys())

    for sec in all_sections:
        if sec == CHECK_SECTION:
            first_with = next((p for p in per_rating if p and sec in (p.get("sections") or {})), None)
            if first_with:
                out["sections"][sec] = first_with["sections"][sec]
            continue

        merged: Dict[str, float] = {}
        for p in per_rating:
            entries = []
            if p and isinstance(p.get("sections"), dict):
                entries = p["sections"].get(sec, []) or []

            local: Dict[str, float] = {}
            for e in entries:
                if "name" in e and "pct" in e:
                    local[str(e["name"])] = float(e["pct"])

            for nm in local.keys():
                if nm not in merged:
                    merged[nm] = 0.0

            for nm in merged.keys():
                merged[nm] += local.get(nm, 0.0)

        n = float(len(ratings))
        out_list = [{"name": nm, "pct": merged[nm] / n} for nm in merged.keys()]
        out_list.sort(key=lambda d: d["pct"], reverse=True)
        out["sections"][sec] = out_list

    return out


def pick_pokemon(
    data: Dict[str, Any],
    fmt: str,
    rating: str,
    pokemon: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    fmt_bucket = data.get(fmt)
    if not fmt_bucket:
        return None, f"Không tìm thấy format `{fmt}` trong data."

    if rating == "all":
        p = _merge_average_across_ratings(fmt_bucket, pokemon)
        if not p:
            return None, f"Không tìm thấy Pokémon `{pokemon}` trong format `{fmt}` (all ratings)."
        return p, None

    pokes = fmt_bucket.get(rating)
    if pokes is None:
        return None, f"Không tìm thấy rating `{rating}` trong format `{fmt}`."

    target = _norm_name(pokemon)
    found = None

    for p in pokes:
        if _norm_name(p.get("name", "")) == target:
            found = p
            break

    if not found:
        for p in pokes:
            if _norm_name(p.get("name", "")).startswith(target):
                found = p
                break

    if not found:
        return None, f"Không tìm thấy Pokémon `{pokemon}` trong `{fmt}-{rating}`."
    return found, None


def build_embed_stat(fmt: str, rating: str, p: Dict[str, Any]) -> disnake.Embed:
    title = f"{p.get('name','?')}  |  {fmt}-{rating}"
    embed = disnake.Embed(title=title, color=disnake.Color.random())
    secs = p.get("sections", {}) or {}

    for sec in STAT_SECTIONS:
        top = _top_entries(secs.get(sec, []) or [], 10)
        if not top:
            continue
        value = "\n".join([f"• **{nm}**: {_fmt_pct(pc)}" for nm, pc in top])[:1024]
        embed.add_field(name=sec, value=value, inline=False)

    embed.set_footer(text="Stat: Moves / Abilities / Items / Spreads / Tera Types")
    return embed


def build_embed_team(fmt: str, rating: str, p: Dict[str, Any]) -> disnake.Embed:
    title = f"{p.get('name','?')}  |  {fmt}-{rating}"
    embed = disnake.Embed(title=title, color=disnake.Color.random())

    secs = p.get("sections", {}) or {}
    top = _top_entries(secs.get(TEAM_SECTION, []) or [], 15)
    if top:
        value = "\n".join([f"• **{nm}**: {_fmt_pct(pc)}" for nm, pc in top])[:1024]
        embed.add_field(name="Teammates (Top 15)", value=value, inline=False)
    else:
        embed.description = "Không có data teammates."

    embed.set_footer(text="Teammates")
    return embed


def build_embed_checks(fmt: str, rating: str, p: Dict[str, Any]) -> disnake.Embed:
    title = f"{p.get('name','?')}  |  {fmt}-{rating}"
    embed = disnake.Embed(title=title, color=disnake.Color.random())

    secs = p.get("sections", {}) or {}
    rows = secs.get(CHECK_SECTION, []) or []
    if not rows:
        embed.description = "Không có data checks & counters."
        embed.set_footer(text="Checks & Counters")
        return embed

    scored = []
    for e in rows:
        raw = str(e.get("raw", ""))
        m = re.search(r"\s(\d+(?:\.\d+)?)\s*\(", raw)
        score = float(m.group(1)) if m else -1.0
        scored.append((score, e))

    scored.sort(key=lambda t: t[0], reverse=True)
    scored = scored[:10]

    lines = []
    for score, e in scored:
        opp = e.get("opponent") or "?"
        raw = e.get("raw") or ""
        detail = e.get("detail") or ""
        if detail:
            lines.append(f"• **{opp}**\n  {raw}\n  {detail}")
        else:
            lines.append(f"• **{opp}**\n  {raw}")

    embed.add_field(name="Checks & Counters (Top 10)", value="\n".join(lines)[:1024], inline=False)
    embed.set_footer(text="Checks & Counters")
    return embed


class PokemonMovesetView(disnake.ui.View):
    def __init__(self, fmt: str, rating: str, pokemon: str, data: Dict[str, Any]):
        super().__init__(timeout=120)
        self.fmt = fmt
        self.rating = rating
        self.pokemon = pokemon
        self.data = data

    def _get_pokemon_or_error(self):
        return pick_pokemon(self.data, self.fmt, self.rating, self.pokemon)

    @disnake.ui.button(label="Stat", style=disnake.ButtonStyle.primary)
    async def btn_stat(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        p, err = self._get_pokemon_or_error()
        if err:
            await inter.response.edit_message(
                embed=disnake.Embed(description=err, color=disnake.Color.red()),
                view=self,
            )
            return
        await inter.response.edit_message(embed=build_embed_stat(self.fmt, self.rating, p), view=self)

    @disnake.ui.button(label="Teammates", style=disnake.ButtonStyle.secondary)
    async def btn_team(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        p, err = self._get_pokemon_or_error()
        if err:
            await inter.response.edit_message(
                embed=disnake.Embed(description=err, color=disnake.Color.red()),
                view=self,
            )
            return
        await inter.response.edit_message(embed=build_embed_team(self.fmt, self.rating, p), view=self)

    @disnake.ui.button(label="Checks", style=disnake.ButtonStyle.secondary)
    async def btn_checks(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        p, err = self._get_pokemon_or_error()
        if err:
            await inter.response.edit_message(
                embed=disnake.Embed(description=err, color=disnake.Color.red()),
                view=self,
            )
            return
        await inter.response.edit_message(embed=build_embed_checks(self.fmt, self.rating, p), view=self)
