import disnake
from modules import tr3tr4ulib
from disnake.ext import commands
TV = commands.option_enum ({"Tiếng Việt":"0", 
                            "TiẾnG vIệT":"1",
                            "Tiếng's Việt's":"2",
                            "T I Ế N G  V I Ệ T":"3",
                            "t!3ng v!3t":"4" })

class Translator(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


    @commands.slash_command(name="translate", description="Dịch ra ngôn ngữ xàm loz")
    @commands.cooldown(1,5,commands.BucketType.user)
    async def translate(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        option: TV,
        text: str
    ):
        if option == "0":
            await interaction.response.send_message(text)
        if option == "1":
            await interaction.response.send_message(tr3tr4ulib.l1(text))
        if option == "2":
            await interaction.response.send_message(tr3tr4ulib.l2(text))
        if option == "3":
            await interaction.response.send_message(tr3tr4ulib.l3(text))
        if option == "4":
            await interaction.response.send_message(tr3tr4ulib.l4(text))
def setup(bot):
      bot.add_cog(Translator(bot))

