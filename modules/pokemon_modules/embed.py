import disnake

# --- ANSI COLORS ---
ANSI_RESET = "\u001b[0m"
ANSI_GRAY = "\u001b[0;30m"   # Dark Gray (Background)
ANSI_RED = "\u001b[0;31m"    # Stat < 70
ANSI_ORANGE = "\u001b[0;33m" # Stat 70-100
ANSI_GREEN = "\u001b[0;32m"  # Stat 100-130
ANSI_CYAN = "\u001b[0;36m"   # Stat > 130
ANSI_WHITE = "\u001b[0;37m"  # Text chính
ANSI_PINK = "\u001b[0;35m"   # Highlight

DITTO_SPRITE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/132.png"

def _get_stat_color(value: int) -> str:
    """Gradient Base Stats chi tiết hơn"""
    if value >= 130: return ANSI_CYAN    # Rất cao
    if value >= 100: return ANSI_GREEN   # Cao
    if value >= 80:  return ANSI_ORANGE  # Trung bình khá
    if value >= 60:  return ANSI_ORANGE  # Trung bình (dùng chung màu cam cho dễ nhìn)
    return ANSI_RED                      # Thấp

def _get_pct_color(pct: float) -> str:
    if pct >= 50: return ANSI_CYAN
    if pct >= 20: return ANSI_GREEN
    if pct >= 5:  return ANSI_ORANGE
    return ANSI_GRAY

def _make_bar(current: float, total: float, length: int = 20, color_code: str = ANSI_RESET) -> str:
    """Tạo thanh bar dài 20 ký tự: ████░░░"""
    percent = min(1.0, current / total)
    filled_len = int(length * percent)
    empty_len = length - filled_len
    return f"{color_code}{'█' * filled_len}{ANSI_GRAY}{'░' * empty_len}{ANSI_RESET}"

def _create_base_embed(smogon_data: dict, color: disnake.Color, title_suffix: str) -> disnake.Embed:
    p_name = smogon_data.get("name", "Pokemon")
    embed = disnake.Embed(title=f"{p_name} {title_suffix}", color=color)
    footer_text = []
    if smogon_data.get("raw_count"):
        footer_text.append(f"Samples: {smogon_data['raw_count']}")
    embed.set_footer(text=" | ".join(footer_text))
    return embed

# --- TAB 1: POKEDEX ---
def create_pokedex_embed(smogon_data: dict, api_data: dict, color: disnake.Color) -> disnake.Embed:
    embed = _create_base_embed(smogon_data, color, "- Pokedex Info")
    
    if not api_data:
        embed.description = "⚠️ No API Data."
        return embed

    if api_data.get("image_url"):
        embed.set_image(url=api_data["image_url"])

    types_str = " ".join([f"[{t.upper()}]" for t in api_data['types']])
    
    desc_block = (
        f"**National №**: {api_data['id']}\n"
        f"**Type**: {types_str}\n"
        f"**Species**: {api_data['species']}\n"
        f"**Height**: {api_data['height']} m\n"
        f"**Weight**: {api_data['weight']} kg"
    )
    embed.add_field(name="Pokedex Data", value=desc_block, inline=True)

    # Abilities (Có %)
    smogon_abil = smogon_data.get("sections", {}).get("Abilities", [])
    abil_lines = []
    for i, a in enumerate(smogon_abil):
        if a['pct'] < 1: continue
        col = _get_pct_color(a['pct'])
        abil_lines.append(f"{i+1}. {a['name']:<15} {col}{a['pct']:>5.1f}%{ANSI_RESET}")
    
    embed.add_field(name="Abilities", value=f"```ansi\n" + "\n".join(abil_lines) + "\n```" if abil_lines else "None", inline=True)
    
    # Base Stats (Bar Chart dài 20 ký tự)
    stats = api_data['stats']
    stat_labels = {"hp": "HP", "attack": "Atk", "defense": "Def", "special-attack": "SpA", "special-defense": "SpD", "speed": "Spe"}
    stat_lines = []
    for key, label in stat_labels.items():
        val = stats[key]
        col = _get_stat_color(val)
        # Max stat chuẩn là 180 để thanh bar trông đầy đặn
        bar = _make_bar(val, 180, length=20, color_code=col)
        stat_lines.append(f"{label:<4} {col}{val:>3}{ANSI_RESET} {bar}")
    
    total = sum(stats.values())
    embed.add_field(name="Base Stats", value=f"```ansi\n" + "\n".join(stat_lines) + f"\nTOT  {ANSI_WHITE}{total}{ANSI_RESET}\n```", inline=False)
    
    embed.add_field(name="Pokedex Entry", value=f"*{api_data['description']}*", inline=False)
    return embed

