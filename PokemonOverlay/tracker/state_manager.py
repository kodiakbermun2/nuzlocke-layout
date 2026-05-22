from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional
import hashlib
import json
import logging

LOGGER = logging.getLogger(__name__)


class StateManager:
    def __init__(self, state_path: Path):
        self.state_path = state_path
        self._last_hash: Optional[str] = None
        self._load_existing_hash()

    def update_if_changed(self, state: Dict) -> bool:
        payload = json.dumps(state, indent=2, sort_keys=True)
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        if payload_hash == self._last_hash:
            LOGGER.debug("State unchanged; skip write hash=%s", payload_hash[:12])
            return False

        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(payload + "\n", encoding="utf-8")
        self._last_hash = payload_hash
        LOGGER.info("State updated: %s hash=%s", self.state_path, payload_hash[:12])
        return True

    def _load_existing_hash(self) -> None:
        if not self.state_path.exists():
            return
        existing = self.state_path.read_text(encoding="utf-8")
        self._last_hash = hashlib.sha256(existing.encode("utf-8")).hexdigest()
