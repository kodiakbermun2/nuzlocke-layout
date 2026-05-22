from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


@dataclass
class PokemonState:
    species: str
    species_id: int
    nickname: str
    level: Optional[int]
    gender: str = "unknown"
    shiny: bool = False
    held_item: Optional[str] = None
    slot: int = 1
    box: Optional[int] = None
    box_slot: Optional[int] = None

    def to_dict(self) -> Dict:
        payload = asdict(self)
        if self.box is None:
            payload.pop("box", None)
        if self.box_slot is None:
            payload.pop("box_slot", None)
        return payload


@dataclass
class TrackerState:
    party: List[Dict] = field(default_factory=list)
    pc: List[Dict] = field(default_factory=list)
    dead: List[Dict] = field(default_factory=list)
    meta: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "party": self.party,
            "pc": self.pc,
            "dead": self.dead,
            "meta": self.meta,
        }
