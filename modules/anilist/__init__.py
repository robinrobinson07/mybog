import requests
import disnake
import animec

ANILIST_GQL = "https://graphql.anilist.co"

class AnilistDiscord:
    def __init__(self):
        self.session = requests.Session()

    def get_character(self, character_name: str):
        try:
            char = animec.Charsearch(character_name)
        except Exception:
            return -1

        embed = disnake.Embed(title=char.title, url=char.url, color=disnake.Color.random())
        embed.set_image(url=char.image_url)

        try:
            embed.set_footer(text=", ".join(list(char.references.keys())[:2]))
        except Exception:
            pass

        return embed

    def get_anime_discord(self, anime_name: str):
        query = """
        query ($search: String) {
          Media(search: $search, type: ANIME) {
            title { romaji english }
            description(asHtml: false)
            startDate { year month day }
            endDate { year month day }
            coverImage { large }
            bannerImage
            format
            status
            episodes
            season
            genres
            nextAiringEpisode { timeUntilAiring episode }
            siteUrl
          }
        }
        """
        try:
            r = self.session.post(
                ANILIST_GQL,
                json={"query": query, "variables": {"search": anime_name}},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()["data"]["Media"]
            if not data:
                return -1

            # animec để lấy ranked/rating/producers như mày đang dùng
            anime = animec.Anime(anime_name)
        except Exception:
            return -1

        title_romaji = (data["title"]["romaji"] or "Not Available").strip()
        title_english = (data["title"]["english"] or "Not Available").strip()
        desc = data.get("description") or "Not Available"
        desc = (
            desc.replace("<br>", "")
                .replace("<i>", "")
                .replace("</i>", "")
                .strip()
        )
        cover = (data.get("coverImage") or {}).get("large")
        banner = data.get("bannerImage")
        status = data.get("status") or "Not Available"
        fmt = data.get("format") or "Not Available"
        eps = data.get("episodes")
        season = data.get("season") or "Not Available"
        genres = data.get("genres") or []
        url = data.get("siteUrl")

        next_ep = data.get("nextAiringEpisode")
        next_ep_string = "Not Available"
        if next_ep:
            t = int(next_ep["timeUntilAiring"])
            days, rem = divmod(t, 86400)
            hours, rem = divmod(rem, 3600)
            mins, secs = divmod(rem, 60)
            next_ep_string = f"Tập {next_ep['episode']} sẽ chiếu sau {days}d {hours}h {mins}m {secs}s"

        try:
            embed = disnake.Embed(
                title=f"**{title_romaji}**",
                description=title_english,
                color=disnake.Color.random(),
                url=url
            )
        except Exception:
            embed = disnake.Embed(
                title=f"**{title_romaji}**",
                description=title_english,
                color=disnake.Color.random()
            )

        if banner:
            embed.set_image(url=banner)
        if cover:
            embed.set_thumbnail(url=cover)

        embed.add_field(name="Giới Thiệu", value=desc[:1024], inline=False)

        embed.add_field(name="Mùa", value=season, inline=True)

        if eps:
            embed.add_field(name="Định Dạng", value=f"{fmt} ({eps} tập)", inline=True)
        else:
            embed.add_field(name="Định Dạng", value=fmt, inline=True)

        embed.add_field(name="Trạng Thái", value=status, inline=True)
        embed.add_field(name="Xếp hạng", value=str(getattr(anime, "ranked", "N/A")), inline=True)
        embed.add_field(name="Giới hạn độ tuổi", value=str(getattr(anime, "rating", "N/A")), inline=True)
        embed.add_field(name="Tập Kế Tiếp ~", value=next_ep_string, inline=False)

        if genres:
            embed.add_field(name="Thể Loại", value="\n".join(genres)[:1024], inline=True)

        try:
            embed.add_field(name="Các nhà sản xuất", value="\n".join(anime.producers)[:1024], inline=False)
        except Exception:
            pass

        embed.set_footer(text="hãy donate cho nhà phát triển bot này vì anh ấy tạch gacha ( ಠ‿<)")
        return embed
