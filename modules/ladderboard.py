import asyncio
from typing import Dict

import disnake
from disnake.ext import commands
import requests

# ====== CẤU HÌNH FIREBASE (REST) ======
FIREBASE_URL = "https://vo-robin-default-rtdb.asia-southeast1.firebasedatabase.app"
TIMEOUT = 10  # seconds cho mỗi request

def _url(path: str) -> str:
    # đảm bảo không có // dư
    return f"{FIREBASE_URL.rstrip('/')}/{path.lstrip('/')}.json"


class Ladderboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._lock = asyncio.Lock()

    def _safe_int(self, x, default=0):
        try:
            return int(x)
        except Exception:
            return default

    def _safe_float(self, x, default=0.0):
        try:
            return float(x)
        except Exception:
            return default

    # ------------------ synchronous helpers using requests ------------------
    def _get_bucket_sync(self, guild_id: int) -> Dict[str, float]:
        """GET /ladderboard/{guild_id}.json"""
        try:
            url = _url(f"ladderboard/{guild_id}")
            r = requests.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict):
                return data
            return {}
        except requests.RequestException:
            # network / firebase error -> trả về rỗng (caller có thể xử lý)
            return {}

    def _set_user_score_sync(self, guild_id: int, user_id: int, points: float) -> bool:
        """PUT /ladderboard/{guild_id}/{user_id}.json"""
        try:
            url = _url(f"ladderboard/{guild_id}/{user_id}")
            r = requests.put(url, json=points, timeout=TIMEOUT)
            r.raise_for_status()
            return True
        except requests.RequestException:
            return False

    def _delete_user_sync(self, guild_id: int, user_id: int) -> bool:
        """DELETE /ladderboard/{guild_id}/{user_id}.json"""
        try:
            url = _url(f"ladderboard/{guild_id}/{user_id}")
            r = requests.delete(url, timeout=TIMEOUT)
            r.raise_for_status()
            return True
        except requests.RequestException:
            return False

    def _delete_bucket_sync(self, guild_id: int) -> bool:
        """DELETE /ladderboard/{guild_id}.json"""
        try:
            url = _url(f"ladderboard/{guild_id}")
            r = requests.delete(url, timeout=TIMEOUT)
            r.raise_for_status()
            return True
        except requests.RequestException:
            return False

    # ------------------ async wrappers (to avoid blocking event loop) ------------------
    async def _get_bucket(self, guild_id: int) -> Dict[str, float]:
        return await asyncio.to_thread(self._get_bucket_sync, guild_id)

    async def _set_user_score(self, guild_id: int, user_id: int, points: float) -> bool:
        return await asyncio.to_thread(self._set_user_score_sync, guild_id, user_id, points)

    async def _delete_user(self, guild_id: int, user_id: int) -> bool:
        return await asyncio.to_thread(self._delete_user_sync, guild_id, user_id)

    async def _delete_bucket(self, guild_id: int) -> bool:
        return await asyncio.to_thread(self._delete_bucket_sync, guild_id)

    # ================= COMMANDS =================

    @commands.slash_command(
        name="ladder_update",
        description="(Mod) Cập nhật (set) điểm ladderboard cho 1 người"
    )
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def ladder_update(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        points: float
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Lệnh này chỉ dùng trong server.", ephemeral=True)
            return

        if points < 0:
            await interaction.response.send_message("Điểm phải >= 0.", ephemeral=True)
            return

        async with self._lock:
            ok = await self._set_user_score(interaction.guild.id, user.id, float(points))

        if not ok:
            await interaction.response.send_message("Lỗi khi lưu dữ liệu lên Firebase.", ephemeral=True)
            return

        embed = disnake.Embed(
            title="✅ Ladderboard cập nhật",
            description=f"Đã set điểm cho {user.mention} = **{points}**",
            color=disnake.Color.random()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(
        name="ladder_add",
        description="(Mod) Cộng thêm điểm ladderboard cho 1 người"
    )
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def ladder_add(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        points: float
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Lệnh này chỉ dùng trong server.", ephemeral=True)
            return

        if points <= 0:
            await interaction.response.send_message("Điểm cộng phải > 0.", ephemeral=True)
            return

        async with self._lock:
            bucket = await self._get_bucket(interaction.guild.id)
            current = self._safe_float(bucket.get(str(user.id), 0.0))
            new_score = current + float(points)
            ok = await self._set_user_score(interaction.guild.id, user.id, new_score)

        if not ok:
            await interaction.response.send_message("Lỗi khi lưu dữ liệu lên Firebase.", ephemeral=True)
            return

        embed = disnake.Embed(
            title="➕ Ladderboard cộng điểm",
            description=f"{user.mention} được cộng **{points}** điểm → **{new_score}**",
            color=disnake.Color.random()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(
        name="ladder_delete",
        description="(Mod) Xóa điểm ladderboard của 1 người"
    )
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def ladder_delete(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        user: disnake.Member
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Lệnh này chỉ dùng trong server.", ephemeral=True)
            return

        async with self._lock:
            bucket = await self._get_bucket(interaction.guild.id)
            if str(user.id) not in bucket:
                await interaction.response.send_message(
                    f"{user.mention} chưa có điểm để xóa.",
                    ephemeral=True
                )
                return
            ok = await self._delete_user(interaction.guild.id, user.id)

        if not ok:
            await interaction.response.send_message("Lỗi khi xóa dữ liệu trên Firebase.", ephemeral=True)
            return

        embed = disnake.Embed(
            title="🗑️ Ladderboard đã xóa",
            description=f"Đã xóa điểm của {user.mention}.",
            color=disnake.Color.random()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(
        name="ladderboard_reset",
        description="(Mod) Xóa toàn bộ điểm ladderboard của server"
    )
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def ladderboard_reset(
        self,
        interaction: disnake.ApplicationCommandInteraction
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Lệnh này chỉ dùng trong server.", ephemeral=True)
            return

        async with self._lock:
            ok = await self._delete_bucket(interaction.guild.id)

        if not ok:
            await interaction.response.send_message("Lỗi khi xóa dữ liệu trên Firebase.", ephemeral=True)
            return

        embed = disnake.Embed(
            title="♻️ Ladderboard đã reset",
            description="Đã xóa toàn bộ điểm của server.",
            color=disnake.Color.random()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(
        name="ladderboard",
        description="Hiện bảng xếp hạng điểm trong server"
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ladderboard(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        limit: int = 10
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Lệnh này chỉ dùng trong server.", ephemeral=True)
            return

        if limit < 1:
            limit = 1
        if limit > 25:
            limit = 25

        async with self._lock:
            bucket = await self._get_bucket(interaction.guild.id)

        items = []
        for uid, pts in bucket.items():
            items.append((self._safe_int(uid, 0), self._safe_float(pts, 0.0)))

        items.sort(key=lambda x: (-x[1], x[0]))
        top = items[:limit]

        embed = disnake.Embed(
            title=f"🏆 Ladderboard | {interaction.guild.name}",
            color=disnake.Color.random()
        )

        if not top:
            embed.description = "Chưa có ai có điểm. Mod dùng `/ladder_update` hoặc `/ladder_add` để set điểm."
            await interaction.response.send_message(embed=embed)
            return

        lines = []
        for i, (uid, pts) in enumerate(top, start=1):
            lines.append(f"**#{i}** <@{uid}>  |  **{pts}** điểm")

        embed.description = "\n".join(lines)
        embed.set_footer(text=f"Top {len(top)} • dùng /ladderboard limit để đổi số lượng")
        await interaction.response.send_message(embed=embed)

    @ladder_update.error
    @ladderboard_reset.error
    @ladder_delete.error
    async def _mod_cmd_error(self, interaction: disnake.ApplicationCommandInteraction, error):
        if isinstance(error, commands.MissingPermissions):
            await interaction.response.send_message("Không đủ quyền (cần Manage Server).", ephemeral=True)
            return
        raise error


def setup(bot: commands.Bot):
    bot.add_cog(Ladderboard(bot))
