import disnake
from disnake.ext import commands
bot = commands.Bot(command_prefix="?",
                  intents=disnake.Intents.all(),
)

class Amogus(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


    @commands.slash_command(name="amogus", description="sussy baka")
    @commands.cooldown(1,5,commands.BucketType.user)
    async def amogus(self, interaction: disnake.ApplicationCommandInteraction):

            await interaction.response.send_message("AMOGUS, SUSSY BAKA!", ephemeral=True)
            print(f"Thằng {interaction.author.name} là impostor.")
        
    

        


def setup(bot: commands.Bot):
    bot.add_cog(Amogus(bot))
