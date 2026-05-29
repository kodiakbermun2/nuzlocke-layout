from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import copy
import json
import logging
import os
import re
import secrets
import threading
import time

LOGGER = logging.getLogger("pokemon_overlay_points")


SHOP_ITEMS: List[Dict[str, Any]] = [
    {
        "id": "encounter_reroll",
        "name": "Encounter Reroll",
        "cost": 1,
        "description": "Reroll your first encounter on current route",
        "category": "Encounters",
        "stock_limit": 20,
    },
    {
        "id": "encounter_reroll_2",
        "name": "Encounter Reroll 2",
        "cost": 0,
        "description": "Reroll your first encounter on current route",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "safari_hunt",
        "name": "Safari Hunt",
        "cost": 2,
        "description": "Gain an additional safari zone run and encounter",
        "category": "Encounters",
        "stock_limit": 1,
    },
    {
        "id": "safari_hunt_2",
        "name": "Safari Hunt 2",
        "cost": 0,
        "description": "Gain an additional safari zone run and encounter",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "target_hunt",
        "name": "Target Hunt",
        "cost": 5,
        "description": "Reroll all encounters on a route of your choice",
        "category": "Encounters",
        "stock_limit": 10,
    },
    {
        "id": "spelunker",
        "name": "Spelunker",
        "cost": 2,
        "description": "Gain an encounter with the first Pokemon you encounter on any floor of any cave (no DexNav)",
        "category": "Encounters",
        "stock_limit": 3,
    },
    {
        "id": "cryptid_hunter",
        "name": "Cryptid Hunter",
        "cost": 2,
        "description": "Choose a route and attempt up to ten encounters to find its rarest spawn (no DexNav)",
        "category": "Encounters",
        "stock_limit": 5,
    },
    {
        "id": "fishing_boon",
        "name": "Fishing Boon",
        "cost": 2,
        "description": "Gain an additional fishing encounter",
        "category": "Encounters",
        "stock_limit": 3,
    },
    {
        "id": "surf_s_up",
        "name": "Surf's Up",
        "cost": 2,
        "description": "Gain an additional surfing encounter on a route you have not surfed on previously",
        "category": "Encounters",
        "stock_limit": 3,
    },
    {
        "id": "surf_s_up_2",
        "name": "Surf's Up 2",
        "cost": 0,
        "description": "Gain an additional surfing encounter on a route you have not surfed on previously",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "fishing_boon_2",
        "name": "Fishing Boon 2",
        "cost": 0,
        "description": "Gain an additional fishing encounter",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "raid_roll",
        "name": "Raid Roll",
        "cost": 3,
        "description": "Gain an additional raid encounter",
        "category": "Encounters",
        "stock_limit": 1,
    },
    {
        "id": "raid_roll_2",
        "name": "Raid Roll 2",
        "cost": 0,
        "description": "Gain an additional raid encounter",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "boss_reset",
        "name": "Boss Reset",
        "cost": 3,
        "description": "Reset one completed boss battle for another attempt",
        "category": "Lifeline",
        "stock_limit": 10,
    },
    {
        "id": "boss_reset_2",
        "name": "Boss Reset 2",
        "cost": 0,
        "description": "Reset one completed boss battle for another attempt",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "next_of_kin",
        "name": "Next Of Kin",
        "cost": 2,
        "description": "Allows a replacement encounter tied to a fallen teammate",
        "category": "Lifeline",
        "stock_limit": 3,
    },
    {
        "id": "next_of_kin_2",
        "name": "Next Of Kin 2",
        "cost": 0,
        "description": "Allows a replacement encounter tied to a fallen teammate",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "revive",
        "name": "Revive",
        "cost": 3,
        "description": "Revive one memorial Pokemon back into the run",
        "category": "Lifeline",
        "stock_limit": 20,
    },
    {
        "id": "revive_2",
        "name": "Revive 2",
        "cost": 0,
        "description": "Revive one memorial Pokemon back into the run",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "soft_reset",
        "name": "Soft Reset",
        "cost": 10,
        "description": "Undo one failed result and retry the immediate scenario",
        "category": "Lifeline",
        "stock_limit": 20,
    },
    {
        "id": "soft_reset_2",
        "name": "Soft Reset 2",
        "cost": 0,
        "description": "Undo one failed result and retry the immediate scenario",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "event_encounter",
        "name": "Event Encounter",
        "cost": 2,
        "description": "Gain one additional special event encounter",
        "category": "Events",
        "stock_limit": 3,
    },
    {
        "id": "gift_pokemon",
        "name": "Gift Pokemon",
        "cost": 2,
        "description": "Claim one additional gift Pokemon",
        "category": "Events",
        "stock_limit": 3,
    },
    {
        "id": "gift_pokemon_2",
        "name": "Gift Pokemon 2",
        "cost": 0,
        "description": "Claim one additional gift Pokemon",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "high_roller",
        "name": "High Roller",
        "cost": 3,
        "description": "Enable one high-risk, high-reward event roll",
        "category": "Events",
        "stock_limit": 3,
    },
    {
        "id": "high_roller_2",
        "name": "High Roller 2",
        "cost": 0,
        "description": "Enable one high-risk, high-reward event roll",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "in_game_trade",
        "name": "In-Game Trade",
        "cost": 3,
        "description": "Unlock one additional in-game trade redemption",
        "category": "Events",
        "stock_limit": 3,
    },
    {
        "id": "pokemon_breeder",
        "name": "Pokemon Breeder",
        "cost": 3,
        "description": "Unlock one breeder bonus action",
        "category": "Events",
        "stock_limit": 1,
    },
    {
        "id": "bird_watcher",
        "name": "Bird Watcher",
        "cost": 0,
        "description": "Free first flying-type encounter on a route of your choice (no DexNav)",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "bug_catcher",
        "name": "Bug Catcher",
        "cost": 0,
        "description": "Free first bug-type encounter on a route of your choice (no DexNav)",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "ex_boyfriend",
        "name": "Ex-Boyfriend",
        "cost": 0,
        "description": "Release a male Pokemon, then gain a free first male encounter on a route of your choice",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "hatch_of_the_day",
        "name": "Hatch Of The Day",
        "cost": 0,
        "description": "You may hatch any egg obtained from an NPC without spending a route encounter",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "cash_out",
        "name": "Cash Out",
        "cost": 0,
        "description": "Release any number of living storage Pokemon and gain 1 point per Pokemon released",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "foresight",
        "name": "Foresight",
        "cost": 0,
        "description": "Declare your next boss and gain a type-advantage encounter against that boss lead",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "harvest_season",
        "name": "Harvest Season",
        "cost": 0,
        "description": "Release any number of grass-type Pokemon and gain points based on living or dead status",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "bunshin_technique",
        "name": "Bunshin Technique",
        "cost": 0,
        "description": "Encounter a Pokemon species you already own while keeping both copies in the same stage",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "all_in",
        "name": "All In",
        "cost": 0,
        "description": "Wager X points on a called coin flip; win doubles points and lose removes wagered points",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "black_market_trading",
        "name": "Black Market Trading",
        "cost": 0,
        "description": "Force-release another player's Pokemon for points, then gain an encounter from its family",
        "category": "Awards",
        "purchasable": False,
    },
    {
        "id": "dragon_tamer",
        "name": "Dragon Tamer",
        "cost": 0,
        "description": "Gain a free first dragon-type encounter on a route of your choice (no DexNav)",
        "category": "Awards",
        "purchasable": False,
    },
]

