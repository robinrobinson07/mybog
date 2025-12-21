import disnake

def _format_pct_list(items: list, limit: int = 10) -> str:
    """Hàm phụ trợ: Format danh sách có % (Moves, Abilities...)"""
    if not items:
        return "No data"
    lines = []
    # Chỉ lấy top 'limit' phần tử
    for i in items[:limit]:
        name = i.get("name", "Unknown")
        pct = i.get("pct", 0)
        lines.append(f"**{name}**: {pct:.2f}%")
    return "\n".join(lines)

def _create_base_embed(data: dict, color: disnake.Color, title_suffix: str = "") -> disnake.Embed:
    """Hàm phụ trợ: Tạo khung Embed cơ bản (Title, Footer)"""
    p_name = data.get("name", "Pokemon")
    # Nếu là rating 'all', info sẽ là 'Average Stats...', ngược lại lấy từ path
    info = data.get("info", "") 
    
    embed = disnake.Embed(
        title=f"Analyze: {p_name} {title_suffix}",
        description=f"*{info}*" if info else None,
        color=color
    )
    
    if data.get("raw_count"):
        embed.set_footer(text=f"Sample size (Raw Count): {data['raw_count']}")
    
    return embed

def create_stats_embed(data: dict, color: disnake.Color) -> disnake.Embed:
    """Tạo Embed cho nút 'Stats' (General)"""
    embed = _create_base_embed(data, color, "- General Stats")
    sections = data.get("sections", {})

    # 1. Moves
    moves = sections.get("Moves", [])
    embed.add_field(name="Top Moves", value=_format_pct_list(moves, 6), inline=True)

    # 2. Abilities
    abilities = sections.get("Abilities", [])
    embed.add_field(name="Abilities", value=_format_pct_list(abilities, 4), inline=True)

    # 3. Items
    items = sections.get("Items", [])
    embed.add_field(name="Items", value=_format_pct_list(items, 4), inline=True)

    # 4. Tera Types (Gen 9)
    if "Tera Types" in sections:
        tera = sections.get("Tera Types", [])
        embed.add_field(name="Tera Types", value=_format_pct_list(tera, 4), inline=False)

    # 5. Spreads (Nature/EVs)
    if "Spreads" in sections:
        spreads = sections.get("Spreads", [])
        embed.add_field(name="Nature & EV Spreads", value=_format_pct_list(spreads, 4), inline=False)

    return embed

def create_teammates_embed(data: dict, color: disnake.Color) -> disnake.Embed:
    """Tạo Embed cho nút 'Teammates'"""
    embed = _create_base_embed(data, color, "- Teammates")
    sections = data.get("sections", {})
    teammates = sections.get("Teammates", [])

    if teammates:
        content = _format_pct_list(teammates, 15) # Lấy nhiều hơn chút
        embed.description = f"**Các đồng đội phổ biến:**\n\n{content}"
    else:
        embed.description = "❌ Không có dữ liệu về đồng đội."
    
    return embed

def create_counters_embed(data: dict, color: disnake.Color) -> disnake.Embed:
    """Tạo Embed cho nút 'Checks & Counters'"""
    embed = _create_base_embed(data, color, "- Checks & Counters")
    sections = data.get("sections", {})
    counters = sections.get("Checks and Counters", [])

    if counters:
        lines = []
        # Cấu trúc C&C: [{"opponent": "Zapdos", "detail": "..."}, ...]
        for c in counters[:10]:
            opp = c.get("opponent", "Unknown")
            # Tùy chỉnh hiển thị thêm nếu muốn (ví dụ thêm detail)
            lines.append(f"• **{opp}**")
        
        embed.description = "**Top khắc chế (Checks & Counters):**\n" + "\n".join(lines)
    else:
        embed.description = "❌ Không có dữ liệu khắc chế."

    return embed