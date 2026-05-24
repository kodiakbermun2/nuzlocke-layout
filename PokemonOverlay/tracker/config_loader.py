from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import json
import logging

LOGGER = logging.getLogger(__name__)


@dataclass
class TrackerConfig:
    save_path: str = ""
    state_path: str = "state.json"
    poll_seconds: float = 1.0
    debug: bool = False
    party_only: bool = False
    simulate_if_missing: bool = False
    parser_mode: str = "auto"
    websocket_enabled: bool = True
    websocket_host: str = "127.0.0.1"
    websocket_port: int = 8765
    websocket_heartbeat_seconds: float = 10.0
    provider_mode: str = "auto"
    memory_enabled: bool = False
    memory_backend: str = "mgba_json_bridge"
    memory_bridge_path: str = "tracker/memory_state.json"
    memory_poll_seconds: float = 0.15
    memory_stale_after_seconds: float = 2.0


DEFAULT_CONFIG: Dict[str, Any] = {
    "tracker": {
        "save_path": "",
        "state_path": "tracker/state.json",
        "poll_interval_ms": 1000,
        "debug": False,
        "party_only": False,
        "simulate_if_missing": False,
        "radical_red_mode": "auto",
        "websocket": {
            "enabled": True,
            "host": "127.0.0.1",
            "port": 8765,
            "heartbeat_interval_ms": 10000,
        },
        "provider_mode": "auto",
        "memory": {
            "enabled": False,
            "backend": "mgba_json_bridge",
            "bridge_path": "tracker/memory_state.json",
            "poll_interval_ms": 150,
            "stale_after_ms": 2000,
        },
    },
    "overlay": {
        "poll_interval_ms": 1000,
        "theme": "default",
        "sprite_style": "auto",
        "overlay_scale": 1.0,
        "websocket": {
            "enabled": True,
            "host": "127.0.0.1",
            "port": 8765,
            "reconnect_interval_ms": 1000,
        },
    },
}


def load_project_config(config_path: Path) -> Dict[str, Any]:
    if not config_path.exists():
        LOGGER.info("Config file not found at %s; using defaults", config_path)
        return dict(DEFAULT_CONFIG)

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.error("Failed to parse config file %s: %s", config_path, exc)
        return dict(DEFAULT_CONFIG)

    merged = dict(DEFAULT_CONFIG)
    for key in ("tracker", "overlay"):
        base = dict(DEFAULT_CONFIG.get(key, {}))
        raw = payload.get(key, {})
        if isinstance(raw, dict):
            base.update(raw)
        merged[key] = base
    return merged


def resolve_tracker_config(
    config_payload: Dict[str, Any],
    save_path: Optional[str],
    state_path: Optional[str],
    poll_seconds: Optional[float],
    debug: bool,
    party_only: bool,
    simulate_if_missing: bool,
    parser_mode: Optional[str],
) -> TrackerConfig:
    tracker = config_payload.get("tracker", {})
    websocket = tracker.get("websocket", {}) if isinstance(tracker.get("websocket", {}), dict) else {}
    memory = tracker.get("memory", {}) if isinstance(tracker.get("memory", {}), dict) else {}

    cfg = TrackerConfig(
        save_path=str(save_path or tracker.get("save_path") or ""),
        state_path=str(state_path or tracker.get("state_path") or "state.json"),
        poll_seconds=max(
            0.1,
            float(
                poll_seconds
                if poll_seconds is not None
                else float(tracker.get("poll_interval_ms", 1000)) / 1000.0
            ),
        ),
        debug=bool(debug or tracker.get("debug", False)),
        party_only=bool(party_only or tracker.get("party_only", False)),
        simulate_if_missing=bool(simulate_if_missing or tracker.get("simulate_if_missing", False)),
        parser_mode=str(parser_mode or tracker.get("radical_red_mode") or "auto"),
        websocket_enabled=bool(websocket.get("enabled", True)),
        websocket_host=str(websocket.get("host") or "127.0.0.1"),
        websocket_port=max(1, min(65535, int(websocket.get("port", 8765)))),
        websocket_heartbeat_seconds=max(
            1.0,
            float(websocket.get("heartbeat_interval_ms", 10000)) / 1000.0,
        ),
        provider_mode=str(tracker.get("provider_mode") or "auto"),
        memory_enabled=bool(memory.get("enabled", False)),
        memory_backend=str(memory.get("backend") or "mgba_json_bridge"),
        memory_bridge_path=str(memory.get("bridge_path") or "tracker/memory_state.json"),
        memory_poll_seconds=max(
            0.05,
            float(memory.get("poll_interval_ms", 150)) / 1000.0,
        ),
        memory_stale_after_seconds=max(
            0.2,
            float(memory.get("stale_after_ms", 2000)) / 1000.0,
        ),
    )

    return cfg
