import os
import disnake
from disnake.ext import commands
from pathlib import Path

bot = commands.Bot(command_prefix="?", intents=disnake.Intents.all())

@bot.event
async def on_ready():
    print("bot cháy đấy")

@bot.event
async def on_slash_command_error(inter: disnake.ApplicationCommandInteraction, error):
    if isinstance(error, commands.CommandOnCooldown):
        await inter.response.send_message(
            f"**Bạn sử dụng bot quá nhanh thử lại sau {error.retry_after:.2f} giây**",
            ephemeral=False
        )

if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    modules_dir = base_dir / "modules"

    for p in modules_dir.glob("*.py"):
        if not p.name.startswith("_"):
            bot.load_extension(f"modules.{p.stem}")
            print(f"Loaded module: {p.stem}")
  
   
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing BOT_TOKEN in environment variables")

    bot.run(token)
