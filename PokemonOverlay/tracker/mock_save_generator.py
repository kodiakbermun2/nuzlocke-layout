from __future__ import annotations

from pathlib import Path
import argparse
import json
import struct

from party_parser import PARTY_MON_SIZE, PARTY_COUNT_CANDIDATES, PARTY_DATA_CANDIDATES


def build_mock_saveblock(mode: str, party_count: int) -> bytes:
    size = 0xF80 * 14
    saveblock = bytearray(b"\x00" * size)
    count_offset = PARTY_COUNT_CANDIDATES[0]
    party_offset = PARTY_DATA_CANDIDATES[0]
    struct.pack_into("<I", saveblock, count_offset, party_count)

    for i in range(party_count):
        start = party_offset + i * PARTY_MON_SIZE
        mon = bytearray(b"\x00" * PARTY_MON_SIZE)

        # Minimal stable identity fields.
        pid = 0x10000001 + i
        ot = 0x20000002 + i
        struct.pack_into("<I", mon, 0, pid)
        struct.pack_into("<I", mon, 4, ot)

        nickname = f"Mock{i + 1}".encode("ascii", errors="ignore")[:10]
        mon[8 : 8 + len(nickname)] = nickname
        mon[8 + len(nickname) : 18] = b"\xFF" * (10 - len(nickname))
        mon[84] = min(100, 10 + i)

        if mode == "radical_red":
            struct.pack_into("<H", mon, 28, 0)
            struct.pack_into("<H", mon, 32, 25 + i)
            struct.pack_into("<H", mon, 34, 0)
            struct.pack_into("<I", mon, 36, 1000 + i * 50)
        else:
            # Vanilla generation is intentionally minimal in this helper and does
            # not attempt full encrypted block synthesis.
            struct.pack_into("<H", mon, 28, 0xFFFF)
        saveblock[start : start + PARTY_MON_SIZE] = mon

    return bytes(saveblock)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate mock saveblock payload for parser tests")
    parser.add_argument("--out", default="mock_saveblock.bin", help="Output binary file")
    parser.add_argument("--mode", choices=["radical_red", "vanilla_firered"], default="radical_red")
    parser.add_argument("--party-count", type=int, default=6)
    parser.add_argument("--meta-out", default="", help="Optional metadata JSON output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_path = Path(args.out).expanduser().resolve()
    saveblock = build_mock_saveblock(args.mode, max(0, min(6, args.party_count)))
    out_path.write_bytes(saveblock)
    print(f"wrote {out_path} ({len(saveblock)} bytes)")

    if args.meta_out:
        meta_path = Path(args.meta_out).expanduser().resolve()
        payload = {
            "mode": args.mode,
            "party_count": max(0, min(6, args.party_count)),
            "offsets": {
                "count": PARTY_COUNT_CANDIDATES[0],
                "party": PARTY_DATA_CANDIDATES[0],
            },
        }
        meta_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {meta_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
