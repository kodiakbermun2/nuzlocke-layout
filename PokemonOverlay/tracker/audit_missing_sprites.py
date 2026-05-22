from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Set

from rr_sprite_renamer import normalize_token, parse_species_entries


FORM_ALIAS_MAP = {
    "AEGISLASH_BLADE": ["AEGISLASH_1"],
    "AEGISLASH_SHIELD": ["AEGISLASH"],
    "ARCEUS_FIRE": ["ARCEUS_12"],
    "BASCULEGION_F": ["BASCULEGION_FEMALE"],
    "FLABB": ["FLABEBE"],
}


def load_rr_entries(rr_path: Path):
    text = rr_path.read_text(encoding="utf-8", errors="replace")
    return parse_species_entries(text)


def folder_stems(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    return {p.stem.upper() for p in path.glob("*.png")}


def expected_tokens(entries) -> Set[str]:
    out: Set[str] = set()
    for e in entries:
        token = normalize_token(e.key)
        if token:
            out.add(token)
    return out


def missing_for_folder(expected: Set[str], present: Set[str]) -> List[str]:
    normalized_present = set(present)

    for token in list(expected):
        for alias in FORM_ALIAS_MAP.get(token, []):
            if alias in normalized_present:
                normalized_present.add(token)

        # RR FLABB variants should accept FLABEBE legacy names.
        if token == "FLABB" and "FLABEBE" in normalized_present:
            normalized_present.add(token)
        elif token.startswith("FLABB_"):
            flabebe_variant = token.replace("FLABB_", "FLABEBE_", 1)
            if flabebe_variant in normalized_present:
                normalized_present.add(token)

    return sorted([t for t in expected if t not in normalized_present])


def report() -> Dict[str, List[str]]:
    script_dir = Path(__file__).resolve().parent
    root = script_dir.parent.parent

    rr_path = script_dir.parent / "_rr_data_tmp.js"
    entries = load_rr_entries(rr_path)
    expected = expected_tokens(entries)

    front = folder_stems(root / "Front")
    front_shiny = folder_stems(root / "Front shiny")
    icons = folder_stems(root / "Icons")
    icons_shiny = folder_stems(root / "Icons shiny")

    return {
        "meta": [
            f"rr_entries={len(entries)}",
            f"expected_unique_tokens={len(expected)}",
        ],
        "missing_front": missing_for_folder(expected, front),
        "missing_front_shiny": missing_for_folder(expected, front_shiny),
        "missing_icons": missing_for_folder(expected, icons),
        "missing_icons_shiny": missing_for_folder(expected, icons_shiny),
    }


def main() -> int:
    out = report()

    script_dir = Path(__file__).resolve().parent
    out_path = script_dir / "missing_sprites_report.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print("Wrote", out_path)
    for line in out["meta"]:
        print(line)
    print("missing_front", len(out["missing_front"]))
    print("missing_front_shiny", len(out["missing_front_shiny"]))
    print("missing_icons", len(out["missing_icons"]))
    print("missing_icons_shiny", len(out["missing_icons_shiny"]))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
