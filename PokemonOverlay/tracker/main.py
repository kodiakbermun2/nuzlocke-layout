from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import argparse
import json
import logging
import os
import random
import sys
import time

from party_parser import PartyParser
from config_loader import load_project_config, resolve_tracker_config
from save_parser import SaveParser
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
        "dead": [],
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

    return {"party": party, "pc": [], "dead": []}


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
) -> None:
    save_parser = SaveParser()
    party_parser = PartyParser(parser_mode=parser_mode)
    state_manager = StateManager(state_path)

    debug_json_path = os.getenv("POKEMON_OVERLAY_DEBUG_JSON")
    if debug_json_path:
        LOGGER.warning("Debug mode enabled: using JSON state from %s", debug_json_path)

    last_mtime = None
    sim_tick = 0

    log_event(
        "tracker_start",
        save_path=str(save_path),
        state_path=str(state_path),
        poll_seconds=round(poll_seconds, 3),
        party_only=party_only,
        simulate_if_missing=simulate_if_missing,
        parser_mode=parser_mode,
    )
    if debug:
        log_save_diagnostics(save_parser, save_path)

    # Ensure an initial state exists even before the first save parse.
    state_manager.update_if_changed(make_default_state())

    while True:
        try:
            if debug_json_path:
                state = load_debug_state(Path(debug_json_path))
                state_manager.update_if_changed(state)
                time.sleep(poll_seconds)
                continue

            if not save_path.exists():
                if simulate_if_missing:
                    sim_tick += 1
                    LOGGER.warning("Save file missing: %s. Emitting simulated state tick=%s", save_path, sim_tick)
                    sim_state = make_simulated_state(sim_tick)
                    wrote = state_manager.update_if_changed(sim_state)
                    if wrote:
                        log_event(
                            "simulated_state_write",
                            party_count=len(sim_state.get("party", [])),
                            summary=summarize_party(sim_state),
                        )
                    time.sleep(max(poll_seconds, 2.0))
                    continue

                LOGGER.error("Save file missing: %s", save_path)
                time.sleep(poll_seconds)
                continue

            mtime = save_path.stat().st_mtime
            if last_mtime is not None and mtime == last_mtime:
                time.sleep(poll_seconds)
                continue

            mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
            log_event("save_changed", modified_at=mtime_str, mtime=mtime)
            last_mtime = mtime

            read_start = time.perf_counter()
            parsed_save = save_parser.read(save_path, debug=debug)
            read_ms = (time.perf_counter() - read_start) * 1000

            if parsed_save is None:
                LOGGER.error("Save parsing failed. Keeping previous state.")
                time.sleep(poll_seconds)
                continue

            log_event(
                "save_read_ok",
                active_slot=parsed_save.active_slot_index,
                save_index=parsed_save.save_index,
                read_ms=round(read_ms, 2),
            )

            if debug:
                diagnostics = party_parser.party_offset_diagnostics(parsed_save.saveblock)
                for row in diagnostics:
                    LOGGER.debug(
                        "Offset probe count_offset=0x%X count=%s candidates=%s",
                        row["count_offset"],
                        row["count_value"],
                        row["party_candidates"],
                    )

            parse_start = time.perf_counter()
            state = party_parser.parse(
                parsed_save.saveblock,
                include_pc=not party_only,
                debug=debug,
                sections=parsed_save.sections,
                parser_mode=parser_mode,
            )
            parse_ms = (time.perf_counter() - parse_start) * 1000

            log_event(
                "parse_ok",
                parser_mode=(state.get("meta", {}) or {}).get("parser_mode", parser_mode),
                party_count=len(state.get("party", [])),
                pc_count=len(state.get("pc", [])),
                dead_count=len(state.get("dead", [])),
                parse_ms=round(parse_ms, 2),
                summary=summarize_party(state),
            )

            updated = state_manager.update_if_changed(state)
            if updated:
                log_event(
                    "state_write",
                    party=len(state.get("party", [])),
                    pc=len(state.get("pc", [])),
                    dead=len(state.get("dead", [])),
                )
            else:
                log_event("state_unchanged")

            time.sleep(poll_seconds)

        except KeyboardInterrupt:
            LOGGER.info("Tracker stopped by user.")
            break
        except Exception as exc:
            LOGGER.exception("Unhandled tracker error: %s", exc)
            time.sleep(poll_seconds)


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

    run_loop(
        save_path=save_path,
        state_path=state_path,
        poll_seconds=max(tracker_config.poll_seconds, 0.1),
        debug=tracker_config.debug,
        party_only=tracker_config.party_only,
        simulate_if_missing=tracker_config.simulate_if_missing,
        parser_mode=tracker_config.parser_mode,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
