from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import argparse
from collections import Counter
import json
import logging
import os
import random
import re
import sys
import time

from party_parser import PartyParser
from config_loader import load_project_config, resolve_tracker_config
from live_ws import LiveWebSocketServer, WebSocketRuntimeConfig
from save_parser import SaveParser
from state_provider import EmulatorMemoryProvider, SaveFileProvider, choose_provider_order
from state_manager import StateManager

LOGGER = logging.getLogger("pokemon_overlay_tracker")


def setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    LOGGER.info(json.dumps(payload, default=str, sort_keys=True))


def make_default_state() -> Dict[str, List[Dict]]:
    return {
        "party": [],
        "pc": [],
        "pc_cached": [],
        "dead": [],
        "meta": {
            "parser_mode": "auto",
        },
    }


def load_debug_state(path: Path) -> Dict[str, List[Dict]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.error("Failed to load debug JSON %s: %s", path, exc)
        return make_default_state()


def summarize_party(state: Dict[str, List[Dict]]) -> str:
    party = state.get("party", [])
    if not party:
        return "(empty)"
    chunks = []
    for mon in party:
        name = mon.get("nickname") or mon.get("species") or "unknown"
        level = mon.get("level")
        species = mon.get("species") or "unknown"
        if level is None:
            chunks.append(f"{name} ({species})")
        else:
            chunks.append(f"{name} ({species}) Lv{level}")
    return ", ".join(chunks)


def make_simulated_state(tick: int) -> Dict[str, List[Dict]]:
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
    selected = pools[tick % len(pools)]
    random.seed(tick)
    party = []
    for idx, (species_id, species, nickname) in enumerate(selected, start=1):
        party.append(
            {
                "species": species,
                "species_id": species_id,
                "nickname": nickname,
                "level": random.randint(15, 65),
                "gender": random.choice(["male", "female"]),
                "shiny": random.choice([False, False, False, True]),
                "held_item": None,
                "slot": idx,
            }
        )

    return {"party": party, "pc": [], "pc_cached": [], "dead": []}


def merge_pc_cache(
    pc_cache: Dict[int, Dict[int, Dict[str, Any]]],
    current_pc: List[Dict[str, Any]],
    *,
    replace_seen_boxes: bool = False,
) -> List[Dict[str, Any]]:
    seen_boxes: set[int] = set()
    if replace_seen_boxes:
        for mon in current_pc:
            box = mon.get("box")
            if isinstance(box, int) and box > 0:
                seen_boxes.add(box)

        for box in seen_boxes:
            pc_cache[box] = {}

    for mon in current_pc:
        if is_suspicious_pc_entry(mon):
            continue
        box = mon.get("box")
        box_slot = mon.get("box_slot")
        if not isinstance(box, int) or box <= 0:
            continue
        if not isinstance(box_slot, int) or box_slot <= 0:
            continue
        pc_cache.setdefault(box, {})[box_slot] = dict(mon)

    merged: List[Dict[str, Any]] = []
    for box in sorted(pc_cache.keys()):
        slot_map = pc_cache[box]
        for box_slot in sorted(slot_map.keys()):
            merged.append(dict(slot_map[box_slot]))
    return merged


def is_suspicious_pc_entry(mon: Dict[str, Any]) -> bool:
    species_id = mon.get("species_id")
    box = mon.get("box")
    box_slot = mon.get("box_slot")

    if not isinstance(species_id, int) or species_id <= 0 or species_id > 3000:
        return True
    if not isinstance(box, int) or box <= 0:
        return True
    if not isinstance(box_slot, int) or box_slot <= 0:
        return True

    held_item = mon.get("held_item")
    if isinstance(held_item, str) and held_item.strip().lower() == "item_65535":
        return True

    nickname = mon.get("nickname")
    if not isinstance(nickname, str) or not nickname.strip():
        return True

    return False


def purge_suspicious_pc_cache(pc_cache: Dict[int, Dict[int, Dict[str, Any]]]) -> int:
    removed = 0
    for box in list(pc_cache.keys()):
        slot_map = pc_cache[box]
        for box_slot in list(slot_map.keys()):
            if is_suspicious_pc_entry(slot_map[box_slot]):
                del slot_map[box_slot]
                removed += 1
        if not slot_map:
            del pc_cache[box]
    return removed


def seed_caches_from_existing_state(
    state_path: Path,
    pc_cache: Dict[int, Dict[int, Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    if not state_path.exists():
        return []

    try:
        existing = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    existing_pc = existing.get("pc_cached") or existing.get("pc") or []
    if isinstance(existing_pc, list):
        merge_pc_cache(pc_cache, existing_pc)
        purge_suspicious_pc_cache(pc_cache)

    dead = existing.get("dead")
    if isinstance(dead, list):
        return [dict(mon) for mon in dead]
    return []


def mon_identity(mon: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        int(mon.get("species_id") or 0),
        str(mon.get("species") or ""),
        str(mon.get("nickname") or ""),
        int(mon.get("level") or 0),
        bool(mon.get("shiny") or False),
    )


def mon_identity_relaxed(mon: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        int(mon.get("species_id") or 0),
        str(mon.get("species") or ""),
        str(mon.get("nickname") or ""),
        bool(mon.get("shiny") or False),
    )


def normalized_nickname(mon: Dict[str, Any]) -> str:
    raw = str(mon.get("nickname") or "").strip().lower()
    if not raw:
        return ""
    # Collapse punctuation/spacing differences between parser variants.
    return re.sub(r"[^a-z0-9]+", "", raw)


def party_signature(party: List[Dict[str, Any]]) -> Tuple[Any, ...]:
    rows: List[Tuple[Any, ...]] = []
    for mon in sorted((party or []), key=lambda p: int(p.get("slot") or 0)):
        rows.append(
            (
                int(mon.get("slot") or 0),
                int(mon.get("species_id") or 0),
                str(mon.get("nickname") or ""),
                int(mon.get("level") or 0),
                bool(mon.get("shiny") or False),
            )
        )
    return tuple(rows)


def pc_signature(pc: List[Dict[str, Any]]) -> Tuple[Any, ...]:
    rows: List[Tuple[Any, ...]] = []
    for mon in sorted(
        (pc or []),
        key=lambda p: (
            int(p.get("box") or 0),
            int(p.get("box_slot") or 0),
            int(p.get("species_id") or 0),
            str(p.get("nickname") or ""),
        ),
    ):
        rows.append(
            (
                int(mon.get("box") or 0),
                int(mon.get("box_slot") or 0),
                int(mon.get("species_id") or 0),
                str(mon.get("nickname") or ""),
                bool(mon.get("shiny") or False),
            )
        )
    return tuple(rows)


def remove_matching_from_pc_cache(
    pc_cache: Dict[int, Dict[int, Dict[str, Any]]],
    target: Dict[str, Any],
) -> bool:
    target_key = mon_identity(target)
    target_relaxed = mon_identity_relaxed(target)
    target_nick = normalized_nickname(target)
    target_shiny = bool(target.get("shiny") or False)
    removed_any = False

    for box in sorted(pc_cache.keys()):
        slot_map = pc_cache[box]
        for box_slot in sorted(slot_map.keys()):
            candidate = slot_map[box_slot]
            candidate_nick = normalized_nickname(candidate)
            candidate_shiny = bool(candidate.get("shiny") or False)
            same_nickname_line = bool(target_nick) and candidate_nick == target_nick and candidate_shiny == target_shiny
            if (
                mon_identity(candidate) == target_key
                or mon_identity_relaxed(candidate) == target_relaxed
                or same_nickname_line
            ):
                del slot_map[box_slot]
                removed_any = True

    for box in list(pc_cache.keys()):
        if not pc_cache[box]:
            del pc_cache[box]

    return removed_any


def add_to_pc_cache_first_free(
    pc_cache: Dict[int, Dict[int, Dict[str, Any]]],
    mon: Dict[str, Any],
    preferred_box: int = 1,
) -> None:
    target_relaxed = mon_identity_relaxed(mon)
    for existing_box in sorted(pc_cache.keys()):
        for existing in pc_cache[existing_box].values():
            if mon_identity_relaxed(existing) == target_relaxed:
                return

    box = preferred_box if preferred_box > 0 else 1
    slot_map = pc_cache.setdefault(box, {})

    free_slot = None
    for slot in range(1, 31):
        if slot not in slot_map:
            free_slot = slot
            break
    if free_slot is None:
        free_slot = max(slot_map.keys(), default=0) + 1

    candidate = dict(mon)
    candidate["box"] = box
    candidate["box_slot"] = free_slot
    candidate["slot"] = free_slot
    slot_map[free_slot] = candidate


def remove_matching_from_dead_cache(
    dead_cache: List[Dict[str, Any]],
    target: Dict[str, Any],
) -> bool:
    target_key = mon_identity(target)
    target_relaxed = mon_identity_relaxed(target)
    for idx, candidate in enumerate(dead_cache):
        if mon_identity(candidate) == target_key or mon_identity_relaxed(candidate) == target_relaxed:
            del dead_cache[idx]
            return True
    return False


def add_to_dead_cache_end(dead_cache: List[Dict[str, Any]], mon: Dict[str, Any]) -> None:
    target_relaxed = mon_identity_relaxed(mon)
    for existing in dead_cache:
        if mon_identity_relaxed(existing) == target_relaxed:
            return

    next_slot = 1
    used_slots = {
        int(existing.get("box_slot") or 0)
        for existing in dead_cache
        if int(existing.get("box") or 0) == 25
    }
    while next_slot in used_slots:
        next_slot += 1

    candidate = dict(mon)
    candidate["box"] = 25
    candidate["box_slot"] = next_slot
    candidate["slot"] = next_slot
    dead_cache.append(candidate)


def prune_dead_cache_against_active(
    dead_cache: List[Dict[str, Any]],
    party: List[Dict[str, Any]],
    pc_cached: List[Dict[str, Any]],
) -> None:
    active_keys = {mon_identity_relaxed(mon) for mon in (party or [])}
    active_keys.update(mon_identity_relaxed(mon) for mon in (pc_cached or []))

    dead_cache[:] = [
        dict(mon)
        for mon in dead_cache
        if mon_identity_relaxed(mon) not in active_keys
    ]


def apply_memory_party_swap_inference(
    pc_cache: Dict[int, Dict[int, Dict[str, Any]]],
    previous_party: List[Dict[str, Any]],
    current_party: List[Dict[str, Any]],
    dead_cache: Optional[List[Dict[str, Any]]] = None,
    revived_dead_counts: Optional[Dict[Tuple[Any, ...], int]] = None,
) -> None:
    if not previous_party or not current_party:
        return

    prev_counts = Counter(mon_identity(mon) for mon in previous_party)
    curr_counts = Counter(mon_identity(mon) for mon in current_party)

    departed_keys: List[Tuple[Any, ...]] = []
    arrived_keys: List[Tuple[Any, ...]] = []

    for key, count in prev_counts.items():
        missing = count - curr_counts.get(key, 0)
        if missing > 0:
            departed_keys.extend([key] * missing)

    for key, count in curr_counts.items():
        gained = count - prev_counts.get(key, 0)
        if gained > 0:
            arrived_keys.extend([key] * gained)

    if not departed_keys and not arrived_keys:
        return

    prev_lookup: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    for mon in previous_party:
        prev_lookup.setdefault(mon_identity(mon), []).append(mon)

    curr_lookup: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    for mon in current_party:
        curr_lookup.setdefault(mon_identity(mon), []).append(mon)

    memorial_arrivals = 0

    for key in arrived_keys:
        options = curr_lookup.get(key, [])
        if options:
            arrived = options.pop(0)
            remove_matching_from_pc_cache(pc_cache, arrived)
            if dead_cache is not None and remove_matching_from_dead_cache(dead_cache, arrived):
                memorial_arrivals += 1
                if revived_dead_counts is not None:
                    revived_key = mon_identity_relaxed(arrived)
                    revived_dead_counts[revived_key] = int(revived_dead_counts.get(revived_key, 0)) + 1

    for key in departed_keys:
        options = prev_lookup.get(key, [])
        if options:
            departed = options.pop(0)
            departed_key = mon_identity_relaxed(departed)
            revived_remaining = 0
            if revived_dead_counts is not None:
                revived_remaining = int(revived_dead_counts.get(departed_key, 0))

            if dead_cache is not None and (memorial_arrivals > 0 or revived_remaining > 0):
                add_to_dead_cache_end(dead_cache, departed)
                if memorial_arrivals > 0:
                    memorial_arrivals -= 1
                if revived_dead_counts is not None and revived_remaining > 0:
                    if revived_remaining <= 1:
                        revived_dead_counts.pop(departed_key, None)
                    else:
                        revived_dead_counts[departed_key] = revived_remaining - 1
            else:
                add_to_pc_cache_first_free(pc_cache, departed, preferred_box=1)


def prune_pc_cache_against_party(
    pc_cache: Dict[int, Dict[int, Dict[str, Any]]],
    party: List[Dict[str, Any]],
) -> None:
    # Invariant: a mon should never be shown in both active party and PC.
    for mon in party or []:
        remove_matching_from_pc_cache(pc_cache, mon)


def prune_pc_list_against_party(
    pc_list: List[Dict[str, Any]],
    party: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not pc_list or not party:
        return [dict(mon) for mon in (pc_list or [])]

    party_exact = {mon_identity(mon) for mon in (party or [])}
    party_relaxed = {mon_identity_relaxed(mon) for mon in (party or [])}
    party_names = {
        (normalized_nickname(mon), bool(mon.get("shiny") or False))
        for mon in (party or [])
        if normalized_nickname(mon)
    }

    out: List[Dict[str, Any]] = []
    for mon in pc_list:
        key_exact = mon_identity(mon)
        key_relaxed = mon_identity_relaxed(mon)
        name_key = (normalized_nickname(mon), bool(mon.get("shiny") or False))

        if key_exact in party_exact or key_relaxed in party_relaxed:
            continue
        if name_key[0] and name_key in party_names:
            continue

        out.append(dict(mon))

    return out


def prune_pc_cache_against_dead(
    pc_cache: Dict[int, Dict[int, Dict[str, Any]]],
    dead_cache: List[Dict[str, Any]],
) -> None:
    dead_keys = {mon_identity_relaxed(mon) for mon in (dead_cache or [])}
    for box in list(pc_cache.keys()):
        slot_map = pc_cache[box]
        for box_slot in list(slot_map.keys()):
            if mon_identity_relaxed(slot_map[box_slot]) in dead_keys:
                del slot_map[box_slot]
        if not slot_map:
            del pc_cache[box]


def log_save_diagnostics(save_parser: SaveParser, save_path: Path) -> None:
    diagnostic = save_parser.inspect_save(save_path)
    if diagnostic is None:
        LOGGER.error("Save diagnostics failed for %s", save_path)
        return

    LOGGER.info("Save diagnostic file size: %s bytes", diagnostic.file_size)
    for slot in diagnostic.slots:
        LOGGER.info(
            "Slot %s: valid_sections=%s section_ids=%s save_indices=%s signatures=%s",
            slot.slot_index,
            slot.valid_sections,
            slot.section_ids,
            slot.save_indices,
            slot.signatures,
        )

    LOGGER.info(
        "Selected active save slot=%s save_index=%s",
        diagnostic.selected_slot,
        diagnostic.selected_save_index,
    )


def run_loop(
    save_path: Path,
    state_path: Path,
    poll_seconds: float,
    debug: bool,
    party_only: bool,
    simulate_if_missing: bool,
    parser_mode: str,
    websocket_enabled: bool,
    websocket_host: str,
    websocket_port: int,
    websocket_heartbeat_seconds: float,
    provider_mode: str,
    memory_enabled: bool,
    memory_backend: str,
    memory_bridge_path: Path,
    memory_poll_seconds: float,
    memory_stale_after_seconds: float,
) -> None:
    save_parser = SaveParser()
    party_parser = PartyParser(parser_mode=parser_mode)
    state_manager = StateManager(state_path)
    save_provider = SaveFileProvider(
        save_parser=save_parser,
        party_parser=party_parser,
        save_path=save_path,
        poll_seconds=poll_seconds,
        debug=debug,
        party_only=party_only,
        simulate_if_missing=simulate_if_missing,
        parser_mode=parser_mode,
    )
    memory_provider = EmulatorMemoryProvider(
        enabled=memory_enabled,
        backend=memory_backend,
        bridge_path=memory_bridge_path,
        stale_after_seconds=memory_stale_after_seconds,
    )

    debug_json_path = os.getenv("POKEMON_OVERLAY_DEBUG_JSON")
    if debug_json_path:
        LOGGER.warning("Debug mode enabled: using JSON state from %s", debug_json_path)

    pc_cache: Dict[int, Dict[int, Dict[str, Any]]] = {}
    dead_cache: List[Dict[str, Any]] = seed_caches_from_existing_state(state_path, pc_cache)
    last_party_snapshot: List[Dict[str, Any]] = []
    pc_quarantine_applied = False
    stable_party_sig: Optional[Tuple[Any, ...]] = None
    stable_party_snapshot: List[Dict[str, Any]] = []
    candidate_party_sig: Optional[Tuple[Any, ...]] = None
    candidate_party_streak = 0
    stable_ambiguous_pc_sig: Optional[Tuple[Any, ...]] = None
    stable_ambiguous_pc_snapshot: List[Dict[str, Any]] = []
    candidate_ambiguous_pc_sig: Optional[Tuple[Any, ...]] = None
    candidate_ambiguous_pc_streak = 0
    revived_dead_counts: Dict[Tuple[Any, ...], int] = {}
    save_reconcile_interval_seconds = max(3.0, poll_seconds * 4.0)
    last_forced_save_reconcile_at = 0.0

    ws_server = LiveWebSocketServer(
        WebSocketRuntimeConfig(
            enabled=websocket_enabled,
            host=websocket_host,
            port=websocket_port,
            heartbeat_seconds=websocket_heartbeat_seconds,
        )
    )
    ws_started = ws_server.start()
    if websocket_enabled and not ws_started:
        raise RuntimeError(
            "WebSocket server failed to start while websocket is enabled. "
            "Another tracker instance may already be running on the same port."
        )

    log_event(
        "tracker_start",
        save_path=str(save_path),
        state_path=str(state_path),
        poll_seconds=round(poll_seconds, 3),
        party_only=party_only,
        simulate_if_missing=simulate_if_missing,
        parser_mode=parser_mode,
        provider_mode=provider_mode,
        memory_enabled=memory_enabled,
        memory_backend=memory_backend,
        memory_bridge_path=str(memory_bridge_path),
        websocket_enabled=websocket_enabled,
        websocket_host=websocket_host,
        websocket_port=websocket_port,
    )
    ws_server.broadcast_status("starting", "Tracker started")
    if debug:
        log_save_diagnostics(save_parser, save_path)

    # Ensure an initial state exists even before the first save parse.
    state_manager.update_if_changed(make_default_state())

    try:
        provider_order = choose_provider_order(provider_mode)
        sleep_seconds = max(0.05, min(poll_seconds, memory_poll_seconds if memory_enabled else poll_seconds))
        memory_warning_active = False
        while True:
            if debug_json_path:
                state = load_debug_state(Path(debug_json_path))
                changed = state_manager.update_if_changed(state)
                if changed:
                    mode_name = str((state.get("meta", {}) or {}).get("parser_mode", parser_mode))
                    ws_server.broadcast_state(state, parser_mode=mode_name, debug=debug)
                time.sleep(sleep_seconds)
                continue

            chosen_state: Optional[Dict[str, Any]] = None
            chosen_provider = "save"
            memory_unavailable_detail = ""

            for provider_name in provider_order:
                if provider_name == "memory":
                    result = memory_provider.poll()
                    if result.status == "ok" and result.state is not None:
                        chosen_state = result.state
                        chosen_provider = "memory"
                        break
                    if result.status in ("unavailable", "error"):
                        memory_unavailable_detail = result.detail
                    continue

                result = save_provider.poll()
                if result.status == "ok" and result.state is not None:
                    chosen_state = result.state
                    chosen_provider = "save"
                    break

            if chosen_state is None:
                if provider_mode.lower() in ("auto", "memory") and memory_unavailable_detail:
                    if not memory_warning_active:
                        ws_server.broadcast_status(
                            "warning",
                            f"Memory provider unavailable, using save fallback: {memory_unavailable_detail}",
                        )
                        memory_warning_active = True
                time.sleep(sleep_seconds)
                continue

            if (
                chosen_provider == "save"
                and provider_mode.lower() in ("auto", "memory")
                and memory_unavailable_detail
            ):
                if not memory_warning_active:
                    ws_server.broadcast_status(
                        "warning",
                        f"Memory provider unavailable, using save fallback: {memory_unavailable_detail}",
                    )
                    memory_warning_active = True
            else:
                memory_warning_active = False

            state = chosen_state
            party_now = list(state.get("party", []))
            meta = state.get("meta", {}) if isinstance(state.get("meta"), dict) else {}
            bridge_pc = state.get("pc", [])
            bridge_pc_trusted = list(bridge_pc) if isinstance(bridge_pc, list) else []

            pc_scope = str(meta.get("pc_scope") or "").strip().lower()
            pc_box_known = bool(meta.get("pc_box_known", True))
            if chosen_provider == "memory" and pc_scope == "current_box" and not pc_box_known:
                # Do not merge ambiguous current-box snapshots into shared cache,
                # otherwise unknown boxes can pollute configured Box 1 views.
                if not pc_quarantine_applied:
                    pc_quarantine_applied = True
                    log_event(
                        "pc_cache_quarantine",
                        reason="untrusted_current_box_payload",
                        action="ignore_bridge_pc",
                    )

                # Live bridge party can oscillate between contradictory snapshots
                # for a few frames; require persistence before accepting changes.
                current_sig = party_signature(party_now)
                if stable_party_sig is None:
                    stable_party_sig = current_sig
                    stable_party_snapshot = [dict(mon) for mon in party_now]

                if current_sig != stable_party_sig:
                    if candidate_party_sig == current_sig:
                        candidate_party_streak += 1
                    else:
                        candidate_party_sig = current_sig
                        candidate_party_streak = 1

                    if candidate_party_streak >= 3:
                        stable_party_sig = current_sig
                        stable_party_snapshot = [dict(mon) for mon in party_now]
                        candidate_party_sig = None
                        candidate_party_streak = 0
                    else:
                        stable_keys = Counter(mon_identity_relaxed(mon) for mon in stable_party_snapshot)
                        current_keys = Counter(mon_identity_relaxed(mon) for mon in party_now)
                        add_candidates = Counter(current_keys)
                        add_candidates.subtract(stable_keys)
                        for key, count in add_candidates.items():
                            if count <= 0:
                                continue
                            for mon in party_now:
                                if mon_identity_relaxed(mon) == key:
                                    add_to_pc_cache_first_free(pc_cache, mon, preferred_box=1)
                                    count -= 1
                                    if count <= 0:
                                        break
                        state["party"] = [dict(mon) for mon in stable_party_snapshot]
                        party_now = list(state.get("party", []))
                else:
                    candidate_party_sig = None
                    candidate_party_streak = 0

                current_pc_sig = pc_signature(bridge_pc_trusted)
                if stable_ambiguous_pc_sig is None:
                    stable_ambiguous_pc_sig = current_pc_sig
                    stable_ambiguous_pc_snapshot = [dict(mon) for mon in bridge_pc_trusted]

                if current_pc_sig != stable_ambiguous_pc_sig:
                    if candidate_ambiguous_pc_sig == current_pc_sig:
                        candidate_ambiguous_pc_streak += 1
                    else:
                        candidate_ambiguous_pc_sig = current_pc_sig
                        candidate_ambiguous_pc_streak = 1

                    if candidate_ambiguous_pc_streak >= 3:
                        stable_ambiguous_pc_sig = current_pc_sig
                        stable_ambiguous_pc_snapshot = [dict(mon) for mon in bridge_pc_trusted]
                        candidate_ambiguous_pc_sig = None
                        candidate_ambiguous_pc_streak = 0
                    else:
                        bridge_pc_trusted = [dict(mon) for mon in stable_ambiguous_pc_snapshot]
                else:
                    candidate_ambiguous_pc_sig = None
                    candidate_ambiguous_pc_streak = 0

                state["pc"] = []

            has_live_pc = len(bridge_pc_trusted) > 0

            if chosen_provider == "memory" and not has_live_pc:
                # Memory bridge currently cannot provide trustworthy full PC/dead,
                # so reconcile cache-only zones from save snapshots when available.
                now = time.time()
                force_reconcile = (now - last_forced_save_reconcile_at) >= save_reconcile_interval_seconds
                save_reconcile = save_provider.poll(force_parse=force_reconcile)
                if force_reconcile:
                    last_forced_save_reconcile_at = now
                if save_reconcile.status == "ok" and save_reconcile.state is not None:
                    save_state = save_reconcile.state
                    save_dead = save_state.get("dead", [])
                    save_pc = save_state.get("pc", [])

                    if isinstance(save_dead, list):
                        dead_cache = [dict(mon) for mon in save_dead]

                    if isinstance(save_pc, list):
                        merge_pc_cache(pc_cache, save_pc, replace_seen_boxes=True)

            if chosen_provider == "memory":
                if not has_live_pc:
                    apply_memory_party_swap_inference(
                        pc_cache,
                        last_party_snapshot,
                        party_now,
                        dead_cache=dead_cache,
                        revived_dead_counts=revived_dead_counts,
                    )

                # Keep memorial visible when bridge does not emit dead entries.
                if not state.get("dead") and dead_cache:
                    state["dead"] = [dict(mon) for mon in dead_cache]

            current_dead = state.get("dead", [])
            if current_dead:
                dead_cache = [dict(mon) for mon in current_dead]

            prune_pc_cache_against_party(pc_cache, party_now)
            prune_pc_cache_against_dead(pc_cache, dead_cache)
            removed_suspicious = purge_suspicious_pc_cache(pc_cache)
            if removed_suspicious > 0:
                log_event("pc_cache_cleanup", removed=removed_suspicious)

            replace_seen_boxes = chosen_provider == "memory" and has_live_pc
            state["pc_cached"] = merge_pc_cache(
                pc_cache,
                bridge_pc_trusted,
                replace_seen_boxes=replace_seen_boxes,
            )
            state["pc_cached"] = prune_pc_list_against_party(
                state.get("pc_cached", []),
                party_now,
            )
            prune_dead_cache_against_active(
                dead_cache,
                party_now,
                state.get("pc_cached", []),
            )
            if chosen_provider == "memory":
                state["dead"] = [dict(mon) for mon in dead_cache]
            last_party_snapshot = [dict(mon) for mon in party_now]

            updated = state_manager.update_if_changed(state)
            if updated:
                log_event(
                    "provider_update",
                    provider=chosen_provider,
                    parser_mode=(state.get("meta", {}) or {}).get("parser_mode", parser_mode),
                    party_count=len(state.get("party", [])),
                    pc_count=len(state.get("pc", [])),
                    dead_count=len(state.get("dead", [])),
                    summary=summarize_party(state),
                )
                log_event(
                    "state_write",
                    party=len(state.get("party", [])),
                    pc=len(state.get("pc", [])),
                    dead=len(state.get("dead", [])),
                )
                mode_name = str((state.get("meta", {}) or {}).get("parser_mode", parser_mode))
                ws_server.broadcast_state(state, parser_mode=mode_name, debug=debug)
                ws_server.broadcast_status("ok", f"State updated ({chosen_provider})")

            time.sleep(sleep_seconds)

    except KeyboardInterrupt:
        LOGGER.info("Tracker stopped by user.")
    except Exception as exc:
        LOGGER.exception("Unhandled tracker error: %s", exc)
        ws_server.broadcast_status("error", f"Unhandled tracker error: {exc}")
    finally:
        ws_server.broadcast_status("stopped", "Tracker stopped")
        ws_server.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pokemon Nuzlocke overlay save tracker")
    parser.add_argument(
        "--config",
        default="../config.json",
        help="Path to project config.json",
    )
    parser.add_argument(
        "--save",
        dest="save_path",
        help="Path to emulator .sav file",
    )
    parser.add_argument(
        "--save-path",
        dest="save_path",
        help="Path to emulator .sav file",
    )
    parser.add_argument(
        "--state-path",
        default=None,
        help="Path to output state JSON file",
    )
    parser.add_argument(
        "--poll-seconds",
        default=None,
        type=float,
        help="Polling interval in seconds",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--party-only",
        action="store_true",
        help="Only parse party data (skip PC parsing) for focused integration testing",
    )
    parser.add_argument(
        "--simulate-if-missing",
        action="store_true",
        help="Generate rotating mock data when save file is missing",
    )
    parser.add_argument(
        "--parser-mode",
        choices=["auto", "vanilla_firered", "radical_red"],
        default=None,
        help="Force parser mode; default is auto-detection",
    )
    args = parser.parse_args()
    return args


def main() -> int:
    args = parse_args()

    config_path = Path(args.config).expanduser().resolve()
    config_dir = config_path.parent

    def resolve_user_path(raw_path: str) -> Path:
        base_path = Path(raw_path).expanduser()
        if base_path.is_absolute():
            return base_path.resolve()
        return (config_dir / base_path).resolve()

    config_payload = load_project_config(config_path)
    tracker_config = resolve_tracker_config(
        config_payload=config_payload,
        save_path=args.save_path,
        state_path=args.state_path,
        poll_seconds=args.poll_seconds,
        debug=args.debug,
        party_only=args.party_only,
        simulate_if_missing=args.simulate_if_missing,
        parser_mode=args.parser_mode,
    )

    setup_logging(tracker_config.debug)

    if not tracker_config.save_path:
        LOGGER.error("No save path configured. Set tracker.save_path in config.json or pass --save-path")
        return 2

    save_path = resolve_user_path(tracker_config.save_path)
    state_path = resolve_user_path(tracker_config.state_path)
    memory_bridge_path = resolve_user_path(tracker_config.memory_bridge_path)

    run_loop(
        save_path=save_path,
        state_path=state_path,
        poll_seconds=max(tracker_config.poll_seconds, 0.1),
        debug=tracker_config.debug,
        party_only=tracker_config.party_only,
        simulate_if_missing=tracker_config.simulate_if_missing,
        parser_mode=tracker_config.parser_mode,
        websocket_enabled=tracker_config.websocket_enabled,
        websocket_host=tracker_config.websocket_host,
        websocket_port=tracker_config.websocket_port,
        websocket_heartbeat_seconds=tracker_config.websocket_heartbeat_seconds,
        provider_mode=tracker_config.provider_mode,
        memory_enabled=tracker_config.memory_enabled,
        memory_backend=tracker_config.memory_backend,
        memory_bridge_path=memory_bridge_path,
        memory_poll_seconds=tracker_config.memory_poll_seconds,
        memory_stale_after_seconds=tracker_config.memory_stale_after_seconds,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
