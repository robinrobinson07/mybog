import disnake
from disnake.ext import commands
import asyncio
import random

choice = [
 "https://cdnb.artstation.com/p/assets/images/images/016/599/339/original/charlie-erholm-starters-grookey-2.gif?1552759472","https://cdna.artstation.com/p/assets/images/images/016/599/366/original/charlie-erholm-starters-scorbunny-1.gif?1552759581","https://cdnb.artstation.com/p/assets/images/images/016/599/365/original/charlie-erholm-starters-sobble.gif?1552759579"
]
class cfs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(name="confession",description="Nêu ra những bí mật của bạn! Nhưng không ai biết là bạn nói đâu.")
    @commands.cooldown(1,5,commands.BucketType.user)
    async def cfs(self, interaction: disnake.ApplicationCommandInteraction,chủ_đề:str):
        id=interaction.channel.id
        chude=chủ_đề
        response = disnake.Embed(
            title=(f"Ghi Confession Của Bạn Đi {interaction.user.display_name} !"),
            color=disnake.Color.blue()
        )
        response.set_author(name=interaction.user.name,icon_url=interaction.user.avatar.url)
        response.set_thumbnail(url=random.choice(choice))
        response.set_footer(text="hãy donate cho nhà phát triển bot này vì anh ấy tạch gacha ( ಠ‿<)\n-Cẩn thận lệnh sẽ bị hủy sau 120s\n",icon_url="https://images-wixmp-ed30a86b8c4ca887773594c2.wixmp.com/f/3cbd1933-0f04-45ea-b103-274ffa86cd3c/dera7vx-8fe91262-a09d-47fb-9892-11355fddb803.png?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1cm46YXBwOjdlMGQxODg5ODIyNjQzNzNhNWYwZDQxNWVhMGQyNmUwIiwiaXNzIjoidXJuOmFwcDo3ZTBkMTg4OTgyMjY0MzczYTVmMGQ0MTVlYTBkMjZlMCIsIm9iaiI6W1t7InBhdGgiOiJcL2ZcLzNjYmQxOTMzLTBmMDQtNDVlYS1iMTAzLTI3NGZmYTg2Y2QzY1wvZGVyYTd2eC04ZmU5MTI2Mi1hMDlkLTQ3ZmItOTg5Mi0xMTM1NWZkZGI4MDMucG5nIn1dXSwiYXVkIjpbInVybjpzZXJ2aWNlOmZpbGUuZG93bmxvYWQiXX0.4hajJyTVzWTc8QecEDJK_xlq3kuQ6wjmZLm9k9xGfZ4")
        await interaction.response.send_message(content="Vui lòng xem tin nhắn bot vừa gửi riêng cho bạn", ephemeral=True)
        demand = await interaction.user.send(embed=response)
        try:
            msg = await self.bot.wait_for(
                'message',
                timeout=150,
                check=lambda x: x.channel == interaction.user.dm_channel and x.author == interaction.author,
            )
            
            if msg:
                chủ_đề=chude
                channel = self.bot.get_channel(id)
                response = disnake.Embed(
                    title=(f"Ok. Câu lệnh bạn vừa sử dụng sẽ không ai thấy đâu. đang gửi confession vào kênh #{channel.name} ở {channel.guild.name}"),
                 )
                await interaction.user.send(embed=response)
                print(f"Sending message with content {msg.content} to channel #{channel.name} by {interaction.author}")
                embed = disnake.Embed(title=f"Confession\n***Chủ đề: {chủ_đề}***", description=f"**{msg.content}**", color=disnake.Colour.random())
                embed.set_footer(text="**Mọi Cfs đều là ẩn danh**",icon_url="https://images-wixmp-ed30a86b8c4ca887773594c2.wixmp.com/f/3cbd1933-0f04-45ea-b103-274ffa86cd3c/dera7vx-8fe91262-a09d-47fb-9892-11355fddb803.png?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1cm46YXBwOjdlMGQxODg5ODIyNjQzNzNhNWYwZDQxNWVhMGQyNmUwIiwiaXNzIjoidXJuOmFwcDo3ZTBkMTg4OTgyMjY0MzczYTVmMGQ0MTVlYTBkMjZlMCIsIm9iaiI6W1t7InBhdGgiOiJcL2ZcLzNjYmQxOTMzLTBmMDQtNDVlYS1iMTAzLTI3NGZmYTg2Y2QzY1wvZGVyYTd2eC04ZmU5MTI2Mi1hMDlkLTQ3ZmItOTg5Mi0xMTM1NWZkZGI4MDMucG5nIn1dXSwiYXVkIjpbInVybjpzZXJ2aWNlOmZpbGUuZG93bmxvYWQiXX0.4hajJyTVzWTc8QecEDJK_xlq3kuQ6wjmZLm9k9xGfZ4")
                embed.set_thumbnail(url="https://i.pinimg.com/originals/b9/ff/14/b9ff1465b89fc94fb4b28035798614ff.gif")
                await channel.send(embed=embed)
        except asyncio.TimeoutError:
                response = disnake.Embed(
                    title=("```Quá thời hạn,xóa sau 5 giây```"),
                 )
                await interaction.user.send(embed=response, delete_after=5)
                await demand.delete()       

def setup(bot):
    bot.add_cog(cfs(bot))
