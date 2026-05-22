from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
import logging
import re
import struct

from save_parser import SaveSection

LOGGER = logging.getLogger(__name__)

# FRLG and many FireRed-based hack offsets for SaveBlock1 section payloads.
PARTY_COUNT_CANDIDATES = [0x034, 0x234]
PARTY_DATA_CANDIDATES = [0x038, 0x238]
PC_OFFSET_CANDIDATES = [0x2F20]

PARTY_MON_SIZE = 100
BOX_MON_SIZE = 80
MAX_PARTY = 6
BOXES = 14
BOX_SIZE = 30
MAX_SPECIES_ID = 3000
MAX_EXP = 100_000_000

MISSINGNO_NAME = "missingno"

# A compact species map for starter operation. Unknown IDs fall back to species_<id>.
SPECIES_MAP = {
        47: "parasect",
    1: "bulbasaur",
    2: "ivysaur",
    3: "venusaur",
    4: "charmander",
    5: "charmeleon",
    6: "charizard",
    7: "squirtle",
    8: "wartortle",
    9: "blastoise",
    10: "caterpie",
    16: "pidgey",
    19: "rattata",
    25: "pikachu",
    26: "raichu",
    35: "clefairy",
    39: "jigglypuff",
    41: "zubat",
    43: "oddish",
    52: "meowth",
    54: "psyduck",
    56: "mankey",
    58: "growlithe",
    60: "poliwag",
    63: "abra",
    66: "machop",
    72: "tentacool",
    74: "geodude",
    79: "slowpoke",
    81: "magnemite",
    92: "gastly",
    95: "onix",
    96: "drowzee",
    98: "krabby",
    100: "voltorb",
    104: "cubone",
    109: "koffing",
    111: "rhyhorn",
    113: "chansey",
    116: "horsea",
    120: "staryu",
    123: "scyther",
    129: "magikarp",
    130: "gyarados",
    131: "lapras",
    133: "eevee",
    137: "porygon",
    143: "snorlax",
    147: "dratini",
    148: "dragonair",
    149: "dragonite",
    150: "mewtwo",
    151: "mew",
    162: "furret",
}


def _load_rr_species_map() -> Dict[int, str]:
    """Best-effort loader for full RR species IDs from local data.js.

    This keeps the parser resilient when static fallback IDs are incomplete.
    """
    rr_path = Path(__file__).resolve().parent.parent / "_rr_data_tmp.js"
    if not rr_path.exists():
        return {}

    try:
        from rr_sprite_renamer import parse_species_entries

        text = rr_path.read_text(encoding="utf-8", errors="replace")
        entries = parse_species_entries(text)
        out: Dict[int, str] = {}
        for entry in entries:
            out[entry.species_id] = entry.key.strip().lower()
        return out
    except Exception as exc:
        LOGGER.warning("Could not load RR species map from %s: %s", rr_path, exc)
        return {}


SPECIES_MAP.update(_load_rr_species_map())


def _load_rr_type_map() -> Dict[int, str]:
    rr_path = Path(__file__).resolve().parent.parent / "_rr_data_tmp.js"
    if not rr_path.exists():
        return {}

    try:
        from rr_sprite_renamer import find_balanced_block, split_species_entries

        text = rr_path.read_text(encoding="utf-8", errors="replace")
        marker_positions = [text.find("'types':{"), text.find('"types":{')]
        marker_positions = [p for p in marker_positions if p >= 0]
        if not marker_positions:
            return {}

        marker = min(marker_positions)
        open_brace = text.find("{", marker)
        if open_brace < 0:
            return {}

        types_obj = find_balanced_block(text, open_brace)
        raw_entries = split_species_entries(types_obj)

        name_re_sq = re.compile(r"['\"]name['\"]\s*:\s*'((?:\\.|[^'])*)'")
        name_re_dq = re.compile(r"['\"]name['\"]\s*:\s*\"((?:\\.|[^\"])*)\"")

        out: Dict[int, str] = {}
        for type_id, obj in raw_entries.items():
            m = name_re_sq.search(obj) or name_re_dq.search(obj)
            if not m:
                continue
            name = m.group(1).strip().lower()
            if name:
                out[type_id] = name

        return out
    except Exception as exc:
        LOGGER.warning("Could not load RR type map from %s: %s", rr_path, exc)
        return {}


