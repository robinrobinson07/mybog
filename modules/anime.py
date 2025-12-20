
import disnake
from disnake.ext import commands
bot = commands.Bot(command_prefix="?",
                  intents=disnake.Intents.all(),
)
from modules import anilist

anilist = anilist.AnilistDiscord()
class Anime(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    @commands.slash_command(name="findchar", description="Tìm kiếm chai alime và géi alime")
    @commands.cooldown(1,5,commands.BucketType.user)
    async def findchar(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        query: str
    ):
        await interaction.response.defer()
        anime_embed = anilist.get_character(character_name=query)
        if anime_embed == -1:
            res=disnake.Embed(description=f"Không có anime tên {query} được tìm thấy", color=disnake.Color.random())
            res.set_footer(text="hãy donate cho nhà phát triển bot này vì anh ấy tạch gacha ( ಠ‿<)",icon_url="https://images-wixmp-ed30a86b8c4ca887773594c2.wixmp.com/f/3cbd1933-0f04-45ea-b103-274ffa86cd3c/dera7vx-8fe91262-a09d-47fb-9892-11355fddb803.png?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1cm46YXBwOjdlMGQxODg5ODIyNjQzNzNhNWYwZDQxNWVhMGQyNmUwIiwiaXNzIjoidXJuOmFwcDo3ZTBkMTg4OTgyMjY0MzczYTVmMGQ0MTVlYTBkMjZlMCIsIm9iaiI6W1t7InBhdGgiOiJcL2ZcLzNjYmQxOTMzLTBmMDQtNDVlYS1iMTAzLTI3NGZmYTg2Y2QzY1wvZGVyYTd2eC04ZmU5MTI2Mi1hMDlkLTQ3ZmItOTg5Mi0xMTM1NWZkZGI4MDMucG5nIn1dXSwiYXVkIjpbInVybjpzZXJ2aWNlOmZpbGUuZG93bmxvYWQiXX0.4hajJyTVzWTc8QecEDJK_xlq3kuQ6wjmZLm9k9xGfZ4")
            res.set_thumbnail(url="https://pbs.twimg.com/tweet_video_thumb/FU_DlamWQAUNHOO.jpg")
            res.set_author(name="Ôi không!",icon_url="https://creazilla-store.fra1.digitaloceanspaces.com/cliparts/60279/sad-face-clipart-md.png")
            await interaction.edit_original_message(embed=res)
        else:
            await interaction.edit_original_message(embed=anime_embed)
            
        return
    @commands.slash_command(name="findanime", description="Tìm alime")
    @commands.cooldown(1,5,commands.BucketType.user)
    async def findanime(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        query: str
    ):
        await interaction.response.defer()
        anime_embed = anilist.get_anime_discord(anime_name=query)
        if anime_embed == -1:
            res=disnake.Embed(description=f"Không có anime tên {query} được tìm thấy", color=disnake.Color.random())
            res.set_footer(text="hãy donate cho nhà phát triển bot này vì anh ấy tạch gacha (ಠ‿<)",icon_url="https://images-wixmp-ed30a86b8c4ca887773594c2.wixmp.com/f/3cbd1933-0f04-45ea-b103-274ffa86cd3c/dera7vx-8fe91262-a09d-47fb-9892-11355fddb803.png?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1cm46YXBwOjdlMGQxODg5ODIyNjQzNzNhNWYwZDQxNWVhMGQyNmUwIiwiaXNzIjoidXJuOmFwcDo3ZTBkMTg4OTgyMjY0MzczYTVmMGQ0MTVlYTBkMjZlMCIsIm9iaiI6W1t7InBhdGgiOiJcL2ZcLzNjYmQxOTMzLTBmMDQtNDVlYS1iMTAzLTI3NGZmYTg2Y2QzY1wvZGVyYTd2eC04ZmU5MTI2Mi1hMDlkLTQ3ZmItOTg5Mi0xMTM1NWZkZGI4MDMucG5nIn1dXSwiYXVkIjpbInVybjpzZXJ2aWNlOmZpbGUuZG93bmxvYWQiXX0.4hajJyTVzWTc8QecEDJK_xlq3kuQ6wjmZLm9k9xGfZ4")
            res.set_thumbnail(url="https://pbs.twimg.com/tweet_video_thumb/FU_DlamWQAUNHOO.jpg")
            res.set_author(name="Ôi không!",icon_url="https://creazilla-store.fra1.digitaloceanspaces.com/cliparts/60279/sad-face-clipart-md.png")
            await interaction.edit_original_message(embed=res)
        else:
            await interaction.edit_original_message(embed=anime_embed)
            
        return
        

def setup(bot):
      bot.add_cog(Anime(bot))

    