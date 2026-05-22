from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import logging
import struct

LOGGER = logging.getLogger(__name__)

SECTION_SIZE = 0x1000
SECTION_DATA_SIZE = 0x0FF4
SECTIONS_PER_SLOT = 14
SLOT_SIZE = SECTION_SIZE * SECTIONS_PER_SLOT
SAV_SIGNATURE = 0x08012025


@dataclass
class SaveSection:
    section_id: int
    checksum: int
    signature: int
    save_index: int
    data: bytes


@dataclass
class ParsedSave:
    active_slot_index: int
    save_index: int
    sections: Dict[int, SaveSection]
    saveblock: bytes


@dataclass
class SlotDiagnostic:
    slot_index: int
    valid_sections: int
    section_ids: List[int]
    save_indices: List[int]
    signatures: List[str]


@dataclass
class SaveDiagnostic:
    file_size: int
    slots: List[SlotDiagnostic]
    selected_slot: Optional[int]
    selected_save_index: Optional[int]


class SaveParser:
    """Reads a Gen 3 .sav file and reconstructs the latest save slot data."""

    def read(self, save_path: Path, debug: bool = False) -> Optional[ParsedSave]:
        if not save_path.exists() or not save_path.is_file():
            LOGGER.error("Save file does not exist: %s", save_path)
            return None

        raw = save_path.read_bytes()
        if len(raw) < SLOT_SIZE * 2:
            LOGGER.error("Save file is too small for a Gen 3 save: %s bytes", len(raw))
            return None

        slots = [
            self._parse_slot(raw[0:SLOT_SIZE]),
            self._parse_slot(raw[SLOT_SIZE : SLOT_SIZE * 2]),
        ]

        if debug:
            LOGGER.debug("Read save bytes: %s from %s", len(raw), save_path)

        valid_slots = []
        for idx, slot_sections in enumerate(slots):
            if slot_sections:
                latest_index = max(section.save_index for section in slot_sections.values())
                valid_slots.append((idx, latest_index, slot_sections))
                if debug:
                    LOGGER.debug(
                        "Slot %s valid sections=%s ids=%s latest_save_index=%s",
                        idx,
                        len(slot_sections),
                        sorted(slot_sections.keys()),
                        latest_index,
                    )
            elif debug:
                LOGGER.debug("Slot %s has no valid sections", idx)

        if not valid_slots:
            LOGGER.error("Could not parse any valid save slots from %s", save_path)
            return None

        active_slot_index, save_index, active_sections = max(valid_slots, key=lambda item: item[1])

        missing = [i for i in range(SECTIONS_PER_SLOT) if i not in active_sections]
        if missing:
            LOGGER.warning("Active slot missing sections: %s", missing)
        if debug:
            LOGGER.debug(
                "Active slot=%s save_index=%s section_ids=%s",
                active_slot_index,
                save_index,
                sorted(active_sections.keys()),
            )

        saveblock = bytearray()
        for section_id in range(SECTIONS_PER_SLOT):
            section = active_sections.get(section_id)
            if section is None:
                saveblock.extend(b"\x00" * SECTION_DATA_SIZE)
                continue
            saveblock.extend(section.data)

        return ParsedSave(
            active_slot_index=active_slot_index,
            save_index=save_index,
            sections=active_sections,
            saveblock=bytes(saveblock),
        )

    def inspect_save(self, save_path: Path) -> Optional[SaveDiagnostic]:
        if not save_path.exists() or not save_path.is_file():
            LOGGER.error("Save file does not exist: %s", save_path)
            return None

        raw = save_path.read_bytes()
        if len(raw) < SLOT_SIZE * 2:
            LOGGER.error("Save file is too small for a Gen 3 save: %s bytes", len(raw))
            return None

        slot_diags: List[SlotDiagnostic] = []
        valid_slots = []

        for slot_index in range(2):
            slot_raw = raw[slot_index * SLOT_SIZE : (slot_index + 1) * SLOT_SIZE]
            parsed_sections = self._parse_slot(slot_raw)
            section_ids = sorted(parsed_sections.keys())
            save_indices = sorted({s.save_index for s in parsed_sections.values()})
            signatures = sorted({f"0x{s.signature:08X}" for s in parsed_sections.values()})
            slot_diags.append(
                SlotDiagnostic(
                    slot_index=slot_index,
                    valid_sections=len(parsed_sections),
                    section_ids=section_ids,
                    save_indices=save_indices,
                    signatures=signatures,
                )
            )

            if parsed_sections:
                latest_index = max(section.save_index for section in parsed_sections.values())
                valid_slots.append((slot_index, latest_index))

        if valid_slots:
            selected_slot, selected_save_index = max(valid_slots, key=lambda item: item[1])
        else:
            selected_slot, selected_save_index = None, None

        return SaveDiagnostic(
            file_size=len(raw),
            slots=slot_diags,
            selected_slot=selected_slot,
            selected_save_index=selected_save_index,
        )

    def _parse_slot(self, slot_raw: bytes) -> Dict[int, SaveSection]:
        sections: Dict[int, SaveSection] = {}

        for i in range(SECTIONS_PER_SLOT):
            start = i * SECTION_SIZE
            section_raw = slot_raw[start : start + SECTION_SIZE]
            data = section_raw[:SECTION_DATA_SIZE]
            footer = section_raw[SECTION_DATA_SIZE : SECTION_DATA_SIZE + 12]
            if len(footer) < 12:
                continue

            section_id, checksum = struct.unpack_from("<HH", footer, 0)
            signature = struct.unpack_from("<I", footer, 4)[0]
            save_index = struct.unpack_from("<I", footer, 8)[0]

            if section_id >= SECTIONS_PER_SLOT:
                continue
            if signature != SAV_SIGNATURE:
                continue

            sections[section_id] = SaveSection(
                section_id=section_id,
                checksum=checksum,
                signature=signature,
                save_index=save_index,
                data=data,
            )

        return sections
