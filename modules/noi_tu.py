import disnake
from disnake.ext import commands
import requests
import json
from unidecode import unidecode
import re
# --- CẤU HÌNH FIREBASE URL ---
# Lưu ý: Với Firebase REST API, luôn phải thêm đuôi ".json" vào cuối đường dẫn
BASE_DB_URL = "https://vo-robin-default-rtdb.asia-southeast1.firebasedatabase.app/pokemondata/noi-tu"

# def check_dictionary(word):
#     """Kiểm tra từ có tồn tại qua Free Dictionary API"""
#     url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower()}"
#     try:
#         response = requests.get(url, timeout=3)
#         return response.status_code == 200
#     except:
#         # Nếu lỗi mạng api từ điển, tạm thời cho qua hoặc chặn tùy bạn
#         return False

def check_cambridge_dictionary(word):
    """
    Check tồn tại bằng cách chỉ đọc 1.5KB đầu tiên của HTML.
    Cực nhanh, không cần loop.
    """
    clean_word = word.strip().lower()
    word_for_url = clean_word.replace(" ", "-")
    url = f"https://dictionary.cambridge.org/dictionary/english/{word_for_url}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        with requests.get(url, headers=headers, stream=True, timeout=5) as response:
            if response.status_code != 200:
                return False
            first_chunk = next(response.iter_content(chunk_size=1500), b"")
            head_content = first_chunk.decode('utf-8', errors='ignore').lower()
            if "english meaning - cambridge dictionary" in head_content and response.url==url:
                return True
                
            return False

    except:
        return False



class NoiTu(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- HÀM HỖ TRỢ GỌI FIREBASE (REST) ---
    def get_server_data(self, guild_id):
        url = f"{BASE_DB_URL}/{guild_id}.json"
        resp = requests.get(url)
        if resp.status_code == 200 and resp.json() is not None:
            return resp.json()
        return None

    def update_server_data(self, guild_id, data):
        """Dùng PATCH để cập nhật các trường cụ thể mà không ghi đè toàn bộ"""
        url = f"{BASE_DB_URL}/{guild_id}.json"
        requests.patch(url, json=data)

    def set_server_data(self, guild_id, data):
        """Dùng PUT để ghi đè hoặc tạo mới hoàn toàn"""
        url = f"{BASE_DB_URL}/{guild_id}.json"
        requests.put(url, json=data)

    def delete_server_data(self, guild_id):
        url = f"{BASE_DB_URL}/{guild_id}.json"
        requests.delete(url)

    # --- COMMANDS ---

    @commands.slash_command(name="noitu_start", description="Bắt đầu game nối từ tại kênh này")
    @commands.has_permissions(manage_guild=True)
    async def noitu_start(self, inter: disnake.ApplicationCommandInteraction):
        guild_id = str(inter.guild_id)
        channel_id = str(inter.channel_id)
        data = self.get_server_data(guild_id)
        if data:
            await inter.response.send_message("Game đã bắt đầu trước đó rồi! Hãy reset nếu muốn bắt đầu lại.", ephemeral=True)
            return
        # Dữ liệu khởi tạo
        game_data = {
            "channel_id": channel_id,
            "last_player_id": "",
            "last_word": "",
            "history": { "START_GAME": 1 } # Dummy data để tạo object history trong json
        }

        # Gửi request PUT lên Firebase để tạo mới
        self.set_server_data(guild_id, game_data)
        
        await inter.response.send_message(
            f"Nối từ đã bắt đầu bởi <@{inter.author.id}>! Hãy gõ một từ bất kỳ <:9557kannalove:1072407455365091338>", 
            ephemeral=False
        )

    @commands.slash_command(name="noitu_reset", description="Xóa dữ liệu game của server này")
    @commands.has_permissions(manage_guild=True)
    async def noitu_reset(self, inter: disnake.ApplicationCommandInteraction):
        guild_id = str(inter.guild_id)
        
        # Gửi request DELETE lên Firebase
        self.delete_server_data(guild_id)
        
        await inter.response.send_message("🧹 Đã làm sạch dữ liệu game nối từ.")

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.author.bot:
            return

        guild_id = str(message.guild.id)
        
        # 1. Lấy dữ liệu từ Firebase về để check
        data = self.get_server_data(guild_id)

        # Nếu không có dữ liệu (chưa start) hoặc sai kênh -> Bỏ qua
        if not data:
            return
        
        setup_channel_id = data.get("channel_id")
        if str(message.channel.id) != setup_channel_id:
            return

        # --- LOGIC GAME ---
        raw_content = message.content.strip().lower()
        current_word = re.sub(r'[^a-z0-9]+$', '', unidecode(raw_content))
        player_id = str(message.author.id)

        # Chỉ bắt từ đơn (không có dấu cách)
        if " " in current_word or current_word != raw_content or current_word == "":
            return 

        last_player_id = data.get("last_player_id", "")
        last_word = data.get("last_word", "")
        # Lấy history, nếu không có thì mặc định là dict rỗng
        history = data.get("history", {}) 

        #RULE 1: Không được chơi 2 lượt liên tiếp
        if player_id == last_player_id:
            await message.reply("<:7541sageshy:1072406955466952754> Bạn vừa chơi rồi, hãy đợi người khác nhé!", delete_after=10)
            #await message.delete(delay=5) # Xóa tin nhắn sai cho sạch
            return

        # RULE 2: Kiểm tra nối đúng ký tự
        if last_word:
            required_char = last_word[-1]
            if current_word[0] != required_char:
                await message.reply(f"❌ Từ phải bắt đầu bằng **'{required_char}'**", delete_after=10)
                #await message.delete(delay=5)
                return

        # RULE 3: Kiểm tra trùng lặp (đã có trong history chưa)
        if current_word in history:
            await message.reply(f"⚠️ Từ **'{current_word}'** đã được sử dụng rồi!", delete_after=10)
            #await message.delete(delay=5)
            return

        # RULE 4: Check API từ điển
        if not check_cambridge_dictionary(current_word):
            await message.reply(f"<:Youknowintermof:1281988506113146930> Từ **'{current_word}'** không có trong từ điển!", delete_after=10)
            #await message.delete(delay=5)
            return
        # RULE 5: Nếu tận cùng là 'y' thì chửi (nhưng vẫn tính là đúng luật để game tiếp tục)
        if current_word.endswith('y'):
            await message.reply(f"dcm <@{player_id}> tự búng chim 100 cái đi <:7863crysage:1215676192951115847>")

        # --- UPDATE FIREBASE ---
        # 1. Update thông tin người chơi và từ cuối
        # 2. Thêm từ vào history (dùng PATCH để thêm key mới vào dict history mà không ghi đè cái cũ)
        
        # URL update history: .../noi-tu/{guild_id}/history.json
        requests.patch(f"{BASE_DB_URL}/{guild_id}/history.json", json={current_word: 1})
        
        # Update state game
        self.update_server_data(guild_id, {
            "last_player_id": player_id,
            "last_word": current_word
        })

        await message.add_reaction("✅")

def setup(bot: commands.Bot):
    bot.add_cog(NoiTu(bot))
