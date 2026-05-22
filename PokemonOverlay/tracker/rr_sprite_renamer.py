from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from urllib.request import urlopen

RR_DATA_URL = "https://raw.githubusercontent.com/JwowSquared/Radical-Red-Pokedex/master/data.js"


@dataclass
class SpeciesEntry:
    species_id: int
    key: str
    dex_id: Optional[int]
    order: int


def decode_js_string(value: str) -> str:
    try:
        return bytes(value, "utf-8").decode("unicode_escape")
    except Exception:
        return value


def normalize_token(value: str) -> str:
    token = value.strip()
    token = token.replace("\u2019", "'").replace("\u2018", "'")
    token = token.replace("'", "")
    token = token.replace(".", "")
    token = token.replace(":", "")
    token = re.sub(r"[\s\-]+", "_", token)
    token = re.sub(r"[^A-Za-z0-9_]", "", token)
    token = re.sub(r"_+", "_", token).strip("_")
    return token.upper()


def find_balanced_block(text: str, open_index: int) -> str:
    depth = 0
    in_str: Optional[str] = None
    escape = False
    for i in range(open_index, len(text)):
        ch = text[i]
        if in_str is not None:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
            continue

        if ch in ("'", '"'):
            in_str = ch
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[open_index : i + 1]

    raise ValueError("Unbalanced braces while parsing species block")


def split_species_entries(species_obj: str) -> Dict[int, str]:
    entries: Dict[int, str] = {}
    i = 1  # skip opening '{'
    n = len(species_obj)

    while i < n - 1:
        while i < n and species_obj[i] in " \t\r\n,":
            i += 1
        if i >= n - 1:
            break

        key_start = i
        while i < n and species_obj[i].isdigit():
            i += 1
        if key_start == i:
            i += 1
            continue

        key_text = species_obj[key_start:i]

        while i < n and species_obj[i] in " \t\r\n":
            i += 1
        if i >= n or species_obj[i] != ":":
            continue
        i += 1

        while i < n and species_obj[i] in " \t\r\n":
            i += 1
        if i >= n or species_obj[i] != "{":
            continue

        obj_start = i
        obj_text = find_balanced_block(species_obj, obj_start)
        i = obj_start + len(obj_text)

        try:
            sid = int(key_text)
        except ValueError:
            continue
        entries[sid] = obj_text

    return entries


def parse_species_entries(js_text: str) -> List[SpeciesEntry]:
    marker_positions = [js_text.find("'species':{"), js_text.find('"species":{')]
    marker_positions = [p for p in marker_positions if p >= 0]
    if not marker_positions:
        raise ValueError("Could not find species object in RR data")

    marker = min(marker_positions)
    open_brace = js_text.find("{", marker)
    if open_brace < 0:
        raise ValueError("Malformed RR species object")

    species_obj = find_balanced_block(js_text, open_brace)
    raw_entries = split_species_entries(species_obj)

    out: List[SpeciesEntry] = []
    key_re = re.compile(r"['\"]key['\"]\s*:\s*'((?:\\.|[^'])*)'")
    key_re_dq = re.compile(r"['\"]key['\"]\s*:\s*\"((?:\\.|[^\"])*)\"")
    dex_re = re.compile(r"['\"]dexID['\"]\s*:\s*(\d+)")
    order_re = re.compile(r"['\"]order['\"]\s*:\s*(\d+)")

    for sid, obj in raw_entries.items():
        m = key_re.search(obj) or key_re_dq.search(obj)
        if not m:
            continue
        key = decode_js_string(m.group(1))

        dex_match = dex_re.search(obj)
        dex_id = int(dex_match.group(1)) if dex_match else None

        order_match = order_re.search(obj)
        order = int(order_match.group(1)) if order_match else 0

        out.append(SpeciesEntry(species_id=sid, key=key, dex_id=dex_id, order=order))

    if not out:
        raise ValueError("No species entries parsed from RR data")

    return out


