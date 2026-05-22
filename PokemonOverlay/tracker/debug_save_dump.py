from __future__ import annotations

from pathlib import Path
import argparse
import struct

from party_parser import PARTY_COUNT_CANDIDATES, PARTY_DATA_CANDIDATES, PARTY_MON_SIZE, PartyParser
from save_parser import SaveParser, SECTION_DATA_SIZE, SECTION_SIZE, SECTIONS_PER_SLOT, SLOT_SIZE, SAV_SIGNATURE


def hex_line(data: bytes, base_offset: int) -> str:
    hex_part = " ".join(f"{b:02X}" for b in data)
    ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in data)
    return f"0x{base_offset:08X}: {hex_part:<47} |{ascii_part}|"


def hex_dump_window(data: bytes, offset: int, span: int) -> str:
    start = max(0, offset - span)
    end = min(len(data), offset + span)
    out = []
    for pos in range(start, end, 16):
        out.append(hex_line(data[pos : pos + 16], pos))
    return "\n".join(out)


def dump_slot_headers(raw: bytes) -> None:
    print("=== Slot / Section Header Dump ===")
    for slot_index in range(2):
        print(f"Slot {slot_index} @ base 0x{slot_index * SLOT_SIZE:08X}")
        slot_raw = raw[slot_index * SLOT_SIZE : (slot_index + 1) * SLOT_SIZE]
        for section_idx in range(SECTIONS_PER_SLOT):
            section_base = section_idx * SECTION_SIZE
            footer_base = section_base + SECTION_DATA_SIZE
            footer = slot_raw[footer_base : footer_base + 12]
            if len(footer) < 12:
                continue
            section_id, checksum = struct.unpack_from("<HH", footer, 0)
            signature = struct.unpack_from("<I", footer, 4)[0]
            save_index = struct.unpack_from("<I", footer, 8)[0]
            sig_ok = "OK" if signature == SAV_SIGNATURE else "BAD"
            print(
                (
                    f"  section_chunk={section_idx:02d} section_id={section_id:02d} "
                    f"checksum=0x{checksum:04X} signature=0x{signature:08X}({sig_ok}) "
                    f"save_index={save_index}"
                )
            )


def dump_diagnostics(save_path: Path) -> int:
    parser = SaveParser()
    diag = parser.inspect_save(save_path)
    if diag is None:
        print(f"Failed to inspect save: {save_path}")
        return 1

    print("=== Save Diagnostic Summary ===")
    print(f"Path: {save_path}")
    print(f"File size: {diag.file_size} bytes")
    for slot in diag.slots:
        print(
            (
                f"Slot {slot.slot_index}: valid_sections={slot.valid_sections} "
                f"section_ids={slot.section_ids} save_indices={slot.save_indices} "
                f"signatures={slot.signatures}"
            )
        )

    print(f"Selected active slot: {diag.selected_slot}")
    print(f"Selected save index: {diag.selected_save_index}")

    parsed = parser.read(save_path, debug=False)
    if parsed is None:
        print("Unable to build active saveblock; cannot run offset diagnostics.")
        return 1

    pp = PartyParser()

    print("\n=== Party Offset Candidate Diagnostics ===")
    offset_diag = pp.party_offset_diagnostics(parsed.saveblock)
    for row in offset_diag:
        print(f"count_offset=0x{row['count_offset']:X} value={row['count_value']}")
        for cand in row["party_candidates"]:
            print(
                (
                    f"  party_offset=0x{cand['party_offset']:X} "
                    f"valid_slots={cand['valid_slots']} species_ids={cand['species_ids']}"
                )
            )

    print("\n=== Hex Around Party Count Offsets (active saveblock) ===")
    for off in PARTY_COUNT_CANDIDATES:
        print(f"offset=0x{off:X}")
        print(hex_dump_window(parsed.saveblock, off, 48))

    print("\n=== Hex Around Party Data Offsets (active saveblock) ===")
    for off in PARTY_DATA_CANDIDATES:
        print(f"offset=0x{off:X}")
        print(hex_dump_window(parsed.saveblock, off, 96))

    print("\n=== First Slot Raw Party-Mon Windows (each candidate offset) ===")
    for off in PARTY_DATA_CANDIDATES:
        mon = parsed.saveblock[off : off + PARTY_MON_SIZE]
        print(f"offset=0x{off:X} first_mon_size={len(mon)}")
        print(hex_dump_window(mon, 0, min(96, len(mon))))

    raw = save_path.read_bytes()
    print()
    dump_slot_headers(raw)

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dump Gen 3 save internals for debug/reverse engineering")
    parser.add_argument("--save", required=True, help="Path to .sav file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    save_path = Path(args.save).expanduser().resolve()
    return dump_diagnostics(save_path)


if __name__ == "__main__":
    raise SystemExit(main())
