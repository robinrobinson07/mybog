import json
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin
import requests

# --- CẤU HÌNH ---
MONTH = "2025-11"
INDEX_URL = f"https://www.smogon.com/stats/{MONTH}/moveset/"
OUTFILE = "pokemon_data.json"

SECTION_NAMES = {
    "Abilities", "Items", "Spreads", "Moves", 
    "Tera Types", "Teammates", "Checks and Counters"
}

# --- REGEX COMPILING ---
BORDER_RE = re.compile(r"^\+\-+\+$")
FILENAME_RE = re.compile(r"^(?P<fmt>.+)-(?P<rating>\d+)\.txt$")
HREF_TXT_RE = re.compile(r'href="([^"]+?\.txt)"', re.I)

def fetch_text(url: str) -> str:
    try:
        r = requests.get(
            url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (compatible; smogon-stats-parser/1.0)"},
        )
        r.raise_for_status()
        r.encoding = "utf-8"
        return r.text
    except requests.RequestException as e:
        print(f"[ERR] Không tải được {url}: {e}")
        return ""

def list_txt_files(index_url: str) -> List[str]:
    html = fetch_text(index_url)
    if not html:
        return []

    found = HREF_TXT_RE.findall(html)
    files = []
    seen = set()
    for href in found:
        if href.endswith(".txt.gz"): continue
        fname = href.split("/")[-1]
        if not fname.endswith(".txt") or fname.endswith(".txt.gz"): continue
        if fname not in seen:
            seen.add(fname)
            files.append(fname)
    files.sort()
    return files

def normalize_lines(text: str) -> List[str]:
    lines = text.splitlines()
    out = []
    for i, ln in enumerate(lines):
        if i == 0: ln = ln.lstrip("\ufeff")
        ln = ln.strip()
        if ln: out.append(ln)
    return out

def clean_cell(line: str) -> str:
    return line.strip().strip("|").rstrip("|").strip()

def is_border(line: str) -> bool:
    return bool(BORDER_RE.match(line.strip()))

def find_headers(lines: List[str]) -> List[Tuple[int, str]]:
    headers = []
    for i in range(len(lines) - 2):
        if (is_border(lines[i]) and 
            lines[i+1].startswith("|") and lines[i+1].endswith("|") and 
            is_border(lines[i+2])):
            name = clean_cell(lines[i+1])
            if name and name not in SECTION_NAMES and ":" not in name:
                headers.append((i, name))
    return headers

def parse_block(blines: List[str]) -> Dict[str, Any]:
    """
    Parse thông tin chi tiết. 
    LƯU Ý: Không còn chứa trường 'name' ở đây nữa.
    """
    out: Dict[str, Any] = {
        "raw_count": None,
        "avg_weight": None,
        "viability_ceiling": None,
        "sections": {},
    }

    current_section: Optional[str] = None
    i = 0
    while i < len(blines):
        line = blines[i]
        if line.startswith("|") and line.endswith("|"):
            cell = clean_cell(line)

            if cell in SECTION_NAMES:
                current_section = cell
                out["sections"].setdefault(current_section, [])
                i += 1
                continue

            meta_match = re.match(r"^(Raw count|Avg\. weight|Viability Ceiling):\s*(.+)$", cell)
            if meta_match:
                k, v = meta_match.group(1), meta_match.group(2).strip()
                if k == "Raw count": out["raw_count"] = int(v.replace(",", ""))
                elif k == "Avg. weight": out["avg_weight"] = float(v)
                elif k == "Viability Ceiling": out["viability_ceiling"] = int(v)
                i += 1
                continue

            if current_section and cell:
                if current_section == "Checks and Counters":
                    opp_match = re.match(r"^(.+?)\s+(\d+\.\d+)\s+\(", cell)
                    entry = {"opponent": None, "raw": cell, "detail": None}
                    if opp_match:
                        entry["opponent"] = opp_match.group(1).strip()
                    
                    if i + 1 < len(blines):
                        nxt_line = blines[i+1]
                        if nxt_line.startswith("|") and nxt_line.endswith("|"):
                            nxt_cell = clean_cell(nxt_line)
                            if nxt_cell.startswith("("):
                                entry["detail"] = nxt_cell
                                i += 1
                    out["sections"][current_section].append(entry)
                else:
                    pct_match = re.match(r"^(.*?)(\s+)([\d.]+%)$", cell)
                    if pct_match:
                        out["sections"][current_section].append({
                            "name": pct_match.group(1).strip(),
                            "pct": float(pct_match.group(3)[:-1])
                        })
                    else:
                        out["sections"][current_section].append({"raw": cell})
        i += 1

    out["sections"] = {k: v for k, v in out["sections"].items() if v}
    return out

def parse_smogon_text(text: str) -> Dict[str, Dict[str, Any]]:
    """
    Trả về Dictionary: {"Tauros": {...data...}, "Snorlax": {...}}
    """
    lines = normalize_lines(text)
    headers = find_headers(lines)
    
    # Đây là Dict chứa các Pokemon, key là tên Pokemon
    pokemon_dict = {}
    
    for idx, (start, name) in enumerate(headers):
        end = headers[idx + 1][0] if idx + 1 < len(headers) else len(lines)
        block_lines = lines[start:end]
        
        # Gọi parse_block (không cần truyền name nữa)
        pokemon_data = parse_block(block_lines)
        
        # Gán vào Dict với key là tên Pokemon
        pokemon_dict[name] = pokemon_data
        
    return pokemon_dict

def main() -> None:
    filenames = list_txt_files(INDEX_URL)
    print(f"Found {len(filenames)} .txt files.")

    data_store: Dict[str, Dict[str, Any]] = {}
    processed_count = 0
    skipped_count = 0

    for fname in filenames:
        m = FILENAME_RE.match(fname)
        if not m:
            skipped_count += 1
            continue

        fmt = m.group("fmt")
        rating = m.group("rating")
        file_url = urljoin(INDEX_URL, fname)

        text = fetch_text(file_url)
        if not text:
            skipped_count += 1
            continue
            
        # parsed_data bây giờ là Dict { "Tauros": {...} }
        parsed_data = parse_smogon_text(text)

        # Cấu trúc: fmt -> rating -> Dict of Pokemons
        data_store.setdefault(fmt, {})[rating] = parsed_data
        
        processed_count += 1
        print(f"[OK] {fname} -> {fmt}/{rating} ({len(parsed_data)} pokemon)")

    # Bọc trong key "pokemon"
    final_output = {
        "pokemon": data_store
    }

    with open(OUTFILE, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)

    print(f"\nDONE: Processed {processed_count}, Skipped {skipped_count}. Saved to {OUTFILE}")

if __name__ == "__main__":
    main()