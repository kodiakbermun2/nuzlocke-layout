from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple
import argparse
import json
import time


REQUIRED_TOP_LEVEL = ("timestamp_ms", "party", "pc", "dead", "meta")
REQUIRED_PARTY_KEYS = (
    "species",
    "species_id",
    "nickname",
    "level",
    "gender",
    "shiny",
    "held_item",
    "slot",
    "current_hp",
    "max_hp",
)


def validate_schema(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    for key in REQUIRED_TOP_LEVEL:
        if key not in payload:
            errors.append(f"Missing top-level key: {key}")

    if not isinstance(payload.get("timestamp_ms"), (int, float)):
        errors.append("timestamp_ms must be number")

    for key in ("party", "pc", "dead"):
        if not isinstance(payload.get(key), list):
            errors.append(f"{key} must be array")

    if not isinstance(payload.get("meta"), dict):
        errors.append("meta must be object")

    party = payload.get("party", [])
    if isinstance(party, list):
        for i, mon in enumerate(party, start=1):
            if not isinstance(mon, dict):
                errors.append(f"party[{i}] must be object")
                continue
            for key in REQUIRED_PARTY_KEYS:
                if key not in mon:
                    errors.append(f"party[{i}] missing key {key}")
            if "status" in mon and mon["status"] is not None and not isinstance(mon["status"], str):
                errors.append(f"party[{i}] status must be string|null")
            if "types" in mon and not isinstance(mon["types"], list):
                errors.append(f"party[{i}] types must be array")

    return len(errors) == 0, errors


def summarize_party(party: List[Dict[str, Any]]) -> str:
    if not party:
        return "(empty)"
    rows = []
    for mon in party:
        name = mon.get("nickname") or mon.get("species") or "unknown"
        species = mon.get("species") or "unknown"
        hp = f"{mon.get('current_hp', '?')}/{mon.get('max_hp', '?')}"
        level = mon.get("level", "?")
        status = mon.get("status") or "OK"
        rows.append(f"{name} ({species}) Lv{level} HP {hp} {status}")
    return " | ".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and watch memory_state.json bridge payload")
    parser.add_argument("--path", default="memory_state.json", help="Path to memory bridge json")
    parser.add_argument("--poll-ms", type=int, default=100, help="Watch polling interval in ms")
    parser.add_argument("--stale-ms", type=int, default=1200, help="Stale threshold in ms")
    parser.add_argument("--max-events", type=int, default=20, help="Stop after N file updates; 0 means infinite")
    args = parser.parse_args()

    path = Path(args.path).expanduser().resolve()
    poll_seconds = max(0.01, args.poll_ms / 1000.0)
    stale_seconds = max(0.1, args.stale_ms / 1000.0)

    print(f"Watching bridge file: {path}")
    print(f"stale threshold: {stale_seconds:.2f}s")

    last_mtime = None
    last_timestamp = None
    events = 0

    try:
        while True:
            if not path.exists():
                print("[warn] bridge file missing")
                time.sleep(poll_seconds)
                continue

            stat = path.stat()
            age = max(0.0, time.time() - stat.st_mtime)
            if age > stale_seconds:
                print(f"[warn] stale bridge write: age={age:.2f}s")

            if last_mtime is not None and stat.st_mtime == last_mtime:
                time.sleep(poll_seconds)
                continue

            last_mtime = stat.st_mtime
            events += 1

            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                print(f"[error] malformed JSON: {exc}")
                time.sleep(poll_seconds)
                continue

            ok, schema_errors = validate_schema(payload)
            if not ok:
                print("[error] schema invalid:")
                for e in schema_errors:
                    print(f"  - {e}")
                time.sleep(poll_seconds)
                continue

            timestamp_ms = int(payload.get("timestamp_ms") or 0)
            if last_timestamp is not None and timestamp_ms <= last_timestamp:
                print(
                    "[warn] timestamp did not advance "
                    f"(prev={last_timestamp} current={timestamp_ms})"
                )
            last_timestamp = timestamp_ms

            party = payload.get("party", [])
            meta = payload.get("meta", {}) if isinstance(payload.get("meta"), dict) else {}
            provider = meta.get("provider", "unknown")
            game_mode = meta.get("game_mode", "unknown")
            print(
                f"[ok] event={events} provider={provider} game_mode={game_mode} "
                f"party_count={len(party)}"
            )
            print(f"     {summarize_party(party)}")

            if args.max_events > 0 and events >= args.max_events:
                print("Reached max events; exiting.")
                return 0

            time.sleep(poll_seconds)

    except KeyboardInterrupt:
        print("Stopped by user")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
