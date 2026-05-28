from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, Set

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
        self._command_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
        self._pending_broadcasts: Set[concurrent.futures.Future] = set()
        self._pending_lock = threading.Lock()
        self._broadcast_window_started_at: float = time.perf_counter()
        self._broadcast_type_counts: Dict[str, int] = {}

    def set_command_handler(self, handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]]) -> None:
        self._command_handler = handler

    @property
    def is_enabled(self) -> bool:
        return self.cfg.enabled

    @property
    def is_running(self) -> bool:
        return self._started.is_set() and self._loop is not None

    def pending_broadcast_count(self) -> int:
        with self._pending_lock:
            return len(self._pending_broadcasts)

    def _track_future(self, fut: concurrent.futures.Future) -> None:
        with self._pending_lock:
            self._pending_broadcasts.add(fut)

        def _on_done(done: concurrent.futures.Future) -> None:
            with self._pending_lock:
                self._pending_broadcasts.discard(done)

        fut.add_done_callback(_on_done)

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
        LOGGER.info(
            "ws_broadcast_state parser_mode=%s party=%s pc=%s dead=%s",
            parser_mode,
            len(state.get("party", [])),
            len(state.get("pc", [])),
            len(state.get("dead", [])),
        )
        fut = asyncio.run_coroutine_threadsafe(self._broadcast_json(payload), self._loop)
        self._track_future(fut)

    def broadcast_status(self, status: str, message: str) -> None:
        if not self.is_running or not self._loop:
            return

        payload = {
            "type": "tracker_status",
            "timestamp": _utc_now_iso(),
            "status": status,
            "message": message,
        }
        fut = asyncio.run_coroutine_threadsafe(self._broadcast_json(payload), self._loop)
        self._track_future(fut)

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
            async for message in websocket:
                await self._handle_incoming_message(websocket, message)
        finally:
            with self._clients_lock:
                self._clients.discard(websocket)

    async def _handle_incoming_message(self, websocket: Any, message: str) -> None:
        try:
            payload = json.loads(message)
        except Exception:
            await websocket.send(
                json.dumps(
                    {
                        "type": "command_error",
                        "timestamp": _utc_now_iso(),
                        "status": "error",
                        "message": "Invalid JSON payload",
                    },
                    separators=(",", ":"),
                )
            )
            return

        if not isinstance(payload, dict):
            return

        payload_type = str(payload.get("type") or "")
        if payload_type not in {"points_shop_command", "points_command"}:
            return

        request_id = payload.get("request_id")
        command = payload.get("command")

        if self._command_handler is None:
            await websocket.send(
                json.dumps(
                    {
                        "type": "points_shop_response",
                        "timestamp": _utc_now_iso(),
                        "request_id": request_id,
                        "ok": False,
                        "command": command,
                        "message": "Points command handler unavailable",
                    },
                    separators=(",", ":"),
                )
            )
            return

        try:
            result = self._command_handler(payload)
        except Exception as exc:
            LOGGER.exception("Points command handler failed: %s", exc)
            result = {
                "ok": False,
                "message": f"Points command failed: {exc}",
            }

        if not isinstance(result, dict):
            result = {"ok": False, "message": "Invalid points command response"}

        response = {
            "type": "points_shop_response",
            "timestamp": _utc_now_iso(),
            "request_id": request_id,
            "command": command,
            "ok": bool(result.get("ok")),
            "message": str(result.get("message") or ""),
            "state": result.get("state"),
            "overlay_ui": result.get("overlay_ui"),
            "overlay_ui_changed": bool(result.get("overlay_ui_changed")),
        }
        await websocket.send(json.dumps(response, separators=(",", ":")))
        LOGGER.info(
            "ws_points_response request_id=%s command=%s ok=%s",
            request_id,
            command,
            bool(response.get("ok")),
        )

        if response.get("state") is not None:
            # Keep the cached bootstrap state current for newly connected clients.
            # Without this, a refresh can receive an older state_update snapshot and
            # temporarily show stale points/inventory until another command runs.
            if isinstance(self._last_state_payload, dict):
                cached_state = self._last_state_payload.get("state")
                if isinstance(cached_state, dict):
                    cached_state["points_shop"] = response.get("state")
                    if response.get("overlay_ui") is not None:
                        cached_state["overlay_ui"] = response.get("overlay_ui")
            LOGGER.info("ws_points_broadcast_update request_id=%s", request_id)
            await self._broadcast_json(
                {
                    "type": "points_shop_update",
                    "timestamp": _utc_now_iso(),
                    "state": response.get("state"),
                    "overlay_ui": response.get("overlay_ui"),
                }
            )

        if response.get("overlay_ui") is not None and bool(response.get("overlay_ui_changed")):
            LOGGER.info("ws_overlay_ui_broadcast request_id=%s command=%s", request_id, command)
            await self._broadcast_json(
                {
                    "type": "overlay_ui_update",
                    "timestamp": _utc_now_iso(),
                    "overlay_ui": response.get("overlay_ui"),
                }
            )

    async def _heartbeat_loop(self) -> None:
        while self._stop_event and not self._stop_event.is_set():
            await asyncio.sleep(self.cfg.heartbeat_seconds)
            await self._broadcast_json({"type": "heartbeat", "timestamp": _utc_now_iso()})

    async def _broadcast_json(self, payload: Dict[str, Any]) -> None:
        with self._clients_lock:
            clients = list(self._clients)

        if not clients:
            return

        payload_type = str(payload.get("type") or "unknown")
        now = time.perf_counter()
        if (now - self._broadcast_window_started_at) >= 1.0:
            self._broadcast_window_started_at = now
            self._broadcast_type_counts = {}
        self._broadcast_type_counts[payload_type] = int(self._broadcast_type_counts.get(payload_type, 0)) + 1

        if self._broadcast_type_counts[payload_type] > 20:
            LOGGER.warning(
                "ws_broadcast_rate_high type=%s per_second=%s clients=%s",
                payload_type,
                self._broadcast_type_counts[payload_type],
                len(clients),
            )

        if payload_type in {"state_update", "points_shop_update", "tracker_status"}:
            LOGGER.info("ws_broadcast type=%s clients=%s", payload_type, len(clients))

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
