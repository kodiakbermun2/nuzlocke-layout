from pathlib import Path
import struct

SAVE = Path("C:/Users/kodia/Downloads/1636 - Pokemon Fire Red (U)(Squirrels) (patched).sav")
raw = SAVE.read_bytes()

BOXES = 25
BOX_SIZE = 30
REC = 80
TOTAL = BOXES * BOX_SIZE
WINDOW = TOTAL * REC

# Heuristic for plausible boxed entry in Radical Red plaintext-like layout.
def plausible_record(buf: bytes) -> bool:
    if len(buf) != REC:
        return False
    pid = struct.unpack_from("<I", buf, 0)[0]
    ot = struct.unpack_from("<I", buf, 4)[0]
    if pid == 0 and ot == 0:
        return False

    species = struct.unpack_from("<H", buf, 32)[0]
    if not (1 <= species <= 3000):
        return False

    # Nickname bytes in classic position; reject fully empty/all-ff.
    nick = buf[8:18]
    if all(b in (0x00, 0xFF) for b in nick):
        return False

    return True

candidates = []
for start in range(0, len(raw) - WINDOW, 4):
    box_counts = []
    total_hits = 0
    for b in range(BOXES):
        c = 0
        for s in range(BOX_SIZE):
            off = start + (b * BOX_SIZE + s) * REC
            rec = raw[off : off + REC]
            if plausible_record(rec):
                c += 1
        box_counts.append(c)
        total_hits += c

    # User says box1 has multiple, box25 has five.
    if box_counts[0] >= 2 and box_counts[24] >= 5 and total_hits >= 12:
        candidates.append((total_hits, start, box_counts[0], box_counts[24], box_counts))

candidates.sort(reverse=True)
print("candidates", len(candidates))
for row in candidates[:20]:
    total_hits, start, b1, b25, counts = row
    print(f"start=0x{start:X} total={total_hits} box1={b1} box25={b25} counts={counts}")