SHOP_ITEM_MAP = {item["id"]: dict(item) for item in SHOP_ITEMS}

AWARD_FILENAME_TO_ITEM_ID: Dict[str, str] = {
    "encounter reroll.png": "encounter_reroll",
    "encounter reroll 2.png": "encounter_reroll_2",
    "safari hunt.png": "safari_hunt",
    "safari hunt 2.png": "safari_hunt_2",
    "target hunt.png": "target_hunt",
    "spelunker.png": "spelunker",
    "cryptid hunter.png": "cryptid_hunter",
    "fishing boon.png": "fishing_boon",
    "fishing boon 2.png": "fishing_boon_2",
    "surf's up.png": "surf_s_up",
    "surfs up.png": "surf_s_up",
    "surf's up 2.png": "surf_s_up_2",
    "surfs up 2.png": "surf_s_up_2",
    "raid roll.png": "raid_roll",
    "raid roll 2.png": "raid_roll_2",
    "boss reset.png": "boss_reset",
    "boss reset 2.png": "boss_reset_2",
    "next of kin.png": "next_of_kin",
    "next of kin 2.png": "next_of_kin_2",
    "revive.png": "revive",
    "revive 2.png": "revive_2",
    "soft reset.png": "soft_reset",
    "soft reset 2.png": "soft_reset_2",
    "event encounter.png": "event_encounter",
    "gift pokemon.png": "gift_pokemon",
    "gift pokemon 2.png": "gift_pokemon_2",
    "high roller.png": "high_roller",
    "high roller 2.png": "high_roller_2",
    "in-game trade.png": "in_game_trade",
    "pokemon breeder.png": "pokemon_breeder",
    "bird watcher.png": "bird_watcher",
    "bug catcher.png": "bug_catcher",
    "ex-boyfriend.png": "ex_boyfriend",
    "ex boyfriend.png": "ex_boyfriend",
    "hatch of the day.png": "hatch_of_the_day",
    "cash out.png": "cash_out",
    "foresight.png": "foresight",
    "harvest season.png": "harvest_season",
    "bunshin technique.png": "bunshin_technique",
    "all in.png": "all_in",
    "black market trading.png": "black_market_trading",
    "dragon tamer.png": "dragon_tamer",
}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _default_state() -> Dict[str, Any]:
    return {
        "current_points": 0,
        "inventory": [],
        "unseen_inventory_reward_ids": [],
        "transactions": [],
        "awarded_trainers": [],
        "redeemed_codes": {},
        "unlocked_awards": [],
        "purchased_counts": {},
        "trainer_profile_key": "",
        "version": 1,
    }


