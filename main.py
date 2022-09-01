import os
import disnake

from disnake.ext import commands
from config import CONFIG

bot = commands.Bot(command_prefix="?", intents=disnake.Intents.all())

@bot.event
async def on_ready():
    print("bot cháy đấy")


if __name__ == "__main__":
    # Load tất cả module trong folder modules.
    for m in os.listdir("modules"):
        if m.endswith(".py"):
            bot.load_extension(f"modules.{m[:-3]}")

    bot.run(CONFIG.get("botToken"))
