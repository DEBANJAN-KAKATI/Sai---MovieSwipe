"""WebSocket fan-out for duo/group sessions (single-process, in-memory)."""

from __future__ import annotations

import asyncio
import json
import threading

from fastapi import WebSocket


class SessionHub:
    def __init__(self) -> None:
        self.rooms: dict[str, set[WebSocket]] = {}
        self.lock = threading.Lock()
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self.loop = asyncio.get_running_loop()
        with self.lock:
            self.rooms.setdefault(session_id, set()).add(ws)

    def disconnect(self, session_id: str, ws: WebSocket) -> None:
        with self.lock:
            room = self.rooms.get(session_id)
            if room:
                room.discard(ws)
                if not room:
                    self.rooms.pop(session_id, None)

    async def _broadcast(self, session_id: str, payload: str) -> None:
        with self.lock:
            targets = list(self.rooms.get(session_id, ()))
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:
                self.disconnect(session_id, ws)

    def publish(self, session_id: str, event: str, data: dict | None = None) -> None:
        """Thread-safe publish callable from sync route handlers."""
        if self.loop is None or not self.rooms.get(session_id):
            return
        payload = json.dumps({"event": event, "data": data or {}}, default=str)
        try:
            asyncio.run_coroutine_threadsafe(self._broadcast(session_id, payload), self.loop)
        except RuntimeError:
            pass


hub = SessionHub()
