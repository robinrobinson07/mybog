import disnake
from disnake.ext import commands


class Amogus(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


    @commands.slash_command(name="amogus", description="sussy baka")
    async def amogus(self, interaction: disnake.ApplicationCommandInteraction):
        await interaction.response.send_message("AMOGUS, SUSSY BAKA!", ephemeral=True)
        print(f"Thằng {interaction.author.name} là impostor.")


def setup(bot: commands.Bot):
    bot.add_cog(Amogus(bot))