def _load_rr_species_types(type_map: Dict[int, str]) -> Dict[int, List[str]]:
    rr_path = Path(__file__).resolve().parent.parent / "_rr_data_tmp.js"
    if not rr_path.exists() or not type_map:
        return {}

    try:
        from rr_sprite_renamer import find_balanced_block, split_species_entries

        text = rr_path.read_text(encoding="utf-8", errors="replace")
        marker_positions = [text.find("'species':{"), text.find('"species":{')]
        marker_positions = [p for p in marker_positions if p >= 0]
        if not marker_positions:
            return {}

        marker = min(marker_positions)
        open_brace = text.find("{", marker)
        if open_brace < 0:
            return {}

        species_obj = find_balanced_block(text, open_brace)
        raw_entries = split_species_entries(species_obj)
        type_re = re.compile(r"['\"]type['\"]\s*:\s*\[([^\]]*)\]")

        out: Dict[int, List[str]] = {}
        for species_id, obj in raw_entries.items():
            m = type_re.search(obj)
            if not m:
                continue

            type_ids = [int(v) for v in re.findall(r"\d+", m.group(1))]
            type_names = [type_map[t] for t in type_ids if t in type_map]
            if type_names:
                out[species_id] = type_names

        return out
    except Exception as exc:
        LOGGER.warning("Could not load RR species types from %s: %s", rr_path, exc)
        return {}


TYPE_MAP = _load_rr_type_map()
SPECIES_TYPES_MAP = _load_rr_species_types(TYPE_MAP)

ITEM_MAP = {
    0: None,
    79: "oran_berry",
    80: "sitrus_berry",
}

GEN3_CHAR_MAP = {
    0xFF: "",
    0x00: " ",
}

for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", start=0xBB):
    GEN3_CHAR_MAP[i] = ch
for i, ch in enumerate("abcdefghijklmnopqrstuvwxyz", start=0xD5):
    GEN3_CHAR_MAP[i] = ch
for i, ch in enumerate("0123456789", start=0xA1):
    GEN3_CHAR_MAP[i] = ch
GEN3_CHAR_MAP[0xAB] = "!"
GEN3_CHAR_MAP[0xAC] = "?"
GEN3_CHAR_MAP[0xAE] = "."
GEN3_CHAR_MAP[0xB8] = ","
GEN3_CHAR_MAP[0xB4] = "'"
GEN3_CHAR_MAP[0xB7] = "-"

SUBSTRUCT_ORDERS = [
    (0, 1, 2, 3),
    (0, 1, 3, 2),
    (0, 2, 1, 3),
    (0, 3, 1, 2),
    (0, 2, 3, 1),
    (0, 3, 2, 1),
    (1, 0, 2, 3),
    (1, 0, 3, 2),
    (2, 0, 1, 3),
    (3, 0, 1, 2),
    (2, 0, 3, 1),
    (3, 0, 2, 1),
    (1, 2, 0, 3),
    (1, 3, 0, 2),
    (2, 1, 0, 3),
    (3, 1, 0, 2),
    (2, 3, 0, 1),
    (3, 2, 0, 1),
    (1, 2, 3, 0),
    (1, 3, 2, 0),
    (2, 1, 3, 0),
    (3, 1, 2, 0),
    (2, 3, 1, 0),
    (3, 2, 1, 0),
]


class ParserMode(str, Enum):
    AUTO = "auto"
    VANILLA = "vanilla_firered"
    RADICAL_RED = "radical_red"


