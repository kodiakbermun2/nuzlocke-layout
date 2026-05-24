from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from party_parser import (
    RR_BOX25_OFFSET,
    RR_COMPRESSED_MON_SIZE,
    PartyParser,
    SPECIES_MAP,
)
from save_parser import SaveParser


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dump Box 25 compressed entries for verification")
    parser.add_argument("--save", required=True, help="Path to .sav file")
    parser.add_argument("--out", default="_box25_verify_dump.json", help="Output JSON path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    save_path = Path(args.save).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()

    parsed = SaveParser().read(save_path)
    if parsed is None:
        print("ERROR: could not parse save")
        return 2

    section0 = parsed.sections.get(0)
    if section0 is None:
        print("ERROR: section 0 missing")
        return 3

    pp = PartyParser()
    rows = []
    box_bytes = section0.data[RR_BOX25_OFFSET : RR_BOX25_OFFSET + (30 * RR_COMPRESSED_MON_SIZE)]

    for slot_idx in range(30):
        rec_off = RR_BOX25_OFFSET + (slot_idx * RR_COMPRESSED_MON_SIZE)
        rec = section0.data[rec_off : rec_off + RR_COMPRESSED_MON_SIZE]
        if len(rec) != RR_COMPRESSED_MON_SIZE:
            continue

        raw_species = struct.unpack_from("<H", rec, 28)[0]
        personality = struct.unpack_from("<I", rec, 0)[0]
        ot_id = struct.unpack_from("<I", rec, 4)[0]
        nickname_bytes = rec[8:18]
        nickname = pp._decode_gen3_string(nickname_bytes)

        mon = pp._decode_rr_compressed_box_mon(rec)
        if mon is None:
            continue

        rows.append(
            {
                "slot": slot_idx + 1,
                "offset": rec_off,
                "raw_species_id": raw_species,
                "decrypted_species_id": mon.species_id,
                "species": mon.species_name,
                "species_id": mon.species_id,
                "nickname": mon.nickname,
                "nickname_bytes": nickname_bytes.hex(" "),
                "personality": personality,
                "ot_id": ot_id,
                "checksum": None,
                "fallback_nickname_decoded": nickname,
            }
        )

    payload = {
        "box": 25,
        "box25_offset": RR_BOX25_OFFSET,
        "record_size": RR_COMPRESSED_MON_SIZE,
        "entries": rows,
        "section0_len": len(section0.data),
        "box25_bytes_len": len(box_bytes),
    }

    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"wrote {out_path}")
    for row in rows:
        sid = row["species_id"]
        print(f"slot={row['slot']:02d} species_id={sid} species={SPECIES_MAP.get(sid, row['species'])} name={row['nickname']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
