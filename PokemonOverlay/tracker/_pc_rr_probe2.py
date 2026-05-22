from pathlib import Path

from party_parser import MISSINGNO_NAME, ParserMode, PartyParser
from save_parser import SaveParser

SAVE_PATH = Path("C:/Users/kodia/Downloads/1636 - Pokemon Fire Red (U)(Squirrels) (patched).sav")
SECTION_IDS = list(range(5, 14))
RECORD_SIZE = 80


def main() -> int:
    parsed = SaveParser().read(SAVE_PATH)
    if parsed is None:
        print("Could not parse save")
        return 1

    pp = PartyParser()
    mode = pp.detect_parser_mode(parsed.saveblock, parsed.sections)

    chunks = []
    for sid in SECTION_IDS:
        sec = parsed.sections.get(sid)
        if sec is None:
            print(f"section {sid}: missing")
            continue
        chunks.append(sec.data)

    region = b"".join(chunks)
    print("active_slot", parsed.active_slot_index, "save_index", parsed.save_index, "mode", mode.value)
    print("pc_region_bytes", len(region), "sections", SECTION_IDS)

    best = None
    for base in range(RECORD_SIZE):
        valid = 0
        quality = 0
        decoded_rows = []

        i = 0
        while True:
            off = base + i * RECORD_SIZE
            if off + RECORD_SIZE > len(region):
                break
            core = region[off : off + RECORD_SIZE]

            mon = pp._decode_core_mon(core, level=None, mode=mode)
            if mon is None:
                alt = ParserMode.VANILLA if mode == ParserMode.RADICAL_RED else ParserMode.RADICAL_RED
                mon = pp._decode_core_mon(core, level=None, mode=alt)
            if mon is None:
                i += 1
                continue

            valid += 1
            good = mon.nickname != MISSINGNO_NAME and not mon.species_name.startswith("species_")
            if good:
                quality += 1
            decoded_rows.append((i + 1, off, mon.species_id, mon.species_name, mon.nickname, mon.exp, good))
            i += 1

        score = (quality, valid)
        if best is None or score > (best["quality"], best["valid"]):
            best = {
                "base": base,
                "quality": quality,
                "valid": valid,
                "rows": decoded_rows,
            }

    if best is None:
        print("No decodable records found")
        return 0

    print("best_base", best["base"], "quality", best["quality"], "valid", best["valid"])
    for row in best["rows"][:60]:
        idx, off, sid, species, nick, exp, good = row
        marker = "OK" if good else "??"
        print(f"slot={idx:03d} off=0x{off:X} sid={sid:4d} species={species:<20} nick={nick!r:<12} exp={exp:<8d} {marker}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
