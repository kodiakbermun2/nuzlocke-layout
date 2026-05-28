from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import base64
import logging
import re
import time
import copy
import struct

from memory_reader import MemoryReaderUnavailableError, build_memory_reader
from party_parser import PartyParser
from save_parser import SaveParser

LOGGER = logging.getLogger(__name__)

SAVEBLOCK1_FLAGS_OFFSET = 0x0EE0
SAVEBLOCK_FLAGS_BYTES = 0x120
TRAINER_DEFEAT_FLAG_IDS: Dict[str, int] = {
    "FLAG_DEFEATED_BROCK": 0x4B0,
    "FLAG_DEFEATED_MISTY": 0x4B1,
    "FLAG_DEFEATED_LT_SURGE": 0x4B2,
    "FLAG_DEFEATED_ERIKA": 0x4B3,
    "FLAG_DEFEATED_KOGA": 0x4B4,
    "FLAG_DEFEATED_SABRINA": 0x4B5,
    "FLAG_DEFEATED_BLAINE": 0x4B6,
    "FLAG_DEFEATED_GIOVANNI": 0x4B7,
    "FLAG_DEFEATED_LORELEI": 0x4B8,
    "FLAG_DEFEATED_BRUNO": 0x4B9,
    "FLAG_DEFEATED_AGATHA": 0x4BA,
    "FLAG_DEFEATED_LANCE": 0x4BB,
    "FLAG_DEFEATED_CHAMP": 0x4BC,
}
_TRAINER_FLAG_KEYS_ORDER = list(TRAINER_DEFEAT_FLAG_IDS.keys())

SAVE_TRAINER_NAME_OFFSET = 0x0000
SAVE_TRAINER_NAME_LENGTH = 8
SAVE_TRAINER_ID_OFFSET = 0x000A


def _bit_is_set(raw: bytes, bit_index: int) -> bool:
    if bit_index < 0:
        return False
    byte_index = bit_index // 8
    if byte_index >= len(raw):
        return False
    mask = 1 << (bit_index % 8)
    return (raw[byte_index] & mask) != 0


def _decode_bitmap_from_meta(meta: Dict[str, Any]) -> Optional[bytes]:
    b64_candidates = [
        meta.get("trainer_defeat_flags_b64"),
        meta.get("event_flags_b64"),
    ]
    for encoded in b64_candidates:
        if not isinstance(encoded, str) or not encoded.strip():
            continue
        try:
            return base64.b64decode(encoded)
        except Exception:
            continue

    byte_candidates = [
        meta.get("trainer_defeat_flags_bytes"),
        meta.get("event_flags_bytes"),
    ]
    for raw_list in byte_candidates:
        if not isinstance(raw_list, list):
            continue
        try:
            normalized = bytes(int(v) & 0xFF for v in raw_list)
        except Exception:
            continue
        if normalized:
            return normalized

    return None


def _normalize_trainer_defeat_meta(meta: Dict[str, Any], bitmap: Optional[bytes]) -> Dict[str, Any]:
    out_flags: Dict[str, bool] = {}

    flags_obj = meta.get("trainer_defeat_flags")
    if isinstance(flags_obj, dict):
        for key, value in flags_obj.items():
            out_flags[str(key)] = bool(value)

    keys_obj = meta.get("trainer_defeat_flag_keys")
    if isinstance(keys_obj, list):
        for key in keys_obj:
            out_flags[str(key)] = True

    if bitmap:
        for flag_key, flag_id in TRAINER_DEFEAT_FLAG_IDS.items():
            out_flags[flag_key] = _bit_is_set(bitmap, flag_id)

    canonical: Dict[str, bool] = {}
    for flag_key in _TRAINER_FLAG_KEYS_ORDER:
        canonical[flag_key] = bool(out_flags.get(flag_key, False))

    # Preserve any custom/non-canonical flags that may be provided by
    # emulator bridge scripts (e.g. trainer-specific encounters) so
    # reward logic can react to them.
    extras: Dict[str, bool] = {}
    known = set(_TRAINER_FLAG_KEYS_ORDER)
    for key, value in out_flags.items():
        if key not in known:
            extras[str(key)] = bool(value)

    merged: Dict[str, bool] = {}
    merged.update(canonical)
    for key in sorted(extras.keys()):
        merged[key] = extras[key]

    defeated_keys = [key for key, value in merged.items() if bool(value)]
    meta["trainer_defeat_flags"] = merged
    meta["trainer_defeat_flag_keys"] = defeated_keys
    meta["trainer_defeat_flags_b64"] = base64.b64encode(bitmap).decode("ascii") if bitmap else ""
    return merged


def _flags_signature(flags: Dict[str, bool]) -> tuple:
    return tuple(bool(flags.get(key, False)) for key in _TRAINER_FLAG_KEYS_ORDER)


