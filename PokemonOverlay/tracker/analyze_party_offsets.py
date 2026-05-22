from __future__ import annotations

from pathlib import Path
import struct

from save_parser import SaveParser, SECTION_DATA_SIZE
from party_parser import BOX_MON_SIZE, PARTY_MON_SIZE, PartyParser

SAVE_PATH = Path(r"C:\Users\kodia\Downloads\1636 - Pokemon Fire Red (U)(Squirrels) (patched).sav")


def mon_score(pp: PartyParser, data: bytes, start: int):
    core = data[start : start + BOX_MON_SIZE]
    if len(core) != BOX_MON_SIZE:
        return None

    personality = struct.unpack_from("<I", core, 0)[0]
    ot_id = struct.unpack_from("<I", core, 4)[0]
    checksum_stored = struct.unpack_from("<H", core, 28)[0]
    encrypted = core[32:80]

    decrypted = pp._decrypt_substructs(encrypted, personality, ot_id)
    if not decrypted:
        return None

    checksum_calc = 0
    for i in range(0, 48, 2):
        checksum_calc = (checksum_calc + struct.unpack_from("<H", decrypted, i)[0]) & 0xFFFF

    species = struct.unpack_from("<H", decrypted, 0)[0]
    exp = struct.unpack_from("<I", decrypted, 4)[0]
    level = data[start + 84] if start + 84 < len(data) else 0

    return {
        "species": species,
        "level": level,
        "exp": exp,
        "checksum_stored": checksum_stored,
        "checksum_calc": checksum_calc,
        "checksum_ok": checksum_calc == checksum_stored,
        "personality": personality,
        "ot_id": ot_id,
        "nickname_bytes": core[8:18].hex(" "),
    }


def scan_blob(blob_name: str, data: bytes, pp: PartyParser) -> None:
    print(f"\n=== Scan {blob_name} len=0x{len(data):X} ===")

    top = []
    max_start = max(0, len(data) - (PARTY_MON_SIZE * 6))
    for off in range(0, max_start):
        valid_species = 0
        level_ok = 0
        checksum_ok = 0
        species_ids = []

        for slot in range(6):
            st = off + slot * PARTY_MON_SIZE
            m = mon_score(pp, data, st)
            if m is None:
                continue
            if m["checksum_ok"]:
                checksum_ok += 1
            if 0 < m["species"] <= 2000:
                valid_species += 1
                species_ids.append(m["species"])
            if 1 <= m["level"] <= 100:
                level_ok += 1

        score = (checksum_ok * 20) + (valid_species * 15) + level_ok
        if score >= 50:
            top.append((score, off, checksum_ok, valid_species, level_ok, species_ids[:6]))

    top.sort(reverse=True)
    for row in top[:30]:
        score, off, checksum_ok, valid_species, level_ok, species_ids = row
        print(
            f"score={score:3d} off=0x{off:04X} chk_ok={checksum_ok} species_ok={valid_species} "
            f"level_ok={level_ok} species={species_ids}"
        )


def main() -> int:
    sp = SaveParser()
    parsed = sp.read(SAVE_PATH, debug=False)
    if not parsed:
        print("Failed to parse save")
        return 1

    pp = PartyParser()

    # 1) Current parser saveblock reconstruction
    scan_blob("saveblock(id-ordered)", parsed.saveblock, pp)

    # 2) Raw active slot as written in file, chunk-ordered
    raw = SAVE_PATH.read_bytes()
    slot_start = parsed.active_slot_index * (0x1000 * 14)
    slot_end = slot_start + (0x1000 * 14)
    active_slot_raw = raw[slot_start:slot_end]
    slot_data_concat = bytearray()
    for chunk_idx in range(14):
        c_start = chunk_idx * 0x1000
        slot_data_concat.extend(active_slot_raw[c_start : c_start + SECTION_DATA_SIZE])
    scan_blob("active_slot_raw(chunk-ordered)", bytes(slot_data_concat), pp)

    # 3) Per section scan
    for section_id, section in sorted(parsed.sections.items()):
        scan_blob(f"section_{section_id}", section.data, pp)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
