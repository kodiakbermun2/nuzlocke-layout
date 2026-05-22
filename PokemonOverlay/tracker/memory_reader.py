"""Reserved for future emulator RAM reading support.

This module is intentionally minimal in the save-file-first milestone.
"""

from __future__ import annotations


class MemoryReader:
    def __init__(self) -> None:
        self.connected = False

    def connect(self) -> bool:
        self.connected = False
        return self.connected

    def read_party(self):
        raise NotImplementedError("Live RAM reading is not implemented yet.")