class PointsManager:
    def __init__(self, state_path: Path):
        self.state_path = state_path
        self.redemption_codes_path = state_path.parent / "redemption_codes.json"
        self._lock = threading.RLock()
        self._state: Dict[str, Any] = _default_state()
        self._persist_window_started_at: float = time.perf_counter()
        self._persist_window_count: int = 0
        self._load_state()

    def get_state_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            snapshot = copy.deepcopy(self._state)
            unseen_ids = [str(value) for value in snapshot.get("unseen_inventory_reward_ids") or [] if str(value)]
            snapshot["unseen_inventory_reward_ids"] = unseen_ids
            snapshot["unseen_inventory_reward_count"] = len(unseen_ids)
            snapshot["stock_remaining"] = self._build_stock_remaining(snapshot)
            return snapshot

    def sync_trainer_profile(self, profile_key: str) -> Dict[str, Any]:
        with self._lock:
            normalized = str(profile_key or "").strip()
            if not normalized:
                return {"ok": True, "message": "No trainer profile provided", "state": self.get_state_snapshot()}

            existing = str(self._state.get("trainer_profile_key") or "").strip()
            if not existing:
                self._state["trainer_profile_key"] = normalized
                self._persist_state()
                LOGGER.info("points_profile_bind trainer_profile_key=%s", normalized)
                return {"ok": True, "message": "Trainer profile linked", "state": self.get_state_snapshot()}

            if existing == normalized:
                return {"ok": True, "message": "Trainer profile unchanged", "state": self.get_state_snapshot()}

            LOGGER.info("points_profile_changed old=%s new=%s action=reset", existing, normalized)
            self._state = _default_state()
            self._state["trainer_profile_key"] = normalized
            self._persist_state()
            return {
                "ok": True,
                "message": "Trainer profile changed; points state reset",
                "state": self.get_state_snapshot(),
            }

    def handle_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        command = str(payload.get("command") or "").strip().lower()
        data = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}

        with self._lock:
            if command == "purchase":
                item_id = str(data.get("item_id") or "").strip()
                return self._purchase(item_id)
            if command == "redeem":
                inventory_id = str(data.get("inventory_id") or "").strip()
                return self.redeem_reward(inventory_id)
            if command == "sell":
                inventory_id = str(data.get("inventory_id") or "").strip()
                return self.sell_reward(inventory_id)
            if command == "undo_last":
                return self.undo_last_transaction()
            if command == "add_points":
                amount = int(data.get("amount") or 0)
                source = str(data.get("source") or "manual_award")
                return self.add_points(amount, source=source)
            if command == "set_points_total":
                total = int(data.get("amount") or 0)
                source = str(data.get("source") or "manual_set")
                return self.set_points_total(total, source=source)
            if command == "grant_reward":
                item_id = str(data.get("item_id") or "").strip()
                source = str(data.get("source") or "direct_grant")
                metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else None
                notify_inventory = bool(data.get("notify_inventory") or False)
                return self.grant_reward(
                    item_id=item_id,
                    source=source,
                    metadata=metadata,
                    notify_inventory=notify_inventory,
                )
            if command == "ack_inventory_notifications":
                self._clear_unseen_inventory_notifications()
                self._persist_state()
                return {
                    "ok": True,
                    "message": "Inventory notifications acknowledged",
                    "state": self.get_state_snapshot(),
                }
            if command == "get_state":
                return {
                    "ok": True,
                    "message": "Points state loaded",
                    "state": self.get_state_snapshot(),
                }
            if command == "redeem_code":
                raw_code = data.get("code")
                return self.redeem_code(raw_code)
            if command == "get_redeemed_codes":
                return self.get_redeemed_codes()

            return {
                "ok": False,
                "message": f"Unsupported points command: {command}",
                "state": self.get_state_snapshot(),
            }

    def get_redeemed_codes(self) -> Dict[str, Any]:
        redeemed = self._state.get("redeemed_codes") if isinstance(self._state.get("redeemed_codes"), dict) else {}
        normalized = {
            str(key).strip().lower(): bool(value)
            for key, value in redeemed.items()
            if str(key).strip()
        }
        return {
            "ok": True,
            "message": "Redeemed codes loaded",
            "redeemed_codes": normalized,
            "state": self.get_state_snapshot(),
        }

    def redeem_code(self, raw_code: Any) -> Dict[str, Any]:
        code = str(raw_code or "").strip().lower()
        if not code:
            return {
                "ok": False,
                "error": "Invalid code",
                "message": "Invalid code",
                "state": self.get_state_snapshot(),
            }

        catalog = self._load_redemption_codes_catalog()
        entry = catalog.get(code)
        if not isinstance(entry, dict):
            return {
                "ok": False,
                "error": "Invalid code",
                "message": "Invalid code",
                "state": self.get_state_snapshot(),
            }

        redeemed_codes = self._state.setdefault("redeemed_codes", {})
        if bool(redeemed_codes.get(code)):
            return {
                "ok": False,
                "error": "Code already redeemed",
                "message": "Code already redeemed",
                "state": self.get_state_snapshot(),
            }

        points_awarded = max(0, int(entry.get("points") or 0))
        configured_awards = entry.get("awards") if isinstance(entry.get("awards"), list) else []

        before = int(self._state.get("current_points") or 0)
        after = before + points_awarded
        if points_awarded > 0:
            self._state["current_points"] = after
            award_txn = self._build_transaction(
                kind="award",
                item="redeem_code",
                cost=-points_awarded,
                points_before=before,
                points_after=after,
                metadata={
                    "source": "redeem_code",
                    "code": code,
                    "amount": int(points_awarded),
                },
            )
            self._state.setdefault("transactions", []).append(award_txn)

        redeemed_codes[code] = True
        unlocked_awards = self._state.setdefault("unlocked_awards", [])
        inventory = self._state.setdefault("inventory", [])
        unseen = self._state.setdefault("unseen_inventory_reward_ids", [])
        awards_granted: List[str] = []
        awards_unmapped: List[str] = []

        for raw_award in configured_awards:
            award_name = str(raw_award or "").strip()
            if not award_name:
                continue
            if award_name in unlocked_awards:
                continue

            unlocked_awards.append(award_name)
            awards_granted.append(award_name)

            mapped_item_id = self._resolve_award_item_id(award_name)
            item = SHOP_ITEM_MAP.get(mapped_item_id or "")
            if not item:
                awards_unmapped.append(award_name)
                LOGGER.warning(
                    "redeem_code_award_unmapped code=%s award=%s",
                    code,
                    award_name,
                )
                continue

            inventory_item = self._build_inventory_item(
                item=item,
                source="redeem_code",
                metadata={
                    "source": "redeem_code",
                    "code": code,
                    "award_filename": award_name,
                },
            )
            inventory.append(inventory_item)
            inventory_id = str(inventory_item.get("id") or "")
            if inventory_id and inventory_id not in unseen:
                unseen.append(inventory_id)

            grant_txn = self._build_transaction(
                kind="grant",
                item=str(item.get("name") or mapped_item_id or "reward"),
                cost=0,
                points_before=int(self._state.get("current_points") or 0),
                points_after=int(self._state.get("current_points") or 0),
                metadata={
                    "source": "redeem_code",
                    "code": code,
                    "item_id": str(item.get("id") or ""),
                    "inventory_id": inventory_id,
                    "award_filename": award_name,
                    "notify_inventory": True,
                },
            )
            self._state.setdefault("transactions", []).append(grant_txn)

        self._persist_state()
        LOGGER.info(
            "redeem_code_success code=%s points=%s awards=%s",
            code,
            points_awarded,
            len(awards_granted),
        )
        return {
            "ok": True,
            "code": code,
            "points_awarded": int(points_awarded),
            "awards_granted": awards_granted,
            "awards_unmapped": awards_unmapped,
            "message": "Code redeemed",
            "state": self.get_state_snapshot(),
        }

    def _resolve_award_item_id(self, award_filename: str) -> str:
        return self._ensure_award_item_registered(award_filename)

    def _ensure_award_item_registered(self, award_filename: str) -> str:
        raw = str(award_filename or "").strip()
        if not raw:
            return ""

        direct_key = raw.lower()
        mapped = str(AWARD_FILENAME_TO_ITEM_ID.get(direct_key) or "").strip()
        if mapped and mapped in SHOP_ITEM_MAP:
            return mapped

        stem = Path(raw).stem.strip()
        if not stem:
            return ""

        candidate = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
        if not candidate:
            return ""

        if candidate not in SHOP_ITEM_MAP:
            generated_item = {
                "id": candidate,
                "name": stem,
                "cost": 0,
                "description": "Award-only reward unlocked by redemption code",
                "category": "Awards",
                "purchasable": False,
            }
            SHOP_ITEMS.append(generated_item)
            SHOP_ITEM_MAP[candidate] = dict(generated_item)
            LOGGER.info("redeem_code_award_auto_registered award=%s item_id=%s", raw, candidate)

        AWARD_FILENAME_TO_ITEM_ID[direct_key] = candidate
        return candidate

    def _load_redemption_codes_catalog(self) -> Dict[str, Dict[str, Any]]:
        path = self.redemption_codes_path
        if not path.exists():
            return {}

        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            LOGGER.error("redemption_codes_load_failed path=%s error=%s", path, exc)
            return {}

        if not isinstance(parsed, dict):
            LOGGER.error("redemption_codes_invalid_root path=%s", path)
            return {}

        out: Dict[str, Dict[str, Any]] = {}
        for key, value in parsed.items():
            normalized = str(key or "").strip().lower()
            if not normalized or not isinstance(value, dict):
                continue
            points = max(0, int(value.get("points") or 0))
            awards_raw = value.get("awards") if isinstance(value.get("awards"), list) else []
            awards: List[str] = []
            seen_awards = set()
            for award in awards_raw:
                name = str(award or "").strip()
                if not name:
                    continue
                marker = name.lower()
                if marker in seen_awards:
                    continue
                seen_awards.add(marker)
                awards.append(name)
                self._ensure_award_item_registered(name)
            out[normalized] = {
                "points": points,
                "awards": awards,
            }
        return out

    def add_points(
        self,
        amount: int,
        *,
        source: str = "manual_award",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if amount <= 0:
            return {"ok": False, "message": "Amount must be positive", "state": self.get_state_snapshot()}

        before = int(self._state.get("current_points") or 0)
        after = before + amount
        txn = self._build_transaction(
            kind="award",
            item=source,
            cost=-amount,
            points_before=before,
            points_after=after,
            metadata={"source": source, **(metadata or {})},
        )
        self._state["current_points"] = after
        self._state.setdefault("transactions", []).append(txn)
        self._persist_state()
        LOGGER.info(
            "points_add amount=%s before=%s after=%s source=%s metadata=%s",
            amount,
            before,
            after,
            source,
            metadata or {},
        )
        return {"ok": True, "message": f"Added {amount} points", "state": self.get_state_snapshot()}

    def set_points_total(self, total: int, *, source: str = "manual_set") -> Dict[str, Any]:
        target = max(0, int(total or 0))
        before = int(self._state.get("current_points") or 0)
        if before == target:
            return {"ok": True, "message": "Points unchanged", "state": self.get_state_snapshot()}

        self._state["current_points"] = target
        txn = self._build_transaction(
            kind="points_set",
            item="points_set",
            cost=int(before - target),
            points_before=before,
            points_after=target,
            metadata={
                "source": str(source or "manual_set"),
                "target_points": int(target),
            },
        )
        self._state.setdefault("transactions", []).append(txn)
        self._persist_state()
        LOGGER.info(
            "points_set before=%s after=%s source=%s",
            before,
            target,
            source,
        )
        return {"ok": True, "message": f"Set points to {target}", "state": self.get_state_snapshot()}

    def spend_points(self, cost: int, *, item_name: str) -> Dict[str, Any]:
        if cost <= 0:
            return {"ok": False, "message": "Cost must be positive", "state": self.get_state_snapshot()}

        before = int(self._state.get("current_points") or 0)
        if before < cost:
            return {
                "ok": False,
                "message": f"Not enough points for {item_name}",
                "state": self.get_state_snapshot(),
            }

        after = before - cost
        self._state["current_points"] = after
        self._persist_state()
        LOGGER.info("points_spend item=%s cost=%s before=%s after=%s", item_name, cost, before, after)
        return {"ok": True, "message": "Points spent", "state": self.get_state_snapshot()}

    def grant_reward(
        self,
        *,
        item_id: str,
        source: str = "direct_grant",
        metadata: Optional[Dict[str, Any]] = None,
        notify_inventory: bool = False,
    ) -> Dict[str, Any]:
        item = SHOP_ITEM_MAP.get(item_id)
        if not item:
            return {"ok": False, "message": f"Unknown reward: {item_id}", "state": self.get_state_snapshot()}

        inventory_item = self._build_inventory_item(item=item, source=source, metadata=metadata)
        self._state.setdefault("inventory", []).append(inventory_item)
        if notify_inventory:
            unseen = self._state.setdefault("unseen_inventory_reward_ids", [])
            inventory_id = str(inventory_item.get("id") or "")
            if inventory_id and inventory_id not in unseen:
                unseen.append(inventory_id)

        txn = self._build_transaction(
            kind="grant",
            item=item["name"],
            cost=0,
            points_before=int(self._state.get("current_points") or 0),
            points_after=int(self._state.get("current_points") or 0),
            metadata={
                "source": source,
                "inventory_id": inventory_item["id"],
                "item_id": item_id,
                "notify_inventory": bool(notify_inventory),
                **(metadata or {}),
            },
        )
        self._state.setdefault("transactions", []).append(txn)
        self._persist_state()
        LOGGER.info("reward_grant item=%s inventory_id=%s source=%s", item_id, inventory_item["id"], source)
        return {"ok": True, "message": f"Granted {item['name']}", "state": self.get_state_snapshot()}

    def redeem_reward(self, inventory_id: str) -> Dict[str, Any]:
        if not inventory_id:
            return {"ok": False, "message": "Missing inventory id", "state": self.get_state_snapshot()}

        inventory = self._state.setdefault("inventory", [])
        for index, entry in enumerate(inventory):
            if str(entry.get("id")) != inventory_id:
                continue

            removed_entry = inventory.pop(index)
            removed_inventory_id = str(removed_entry.get("id") or "")
            if removed_inventory_id:
                unseen = self._state.setdefault("unseen_inventory_reward_ids", [])
                self._state["unseen_inventory_reward_ids"] = [rid for rid in unseen if str(rid) != removed_inventory_id]

            txn = self._build_transaction(
                kind="redeem",
                item=str(removed_entry.get("name") or "Reward"),
                cost=0,
                points_before=int(self._state.get("current_points") or 0),
                points_after=int(self._state.get("current_points") or 0),
                metadata={
                    "inventory_id": inventory_id,
                    "item_snapshot": copy.deepcopy(removed_entry),
                },
            )
            self._state.setdefault("transactions", []).append(txn)
            self._persist_state()
            LOGGER.info("reward_redeem inventory_id=%s", inventory_id)
            return {"ok": True, "message": "Reward redeemed", "state": self.get_state_snapshot()}

        return {"ok": False, "message": "Inventory item not found", "state": self.get_state_snapshot()}

    def sell_reward(self, inventory_id: str) -> Dict[str, Any]:
        if not inventory_id:
            return {"ok": False, "message": "Missing inventory id", "state": self.get_state_snapshot()}

        inventory = self._state.setdefault("inventory", [])
        for index, entry in enumerate(inventory):
            if str(entry.get("id")) != inventory_id:
                continue

            removed_entry = inventory.pop(index)
            removed_inventory_id = str(removed_entry.get("id") or "")
            if removed_inventory_id:
                unseen = self._state.setdefault("unseen_inventory_reward_ids", [])
                self._state["unseen_inventory_reward_ids"] = [rid for rid in unseen if str(rid) != removed_inventory_id]
            base_cost = int(
                removed_entry.get("base_cost")
                or SHOP_ITEM_MAP.get(str(removed_entry.get("item_id") or removed_entry.get("type") or ""), {}).get("cost")
                or 0
            )
            refund = self._calculate_sell_refund(base_cost)

            before = int(self._state.get("current_points") or 0)
            after = before + refund
            self._state["current_points"] = after

            txn = self._build_transaction(
                kind="sell",
                item=str(removed_entry.get("name") or "Reward"),
                cost=-refund,
                points_before=before,
                points_after=after,
                metadata={
                    "inventory_id": inventory_id,
                    "item_snapshot": copy.deepcopy(removed_entry),
                    "base_cost": base_cost,
                    "refund": refund,
                },
            )
            self._state.setdefault("transactions", []).append(txn)
            self._persist_state()

            LOGGER.info(
                "reward_sell inventory_id=%s base_cost=%s refund=%s points_before=%s points_after=%s",
                inventory_id,
                base_cost,
                refund,
                before,
                after,
            )
            return {"ok": True, "message": f"Sold for {refund} points", "state": self.get_state_snapshot()}

        return {"ok": False, "message": "Inventory item not found", "state": self.get_state_snapshot()}

    def undo_last_transaction(self) -> Dict[str, Any]:
        transactions = self._state.setdefault("transactions", [])
        target: Optional[Dict[str, Any]] = None
        for txn in reversed(transactions):
            if not bool(txn.get("undone")):
                target = txn
                break

        if target is None:
            return {"ok": False, "message": "No transaction to undo", "state": self.get_state_snapshot()}

        txn_type = str(target.get("type") or "")
        if txn_type == "purchase":
            return self._undo_purchase(target)
        if txn_type == "award":
            return self._undo_award(target)
        if txn_type == "grant":
            return self._undo_grant(target)
        if txn_type == "redeem":
            return self._undo_redeem(target)
        if txn_type == "sell":
            return self._undo_sell(target)

        return {"ok": False, "message": f"Cannot undo transaction type: {txn_type}", "state": self.get_state_snapshot()}

    def mark_trainer_awarded(self, trainer_id: str) -> bool:
        trainer_id = str(trainer_id or "").strip()
        if not trainer_id:
            return False

        awarded = self._state.setdefault("awarded_trainers", [])
        if trainer_id in awarded:
            return False
        awarded.append(trainer_id)
        self._persist_state()
        LOGGER.info("trainer_award_marked trainer_id=%s", trainer_id)
        return True

    def has_trainer_award(self, trainer_id: str) -> bool:
        trainer_id = str(trainer_id or "").strip()
        if not trainer_id:
            return False
        awarded = self._state.setdefault("awarded_trainers", [])
        return trainer_id in awarded

    def clear_trainer_awarded(self, trainer_id: str) -> bool:
        trainer_id = str(trainer_id or "").strip()
        if not trainer_id:
            return False

        with self._lock:
            awarded = self._state.setdefault("awarded_trainers", [])
            if trainer_id not in awarded:
                return False
            self._state["awarded_trainers"] = [tid for tid in awarded if str(tid) != trainer_id]
            self._persist_state()
            LOGGER.info("trainer_award_cleared trainer_id=%s", trainer_id)
            return True

    def revoke_trainer_award(
        self,
        trainer_id: str,
        *,
        points: int,
        source: str = "trainer_revoke",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        trainer_id = str(trainer_id or "").strip()
        points = int(points or 0)
        if not trainer_id:
            return {"ok": False, "message": "Missing trainer id", "state": self.get_state_snapshot()}
        if points <= 0:
            return {"ok": False, "message": "Points must be positive", "state": self.get_state_snapshot()}

        with self._lock:
            awarded = self._state.setdefault("awarded_trainers", [])
            if trainer_id not in awarded:
                return {
                    "ok": False,
                    "message": f"Trainer reward not marked: {trainer_id}",
                    "state": self.get_state_snapshot(),
                }

            self._state["awarded_trainers"] = [tid for tid in awarded if str(tid) != trainer_id]

            before = int(self._state.get("current_points") or 0)
            after = before - points
            self._state["current_points"] = after
            txn = self._build_transaction(
                kind="award_revoke",
                item=source,
                cost=points,
                points_before=before,
                points_after=after,
                metadata={"source": source, "trainer_id": trainer_id, **(metadata or {})},
            )
            self._state.setdefault("transactions", []).append(txn)
            self._persist_state()
            LOGGER.info(
                "trainer_award_revoked trainer_id=%s points=%s before=%s after=%s source=%s",
                trainer_id,
                points,
                before,
                after,
                source,
            )
            return {
                "ok": True,
                "message": f"Revoked {points} points for trainer reward",
                "state": self.get_state_snapshot(),
            }

    def revoke_trainer_battle_grants(
        self,
        trainer_id: str,
        *,
        source: str = "trainer_reward_revoke",
    ) -> Dict[str, Any]:
        trainer_id = str(trainer_id or "").strip()
        if not trainer_id:
            return {"ok": False, "message": "Missing trainer id", "state": self.get_state_snapshot()}

        with self._lock:
            transactions = self._state.setdefault("transactions", [])
            inventory = self._state.setdefault("inventory", [])

            removed_items: List[Dict[str, Any]] = []
            removed_inventory_ids: List[str] = []

            for txn in transactions:
                if bool(txn.get("undone")):
                    continue
                if str(txn.get("type") or "") != "grant":
                    continue
                metadata = txn.get("metadata") if isinstance(txn.get("metadata"), dict) else {}
                if str(metadata.get("trainer_id") or "").strip() != trainer_id:
                    continue
                if str(metadata.get("reward_type") or "").strip() != "battle_reward":
                    continue

                inventory_id = str(metadata.get("inventory_id") or "").strip()
                if inventory_id:
                    for entry in list(inventory):
                        if str(entry.get("id") or "") == inventory_id:
                            removed_items.append(copy.deepcopy(entry))
                            inventory.remove(entry)
                            removed_inventory_ids.append(inventory_id)
                            break

                txn["undone"] = True
                txn["undone_at"] = _now_ms()

            if removed_inventory_ids:
                unseen = self._state.setdefault("unseen_inventory_reward_ids", [])
                self._state["unseen_inventory_reward_ids"] = [
                    rid
                    for rid in unseen
                    if str(rid) not in removed_inventory_ids
                ]

            if removed_items:
                txn_revoke = self._build_transaction(
                    kind="grant_revoke",
                    item="trainer_battle_reward_revoke",
                    cost=0,
                    points_before=int(self._state.get("current_points") or 0),
                    points_after=int(self._state.get("current_points") or 0),
                    metadata={
                        "source": str(source or "trainer_reward_revoke"),
                        "trainer_id": trainer_id,
                        "removed_inventory_ids": list(removed_inventory_ids),
                        "removed_items": removed_items,
                    },
                )
                transactions.append(txn_revoke)

            self._persist_state()
            LOGGER.info(
                "trainer_battle_grants_revoked trainer_id=%s removed=%s source=%s",
                trainer_id,
                len(removed_items),
                source,
            )
            return {
                "ok": True,
                "message": f"Revoked {len(removed_items)} trainer battle rewards",
                "removed": len(removed_items),
                "state": self.get_state_snapshot(),
            }

    def _purchase(self, item_id: str) -> Dict[str, Any]:
        item = SHOP_ITEM_MAP.get(item_id)
        if not item:
            return {"ok": False, "message": f"Unknown reward item: {item_id}", "state": self.get_state_snapshot()}
        if not bool(item.get("purchasable", True)):
            return {"ok": False, "message": f"{item['name']} is award-only", "state": self.get_state_snapshot()}

        remaining = self._remaining_stock_for_item(item_id)
        if remaining is not None and remaining <= 0:
            return {
                "ok": False,
                "message": f"{item['name']} is sold out",
                "state": self.get_state_snapshot(),
            }

        cost = int(item.get("cost") or 0)
        before = int(self._state.get("current_points") or 0)
        if before < cost:
            return {
                "ok": False,
                "message": f"Not enough points for {item['name']}",
                "state": self.get_state_snapshot(),
            }

        after = before - cost
        self._state["current_points"] = after

        inventory_item = self._build_inventory_item(item=item, source="shop_purchase")
        self._state.setdefault("inventory", []).append(inventory_item)
        purchased_counts = self._state.setdefault("purchased_counts", {})
        purchased_counts[item_id] = int(purchased_counts.get(item_id) or 0) + 1

        txn = self._build_transaction(
            kind="purchase",
            item=item["name"],
            cost=cost,
            points_before=before,
            points_after=after,
            metadata={
                "item_id": item_id,
                "inventory_id": inventory_item["id"],
            },
        )
        self._state.setdefault("transactions", []).append(txn)
        self._persist_state()

        LOGGER.info(
            "purchase_success item=%s cost=%s points_before=%s points_after=%s inventory_id=%s",
            item_id,
            cost,
            before,
            after,
            inventory_item["id"],
        )
        return {"ok": True, "message": f"Purchased {item['name']}", "state": self.get_state_snapshot()}

    def _undo_purchase(self, txn: Dict[str, Any]) -> Dict[str, Any]:
        metadata = txn.get("metadata") if isinstance(txn.get("metadata"), dict) else {}
        inventory_id = str(metadata.get("inventory_id") or "")
        item_id = str(metadata.get("item_id") or "")
        cost = int(txn.get("cost") or 0)

        if inventory_id:
            inventory = self._state.setdefault("inventory", [])
            inventory[:] = [entry for entry in inventory if str(entry.get("id")) != inventory_id]

        if item_id:
            purchased_counts = self._state.setdefault("purchased_counts", {})
            current = int(purchased_counts.get(item_id) or 0)
            purchased_counts[item_id] = max(0, current - 1)

        self._state["current_points"] = int(self._state.get("current_points") or 0) + max(0, cost)
        txn["undone"] = True
        txn["undone_at"] = _now_ms()
        self._persist_state()

        LOGGER.info("undo_purchase txn=%s inventory_id=%s restored=%s", txn.get("id"), inventory_id, cost)
        return {"ok": True, "message": "Purchase undone", "state": self.get_state_snapshot()}

    def _undo_award(self, txn: Dict[str, Any]) -> Dict[str, Any]:
        restore = abs(int(txn.get("cost") or 0))
        current = int(self._state.get("current_points") or 0)
        self._state["current_points"] = max(0, current - restore)
        txn["undone"] = True
        txn["undone_at"] = _now_ms()
        self._persist_state()

        LOGGER.info("undo_award txn=%s removed=%s", txn.get("id"), restore)
        return {"ok": True, "message": "Award undone", "state": self.get_state_snapshot()}

    def _undo_grant(self, txn: Dict[str, Any]) -> Dict[str, Any]:
        metadata = txn.get("metadata") if isinstance(txn.get("metadata"), dict) else {}
        inventory_id = str(metadata.get("inventory_id") or "")

        if inventory_id:
            inventory = self._state.setdefault("inventory", [])
            inventory[:] = [entry for entry in inventory if str(entry.get("id")) != inventory_id]

        txn["undone"] = True
        txn["undone_at"] = _now_ms()
        self._persist_state()

        LOGGER.info("undo_grant txn=%s inventory_id=%s", txn.get("id"), inventory_id)
        return {"ok": True, "message": "Grant undone", "state": self.get_state_snapshot()}

    def _undo_redeem(self, txn: Dict[str, Any]) -> Dict[str, Any]:
        metadata = txn.get("metadata") if isinstance(txn.get("metadata"), dict) else {}
        inventory_id = str(metadata.get("inventory_id") or "")
        snapshot = metadata.get("item_snapshot") if isinstance(metadata.get("item_snapshot"), dict) else None

        inventory = self._state.setdefault("inventory", [])
        if snapshot and inventory_id and not any(str(entry.get("id")) == inventory_id for entry in inventory):
            inventory.append(copy.deepcopy(snapshot))

        txn["undone"] = True
        txn["undone_at"] = _now_ms()
        self._persist_state()

        LOGGER.info("undo_redeem txn=%s inventory_id=%s", txn.get("id"), inventory_id)
        return {"ok": True, "message": "Redeem undone", "state": self.get_state_snapshot()}

    def _undo_sell(self, txn: Dict[str, Any]) -> Dict[str, Any]:
        metadata = txn.get("metadata") if isinstance(txn.get("metadata"), dict) else {}
        inventory_id = str(metadata.get("inventory_id") or "")
        snapshot = metadata.get("item_snapshot") if isinstance(metadata.get("item_snapshot"), dict) else None
        refund = int(metadata.get("refund") or abs(int(txn.get("cost") or 0)))

        current = int(self._state.get("current_points") or 0)
        self._state["current_points"] = max(0, current - max(0, refund))

        inventory = self._state.setdefault("inventory", [])
        if snapshot and inventory_id and not any(str(entry.get("id")) == inventory_id for entry in inventory):
            inventory.append(copy.deepcopy(snapshot))

        txn["undone"] = True
        txn["undone_at"] = _now_ms()
        self._persist_state()

        LOGGER.info("undo_sell txn=%s inventory_id=%s removed=%s", txn.get("id"), inventory_id, refund)
        return {"ok": True, "message": "Sell undone", "state": self.get_state_snapshot()}

    def _build_inventory_item(self, *, item: Dict[str, Any], source: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        stamp = _now_ms()
        suffix = secrets.token_hex(2)
        item_id = str(item.get("id") or "")
        base_cost = int(item.get("cost") or 0)
        return {
            "id": f"{item_id}_{stamp}_{suffix}",
            "type": item_id,
            "item_id": item_id,
            "name": str(item["name"]),
            "base_cost": base_cost,
            "granted_at": stamp,
            "redeemed": False,
            "redeemed_at": None,
            "source": source,
            "metadata": copy.deepcopy(metadata or {}),
        }

    def _clear_unseen_inventory_notifications(self) -> None:
        self._state["unseen_inventory_reward_ids"] = []

    def _calculate_sell_refund(self, base_cost: int) -> int:
        cost = max(0, int(base_cost or 0))
        if cost == 0:
            return 0
        return max(1, cost // 2)

    def _build_transaction(
        self,
        *,
        kind: str,
        item: str,
        cost: int,
        points_before: int,
        points_after: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        stamp = _now_ms()
        suffix = secrets.token_hex(2)
        return {
            "id": f"txn_{stamp}_{suffix}",
            "timestamp": stamp,
            "type": kind,
            "item": item,
            "cost": int(cost),
            "points_before": int(points_before),
            "points_after": int(points_after),
            "undone": False,
            "metadata": metadata or {},
        }

    def _load_state(self) -> None:
        with self._lock:
            if not self.state_path.exists():
                self._state = _default_state()
                self._persist_state()
                LOGGER.info("points_state_load path=%s source=default_created", self.state_path)
                return

            try:
                parsed = json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception as exc:
                LOGGER.error("points_state_corrupt path=%s error=%s", self.state_path, exc)
                self._backup_corrupt_state()
                self._state = _default_state()
                self._persist_state()
                return

            if not isinstance(parsed, dict):
                LOGGER.error("points_state_invalid path=%s", self.state_path)
                self._backup_corrupt_state()
                self._state = _default_state()
                self._persist_state()
                return

            self._state = _default_state()
            self._state["current_points"] = int(parsed.get("current_points") or 0)
            self._state["inventory"] = list(parsed.get("inventory") or [])
            unseen_inventory = parsed.get("unseen_inventory_reward_ids")
            if isinstance(unseen_inventory, list):
                self._state["unseen_inventory_reward_ids"] = [str(value) for value in unseen_inventory if str(value)]
            else:
                self._state["unseen_inventory_reward_ids"] = []
            self._state["transactions"] = list(parsed.get("transactions") or [])
            self._state["awarded_trainers"] = list(parsed.get("awarded_trainers") or [])
            redeemed_codes = parsed.get("redeemed_codes")
            if isinstance(redeemed_codes, dict):
                self._state["redeemed_codes"] = {
                    str(key).strip().lower(): bool(value)
                    for key, value in redeemed_codes.items()
                    if str(key).strip()
                }
            else:
                self._state["redeemed_codes"] = {}
            unlocked_awards = parsed.get("unlocked_awards")
            if isinstance(unlocked_awards, list):
                seen_awards = set()
                normalized_awards: List[str] = []
                for award in unlocked_awards:
                    award_name = str(award or "").strip()
                    if not award_name:
                        continue
                    marker = award_name.lower()
                    if marker in seen_awards:
                        continue
                    seen_awards.add(marker)
                    normalized_awards.append(award_name)
                self._state["unlocked_awards"] = normalized_awards
            else:
                self._state["unlocked_awards"] = []
            purchased_counts = parsed.get("purchased_counts")
            migrated_counts = False
            if isinstance(purchased_counts, dict):
                self._state["purchased_counts"] = {
                    str(key): max(0, int(value or 0))
                    for key, value in purchased_counts.items()
                }
            else:
                self._state["purchased_counts"] = {}

            if not any(int(value or 0) > 0 for value in self._state["purchased_counts"].values()):
                inferred: Dict[str, int] = {}
                name_to_item: Dict[str, str] = {}
                for item in SHOP_ITEMS:
                    canonical = str(item.get("name") or "").strip().lower()
                    if canonical:
                        name_to_item[canonical] = str(item["id"])
                        name_to_item[canonical.replace("-", " ")] = str(item["id"])

                for txn in self._state["transactions"]:
                    if str(txn.get("type") or "") != "purchase" or bool(txn.get("undone")):
                        continue
                    metadata = txn.get("metadata") if isinstance(txn.get("metadata"), dict) else {}
                    item_id = str(metadata.get("item_id") or "").strip()
                    if not item_id:
                        item_name = str(txn.get("item") or "").strip().lower().replace("-", " ")
                        item_id = str(name_to_item.get(item_name) or "")
                    if not item_id or item_id not in SHOP_ITEM_MAP:
                        continue
                    inferred[item_id] = int(inferred.get(item_id) or 0) + 1

                self._state["purchased_counts"] = inferred
                migrated_counts = bool(inferred)

            self._state["trainer_profile_key"] = str(parsed.get("trainer_profile_key") or "")
            self._state["version"] = int(parsed.get("version") or 1)

            repaired_missing_grants = self._repair_missing_redeem_grants()
            if migrated_counts:
                self._persist_state()
            elif repaired_missing_grants > 0:
                self._persist_state()
            LOGGER.info(
                "points_state_load path=%s points=%s inventory=%s transactions=%s awarded_trainers=%s",
                self.state_path,
                int(self._state.get("current_points") or 0),
                len(self._state.get("inventory") or []),
                len(self._state.get("transactions") or []),
                len(self._state.get("awarded_trainers") or []),
            )

    def _repair_missing_redeem_grants(self) -> int:
        redeemed_codes = self._state.get("redeemed_codes") if isinstance(self._state.get("redeemed_codes"), dict) else {}
        unlocked_awards = self._state.get("unlocked_awards") if isinstance(self._state.get("unlocked_awards"), list) else []
        if not redeemed_codes:
            return 0

        catalog = self._load_redemption_codes_catalog()
        if not catalog:
            return 0

        transactions = self._state.setdefault("transactions", [])
        inventory = self._state.setdefault("inventory", [])
        unseen = self._state.setdefault("unseen_inventory_reward_ids", [])
        unlocked_lookup = {str(name).strip().lower() for name in unlocked_awards if str(name).strip()}

        repaired = 0
        for code, was_redeemed in redeemed_codes.items():
            if not bool(was_redeemed):
                continue
            normalized_code = str(code or "").strip().lower()
            if not normalized_code:
                continue

            entry = catalog.get(normalized_code)
            if not isinstance(entry, dict):
                continue
            awards = entry.get("awards") if isinstance(entry.get("awards"), list) else []
            for award_name_raw in awards:
                award_name = str(award_name_raw or "").strip()
                if not award_name:
                    continue
                if award_name.lower() not in unlocked_lookup:
                    # If award was never unlocked, do not synthesize it.
                    continue

                item_id = self._resolve_award_item_id(award_name)
                item = SHOP_ITEM_MAP.get(item_id or "")
                if not item:
                    continue

                already_granted = False
                for txn in transactions:
                    metadata = txn.get("metadata") if isinstance(txn.get("metadata"), dict) else {}
                    if str(txn.get("type") or "") != "grant":
                        continue
                    if str(metadata.get("source") or "") not in {"redeem_code", "redeem_code_repair"}:
                        continue
                    if str(metadata.get("code") or "").strip().lower() != normalized_code:
                        continue
                    if str(metadata.get("item_id") or "").strip() != str(item_id):
                        continue
                    already_granted = True
                    break

                if already_granted:
                    continue

                inventory_item = self._build_inventory_item(
                    item=item,
                    source="redeem_code_repair",
                    metadata={
                        "source": "redeem_code_repair",
                        "code": normalized_code,
                        "award_filename": award_name,
                    },
                )
                inventory.append(inventory_item)
                inventory_id = str(inventory_item.get("id") or "")
                if inventory_id and inventory_id not in unseen:
                    unseen.append(inventory_id)

                repair_txn = self._build_transaction(
                    kind="grant",
                    item=str(item.get("name") or item_id or "reward"),
                    cost=0,
                    points_before=int(self._state.get("current_points") or 0),
                    points_after=int(self._state.get("current_points") or 0),
                    metadata={
                        "source": "redeem_code_repair",
                        "code": normalized_code,
                        "item_id": str(item.get("id") or ""),
                        "inventory_id": inventory_id,
                        "award_filename": award_name,
                        "notify_inventory": True,
                    },
                )
                transactions.append(repair_txn)
                repaired += 1

        if repaired > 0:
            LOGGER.warning("points_state_repaired_missing_redeem_grants count=%s", repaired)
        return repaired

    def _persist_state(self) -> bool:
        t0 = time.perf_counter()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._state, indent=2, sort_keys=True)
        tmp_path = self.state_path.with_suffix(f"{self.state_path.suffix}.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        except Exception as exc:
            LOGGER.error("points_state_tmp_write_failed path=%s error=%s", tmp_path, exc)
            return False

        replaced = False
        last_error: Optional[BaseException] = None
        for attempt in range(8):
            try:
                os.replace(tmp_path, self.state_path)
                replaced = True
                break
            except PermissionError as exc:
                last_error = exc
                if attempt >= 7:
                    break
                time.sleep(0.015 * (attempt + 1))
            except OSError as exc:
                last_error = exc
                if getattr(exc, "winerror", None) != 5 or attempt >= 7:
                    break
                time.sleep(0.015 * (attempt + 1))

        if not replaced:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            LOGGER.error(
                "points_state_persist_failed path=%s error=%s",
                self.state_path,
                last_error,
            )
            return False

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        now = time.perf_counter()
        if (now - self._persist_window_started_at) >= 1.0:
            self._persist_window_started_at = now
            self._persist_window_count = 0
        self._persist_window_count += 1

        LOGGER.debug("points_state_write path=%s duration_ms=%.3f", self.state_path, elapsed_ms)
        if elapsed_ms >= 50.0:
            LOGGER.warning("points_state_write_slow path=%s duration_ms=%.3f", self.state_path, elapsed_ms)
        if self._persist_window_count > 5:
            LOGGER.warning(
                "points_state_write_burst path=%s writes_in_last_second=%s",
                self.state_path,
                self._persist_window_count,
            )
        return True

    def _backup_corrupt_state(self) -> None:
        if not self.state_path.exists():
            return
        stamp = _now_ms()
        backup = self.state_path.with_suffix(f".corrupt.{stamp}.json")
        try:
            self.state_path.replace(backup)
            LOGGER.warning("points_state_backup source=%s backup=%s", self.state_path, backup)
        except Exception as exc:
            LOGGER.error("points_state_backup_failed source=%s error=%s", self.state_path, exc)

    def _remaining_stock_for_item(self, item_id: str) -> Optional[int]:
        item = SHOP_ITEM_MAP.get(str(item_id or ""))
        if not item:
            return None

        stock_limit_raw = item.get("stock_limit")
        if stock_limit_raw is None:
            return None

        stock_limit = max(0, int(stock_limit_raw or 0))
        purchased_counts = self._state.setdefault("purchased_counts", {})
        purchased = max(0, int(purchased_counts.get(item["id"]) or 0))
        return max(0, stock_limit - purchased)

    def _build_stock_remaining(self, state: Dict[str, Any]) -> Dict[str, int]:
        purchased_counts = state.get("purchased_counts") if isinstance(state.get("purchased_counts"), dict) else {}
        out: Dict[str, int] = {}
        for item in SHOP_ITEMS:
            stock_limit_raw = item.get("stock_limit")
            if stock_limit_raw is None:
                continue
            stock_limit = max(0, int(stock_limit_raw or 0))
            purchased = max(0, int(purchased_counts.get(item["id"]) or 0))
            out[item["id"]] = max(0, stock_limit - purchased)
        return out