def _decode_trainer_name(raw_name: bytes) -> str:
    if not raw_name:
        return ""

    out = []
    for value in raw_name:
        if value in (0x00, 0xFF):
            break
        if 32 <= value <= 126:
            out.append(chr(value))
        else:
            out.append("?")
    return "".join(out).strip()


def _extract_trainer_profile_meta(saveblock: bytes) -> Dict[str, Any]:
    if len(saveblock) < (SAVE_TRAINER_ID_OFFSET + 4):
        return {}

    trainer_id_full = struct.unpack_from("<I", saveblock, SAVE_TRAINER_ID_OFFSET)[0]
    public_id = trainer_id_full & 0xFFFF
    secret_id = (trainer_id_full >> 16) & 0xFFFF
    name_raw = saveblock[SAVE_TRAINER_NAME_OFFSET : SAVE_TRAINER_NAME_OFFSET + SAVE_TRAINER_NAME_LENGTH]
    trainer_name = _decode_trainer_name(name_raw)

    return {
        "trainer_id": int(trainer_id_full),
        "trainer_public_id": int(public_id),
        "trainer_secret_id": int(secret_id),
        "trainer_name": trainer_name,
        "trainer_profile_key": f"{public_id:05d}-{secret_id:05d}",
    }


@dataclass
class ProviderPollResult:
    state: Optional[Dict[str, Any]]
    provider: str
    status: str
    detail: str = ""
    timings_ms: Optional[Dict[str, float]] = None


class SaveFileProvider:
    def __init__(
        self,
        *,
        save_parser: SaveParser,
        party_parser: PartyParser,
        save_path: Path,
        poll_seconds: float,
        debug: bool,
        party_only: bool,
        simulate_if_missing: bool,
        parser_mode: str,
    ) -> None:
        self._save_parser = save_parser
        self._party_parser = party_parser
        self._save_path = save_path
        self._poll_seconds = poll_seconds
        self._debug = debug
        self._party_only = party_only
        self._simulate_if_missing = simulate_if_missing
        self._parser_mode = parser_mode

        self._last_mtime: Optional[float] = None
        self._sim_tick = 0
        self._last_trainer_flags_signature: Optional[tuple] = None
        self._last_pc_parse_at: float = 0.0
        self._pc_parse_interval_seconds: float = max(2.0, min(5.0, poll_seconds * 4.0))

    def _make_simulated_state(self) -> Dict[str, Any]:
        pools = [
            [
                (25, "pikachu", "Sparky"),
                (195, "quagsire", "MudWall"),
                (6, "charizard", "FlareJet"),
            ],
            [
                (130, "gyarados", "Riptide"),
                (149, "dragonite", "SkyKing"),
                (94, "gengar", "Shade"),
                (260, "swampert", "Breaker"),
            ],
            [
                (448, "lucario", "Aegis"),
                (248, "tyranitar", "Quake"),
                (376, "metagross", "Core"),
                (242, "blissey", "Nurse"),
                (445, "garchomp", "Fang"),
            ],
        ]
        selected = pools[self._sim_tick % len(pools)]
        party: List[Dict[str, Any]] = []
        for idx, (species_id, species, nickname) in enumerate(selected, start=1):
            party.append(
                {
                    "species": species,
                    "species_id": species_id,
                    "nickname": nickname,
                    "level": 30,
                    "gender": "unknown",
                    "shiny": False,
                    "held_item": None,
                    "slot": idx,
                }
            )
        return {
            "party": party,
            "pc": [],
            "dead": [],
            "meta": {
                "parser_mode": self._parser_mode,
                "provider": "save",
            },
        }

    def poll(self, *, force_parse: bool = False, include_pc_override: Optional[bool] = None) -> ProviderPollResult:
        timings: Dict[str, float] = {}
        t_poll_start = time.perf_counter()

        def _mark(name: str, start: float) -> None:
            timings[name] = (time.perf_counter() - start) * 1000.0

        if not self._save_path.exists():
            if not self._simulate_if_missing:
                return ProviderPollResult(
                    state=None,
                    provider="save",
                    status="unavailable",
                    detail=f"Save file missing: {self._save_path}",
                    timings_ms=timings,
                )

            self._sim_tick += 1
            sim_state = self._make_simulated_state()
            timings["simulated_state"] = (time.perf_counter() - t_poll_start) * 1000.0
            return ProviderPollResult(
                state=sim_state,
                provider="save",
                status="ok",
                detail="Simulated state emitted",
                timings_ms=timings,
            )

        t_stat = time.perf_counter()
        mtime = self._save_path.stat().st_mtime
        _mark("save_stat", t_stat)
        if not force_parse and self._last_mtime is not None and mtime == self._last_mtime:
            timings["total"] = (time.perf_counter() - t_poll_start) * 1000.0
            return ProviderPollResult(state=None, provider="save", status="unchanged", timings_ms=timings)
        self._last_mtime = mtime

        t_read = time.perf_counter()
        parsed_save = self._save_parser.read(self._save_path, debug=self._debug)
        _mark("save_read", t_read)
        if parsed_save is None:
            timings["total"] = (time.perf_counter() - t_poll_start) * 1000.0
            return ProviderPollResult(
                state=None,
                provider="save",
                status="error",
                detail="Save parser returned no data",
                timings_ms=timings,
            )

        include_pc = not self._party_only
        if include_pc_override is not None:
            include_pc = bool(include_pc_override)
        elif include_pc:
            now = time.time()
            if (now - self._last_pc_parse_at) < self._pc_parse_interval_seconds:
                include_pc = False
            else:
                self._last_pc_parse_at = now

        t_parse = time.perf_counter()
        state = self._party_parser.parse(
            parsed_save.saveblock,
            include_pc=include_pc,
            debug=self._debug,
            sections=parsed_save.sections,
            parser_mode=self._parser_mode,
            slot_raw=parsed_save.active_slot_raw,
        )
        _mark("party_parse", t_parse)
        timings["pc_parse_included"] = 1.0 if include_pc else 0.0

        parser_meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
        parser_timings = parser_meta.get("timings_ms") if isinstance(parser_meta.get("timings_ms"), dict) else {}
        for key in ("party_parse", "pc_parse", "memorial_split", "parse_total"):
            value = parser_timings.get(key)
            if isinstance(value, (int, float)):
                timings[f"parser_{key}"] = float(value)

        t_flags = time.perf_counter()
        meta = state.get("meta", {}) or {}
        meta["provider"] = "save"
        meta.update(_extract_trainer_profile_meta(parsed_save.saveblock))
        flags_bitmap: Optional[bytes] = None
        start = SAVEBLOCK1_FLAGS_OFFSET
        end = start + SAVEBLOCK_FLAGS_BYTES
        if len(parsed_save.saveblock) >= end:
            flags_bitmap = parsed_save.saveblock[start:end]
        normalized = _normalize_trainer_defeat_meta(meta, flags_bitmap)
        _mark("trainer_flag_scan", t_flags)
        signature = _flags_signature(normalized)
        if signature != self._last_trainer_flags_signature:
            defeated = [key for key in _TRAINER_FLAG_KEYS_ORDER if normalized.get(key)]
            LOGGER.info(
                "trainer_flags_provider=save defeated_count=%s defeated=%s slot=%s save_index=%s",
                len(defeated),
                defeated,
                parsed_save.active_slot_index,
                parsed_save.save_index,
            )
            self._last_trainer_flags_signature = signature
        state["meta"] = meta
        timings["total"] = (time.perf_counter() - t_poll_start) * 1000.0
        return ProviderPollResult(state=state, provider="save", status="ok", timings_ms=timings)


