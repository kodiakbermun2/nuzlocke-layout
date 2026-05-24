from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import threading
from typing import Any, Dict, Optional, Set

LOGGER = logging.getLogger(__name__)

try:
    import websockets
except Exception:  # pragma: no cover - runtime dependency optional
    websockets = None


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class WebSocketRuntimeConfig:
    enabled: bool
    host: str
    port: int
    heartbeat_seconds: float


class LiveWebSocketServer:
    """Background asyncio websocket broadcaster for local OBS overlay updates."""

    def __init__(self, cfg: WebSocketRuntimeConfig):
        self.cfg = cfg
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._started = threading.Event()
        self._stop_event: Optional[asyncio.Event] = None
        self._clients: Set[Any] = set()
        self._clients_lock = threading.Lock()
        self._last_state_payload: Optional[Dict[str, Any]] = None

    @property
    def is_enabled(self) -> bool:
        return self.cfg.enabled

    @property
    def is_running(self) -> bool:
        return self._started.is_set() and self._loop is not None

    def start(self) -> bool:
        if not self.cfg.enabled:
            LOGGER.info("WebSocket server disabled by config")
            return False

        if websockets is None:
            LOGGER.error("WebSocket support requires 'websockets' package; continuing without live server")
            return False

        if self._thread and self._thread.is_alive():
            return True

        self._thread = threading.Thread(target=self._run_thread, name="overlay-ws-server", daemon=True)
        self._thread.start()
        self._started.wait(timeout=3.0)
        return self.is_running

    def stop(self) -> None:
        if self._loop and self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def broadcast_state(self, state: Dict[str, Any], parser_mode: str, debug: bool) -> None:
        if not self.is_running or not self._loop:
            return

        payload = {
            "type": "state_update",
            "timestamp": _utc_now_iso(),
            "status": "ok",
            "parser_mode": parser_mode,
            "party_count": len(state.get("party", [])),
            "pc_count": len(state.get("pc", [])),
            "dead_count": len(state.get("dead", [])),
            "debug": {"enabled": debug},
            "state": state,
        }
        self._last_state_payload = payload
        asyncio.run_coroutine_threadsafe(self._broadcast_json(payload), self._loop)

    def broadcast_status(self, status: str, message: str) -> None:
        if not self.is_running or not self._loop:
            return

        payload = {
            "type": "tracker_status",
            "timestamp": _utc_now_iso(),
            "status": status,
            "message": message,
        }
        asyncio.run_coroutine_threadsafe(self._broadcast_json(payload), self._loop)

    def _run_thread(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._stop_event = asyncio.Event()
        try:
            self._loop.run_until_complete(self._serve())
        except Exception as exc:
            LOGGER.exception("WebSocket server failed: %s", exc)
        finally:
            self._started.clear()
            if self._loop and not self._loop.is_closed():
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
                self._loop.close()
            self._loop = None

    async def _serve(self) -> None:
        assert websockets is not None

        async with websockets.serve(
            self._handle_client,
            self.cfg.host,
            self.cfg.port,
            ping_interval=self.cfg.heartbeat_seconds,
            ping_timeout=max(2.0, self.cfg.heartbeat_seconds),
            max_queue=32,
        ):
            LOGGER.info("WebSocket server listening on ws://%s:%s", self.cfg.host, self.cfg.port)
            self._started.set()

            heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            try:
                await self._stop_event.wait()
            finally:
                heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat_task

    async def _handle_client(self, websocket: Any) -> None:
        with self._clients_lock:
            self._clients.add(websocket)

        hello = {
            "type": "hello",
            "timestamp": _utc_now_iso(),
            "message": "tracker websocket connected",
        }
        await websocket.send(json.dumps(hello, separators=(",", ":")))
        if self._last_state_payload is not None:
            await websocket.send(json.dumps(self._last_state_payload, separators=(",", ":")))

        try:
            async for _message in websocket:
                # Read loop exists to keep connection healthy; tracker is push-only.
                pass
        finally:
            with self._clients_lock:
                self._clients.discard(websocket)

    async def _heartbeat_loop(self) -> None:
        while self._stop_event and not self._stop_event.is_set():
            await asyncio.sleep(self.cfg.heartbeat_seconds)
            await self._broadcast_json({"type": "heartbeat", "timestamp": _utc_now_iso()})

    async def _broadcast_json(self, payload: Dict[str, Any]) -> None:
        with self._clients_lock:
            clients = list(self._clients)

        if not clients:
            return

        raw = json.dumps(payload, separators=(",", ":"))
        dead = []
        for client in clients:
            try:
                await client.send(raw)
            except Exception:
                dead.append(client)

        if dead:
            with self._clients_lock:
                for client in dead:
                    self._clients.discard(client)