# --- TAB 2: BUILD ---
def create_build_embed(smogon_data: dict, api_data: dict, move_details: dict, color: disnake.Color) -> disnake.Embed:
    embed = _create_base_embed(smogon_data, color, "- Build")
    sections = smogon_data.get("sections", {})
    
    # Moves
    moves = sections.get("Moves", [])
    move_lines = []
    for m in moves[:10]:
        name = m.get("name")
        pct = m.get("pct", 0)
        detail = move_details.get(name.lower(), {})
        m_type = detail.get("type", "---").upper()[:3] 
        m_cat = detail.get("category", "---").upper()[:3] 
        col = _get_pct_color(pct)
        move_lines.append(f"[{m_type}] {name:<14} ({m_cat}) {ANSI_GRAY}....{ANSI_RESET} {col}{pct:>5.1f}%{ANSI_RESET}")
    embed.add_field(name="Top Moves", value=f"```ansi\n" + "\n".join(move_lines) + "\n```", inline=False)

    # Items
    items = sections.get("Items", [])
    item_lines = []
    for i in items[:6]:
        if i['name'] == "Nothing": continue
        pct = i.get("pct", 0)
        col = _get_pct_color(pct)
        item_lines.append(f"{i['name']:<18} {col}{pct:>5.1f}%{ANSI_RESET}")
    if item_lines: embed.add_field(name="Items", value=f"```ansi\n" + "\n".join(item_lines) + "\n```", inline=False)

    # Spreads
    spreads = sections.get("Spreads", [])
    spread_lines = []
    for s in spreads[:4]: 
        raw = s.get("name")
        pct = s.get("pct", 0)
        col = _get_pct_color(pct)
        try:
            nature, evs_str = raw.split(":")
            evs = evs_str.split("/")
            ev_text = f"H:{ANSI_WHITE}{evs[0]}{ANSI_RESET} A:{ANSI_WHITE}{evs[1]}{ANSI_RESET} D:{ANSI_WHITE}{evs[2]}{ANSI_RESET} SA:{ANSI_WHITE}{evs[3]}{ANSI_RESET} SD:{ANSI_WHITE}{evs[4]}{ANSI_RESET} S:{ANSI_WHITE}{evs[5]}{ANSI_RESET}"
            spread_lines.append(f"{nature:<10} {col}{pct:.1f}%{ANSI_RESET}\n{ev_text}")
        except:
            spread_lines.append(f"{raw} {col}{pct:.1f}%{ANSI_RESET}")
    if spread_lines: embed.add_field(name="Nature & EVs", value=f"```ansi\n" + "\n".join(spread_lines) + "\n```", inline=False)
    return embed

# --- GRID VIEW & COUNTERS FIXED ---

def _create_grid_embeds(main_embed: disnake.Embed, items_slice: list, sprites: list, start_index: int, api_name: str, is_counter: bool = False) -> list[disnake.Embed]:
    safe_name = api_name.replace(" ", "-").lower()
    dummy_url = f"https://pokemondb.net/pokedex/{safe_name}"
    main_embed.url = dummy_url 

    lines = []
    for i, item in enumerate(items_slice):
        idx = start_index + i + 1
        name = item.get("name") or item.get("opponent") or "Unknown"
        # Cắt tên
        display_name = (name[:12] + '..') if len(name) > 12 else name
        
        # Lấy phần trăm / điểm số
        pct = item.get("pct", 0)
        col = _get_pct_color(pct)
        
        # --- STYLE CĂN LỀ TEAMMATE (Áp dụng cho cả Teammate và Counter) ---
        # Dòng 1: Tên (Trái) ... % (Phải)
        # 1. Darkrai ...... 29.3%
        header_line = f"{idx}. {display_name:<13} {col}{pct:>5.1f}%{ANSI_RESET}"
        lines.append(header_line)
        
        if is_counter:
            # Dòng 2: Detail (Màu xám, thụt lề)
            detail = item.get("detail", "").strip("()")
            if detail:
                # Cắt ngắn detail nếu quá dài
                short_detail = (detail[:40] + '..') if len(detail) > 40 else detail
                lines.append(f"   {ANSI_GRAY}{short_detail}{ANSI_RESET}")
            else:
                lines.append(f"   {ANSI_GRAY}-{ANSI_RESET}")
        else:
            # Teammate: Dòng 2 để trống làm spacer cho đẹp
            lines.append("")

    main_embed.description = f"```ansi\n" + "\n".join(lines) + "\n```"

    # Ditto Fallback Logic
    valid_sprites = [s for s in sprites if s is not None]
    while len(valid_sprites) < 4:
        valid_sprites.append(DITTO_SPRITE)
    valid_sprites = valid_sprites[:4]

    embeds_list = [main_embed]
    main_embed.set_image(url=valid_sprites[0])
    
    for sprite_url in valid_sprites[1:4]:
        e = disnake.Embed(url=dummy_url)
        e.set_image(url=sprite_url)
        embeds_list.append(e)
        
    return embeds_list

def create_teammates_grid(smogon_data: dict, api_data: dict, items_slice: list, sprites: list, start_index: int, color: disnake.Color) -> list[disnake.Embed]:
    embed = _create_base_embed(smogon_data, color, "- Teammates")
    if not items_slice:
        embed.description = "❌ No Data."
        return [embed]
    return _create_grid_embeds(embed, items_slice, sprites, start_index, api_data['name'], is_counter=False)

def create_counters_grid(smogon_data: dict, api_data: dict, items_slice: list, sprites: list, start_index: int, color: disnake.Color) -> list[disnake.Embed]:
    embed = _create_base_embed(smogon_data, color, "- Checks & Counters")
    if not items_slice:
        embed.description = "❌ No Data."
        return [embed]
    return _create_grid_embeds(embed, items_slice, sprites, start_index, api_data['name'], is_counter=True)