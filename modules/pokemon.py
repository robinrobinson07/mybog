import disnake
from disnake.ext import commands
import asyncio
from modules.pokemon_modules import embed as p_embed, firebase_request, poke_api

firebase_service = firebase_request.PokemonService()
pokeapi_service = poke_api.PokeApiService()

class PokemonSelect(disnake.ui.Select):
    def __init__(self, total_items: int):
        options = []
        limit = min(total_items, 20)
        for i in range(0, limit, 4):
            end = min(i + 4, limit)
            options.append(disnake.SelectOption(
                label=f"Top {i+1} - {end}", 
                value=str(i), 
                description=f"Show from {i+1} to {end}"
            ))
        super().__init__(placeholder="Select page...", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: disnake.MessageInteraction):
        await self.view.update_grid_view(interaction, int(self.values[0]))

class PokemonView(disnake.ui.View):
    def __init__(self, smogon_data: dict, api_data: dict, move_cache: dict, embed_color: disnake.Color):
        super().__init__(timeout=300)
        self.smogon = smogon_data
        self.api = api_data
        self.move_cache = move_cache
        self.color = embed_color
        self.current_tab = None
        self.current_data_list = []
        self.select_menu = None

    async def update_grid_view(self, interaction: disnake.MessageInteraction, start_index: int):
        await interaction.response.defer()
        end_index = min(start_index + 4, len(self.current_data_list))
        items_slice = self.current_data_list[start_index:end_index]
        
        names = []
        for item in items_slice:
            # Lấy tên từ key chuẩn trước
            n = item.get("name") or item.get("opponent")
            
            # Chỉ khi không có key chuẩn mới lấy từ raw và cắt chuỗi
            if not n:
                raw = item.get("raw", "Unknown")
                n = raw.split()[0]
            
            # TUYỆT ĐỐI KHÔNG DÙNG: if " " in n: n = n.split()[0] 
            # Vì nó sẽ biến "Iron Valiant" thành "Iron" -> Lỗi ảnh
            
            names.append(n)
        
        sprites = await pokeapi_service.get_sprites_batch(names)
        
        if self.current_tab == 'teammates':
            embeds = p_embed.create_teammates_grid(self.smogon, self.api, items_slice, sprites, start_index, self.color)
        else:
            embeds = p_embed.create_counters_grid(self.smogon, self.api, items_slice, sprites, start_index, self.color)
            
        await interaction.edit_original_message(embeds=embeds, attachments=[], view=self)

    def _setup_dropdown(self, data_list):
        if self.select_menu in self.children:
            self.remove_item(self.select_menu)
        if len(data_list) > 4:
            self.select_menu = PokemonSelect(len(data_list))
            self.add_item(self.select_menu)
        else:
            self.select_menu = None

    @disnake.ui.button(label="Pokédex", style=disnake.ButtonStyle.primary, row=2)
    async def dex_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if self.select_menu in self.children: self.remove_item(self.select_menu)
        embed = p_embed.create_pokedex_embed(self.smogon, self.api, self.color)
        await interaction.response.edit_message(embeds=[embed], attachments=[], view=self)

    @disnake.ui.button(label="Build", style=disnake.ButtonStyle.success, row=2)
    async def build_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if self.select_menu in self.children: self.remove_item(self.select_menu)
        embed = p_embed.create_build_embed(self.smogon, self.api, self.move_cache, self.color)
        await interaction.response.edit_message(embeds=[embed], attachments=[], view=self)

    @disnake.ui.button(label="Teammates", style=disnake.ButtonStyle.secondary, row=2)
    async def team_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        self.current_tab = 'teammates'
        self.current_data_list = self.smogon.get("sections", {}).get("Teammates", [])
        self._setup_dropdown(self.current_data_list)
        await self.update_grid_view(interaction, 0)

    @disnake.ui.button(label="Checks & Counters", style=disnake.ButtonStyle.danger, row=2)
    async def counter_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        self.current_tab = 'counters'
        self.current_data_list = self.smogon.get("sections", {}).get("Checks and Counters", [])
        self._setup_dropdown(self.current_data_list)
        await self.update_grid_view(interaction, 0)

class PokemonCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if not firebase_service.is_ready:
            print("⏳ Starting background task...")
            self.bot.loop.create_task(firebase_service.build_cache())

    @commands.slash_command(name="pokemon_search", description="Search Pokemon stats (Smogon + PokéAPI)")
    async def pokemon_search(self, inter: disnake.ApplicationCommandInteraction, gen: str, format: str, rating: str, pokemon: str):
        await inter.response.defer()
        
        smogon_task = firebase_service.get_pokemon_data_async(gen, format, rating, pokemon)
        api_task = pokeapi_service.get_pokemon_static_data(pokemon)
        results = await asyncio.gather(smogon_task, api_task)
        smogon_data, api_data = results[0], results[1]

        if not smogon_data:
            await inter.edit_original_message(content=f"❌ No Smogon data found for **{pokemon}**.")
            return

        move_cache = {}
        if smogon_data.get("sections", {}).get("Moves"):
            top_moves = smogon_data["sections"]["Moves"][:10]
            move_tasks = [pokeapi_service.get_move_details(m["name"]) for m in top_moves]
            move_details = await asyncio.gather(*move_tasks)
            for i, m in enumerate(top_moves):
                if move_details[i]: move_cache[m["name"].lower()] = move_details[i]

        color = disnake.Color.from_rgb(43, 45, 49)
        embed = p_embed.create_pokedex_embed(smogon_data, api_data, color)
        view = PokemonView(smogon_data, api_data, move_cache, color)
        await inter.edit_original_message(embed=embed, view=view)

    # --- AUTOCOMPLETE ---
    @pokemon_search.autocomplete("gen")
    async def gen_autocomp(self, inter, user_input):
        options = firebase_service.get_gens_cached()
        return [g for g in options if user_input.lower() in g][:25]
    @pokemon_search.autocomplete("format")
    async def format_autocomp(self, inter, user_input):
        gen = inter.filled_options.get("gen")
        if not gen: return []
        options = firebase_service.get_formats_cached(gen)
        return [f for f in options if user_input.lower() in f.lower()][:25]
    @pokemon_search.autocomplete("rating")
    async def rating_autocomp(self, inter, user_input):
        gen = inter.filled_options.get("gen")
        fmt = inter.filled_options.get("format")
        if not gen or not fmt: return []
        ratings = firebase_service.get_ratings_cached(gen, fmt)
        options = ["all"] + ratings
        return [r for r in options if user_input in r][:25]
    @pokemon_search.autocomplete("pokemon")
    async def pokemon_autocomp(self, inter, user_input):
        gen = inter.filled_options.get("gen")
        fmt = inter.filled_options.get("format")
        rating = inter.filled_options.get("rating")
        if not all([gen, fmt, rating]): return []
        pokemons = firebase_service.get_pokemons_cached(gen, fmt, rating)
        return [p for p in pokemons if user_input.lower() in p.lower()][:25]

def setup(bot):
    bot.add_cog(PokemonCog(bot))