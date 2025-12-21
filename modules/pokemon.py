import disnake
from disnake.ext import commands
from modules.pokemon_modules import embed as p_embed, firebase_request

# Khởi tạo service query data
poke_service = firebase_request.PokemonService()

class PokemonView(disnake.ui.View):
    def __init__(self, data: dict, embed_color: disnake.Color):
        super().__init__(timeout=180)
        self.data = data
        self.embed_color = embed_color

    @disnake.ui.button(label="Stats", style=disnake.ButtonStyle.primary, emoji="📊")
    async def stats_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        # Gọi từ module p_embed
        embed = p_embed.create_stats_embed(self.data, self.embed_color)
        await interaction.response.edit_message(embed=embed)

    @disnake.ui.button(label="Teammates", style=disnake.ButtonStyle.success, emoji="🤝")
    async def teammates_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        # Gọi từ module p_embed
        embed = p_embed.create_teammates_embed(self.data, self.embed_color)
        await interaction.response.edit_message(embed=embed)

    @disnake.ui.button(label="Checks & Counters", style=disnake.ButtonStyle.danger, emoji="⚔️")
    async def counters_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        # Gọi từ module p_embed
        embed = p_embed.create_counters_embed(self.data, self.embed_color)
        await interaction.response.edit_message(embed=embed)

class PokemonCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gens = [f"gen{i}" for i in range(1, 10)]

    @commands.slash_command(name="pokeshow", description="Xem thống kê Pokemon (Smogon Data)")
    async def pokeshow(
        self,
        inter: disnake.ApplicationCommandInteraction,
        gen: str,
        format: str,
        rating: str,
        pokemon: str
    ):
        await inter.response.defer()
        
        # 1. Lấy dữ liệu
        data = poke_service.get_pokemon_data(gen, format, rating, pokemon)
        
        if not data:
            await inter.edit_original_message(
                content=f"❌ Không tìm thấy dữ liệu cho **{pokemon}** tại {gen}/{format}/{rating}."
            )
            return

        # 2. Tạo Embed mặc định (Stats) từ module p_embed
        color = disnake.Color.blue()
        embed = p_embed.create_stats_embed(data, color)
        
        # 3. Tạo View chứa các nút
        view = PokemonView(data, color)

        await inter.edit_original_message(embed=embed, view=view)

    # --- AUTOCOMPLETE HANDLERS ---
    
    @pokeshow.autocomplete("gen")
    async def gen_autocomp(self, inter, user_input):
        return [g for g in self.gens if user_input.lower() in g]

    @pokeshow.autocomplete("format")
    async def format_autocomp(self, inter, user_input):
        gen = inter.filled_options.get("gen")
        if not gen: return ["Chọn Gen trước"]
        formats = poke_service.get_formats(gen)
        return [f for f in formats if user_input.lower() in f.lower()][:25]

    @pokeshow.autocomplete("rating")
    async def rating_autocomp(self, inter, user_input):
        gen = inter.filled_options.get("gen")
        fmt = inter.filled_options.get("format")
        if not gen or not fmt: return ["Chọn Format trước"]
        ratings = poke_service.get_ratings(gen, fmt)
        options = ["all"] + ratings
        return [r for r in options if user_input in r][:25]

    @pokeshow.autocomplete("pokemon")
    async def pokemon_autocomp(self, inter, user_input):
        gen = inter.filled_options.get("gen")
        fmt = inter.filled_options.get("format")
        rating = inter.filled_options.get("rating")
        if not all([gen, fmt, rating]): return ["Chọn đủ thông tin trước"]
        pokemons = poke_service.get_pokemons(gen, fmt, rating)
        return [p for p in pokemons if user_input.lower() in p.lower()][:25]

def setup(bot):
    bot.add_cog(PokemonCog(bot))