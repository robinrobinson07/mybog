import json
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests

MONTH = "2025-11"
INDEX_URL = f"https://www.smogon.com/stats/{MONTH}/moveset/"
OUTFILE = "pokemon_data.json"

SECTION_NAMES = {
    "Abilities",
    "Items",
    "Spreads",
    "Moves",
    "Tera Types",
    "Teammates",
    "Checks and Counters",
}

BORDER_RE = re.compile(r"^\+\-+\+$")                     # +------+
FILENAME_RE = re.compile(r"^(?P<fmt>.+)-(?P<rating>\d+)\.txt$")
HREF_TXT_RE = re.compile(r'href="([^"]+?\.txt)"', re.I)  # bắt link .txt
# lưu ý: index page có cả .txt.gz; ta sẽ lọc

def fetch_text(url: str) -> str:
    r = requests.get(
        url,
        timeout=60,
        headers={"User-Agent": "Mozilla/5.0 (compatible; smogon-stats-parser/1.0)"},
    )
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text

def list_txt_files(index_url: str) -> List[str]:
    html = fetch_text(index_url)

    found = HREF_TXT_RE.findall(html)
    # found có thể gồm cả "gen1ou-0.txt" và đôi khi dạng path, nên normalize bằng urljoin
    # nhưng ta chỉ cần filename => tách basename
    files = []
    seen = set()
    for href in found:
        # bỏ .txt.gz (cái này regex đã bắt .txt, nhưng một số server có thể để href="x.txt.gz"
        # và regex vẫn match ".txt" phần đầu, nên check cứng)
        if href.endswith(".txt.gz"):
            continue

        # lấy filename (phần cuối)
        fname = href.split("/")[-1]
        if not fname.endswith(".txt"):
            continue
        if fname.endswith(".txt.gz"):
            continue

        if fname not in seen:
            seen.add(fname)
            files.append(fname)

    # sort để output ổn định
    files.sort()
    return files

def normalize_lines(text: str) -> List[str]:
    lines = text.splitlines()
    out = []
    for i, ln in enumerate(lines):
        if i == 0:
            ln = ln.lstrip("\ufeff")
        ln = ln.strip()
        if ln:
            out.append(ln)
    return out

def clean_cell(line: str) -> str:
    return line.strip().strip("|").rstrip("|").strip()

def is_border(line: str) -> bool:
    return bool(BORDER_RE.match(line.strip()))

def is_header_triplet(lines: List[str], i: int) -> Optional[str]:
    if i + 2 >= len(lines):
        return None
    if not is_border(lines[i]):
        return None
    if not (lines[i + 1].startswith("|") and lines[i + 1].endswith("|")):
        return None
    if not is_border(lines[i + 2]):
        return None

    name = clean_cell(lines[i + 1])
    if not name:
        return None
    if name in SECTION_NAMES:
        return None
    if ":" in name:
        return None
    return name

def find_headers(lines: List[str]) -> List[Tuple[int, str]]:
    headers = []
    for i in range(len(lines) - 2):
        name = is_header_triplet(lines, i)
        if name:
            headers.append((i, name))
    return headers

def parse_blocks(lines: List[str]) -> List[Tuple[str, List[str]]]:
    headers = find_headers(lines)
    blocks = []
    for idx, (start, name) in enumerate(headers):
        end = headers[idx + 1][0] if idx + 1 < len(headers) else len(lines)
        blocks.append((name, lines[start:end]))
    return blocks

def parse_block(name: str, blines: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "name": name,
        "raw_count": None,
        "avg_weight": None,
        "viability_ceiling": None,
        "sections": {},
    }

    section: Optional[str] = None
    i = 0
    while i < len(blines):
        line = blines[i]

        if line.startswith("|") and line.endswith("|"):
            cell = clean_cell(line)

            if cell in SECTION_NAMES:
                section = cell
                out["sections"].setdefault(section, [])
                i += 1
                continue

            m = re.match(r"^(Raw count|Avg\. weight|Viability Ceiling):\s*(.+)$", cell)
            if m:
                k, v = m.group(1), m.group(2).strip()
                if k == "Raw count":
                    out["raw_count"] = int(v.replace(",", ""))
                elif k == "Avg. weight":
                    out["avg_weight"] = float(v)
                elif k == "Viability Ceiling":
                    out["viability_ceiling"] = int(v)
                i += 1
                continue

            if section in {"Abilities", "Items", "Spreads", "Moves", "Tera Types", "Teammates"}:
                if cell:
                    m2 = re.match(r"^(.*?)(\s+)([\d.]+%)$", cell)
                    if m2:
                        out["sections"][section].append(
                            {"name": m2.group(1).strip(), "pct": float(m2.group(3)[:-1])}
                        )
                    else:
                        out["sections"][section].append({"raw": cell})
                i += 1
                continue

            if section == "Checks and Counters":
                if cell:
                    entry = {"opponent": None, "raw": cell, "detail": None}
                    m3 = re.match(r"^(.+?)\s+(\d+\.\d+)\s+\(", cell)
                    if m3:
                        entry["opponent"] = m3.group(1).strip()

                    if i + 1 < len(blines) and blines[i + 1].startswith("|") and blines[i + 1].endswith("|"):
                        nxt = clean_cell(blines[i + 1])
                        if nxt.startswith("("):
                            entry["detail"] = nxt
                            i += 1

                    out["sections"][section].append(entry)
                i += 1
                continue

        i += 1

    out["sections"] = {k: v for k, v in out["sections"].items() if v}
    return out

def parse_smogon(text: str) -> List[Dict[str, Any]]:
    lines = normalize_lines(text)
    blocks = parse_blocks(lines)
    return [parse_block(name, blines) for name, blines in blocks]

def fetch_and_build() -> None:
    filenames = list_txt_files(INDEX_URL)
    print(f"Found {len(filenames)} .txt files (excluding .gz)")

    out: Dict[str, Dict[str, Any]] = {}
    ok = 0
    skipped = 0

    for fname in filenames:
        m = FILENAME_RE.match(fname)
        if not m:
            skipped += 1
            continue

        fmt = m.group("fmt")
        rating = m.group("rating")
        file_url = urljoin(INDEX_URL, fname)

        text = fetch_text(file_url)
        data = parse_smogon(text)

        out.setdefault(fmt, {})[rating] = data
        ok += 1
        print(f"[OK] {fname} -> {fmt}/{rating} ({len(data)} pokemon)")

    with open(OUTFILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\nDONE: fetched {ok} files, skipped {skipped}, wrote {OUTFILE}")

if __name__ == "__main__":
    fetch_and_build()
