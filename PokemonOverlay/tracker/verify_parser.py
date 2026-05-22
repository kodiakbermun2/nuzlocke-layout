from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

from party_parser import PartyParser
from save_parser import SaveParser


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify parser output from a real save file")
    parser.add_argument("--save", required=True, help="Path to .sav file")
    parser.add_argument(
        "--mode",
        default="auto",
        choices=["auto", "vanilla_firered", "radical_red"],
        help="Parser mode to use",
    )
    parser.add_argument("--expect-party", type=int, default=None, help="Expected party count")
    parser.add_argument("--out", default="", help="Optional path to write parsed JSON output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    save_path = Path(args.save).expanduser().resolve()

    parsed = SaveParser().read(save_path)
    if parsed is None:
        print("ERROR: could not parse save slot")
        return 2

    state = PartyParser(parser_mode=args.mode).parse(
        parsed.saveblock,
        include_pc=False,
        sections=parsed.sections,
        parser_mode=args.mode,
        debug=False,
    )

    party = state.get("party", [])
    mode = (state.get("meta", {}) or {}).get("parser_mode", args.mode)
    print(f"mode={mode} party_count={len(party)}")
    for idx, mon in enumerate(party, start=1):
        print(f"{idx}. {mon.get('nickname')} ({mon.get('species')}) Lv{mon.get('level')}")

    if args.expect_party is not None and len(party) != args.expect_party:
        print(f"ERROR: expected party count {args.expect_party}, got {len(party)}")
        return 3

    if args.out:
        out = Path(args.out).expanduser().resolve()
        out.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
