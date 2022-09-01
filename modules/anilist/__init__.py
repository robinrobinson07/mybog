import dis
import random
from AnilistPython import Anilist
import animec
anilist = Anilist()


import disnake

class AnilistDiscord:
    def __init__(self):
        pass
    def get_character(self,character_name):
        try:
            char=animec.Charsearch(character_name)
        except:
            return -1
        embed=disnake.Embed(title=char.title,url=char.url,color=disnake.Color.random())
        embed.set_image(url=char.image_url)
        embed.set_footer(text=", ".join(list(char.references.keys())[:2]))
        return embed
        
    def get_anime_discord(self, anime_name):
        try:
            anime_dict = anilist.get_anime(anime_name=anime_name)
            anime=animec.Anime(anime_name)
        except:
            return -1

        eng_name = anime_dict["name_english"]
        jap_name = anime_dict["name_romaji"]
        desc = anime_dict['desc']
        starting_time = anime_dict["starting_time"]
        ending_time = anime_dict["ending_time"]
        cover_image = anime_dict["cover_image"]
        banner_image=anime_dict["banner_image"]
        airing_format = anime_dict["airing_format"]
        airing_status = anime_dict["airing_status"]
        airing_ep = anime_dict["airing_episodes"]
        season = anime_dict["season"]
        genres = anime_dict["genres"]
        next_airing_ep = anime_dict["next_airing_ep"]
        anime_link = anime.url
        genres="\n".join(genres)

        next_ep_string = ''
        try:
            initial_time = next_airing_ep['timeUntilAiring']
            mins, secs = divmod(initial_time, 60)
            hours, mins = divmod(mins, 60)
            days, hours = divmod(hours, 24)
            timer = f'{days} ngày {hours} giờ {mins} phút {secs} giây'
            next_ep_num = next_airing_ep['episode']
            next_ep_string = f"Tập {next_ep_num} sẽ được công chiếu vào {timer}!\
                            \n\n[{jap_name} AniList Page]({anime_link})"
        except:
            next_ep_string = f"This anime's release date has not been confirmed!\
                            \n\n[{jap_name} AniList Page]({anime_link})"

        if desc != None and len(desc) != 0:
            desc = desc.strip().replace('<br>', '')
            desc = desc.strip().replace('<i>', '')
            desc = desc.strip().replace('</i>', '')
        
        key_list = [eng_name, jap_name, desc, starting_time, ending_time, cover_image, airing_format, airing_status, airing_ep, season, genres, next_ep_string]
        info = self.embedValueCheck(key_list)

        try:
            anime_embed = disnake.Embed(title=f"**{jap_name}**", description=eng_name, color=disnake.Color.random(),url=anime_link)
        except:
            anime_embed = disnake.Embed(title=f"**{jap_name}**", description=eng_name, color=disnake.Color.random())
            
        if banner_image!=None:   
            anime_embed.set_image(url=banner_image)
        anime_embed.set_thumbnail(url=cover_image)
        anime_embed.add_field(name="Giới Thiệu", value=info[2], inline=False)
        anime_embed.add_field(name="Ngày Khởi Chiếu", value=info[3], inline=True)
        anime_embed.add_field(name="Ngày Kết Thúc", value=info[4], inline=True)
        anime_embed.add_field(name="Mùa", value=info[9], inline=True)

        try:
            episodes = int(airing_ep)

            if episodes > 1:
                anime_embed.add_field(name="Định Dạng Phát Sóng", value=f"{info[6]} ({airing_ep} tập)", inline=True)
            else:
                anime_embed.add_field(name="Định Dạng Phát Sóng", value=f"{info[6]} ({airing_ep} tập)", inline=True)

        except:
            anime_embed.add_field(name="Định Dạng Phát Sóng", value=info[6], inline=True)


        if info[7].upper() == 'FINISHED':
            anime_embed.add_field(name="Trạng Thái Phát Sóng", value=info[7], inline=True)
            anime_embed.add_field(name="Xếp hạng",value=anime.ranked)
            anime_embed.add_field(name="Giới hạn độ tuổi",value=anime.rating)
            anime_embed.add_field(name="Tập Kế Tiếp ~", value=f"Bộ anime này đã kết thúc!",inline=False)

        else:
            anime_embed.add_field(name="Trạng Thái Phát Sóng", value=info[7], inline=True)
            anime_embed.add_field(name="Xếp hạng",value=anime.ranked)
            anime_embed.add_field(name="Giới hạn độ tuổi",value=anime.rating)
            anime_embed.add_field(name="Tập Kế Tiếp ~", value=info[11], inline=False)

        anime_embed.set_footer(text="hãy donate cho nhà phát triển bot này vì anh ấy tạch gacha ( ಠ‿<)",icon_url="https://images-wixmp-ed30a86b8c4ca887773594c2.wixmp.com/f/3cbd1933-0f04-45ea-b103-274ffa86cd3c/dera7vx-8fe91262-a09d-47fb-9892-11355fddb803.png?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1cm46YXBwOjdlMGQxODg5ODIyNjQzNzNhNWYwZDQxNWVhMGQyNmUwIiwiaXNzIjoidXJuOmFwcDo3ZTBkMTg4OTgyMjY0MzczYTVmMGQ0MTVlYTBkMjZlMCIsIm9iaiI6W1t7InBhdGgiOiJcL2ZcLzNjYmQxOTMzLTBmMDQtNDVlYS1iMTAzLTI3NGZmYTg2Y2QzY1wvZGVyYTd2eC04ZmU5MTI2Mi1hMDlkLTQ3ZmItOTg5Mi0xMTM1NWZkZGI4MDMucG5nIn1dXSwiYXVkIjpbInVybjpzZXJ2aWNlOmZpbGUuZG93bmxvYWQiXX0.4hajJyTVzWTc8QecEDJK_xlq3kuQ6wjmZLm9k9xGfZ4")
        anime_embed.add_field(name="Thể Loại", value=info[10], inline=True)
        anime_embed.add_field(name="Các nhà xản xuất",value="\n".join(anime.producers))
        return anime_embed


    def embedValueCheck(self, key_list) -> list:
        MAXLEN = 1024
        index = 0
        for i in key_list:

            
            if i == None:
                key_list[index] = 'Not Available'
            if isinstance(i, str) and len(i) == 0:
                key_list[index] = 'Not Available'

            
            if isinstance(i, str) and len(i) >= MAXLEN:
                toCrop = (len(i) - MAXLEN) + 3
                key_list[index] = i[: -toCrop] + "..."
                        
            index += 1
        return key_list