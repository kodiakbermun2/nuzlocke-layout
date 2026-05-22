from pathlib import Path

from party_parser import BOX_MON_SIZE, ParserMode, PartyParser
from save_parser import SaveParser

save_path = Path("C:/Users/kodia/Downloads/1636 - Pokemon Fire Red (U)(Squirrels) (patched).sav")
raw = save_path.read_bytes()
pp = PartyParser()

# Candidate starts from probe results.
candidates = [0x5184, 0x5134, 0x50E4, 0x5094, 0x5864, 0x5F44, 0x5F94]

BOXES = 25
BOX_SIZE = 30

for start in candidates:
    print(f"\n=== start=0x{start:X} ===")
    total = 0
    for box in (1, 2, 24, 25):
        found = []
        for slot in range(BOX_SIZE):
            off = start + ((box - 1) * BOX_SIZE + slot) * BOX_MON_SIZE
            core = raw[off : off + BOX_MON_SIZE]
            mon = pp._decode_box_mon(core, mode=ParserMode.RADICAL_RED)
            if mon is None:
                mon = pp._decode_box_mon(core, mode=ParserMode.VANILLA)
            if mon is None:
                continue
            if mon.nickname == "missingno":
                continue
            found.append((slot + 1, mon.species_id, mon.species_name, mon.nickname))

        total += len(found)
        print(f"box {box}: {len(found)}")
        for row in found[:8]:
            print("  ", row)
    print("sample total in boxes [1,2,24,25] =", total)