@dataclass
class DecodedPokemon:
    species_id: int
    species_name: str
    nickname: str
    level: Optional[int]
    gender: str
    shiny: bool
    held_item: Optional[str]
    personality: int
    ot_id: int
    checksum_stored: int
    checksum_calculated: int
    substructure_order_index: int
    substructure_order: tuple[int, int, int, int]
    exp: int
    parser_mode: ParserMode
    current_hp: Optional[int] = None
    max_hp: Optional[int] = None
    status: Optional[str] = None
    types: Optional[List[str]] = None

    def to_state_dict(self, slot: int, box: Optional[int] = None, box_slot: Optional[int] = None) -> Dict:
        out = {
            "species": self.species_name,
            "species_id": self.species_id,
            "nickname": self.nickname,
            "level": self.level,
            "gender": self.gender,
            "shiny": self.shiny,
            "held_item": self.held_item,
            "slot": slot,
        }
        if self.current_hp is not None:
            out["current_hp"] = self.current_hp
        if self.max_hp is not None:
            out["max_hp"] = self.max_hp
        if self.status:
            out["status"] = self.status
        if self.types:
            out["types"] = self.types
        if box is not None:
            out["box"] = box
        if box_slot is not None:
            out["box_slot"] = box_slot
        return out


@dataclass
class _DecodedCore:
    personality: int
    ot_id: int
    checksum_stored: int
    checksum_calculated: int
    order_index: int
    order_tuple: tuple[int, int, int, int]
    nickname_raw: bytes
    species_id: int
    held_item_id: int
    exp: int


