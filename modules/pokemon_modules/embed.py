import disnake

def _format_pct_list(items: list, limit: int = 10) -> str:
    """
    Format danh sách dạng: Name: 80.5%
    Loại bỏ các mục 'Nothing', 'No Ability' để đỡ rác nếu chiếm 100%
    """
    if not items:
        return "No data"
    
    lines = []
    count = 0
    
    for i in items:
        if count >= limit: break
        
        name = i.get("name", "Unknown")
        pct = i.get("pct", 0)
        
        # Nếu item là "Nothing" hoặc "No Ability" và chiếm > 99%, có thể bỏ qua hoặc hiển thị "None"
        if name in ["Nothing", "No Ability"] and pct > 99:
            lines.append(f"_{name}_")
            count += 1
            continue

        lines.append(f"**{name}**: {pct:.2f}%")
        count += 1
        
    return "\n".join(lines)

def _create_base_embed(data: dict, color: disnake.Color, title_suffix: str = "") -> disnake.Embed:
    print(data)
    p_name = data.get("name", "Pokemon")
    # Lấy info (nếu là rating 'all' thì có text này, còn json gốc thì không có, dùng get an toàn)
    info = data.get("info", "") 
    
    embed = disnake.Embed(
        title=f"Analyze: {p_name} {title_suffix}",
        description=f"*{info}*" if info else None,
        color=color
    )
    
    # Hiển thị Raw count và Viability Ceiling (nếu có)
    footer_text = []
    if data.get("raw_count"):
        footer_text.append(f"Sample size: {data['raw_count']}")
    if data.get("viability_ceiling"):
        footer_text.append(f"Ceiling: {data['viability_ceiling']}")
        
    if footer_text:
        embed.set_footer(text=" | ".join(footer_text))
        
    return embed

def create_stats_embed(data: dict, color: disnake.Color) -> disnake.Embed:
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
    # Kiểm tra nếu Gen cũ (Gen 1) thì Tera Types thường là "Nothing" -> Có thể ẩn nếu muốn
    if "Tera Types" in sections:
        tera = sections.get("Tera Types", [])
        # Chỉ hiện nếu không phải là list rỗng hoặc toàn "Nothing"
        if tera and not (len(tera) == 1 and tera[0].get("name") == "Nothing"):
             embed.add_field(name="Tera Types", value=_format_pct_list(tera, 4), inline=False)

    # 5. Spreads (Nature/EVs)
    if "Spreads" in sections:
        spreads = sections.get("Spreads", [])
        # Spreads tên khá dài (Serious:252/...), format lại list hiển thị ít hơn
        embed.add_field(name="Nature & EV Spreads", value=_format_pct_list(spreads, 4), inline=False)

    return embed

def create_teammates_embed(data: dict, color: disnake.Color) -> disnake.Embed:
    embed = _create_base_embed(data, color, "- Teammates")
    sections = data.get("sections", {})
    teammates = sections.get("Teammates", [])

    if teammates:
        content = _format_pct_list(teammates, 12)
        embed.description = f"**Các đồng đội phổ biến:**\n\n{content}"
    else:
        embed.description = "❌ Không có dữ liệu về đồng đội."
    
    return embed

def create_counters_embed(data: dict, color: disnake.Color) -> disnake.Embed:
    """
    Xử lý đặc biệt cho Checks and Counters dựa trên JSON mẫu:
    {
      "opponent": "Articuno",
      "raw": "Articuno 60.101 (66.71±1.65)",
      "detail": "(33.8% KOed / 32.9% switched out)"
    }
    """
    embed = _create_base_embed(data, color, "- Checks & Counters")
    sections = data.get("sections", {})
    counters = sections.get("Checks and Counters", [])

    if counters:
        lines = []
        for c in counters[:10]:
            # Lấy tên đối thủ
            opp = c.get("opponent")
            if not opp:
                # Fallback nếu JSON bị lỗi, lấy từ raw
                opp = c.get("raw", "Unknown").split()[0]
            
            # Lấy thông tin chi tiết (KO/Switch)
            # detail có dạng: "(33.8% KOed / 32.9% switched out)"
            detail = c.get("detail", "")
            
            # Format dòng hiển thị
            if detail:
                # Làm gọn detail chút xíu: bỏ ngoặc đơn bao quanh nếu thích
                detail_clean = detail.strip("()")
                lines.append(f"• **{opp}** - *{detail_clean}*")
            else:
                lines.append(f"• **{opp}**")
        
        content = "\n".join(lines)
        if len(content) > 4000:
            content = content[:4000] + "..."
            
        embed.description = "**Top khắc chế (Checks & Counters):**\n" + content
    else:
        embed.description = "❌ Không có dữ liệu khắc chế."

    return embed