def load_rr_data(path: Path, download_if_missing: bool) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")

    if not download_if_missing:
        raise FileNotFoundError(f"RR data file not found: {path}")

    with urlopen(RR_DATA_URL, timeout=20) as resp:
        data = resp.read().decode("utf-8", errors="replace")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")
    return data


def build_alias_plan(entries: List[SpeciesEntry], folder: Path) -> List[tuple[Path, Path]]:
    by_dex: Dict[int, List[SpeciesEntry]] = {}
    for e in entries:
        if e.dex_id is None:
            continue
        by_dex.setdefault(e.dex_id, []).append(e)

    base_token_by_dex: Dict[int, str] = {}
    for dex_id, group in by_dex.items():
        group_sorted = sorted(group, key=lambda x: (x.order, x.species_id))
        base = next((g for g in group_sorted if g.order == 0), group_sorted[0])
        base_token_by_dex[dex_id] = normalize_token(base.key)

    file_map: Dict[str, Path] = {p.stem.upper(): p for p in folder.glob("*.png")}

    moves: List[tuple[Path, Path]] = []
    target_taken = {p.name.upper() for p in folder.glob("*.png")}

    for e in sorted(entries, key=lambda x: x.species_id):
        rr_token = normalize_token(e.key)
        if not rr_token:
            continue

        target = folder / f"{rr_token}.png"
        if target.name.upper() in target_taken:
            continue

        legacy_candidates: List[str] = []
        if e.dex_id is not None:
            base = base_token_by_dex.get(e.dex_id)
            if base:
                if e.order > 0:
                    legacy_candidates.append(f"{base}_{e.order}")
                else:
                    legacy_candidates.append(base)

        legacy_candidates.append(rr_token)
        legacy_candidates.append(rr_token.replace("_", ""))

        source_path: Optional[Path] = None
        for cand in legacy_candidates:
            p = file_map.get(cand.upper())
            if p is not None and p != target:
                source_path = p
                break

        if source_path is None:
            continue

        moves.append((source_path, target))
        target_taken.add(target.name.upper())

    return moves


def apply_moves(moves: List[tuple[Path, Path]], mode: str) -> None:
    for src, dst in moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if mode == "copy":
            shutil.copy2(src, dst)
        elif mode == "rename":
            src.rename(dst)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate/apply RR dex-based sprite aliases")
    parser.add_argument(
        "--rr-data",
        default="../_rr_data_tmp.js",
        help="Path to Radical Red data.js (relative to this script)",
    )
    parser.add_argument(
        "--download-if-missing",
        action="store_true",
        help="Download RR data.js if local file does not exist",
    )
    parser.add_argument(
        "--mode",
        choices=["plan", "copy", "rename"],
        default="plan",
        help="plan=print changes only; copy=create aliases; rename=rename files",
    )
    parser.add_argument(
        "--folders",
        nargs="+",
        default=["../../Front", "../../Front shiny", "../../Icons", "../../Icons shiny"],
        help="Sprite folders to process",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max moves per folder for testing (0 = no limit)",
    )

    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    rr_path = (script_dir / args.rr_data).resolve()

    try:
        rr_text = load_rr_data(rr_path, download_if_missing=args.download_if_missing)
        entries = parse_species_entries(rr_text)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Parsed RR entries: {len(entries)}")

    total_moves = 0
    for folder_arg in args.folders:
        folder = (script_dir / folder_arg).resolve()
        if not folder.exists():
            print(f"[skip] missing folder: {folder}")
            continue

        moves = build_alias_plan(entries, folder)
        if args.limit > 0:
            moves = moves[: args.limit]

        total_moves += len(moves)
        print(f"\n[{folder}] planned: {len(moves)}")

        for src, dst in moves[:25]:
            print(f"  {src.name} -> {dst.name}")
        if len(moves) > 25:
            print(f"  ... {len(moves) - 25} more")

        if args.mode in ("copy", "rename") and moves:
            apply_moves(moves, mode=args.mode)
            print(f"  applied mode={args.mode}")

    print(f"\nTotal planned moves: {total_moves}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
