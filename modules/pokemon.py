import disnake
from disnake.ext import commands

from modules.pokemon_modules import embed as p_embed, firebase_request
poke_service = firebase_request.PokemonService()

class PokemonView(disnake.ui.View):
    def __init__(self, data: dict, embed_color: disnake.Color):
        super().__init__(timeout=180)
        self.data = data
        self.embed_color = embed_color

    # Nút Stats
    @disnake.ui.button(label="Stats", style=disnake.ButtonStyle.primary)
    async def stats_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        # Gọi hàm tạo embed từ module p_embed
        embed = p_embed.create_stats_embed(self.data, self.embed_color)
        await interaction.response.edit_message(embed=embed)

    # Nút Teammates
    @disnake.ui.button(label="Teammates", style=disnake.ButtonStyle.success)
    async def teammates_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        embed = p_embed.create_teammates_embed(self.data, self.embed_color)
        await interaction.response.edit_message(embed=embed)

    # Nút Checks & Counters
    @disnake.ui.button(label="Checks & Counters", style=disnake.ButtonStyle.danger)
    async def counters_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        embed = p_embed.create_counters_embed(self.data, self.embed_color)
        await interaction.response.edit_message(embed=embed)

class PokemonCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Sự kiện khi Bot khởi động xong.
        Bắt đầu tải cache dữ liệu (chạy ngầm, không chặn bot).
        """
        if not poke_service.is_ready:
            print("⏳ Đang khởi chạy background task tải dữ liệu Pokemon (Requests mode)...")
            self.bot.loop.create_task(poke_service.build_cache())

    @commands.slash_command(name="moveset", description="Xem thống kê Pokemon (Smogon Data)")
    async def moveset(
        self,
        inter: disnake.ApplicationCommandInteraction,
        gen: str,
        format: str,
        rating: str,
        pokemon: str
    ):
        await inter.response.defer()
        
        # Kiểm tra nếu cache chưa load xong
        if not poke_service.is_ready:
            await inter.edit_original_message(content="⚠️ Bot đang khởi động và tải dữ liệu, vui lòng thử lại sau 30 giây!")
            return

        # Lấy dữ liệu chi tiết
        # (Ở đây vẫn dùng await được vì bên kia mình đã bọc nó trong run_in_executor)
        data = await poke_service.get_pokemon_data_async(gen, format, rating, pokemon)
        
        if not data:
            await inter.edit_original_message(
                content=f"❌ Không tìm thấy dữ liệu cho **{pokemon}** tại {gen}/{format}/{rating}."
            )
            return

        # Tạo Embed mặc định
        color = disnake.Color.blue()
        embed = p_embed.create_stats_embed(data, color)
        
        # Tạo View (các nút bấm)
        view = PokemonView(data, color)

        await inter.edit_original_message(embed=embed, view=view)

    # --- AUTOCOMPLETE HANDLERS (Đọc từ RAM - Siêu nhanh) ---
    
    @moveset.autocomplete("gen")
    async def gen_autocomp(self, inter, user_input):
        options = poke_service.get_gens_cached()
        return [g for g in options if user_input.lower() in g][:25]

    @moveset.autocomplete("format")
    async def format_autocomp(self, inter, user_input):
        gen = inter.filled_options.get("gen")
        if not gen: return []
        options = poke_service.get_formats_cached(gen)
        return [f for f in options if user_input.lower() in f.lower()][:25]

    @moveset.autocomplete("rating")
    async def rating_autocomp(self, inter, user_input):
        gen = inter.filled_options.get("gen")
        fmt = inter.filled_options.get("format")
        if not gen or not fmt: return []
        ratings = poke_service.get_ratings_cached(gen, fmt)
        options = ["all"] + ratings
        return [r for r in options if user_input in r][:25]

    @moveset.autocomplete("pokemon")
    async def pokemon_autocomp(self, inter, user_input):
        gen = inter.filled_options.get("gen")
        fmt = inter.filled_options.get("format")
        rating = inter.filled_options.get("rating")
        if not all([gen, fmt, rating]): return []
        pokemons = poke_service.get_pokemons_cached(gen, fmt, rating)
        return [p for p in pokemons if user_input.lower() in p.lower()][:25]

def setup(bot):
    bot.add_cog(PokemonCog(bot))