class EmulatorMemoryProvider:
    def __init__(
        self,
        *,
        enabled: bool,
        backend: str,
        bridge_path: Path,
        stale_after_seconds: float,
    ) -> None:
        self._enabled = enabled
        self._backend = backend
        self._bridge_path = bridge_path
        self._stale_after_seconds = stale_after_seconds
        self._reader = build_memory_reader(
            backend=backend,
            bridge_path=bridge_path,
            stale_after_seconds=stale_after_seconds,
        )
        self._last_status: Optional[str] = None
        self._last_status_detail: str = ""
        self._last_status_warning_at: float = 0.0
        self._status_warning_interval_seconds: float = 60.0
        self._last_good_state: Optional[Dict[str, Any]] = None
        self._last_good_at: float = 0.0
        # Hold last live snapshot longer during transient bridge stalls so
        # overlays don't flicker or bounce between providers.
        self._grace_seconds: float = max(5.0, min(60.0, stale_after_seconds * 6.0))
        self._last_trainer_flags_signature: Optional[tuple] = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def poll(self) -> ProviderPollResult:
        timings: Dict[str, float] = {}
        t_poll_start = time.perf_counter()

        def _mark(name: str, start: float) -> None:
            timings[name] = (time.perf_counter() - start) * 1000.0

        def _normalize_status_detail(status: str, detail: str) -> str:
            text = str(detail or "").strip()
            if not text:
                return ""
            if status == "unavailable":
                lower = text.lower()
                if "memory bridge payload is stale" in lower:
                    # Age increments every poll; keep a stable key so warning
                    # throttling works and logs do not spam continuously.
                    return "memory bridge payload is stale"
                if "memory bridge file" in lower and "not found" in lower:
                    return "memory bridge file missing"
                if "memory bridge" in lower and "invalid" in lower:
                    return "memory bridge payload invalid"
            # Collapse repeated whitespace and dynamic numbers to avoid noisy
            # detail churn defeating rate-limit checks.
            compact = re.sub(r"\s+", " ", text)
            compact = re.sub(r"\d+(?:\.\d+)?", "#", compact)
            return compact

        def _should_log_status(status: str, detail: str) -> bool:
            now = time.time()
            detail_norm = _normalize_status_detail(status, str(detail or ""))
            status_changed = status != self._last_status
            detail_changed = detail_norm != self._last_status_detail
            interval_elapsed = (now - self._last_status_warning_at) >= self._status_warning_interval_seconds
            should_log = status_changed or detail_changed or interval_elapsed
            self._last_status = status
            self._last_status_detail = detail_norm
            if should_log:
                self._last_status_warning_at = now
            return should_log

        if not self._enabled:
            timings["total"] = (time.perf_counter() - t_poll_start) * 1000.0
            return ProviderPollResult(state=None, provider="memory", status="disabled", timings_ms=timings)

        try:
            t_read = time.perf_counter()
            state = self._reader.read_state()
            _mark("memory_read", t_read)
        except MemoryReaderUnavailableError as exc:
            status = "unavailable"
            if _should_log_status(status, str(exc)):
                LOGGER.warning("Memory provider unavailable: %s", exc)
            if self._last_good_state is not None and (time.time() - self._last_good_at) <= self._grace_seconds:
                state = copy.deepcopy(self._last_good_state)
                meta = state.get("meta", {}) or {}
                meta["provider"] = "memory"
                meta["memory_backend"] = self._backend
                meta["memory_bridge_path"] = str(self._bridge_path)
                meta["memory_grace_mode"] = True
                meta["memory_grace_reason"] = "unavailable"
                state["meta"] = meta
                timings["total"] = (time.perf_counter() - t_poll_start) * 1000.0
                return ProviderPollResult(
                    state=state,
                    provider="memory",
                    status="ok",
                    detail="using recent memory state during transient bridge outage",
                    timings_ms=timings,
                )
            timings["total"] = (time.perf_counter() - t_poll_start) * 1000.0
            return ProviderPollResult(
                state=None,
                provider="memory",
                status=status,
                detail=str(exc),
                timings_ms=timings,
            )
        except Exception as exc:
            status = "error"
            if _should_log_status(status, str(exc)):
                LOGGER.exception("Memory provider failed: %s", exc)
            if self._last_good_state is not None and (time.time() - self._last_good_at) <= self._grace_seconds:
                state = copy.deepcopy(self._last_good_state)
                meta = state.get("meta", {}) or {}
                meta["provider"] = "memory"
                meta["memory_backend"] = self._backend
                meta["memory_bridge_path"] = str(self._bridge_path)
                meta["memory_grace_mode"] = True
                meta["memory_grace_reason"] = "error"
                state["meta"] = meta
                timings["total"] = (time.perf_counter() - t_poll_start) * 1000.0
                return ProviderPollResult(
                    state=state,
                    provider="memory",
                    status="ok",
                    detail="using recent memory state during transient bridge error",
                    timings_ms=timings,
                )
            timings["total"] = (time.perf_counter() - t_poll_start) * 1000.0
            return ProviderPollResult(
                state=None,
                provider="memory",
                status=status,
                detail=str(exc),
                timings_ms=timings,
            )

        t_flags = time.perf_counter()
        meta = state.get("meta", {}) or {}
        flags_bitmap = _decode_bitmap_from_meta(meta)
        normalized = _normalize_trainer_defeat_meta(meta, flags_bitmap)
        meta["provider"] = "memory"
        meta["memory_backend"] = self._backend
        meta["memory_bridge_path"] = str(self._bridge_path)
        state["meta"] = meta
        _mark("trainer_flag_scan", t_flags)

        signature = _flags_signature(normalized)
        if signature != self._last_trainer_flags_signature:
            defeated = [key for key in _TRAINER_FLAG_KEYS_ORDER if normalized.get(key)]
            LOGGER.info(
                "trainer_flags_provider=memory defeated_count=%s defeated=%s",
                len(defeated),
                defeated,
            )
            self._last_trainer_flags_signature = signature

        self._last_good_state = copy.deepcopy(state)
        self._last_good_at = time.time()
        self._last_status = "ok"
        self._last_status_detail = ""
        timings["total"] = (time.perf_counter() - t_poll_start) * 1000.0
        return ProviderPollResult(state=state, provider="memory", status="ok", timings_ms=timings)


def choose_provider_order(provider_mode: str) -> List[str]:
    normalized = str(provider_mode or "auto").strip().lower()
    if normalized == "save":
        return ["save"]
    if normalized == "memory":
        return ["memory", "save"]
    return ["memory", "save"]
