from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging
import time
import copy

from memory_reader import MemoryReaderUnavailableError, build_memory_reader
from party_parser import PartyParser
from save_parser import SaveParser

LOGGER = logging.getLogger(__name__)


@dataclass
class ProviderPollResult:
    state: Optional[Dict[str, Any]]
    provider: str
    status: str
    detail: str = ""


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

    def poll(self, *, force_parse: bool = False) -> ProviderPollResult:
        if not self._save_path.exists():
            if not self._simulate_if_missing:
                return ProviderPollResult(
                    state=None,
                    provider="save",
                    status="unavailable",
                    detail=f"Save file missing: {self._save_path}",
                )

            self._sim_tick += 1
            sim_state = self._make_simulated_state()
            return ProviderPollResult(
                state=sim_state,
                provider="save",
                status="ok",
                detail="Simulated state emitted",
            )

        mtime = self._save_path.stat().st_mtime
        if not force_parse and self._last_mtime is not None and mtime == self._last_mtime:
            return ProviderPollResult(state=None, provider="save", status="unchanged")
        self._last_mtime = mtime

        parsed_save = self._save_parser.read(self._save_path, debug=self._debug)
        if parsed_save is None:
            return ProviderPollResult(
                state=None,
                provider="save",
                status="error",
                detail="Save parser returned no data",
            )

        state = self._party_parser.parse(
            parsed_save.saveblock,
            include_pc=not self._party_only,
            debug=self._debug,
            sections=parsed_save.sections,
            parser_mode=self._parser_mode,
            slot_raw=parsed_save.active_slot_raw,
        )
        meta = state.get("meta", {}) or {}
        meta["provider"] = "save"
        state["meta"] = meta
        return ProviderPollResult(state=state, provider="save", status="ok")


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
        self._last_good_state: Optional[Dict[str, Any]] = None
        self._last_good_at: float = 0.0
        # Hold last live snapshot longer during transient bridge stalls so
        # overlays don't flicker or bounce between providers.
        self._grace_seconds: float = max(5.0, min(60.0, stale_after_seconds * 6.0))

    @property
    def enabled(self) -> bool:
        return self._enabled

    def poll(self) -> ProviderPollResult:
        if not self._enabled:
            return ProviderPollResult(state=None, provider="memory", status="disabled")

        try:
            state = self._reader.read_state()
        except MemoryReaderUnavailableError as exc:
            status = "unavailable"
            if self._last_status != status:
                LOGGER.warning("Memory provider unavailable: %s", exc)
            self._last_status = status
            if self._last_good_state is not None and (time.time() - self._last_good_at) <= self._grace_seconds:
                state = copy.deepcopy(self._last_good_state)
                meta = state.get("meta", {}) or {}
                meta["provider"] = "memory"
                meta["memory_backend"] = self._backend
                meta["memory_bridge_path"] = str(self._bridge_path)
                meta["memory_grace_mode"] = True
                meta["memory_grace_reason"] = "unavailable"
                state["meta"] = meta
                return ProviderPollResult(
                    state=state,
                    provider="memory",
                    status="ok",
                    detail="using recent memory state during transient bridge outage",
                )
            return ProviderPollResult(
                state=None,
                provider="memory",
                status=status,
                detail=str(exc),
            )
        except Exception as exc:
            status = "error"
            if self._last_status != status:
                LOGGER.exception("Memory provider failed: %s", exc)
            self._last_status = status
            if self._last_good_state is not None and (time.time() - self._last_good_at) <= self._grace_seconds:
                state = copy.deepcopy(self._last_good_state)
                meta = state.get("meta", {}) or {}
                meta["provider"] = "memory"
                meta["memory_backend"] = self._backend
                meta["memory_bridge_path"] = str(self._bridge_path)
                meta["memory_grace_mode"] = True
                meta["memory_grace_reason"] = "error"
                state["meta"] = meta
                return ProviderPollResult(
                    state=state,
                    provider="memory",
                    status="ok",
                    detail="using recent memory state during transient bridge error",
                )
            return ProviderPollResult(
                state=None,
                provider="memory",
                status=status,
                detail=str(exc),
            )

        meta = state.get("meta", {}) or {}
        meta["provider"] = "memory"
        meta["memory_backend"] = self._backend
        meta["memory_bridge_path"] = str(self._bridge_path)
        state["meta"] = meta

        self._last_good_state = copy.deepcopy(state)
        self._last_good_at = time.time()
        self._last_status = "ok"
        return ProviderPollResult(state=state, provider="memory", status="ok")


def choose_provider_order(provider_mode: str) -> List[str]:
    normalized = str(provider_mode or "auto").strip().lower()
    if normalized == "save":
        return ["save"]
    if normalized == "memory":
        return ["memory", "save"]
    return ["memory", "save"]