class PartyParser:
    """Parses party and PC Pokemon from FRLG-compatible save payloads.

    The parser supports two decode modes:
    - vanilla_firered: standard Gen 3 encrypted substructure + checksum flow
    - radical_red: plaintext growth block fallback at core[0x20:0x2C] with checksum 0

    With mode="auto", detection probes section-backed party slots and chooses
    the best-fit mode for the current save.
    """

    def __init__(self, parser_mode: str = ParserMode.AUTO.value):
        self._forced_mode = self._coerce_mode(parser_mode)

    def parse(
        self,
        saveblock: bytes,
        include_pc: bool = True,
        debug: bool = False,
        sections: Optional[Dict[int, SaveSection]] = None,
        parser_mode: Optional[str] = None,
    ) -> Dict[str, List[Dict]]:
        mode = self.resolve_mode(saveblock=saveblock, sections=sections, parser_mode=parser_mode, debug=debug)
        party = self._parse_party(saveblock, mode=mode, debug=debug, sections=sections)
        pc = self._parse_pc(saveblock, mode=mode, debug=debug) if include_pc else []
        return {
            "party": party,
            "pc": pc,
            "dead": [],
            "meta": {
                "parser_mode": mode.value,
            },
        }

    def resolve_mode(
        self,
        saveblock: bytes,
        sections: Optional[Dict[int, SaveSection]] = None,
        parser_mode: Optional[str] = None,
        debug: bool = False,
    ) -> ParserMode:
        if parser_mode:
            mode = self._coerce_mode(parser_mode)
        else:
            mode = self._forced_mode

        if mode != ParserMode.AUTO:
            return mode

        detected = self.detect_parser_mode(saveblock=saveblock, sections=sections)
        if debug:
            LOGGER.debug("Parser mode detection selected=%s", detected.value)
        return detected

    def detect_parser_mode(
        self,
        saveblock: bytes,
        sections: Optional[Dict[int, SaveSection]] = None,
    ) -> ParserMode:
        section_payloads: List[bytes] = []
        if sections:
            for section_id in (1, 0, 4):
                section = sections.get(section_id)
                if section is not None:
                    section_payloads.append(section.data)
        if not section_payloads:
            section_payloads.append(saveblock)

        radical_hits = 0
        vanilla_hits = 0

        for payload in section_payloads:
            for count_offset in PARTY_COUNT_CANDIDATES:
                if count_offset + 4 > len(payload):
                    continue
                count = struct.unpack_from("<I", payload, count_offset)[0]
                if not (0 <= count <= MAX_PARTY):
                    continue

                for party_offset in PARTY_DATA_CANDIDATES:
                    max_needed = party_offset + (MAX_PARTY * PARTY_MON_SIZE)
                    if max_needed > len(payload):
                        continue
                    for slot_index in range(min(MAX_PARTY, max(count, 1))):
                        start = party_offset + (slot_index * PARTY_MON_SIZE)
                        mon_raw = payload[start : start + PARTY_MON_SIZE]
                        if len(mon_raw) != PARTY_MON_SIZE:
                            continue
                        core = mon_raw[:BOX_MON_SIZE]
                        level = mon_raw[84]
                        if self._try_decode_mode(core, level=level, mode=ParserMode.RADICAL_RED):
                            radical_hits += 1
                        if self._try_decode_mode(core, level=level, mode=ParserMode.VANILLA):
                            vanilla_hits += 1

        if radical_hits > vanilla_hits:
            return ParserMode.RADICAL_RED
        return ParserMode.VANILLA

    def _parse_party(
        self,
        saveblock: bytes,
        mode: ParserMode,
        debug: bool = False,
        sections: Optional[Dict[int, SaveSection]] = None,
    ) -> List[Dict]:
        # Prefer section-aware parsing first. Gen 3 saves can have per-section
        # padding/layout details that make naive global offsets brittle.
        if sections:
            from_sections = self._parse_party_from_sections(sections, mode=mode, debug=debug)
            if from_sections is not None:
                if debug:
                    LOGGER.debug("Section-aware party parse selected count=%s", len(from_sections))
                return from_sections

        best_result: List[Dict] = []

        for count_offset in PARTY_COUNT_CANDIDATES:
            if count_offset + 4 > len(saveblock):
                continue
            count = struct.unpack_from("<I", saveblock, count_offset)[0]
            if debug:
                LOGGER.debug("Party count candidate offset=0x%X -> %s", count_offset, count)
            if count < 0 or count > MAX_PARTY:
                continue

            for party_offset in PARTY_DATA_CANDIDATES:
                if party_offset + (MAX_PARTY * PARTY_MON_SIZE) > len(saveblock):
                    continue

                if debug:
                    LOGGER.debug(
                        "Trying party data offset=0x%X with count offset=0x%X mode=%s",
                        party_offset,
                        count_offset,
                        mode.value,
                    )

                parsed = []
                for slot_index in range(MAX_PARTY):
                    start = party_offset + (slot_index * PARTY_MON_SIZE)
                    mon_raw = saveblock[start : start + PARTY_MON_SIZE]
                    mon = self._decode_party_mon(
                        mon_raw,
                        mode=mode,
                        debug=debug,
                        slot=slot_index + 1,
                        mon_offset=start,
                    )
                    if mon is None:
                        continue
                    parsed.append(mon.to_state_dict(slot=slot_index + 1))

                if len(parsed) == count and (parsed or count == 0):
                    if debug:
                        LOGGER.debug(
                            "Selected party offset=0x%X count offset=0x%X parsed_count=%s",
                            party_offset,
                            count_offset,
                            len(parsed),
                        )
                    return parsed
                if len(parsed) > len(best_result):
                    best_result = parsed

        if debug:
            LOGGER.debug("Falling back to best party parse result size=%s", len(best_result))

        return best_result

    def _parse_party_from_sections(
        self,
        sections: Dict[int, SaveSection],
        mode: ParserMode,
        debug: bool = False,
    ) -> Optional[List[Dict]]:
        best: List[Dict] = []

        # Verified Radical Red data is currently observed in section 1 at:
        # - party count offsets: 0x34 / 0x234
        # - party data offsets: 0x38 / 0x238
        # Keep 0 and 4 as compatibility fallback for FRLG-derived variants.
        section_id_candidates = [1, 0, 4]

        for section_id in section_id_candidates:
            section = sections.get(section_id)
            if section is None:
                continue

            data = section.data
            for count_offset in PARTY_COUNT_CANDIDATES:
                if count_offset + 4 > len(data):
                    continue
                count = struct.unpack_from("<I", data, count_offset)[0]
                if debug:
                    LOGGER.debug(
                        "Section %s party count offset=0x%X -> %s",
                        section_id,
                        count_offset,
                        count,
                    )
                if count < 0 or count > MAX_PARTY:
                    continue

                for party_offset in PARTY_DATA_CANDIDATES:
                    if party_offset + (MAX_PARTY * PARTY_MON_SIZE) > len(data):
                        continue

                    parsed: List[Dict] = []
                    for slot_index in range(MAX_PARTY):
                        start = party_offset + (slot_index * PARTY_MON_SIZE)
                        mon_raw = data[start : start + PARTY_MON_SIZE]
                        mon = self._decode_party_mon(
                            mon_raw,
                            mode=mode,
                            debug=debug,
                            slot=slot_index + 1,
                            mon_offset=start,
                        )
                        if mon is None:
                            continue
                        parsed.append(mon.to_state_dict(slot=slot_index + 1))

                    if debug:
                        LOGGER.debug(
                            "Section %s candidate party_offset=0x%X count=%s parsed=%s mode=%s",
                            section_id,
                            party_offset,
                            count,
                            len(parsed),
                            mode.value,
                        )

                    if count == len(parsed) and (count > 0 or count == 0):
                        return parsed
                    if len(parsed) > len(best):
                        best = parsed

        if best:
            return best
        return None

    def _parse_pc(self, saveblock: bytes, mode: ParserMode, debug: bool = False) -> List[Dict]:
        for pc_offset in PC_OFFSET_CANDIDATES:
            needed = pc_offset + (BOXES * BOX_SIZE * BOX_MON_SIZE)
            if needed > len(saveblock):
                continue

            if debug:
                LOGGER.debug("Trying PC offset candidate=0x%X mode=%s", pc_offset, mode.value)

            parsed: List[Dict] = []
            quality_hits = 0
            absolute_slot = 1
            for box_idx in range(BOXES):
                for slot_idx in range(BOX_SIZE):
                    start = pc_offset + ((box_idx * BOX_SIZE + slot_idx) * BOX_MON_SIZE)
                    mon_raw = saveblock[start : start + BOX_MON_SIZE]
                    mon = self._decode_box_mon(mon_raw, mode=mode)
                    if mon is None:
                        absolute_slot += 1
                        continue

                    parsed.append(mon.to_state_dict(slot=absolute_slot, box=box_idx + 1, box_slot=slot_idx + 1))
                    if mon.nickname != MISSINGNO_NAME and not mon.species_name.startswith("species_"):
                        quality_hits += 1
                    absolute_slot += 1

            # A lone missingno-like decode is usually a false positive from the
            # wrong block offset. Require multiple quality entries before accepting.
            if parsed and quality_hits >= 2:
                if debug:
                    LOGGER.debug(
                        "Selected PC offset=0x%X parsed_count=%s quality_hits=%s",
                        pc_offset,
                        len(parsed),
                        quality_hits,
                    )
                return parsed
            if debug and parsed:
                LOGGER.debug(
                    "Rejected PC offset=0x%X parsed_count=%s quality_hits=%s",
                    pc_offset,
                    len(parsed),
                    quality_hits,
                )

        LOGGER.warning("PC parser could not find a valid PC block; returning an empty PC list")
        return []

    def _decode_party_mon(
        self,
        mon_raw: bytes,
        mode: ParserMode,
        debug: bool = False,
        slot: Optional[int] = None,
        mon_offset: Optional[int] = None,
    ) -> Optional[DecodedPokemon]:
        if len(mon_raw) != PARTY_MON_SIZE:
            return None
        core = mon_raw[:BOX_MON_SIZE]
        level = mon_raw[84]

        decoded = self._decode_core_mon(core, level=level, mode=mode, debug=debug, slot=slot, mon_offset=mon_offset)
        if decoded is not None:
            status_word = struct.unpack_from("<I", mon_raw, 80)[0]
            current_hp = struct.unpack_from("<H", mon_raw, 86)[0]
            max_hp = struct.unpack_from("<H", mon_raw, 88)[0]
            decoded.status = self._decode_status(status_word)
            if 0 <= current_hp <= 65535:
                decoded.current_hp = current_hp
            if 1 <= max_hp <= 65535:
                decoded.max_hp = max_hp

        if debug and slot is not None and mon_offset is not None:
            LOGGER.debug(
                "Party slot=%s offset=0x%X raw_head=%s",
                slot,
                mon_offset,
                mon_raw[:24].hex(" "),
            )
        return decoded

    def _decode_box_mon(self, mon_raw: bytes, mode: ParserMode) -> Optional[DecodedPokemon]:
        if len(mon_raw) != BOX_MON_SIZE:
            return None

        # PC storage in ROM hacks can mix structures. Try the selected mode first,
        # then fall back to the alternate mode for resilience.
        decoded = self._decode_core_mon(mon_raw, level=None, mode=mode)
        if decoded is not None:
            if decoded.nickname == MISSINGNO_NAME:
                return None
            return decoded

        fallback_mode = ParserMode.VANILLA if mode == ParserMode.RADICAL_RED else ParserMode.RADICAL_RED
        decoded = self._decode_core_mon(mon_raw, level=None, mode=fallback_mode)
        if decoded is not None and decoded.nickname == MISSINGNO_NAME:
            return None
        return decoded

    def _decode_core_mon(
        self,
        core: bytes,
        level: Optional[int],
        mode: ParserMode,
        debug: bool = False,
        slot: Optional[int] = None,
        mon_offset: Optional[int] = None,
    ) -> Optional[DecodedPokemon]:
        if len(core) != BOX_MON_SIZE:
            return None

        personality = struct.unpack_from("<I", core, 0)[0]
        ot_id = struct.unpack_from("<I", core, 4)[0]
        checksum_stored = struct.unpack_from("<H", core, 28)[0]
        nickname_raw = core[8:18]

        # Corrupted or empty slot guard: both IDs zero with empty nickname.
        if personality == 0 and ot_id == 0 and all(b in (0, 0xFF) for b in nickname_raw):
            return None

        decoded_core = self._decode_growth(core, mode=mode)
        if decoded_core is None:
            if debug and slot is not None:
                LOGGER.debug(
                    "Party slot=%s failed decode mode=%s pid=0x%08X checksum=0x%04X",
                    slot,
                    mode.value,
                    personality,
                    checksum_stored,
                )
            return None

        species_id = decoded_core.species_id
        if not (1 <= species_id <= MAX_SPECIES_ID):
            if debug and slot is not None:
                LOGGER.debug(
                    "Party slot=%s rejected invalid species=%s pid=0x%08X offset=%s",
                    slot,
                    species_id,
                    personality,
                    f"0x{mon_offset:X}" if mon_offset is not None else "unknown",
                )
            return None

        if not (0 <= decoded_core.exp <= MAX_EXP):
            if debug and slot is not None:
                LOGGER.debug("Party slot=%s rejected impossible exp=%s", slot, decoded_core.exp)
            return None

        if level is not None and not (1 <= level <= 100):
            if debug and slot is not None:
                LOGGER.debug("Party slot=%s rejected impossible level=%s", slot, level)
            return None

        species_name = SPECIES_MAP.get(species_id, f"species_{species_id}")
        types = SPECIES_TYPES_MAP.get(species_id, [])
        nickname = self._decode_gen3_string(nickname_raw).strip() or species_name
        held_item = ITEM_MAP.get(decoded_core.held_item_id, f"item_{decoded_core.held_item_id}" if decoded_core.held_item_id else None)

        if debug and slot is not None:
            LOGGER.debug(
                (
                    "Party slot=%s mode=%s pid=0x%08X ot=0x%08X checksum=0x%04X(calc=0x%04X) "
                    "order_idx=%s order=%s species=%s nickname=%s level=%s held_item_id=%s exp=%s"
                ),
                slot,
                mode.value,
                decoded_core.personality,
                decoded_core.ot_id,
                decoded_core.checksum_stored,
                decoded_core.checksum_calculated,
                decoded_core.order_index,
                decoded_core.order_tuple,
                species_name,
                nickname,
                level,
                decoded_core.held_item_id,
                decoded_core.exp,
            )

        return DecodedPokemon(
            species_id=species_id,
            species_name=species_name,
            nickname=nickname,
            level=level,
            gender="unknown",
            shiny=self._is_shiny(decoded_core.personality, decoded_core.ot_id),
            held_item=held_item,
            personality=decoded_core.personality,
            ot_id=decoded_core.ot_id,
            checksum_stored=decoded_core.checksum_stored,
            checksum_calculated=decoded_core.checksum_calculated,
            substructure_order_index=decoded_core.order_index,
            substructure_order=decoded_core.order_tuple,
            exp=decoded_core.exp,
            parser_mode=mode,
            types=types,
        )

    def _decode_growth(self, core: bytes, mode: ParserMode) -> Optional[_DecodedCore]:
        personality = struct.unpack_from("<I", core, 0)[0]
        ot_id = struct.unpack_from("<I", core, 4)[0]
        checksum_stored = struct.unpack_from("<H", core, 28)[0]

        encrypted = core[32:80]
        decrypted = self._decrypt_substructs(encrypted, personality, ot_id)
        if not decrypted:
            return None

        checksum_calculated = self._calculate_checksum(decrypted)
        order_index = personality % 24
        order_tuple = SUBSTRUCT_ORDERS[order_index]

        if mode == ParserMode.VANILLA:
            if checksum_calculated != checksum_stored:
                return None
            growth = decrypted[0:12]
            return _DecodedCore(
                personality=personality,
                ot_id=ot_id,
                checksum_stored=checksum_stored,
                checksum_calculated=checksum_calculated,
                order_index=order_index,
                order_tuple=order_tuple,
                nickname_raw=core[8:18],
                species_id=struct.unpack_from("<H", growth, 0)[0],
                held_item_id=struct.unpack_from("<H", growth, 2)[0],
                exp=struct.unpack_from("<I", growth, 4)[0],
            )

        if mode == ParserMode.RADICAL_RED:
            # Radical Red/CFRU party variant: growth words can be plaintext at 0x20
            # while PID/OT/nickname remain in Gen 3 layout and checksum is commonly 0.
            plaintext_growth = core[32:44]
            species_id = struct.unpack_from("<H", plaintext_growth, 0)[0]
            held_item_id = struct.unpack_from("<H", plaintext_growth, 2)[0]
            exp = struct.unpack_from("<I", plaintext_growth, 4)[0]
            if checksum_stored != 0:
                return None
            if not (1 <= species_id <= MAX_SPECIES_ID):
                return None
            if not (0 <= exp <= MAX_EXP):
                return None
            return _DecodedCore(
                personality=personality,
                ot_id=ot_id,
                checksum_stored=checksum_stored,
                checksum_calculated=checksum_calculated,
                order_index=order_index,
                order_tuple=order_tuple,
                nickname_raw=core[8:18],
                species_id=species_id,
                held_item_id=held_item_id,
                exp=exp,
            )

        return None

    def _try_decode_mode(self, core: bytes, level: Optional[int], mode: ParserMode) -> bool:
        if len(core) != BOX_MON_SIZE:
            return False
        decoded = self._decode_core_mon(core, level=level, mode=mode)
        return decoded is not None

    def party_offset_diagnostics(self, saveblock: bytes) -> List[Dict]:
        diagnostics: List[Dict] = []
        for count_offset in PARTY_COUNT_CANDIDATES:
            if count_offset + 4 > len(saveblock):
                continue
            count = struct.unpack_from("<I", saveblock, count_offset)[0]

            candidates = []
            for party_offset in PARTY_DATA_CANDIDATES:
                if party_offset + (MAX_PARTY * PARTY_MON_SIZE) > len(saveblock):
                    continue

                valid_slots = 0
                slot_species: List[int] = []
                for slot_index in range(MAX_PARTY):
                    start = party_offset + (slot_index * PARTY_MON_SIZE)
                    core = saveblock[start : start + BOX_MON_SIZE]
                    if len(core) != BOX_MON_SIZE:
                        continue

                    personality = struct.unpack_from("<I", core, 0)[0]
                    ot_id = struct.unpack_from("<I", core, 4)[0]
                    decrypted = self._decrypt_substructs(core[32:80], personality, ot_id)
                    if not decrypted:
                        continue
                    species_id = struct.unpack_from("<H", decrypted[0:12], 0)[0]
                    if 0 < species_id <= MAX_SPECIES_ID:
                        valid_slots += 1
                        slot_species.append(species_id)

                candidates.append(
                    {
                        "party_offset": party_offset,
                        "valid_slots": valid_slots,
                        "species_ids": slot_species,
                    }
                )

            diagnostics.append(
                {
                    "count_offset": count_offset,
                    "count_value": count,
                    "party_candidates": candidates,
                }
            )

        return diagnostics

    def _coerce_mode(self, parser_mode: str) -> ParserMode:
        try:
            return ParserMode(parser_mode)
        except ValueError:
            LOGGER.warning("Unknown parser mode '%s'; defaulting to auto", parser_mode)
            return ParserMode.AUTO

    def _decrypt_substructs(self, encrypted: bytes, personality: int, ot_id: int) -> Optional[bytes]:
        if len(encrypted) != 48:
            return None

        key = personality ^ ot_id
        decrypted = bytearray()
        for i in range(0, 48, 4):
            chunk = struct.unpack_from("<I", encrypted, i)[0]
            decrypted.extend(struct.pack("<I", chunk ^ key))

        order = SUBSTRUCT_ORDERS[personality % 24]
        canonical = [b"" for _ in range(4)]
        for encrypted_block_index in range(4):
            block_type = order[encrypted_block_index]
            block_start = encrypted_block_index * 12
            canonical[block_type] = bytes(decrypted[block_start : block_start + 12])

        return b"".join(canonical)

    def _calculate_checksum(self, decrypted_substructs: bytes) -> int:
        checksum = 0
        for i in range(0, len(decrypted_substructs), 2):
            checksum = (checksum + struct.unpack_from("<H", decrypted_substructs, i)[0]) & 0xFFFF
        return checksum

    def _decode_gen3_string(self, raw: bytes) -> str:
        chars = []
        for b in raw:
            if b == 0xFF:
                break
            chars.append(GEN3_CHAR_MAP.get(b, ""))
        out = "".join(chars).strip()
        return out if out else MISSINGNO_NAME

    def _is_shiny(self, personality: int, ot_id: int) -> bool:
        tid = ot_id & 0xFFFF
        sid = (ot_id >> 16) & 0xFFFF
        pid_low = personality & 0xFFFF
        pid_high = (personality >> 16) & 0xFFFF
        return (tid ^ sid ^ pid_low ^ pid_high) < 8

    def _decode_status(self, status: int) -> Optional[str]:
        if status & 0x7:
            return "SLP"
        if status & 0x80:
            return "TOX"
        if status & 0x10:
            return "BRN"
        if status & 0x20:
            return "FRZ"
        if status & 0x40:
            return "PAR"
        if status & 0x8:
            return "PSN"
        return None
